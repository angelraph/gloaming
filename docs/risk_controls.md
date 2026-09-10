# Gloaming — Risk Controls

Gloaming Agent's Qwen-driven decisions are always gated by a separate, deterministic,
non-LLM risk layer (`gloaming_agent/risk_controls.py`) before any execution call is
made. This is the "human-authored safety layer" disclosed in the Agentic Trading
submission's LLM role section.

## Controls (v1)

1. **Position size cap** — max notional per rToken, and max aggregate book notional,
   as a fraction of paper-account equity.
2. **Per-trade max-loss circuit breaker** — a proposed trade whose stop-loss distance
   implies loss beyond a fixed threshold is rejected outright.
3. **Daily max-loss circuit breaker** — once realized+unrealized daily loss crosses a
   threshold, the loop stops opening new positions for the remainder of that
   overnight window (existing positions may still be closed/hedged).
4. **Volatility-scaled sizing** — position size scales inversely with recent realized
   volatility of the fair-value/actual spread for that symbol.
5. **No leverage** — spot/paper exposure only; no margin or leverage instructions are
   ever sent to execution.
6. **Hardcoded paper mode** — `execution.py` hardcodes `--paper-trading` (and
   `--read-only` where the operation allows it) regardless of any config passed in;
   this is not an env toggle an LLM output could ever influence.
7. **Withdrawal-disabled account** — the Bitget Agentic Account used has withdrawal
   permissions disabled at the account level, independent of anything in this repo.

## Test coverage

`tests/test_risk_controls.py` must include at least one forced test case per control
above, asserting that an over-cap/over-loss decision is blocked before reaching
`execution.py`.
