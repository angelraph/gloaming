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
   as a fraction of the paper ledger's equity.
2. **Per-trade max-loss circuit breaker** - a proposed trade whose stop-loss distance
   implies loss beyond a fixed threshold is rejected outright.
3. **Daily max-loss circuit breaker** - once realized+unrealized daily loss crosses a
   threshold, the loop stops opening new positions for the remainder of that
   overnight window (existing positions may still be closed/hedged).
4. **Volatility-scaled sizing** - position size scales inversely with recent realized
   volatility of the fair-value/actual spread for that symbol.
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

## Test coverage

`tests/test_risk_controls.py` must include at least one forced test case per control
above, asserting that an over-cap/over-loss decision is blocked before reaching
`execution.py`.
