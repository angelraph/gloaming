# Gloaming - Risk Controls

Gloaming Agent's Qwen-driven decisions are always gated by a separate, deterministic,
non-LLM risk layer (`gloaming_agent/risk_controls.py`) before any fill is recorded.
This is the "human-authored safety layer" disclosed in the Agentic Trading
submission's LLM role section. Qwen is the primary decision-maker (see
`agent_loop.py`'s `decide()` dispatcher) whenever `QWEN_API_KEY` is configured; a
deterministic fixed-threshold rule is the disclosed automatic fallback for when it
isn't, or a call fails, never a second vote alongside it.

## Controls (v1)

1. **Position size cap** - max notional per rToken, and max aggregate book notional,
   as a fraction of the paper ledger's equity. Net-exposure aware: a trade that
   reduces an existing position (trades opposite to its sign) is exempt from these
   caps up to the point of fully flattening it - confirmed live Sept 22 that
   without this, a book sitting over its own cap rejects every decision including
   ones that would reduce its risk, for as long as it stays over cap. A trade that
   adds exposure is still capped exactly as before.
2. **Per-trade max-loss circuit breaker** - a proposed trade whose stop-loss distance
   implies loss beyond a fixed threshold is rejected outright.
3. **Daily max-loss circuit breaker** - once realized+unrealized daily loss crosses a
   threshold, the loop stops opening new positions for the remainder of that
   overnight window (existing positions may still be closed/hedged). Confirmed
   live Sept 22 that the code did not actually honor the "may still be
   closed/hedged" part - it rejected every decision outright, the same gap as
   control #1 above, fixed the same way and by the same commit.
4. **Volatility-scaled sizing** - position size scales inversely with recent realized
   volatility of the real share (standard deviation of its last 10 daily returns).
   Before Sept 25 the input was the size of the fair-value/actual spread, which only
   worked while that spread was a multi-percent number; with the signal anchored to
   the real close the spread is a few tenths of a percent and is no longer a
   volatility, so it would have quietly switched the control off.
5. **No leverage** - spot/paper exposure only; no margin or leverage instructions are
   ever sent to execution.
6. **LLM notional ceiling** - `decide_llm()` hard-caps whatever `notional_usd` Qwen
   suggests at 1000 USD before the number even reaches `risk_controls.py`'s own
   (usually stricter) caps above - a second, independent bound on what the LLM's
   output can ever request.
7. **No real exchange in the rToken decision path at all** - `paper_ledger.py`
   never talks to Bitget's live or demo order-matching for rTokens; it only marks
   a local virtual ledger to real market prices (see docs/architecture.md's
   "Execution model" section), so there is no live-trading toggle an LLM output
   could influence even in principle for this part of the system.
8. **Withdrawal-disabled account** - the Bitget Agentic Account used for account
   reads (`execution.py`) has withdrawal permissions disabled at the account level,
   independent of anything in this repo.
9. **Net directional exposure cap** - |net long minus net short| across the whole
   book is capped at 25% of equity, in addition to the gross caps in control #1.
   Added Sept 24 after live operation showed the gross caps alone allow a
   full-size one-way bet: the book went from about 60% net short to about 60% net
   long (concentrated in the most volatile names) while every gross cap was
   respected. A trade that pushes net further from zero gets only the room left
   under the cap. A trade toward zero is always allowed, up to fully flattening
   net plus at most the cap on the other side. The cap itself only limits new
   exposure and never forces a trade, so a book already over it stays put until a
   net-reducing decision arrives; see control #10.
10. **Net-exposure backstop trim** - the LLM is the primary way an over-cap book
    comes back under the net cap: every decision prompt now shows Qwen its own book
    (its position in the symbol, net and gross exposure against the caps, what the
    risk layer would approve right now, and its recent fills in that symbol), and
    the system prompt tells it that managing the book is part of its job. Only if
    the book stays over the cap for 8 active cycles (about 2 hours of market-closed
    time) with no real progress (the excess shrinking by less than 1% of equity)
    does deterministic code step in: it sells (or buys back, for a net short book)
    at most 2% of equity per cycle, spread across the over-exposed positions in
    proportion to their size, until the book is back inside the cap plus a 1%
    tolerance band. Every backstop trade goes through `evaluate_decision()`, the
    ledger and the decision log like any other trade, and is labeled
    `risk_backstop_trim (deterministic risk layer, not the LLM)` in
    `decision_source`, so it can never be mistaken for an LLM decision. The
    backstop's own trims do not count as the LLM making progress, so it stays
    engaged until the book is back inside the cap. This means the risk layer can
    originate an order, which the earlier version of this document (and the
    submission's LLM role disclosure) said it never did; both now say so.

## Test coverage

`tests/test_risk_controls.py` must include at least one forced test case per control
above, asserting that an over-cap/over-loss decision is blocked before reaching
`execution.py`.
