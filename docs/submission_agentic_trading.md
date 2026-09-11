# Gloaming Agent - Agentic Trading track submission draft

Copy each section into the corresponding field on the submission form
(https://forms.gle/GyWZCMCPocgJdJon6). Numbers below are pulled live from the
real running system as of this draft - re-pull before submitting if more time
passes (the paper-trading log keeps growing).

## Track + Sub-theme

**Agentic Trading** - Open Theme (closest named sub-theme is Cross-Asset
Execution Agent, but the core thesis - overnight rToken/fair-value arbitrage -
doesn't map cleanly onto any single named sub-theme, so Open Theme is the
honest choice).

## Project description

### Thesis

Bitget rTokens trade 24/7 on-chain, but the real shares they track only trade
on NYSE/Nasdaq for ~6.5 hours a day on weekdays. Outside that window there is
no direct arbitrage pressure holding the rToken price to the real share's
value - yet the rToken keeps trading. Gloaming Agent estimates a synthetic
fair value during that closed window from proxies that stay live overnight (an
index-futures proxy, crypto market beta, FX risk sentiment), and trades the
spread between that fair value and the rToken's actual on-chain price,
expecting convergence at or after the next NYSE open. This is a mechanic
specific to how rToken actually works, not a generic sentiment- or
news-trading bot retargeted at a new asset.

### Target user & product value

24/7 crypto-native funds and traders who hold rToken exposure and want
automated risk-managed coverage during the hours a traditional desk would be
unstaffed - specifically, holders who currently either close out rToken
positions before the real market closes (giving up the overnight thesis
entirely) or hold them unmanaged overnight (accepting uncontrolled overnight
risk). Gloaming Agent is the middle path: active, risk-gated management
during exactly that window.

### Validation data & key metrics

- **Backtest** (`alpha_factory/`, `engine/backtest/run_backtest.py`), on real
  ~90-day rToken price history across a 9-symbol universe (AAPL, AMZN, META,
  TSLA, GOOGL, NVDA, MSFT, QQQ, SPY), 54+ days in-sample / 30 days
  out-of-sample per symbol:
  - Portfolio Sharpe **2.09**, Sortino **2.29**
  - Max drawdown **-3.51%**
  - Win rate **57%**
  - Total return **+4.65%** over the 84-day window
- **Live paper-trading log** (`gloaming_agent/decision_log/`, mirrored live to
  Redis): **93 real fills** since Sept 11, running unattended every 15 minutes
  via a scheduled task that self-gates on NYSE hours. Of the decisions
  produced since Qwen was wired in, **95 of 107** were generated directly by
  Qwen3.8-max (the remainder are the disclosed deterministic fallback, used
  only when Qwen is unavailable or a call fails).
- Every fill is marked to a real, live rToken price at decision time (see LLM
  role disclosure and "Execution model" below) - not synthetic or simulated
  prices.

### Progress / build status

Fully built and running live, unattended, right now:
- `engine/` - real market-data loaders, fair-value model, backtest
- `gloaming_agent/` - the agent loop, non-LLM risk gate, self-maintained
  paper ledger, Qwen integration, scheduled every 15 minutes
- `gloaming_desk/` - the companion AI Trading Desk submission, live at
  https://gloamingdesk.vercel.app
- Public repo: https://github.com/angelraph/gloaming

### Deliverables

- Agent code: `gloaming_agent/` (this repo)
- Decision log: `gloaming_agent/decision_log/*.jsonl` (full event -> decision
  -> execution trail, also live-readable via the deployed Desk)
- Architecture diagram: `docs/architecture.md`
- Event -> decision -> execution flow doc, with a worked real example:
  `docs/event_decision_execution_flow.md`
- Supplementary quant validation: `alpha_factory/` (backtest report + raw
  results)
- Demo video: [ADD LINK]

### AI trading perspective (optional)

Qwen3.8-max reasons over real overnight proxy data the way a discretionary
overnight trader would: it explicitly discounts spreads it cannot fully
explain (repeatedly sizing down because "the premium could reflect
idiosyncratic or unseen news"), rather than trading every mechanical
mispricing at full size. That caution is visible directly in its own
rationale text logged for every decision - not asserted after the fact.

## LLM role disclosure

**Qwen3.8-max**, via the hackathon's OpenAI-compatible endpoint, is the
**primary autonomous decision-maker** for direction and position size during
NYSE-closed hours. It reasons over a real live snapshot per symbol (rToken
price/return, futures-proxy/crypto-beta/FX-proxy returns, the resulting
spread vs. synthetic fair value) and returns a structured decision (buy/sell/
hold, notional, stop-loss, confidence, rationale).

It is never the last word: `gloaming_agent/risk_controls.py` is a **separate,
deterministic, non-LLM** module that can reject or resize any decision
regardless of Qwen's confidence (position caps, daily/per-trade circuit
breakers, volatility-scaled sizing, no leverage), and only an approved
decision can reach execution. A fixed-threshold rule (`decide_rule_based()`)
is the disclosed automatic fallback used only when Qwen is unconfigured or a
call fails - never a parallel second opinion - and every logged decision
records which path actually produced it (`decision_source`), so the full
history is auditable.

## Execution model note

Bitget's demo/paper trading environment does not list rToken symbols at all
(confirmed live: `RAAPLUSDT` orders are rejected outright, `BTCUSDT` orders
succeed normally) - a gap in Bitget's own demo environment, not this project.
Gloaming Agent's fills therefore post to a self-maintained virtual ledger
marked to real, live rToken prices from the same public Bitget market-data
feed used everywhere else in the project - the standard approach any
paper-trading system uses when a broker's own sandbox doesn't cover an
instrument. Only the "exchange accepting the order" step is simulated; the
price, timing, decision logic, and risk gating are all real. Full reasoning
in `docs/architecture.md`.

## Submission materials link

https://github.com/angelraph/gloaming (public repo - code, docs, backtest
results, decision log)
Live Desk (reads the same live data): https://gloamingdesk.vercel.app
