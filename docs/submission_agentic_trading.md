# Gloaming Agent - Agentic Trading track submission draft

Copy each section into the corresponding field on the submission form
(https://forms.gle/GyWZCMCPocgJdJon6). Numbers below are pulled live from the
real running system as of this draft - re-pull before submitting if more time
passes (the paper-trading log keeps growing).

## Track + Sub-theme

**Agentic Trading** - **Cross-Asset Execution Agent** (its own description is
"rToken + Crypto management" - Gloaming Agent's fair-value model is literally
built on blending an rToken's price against a crypto-beta signal alongside
futures/FX proxies, and decides rToken execution from that cross-asset read).

Named sub-themes carry 5 Theme Prize slots per track vs. Open Theme's 2, so
this is also the higher-odds choice, not just the better categorical fit -
worth you double-checking this framing still feels honest to you before
submitting, since you're the one who has to defend it if asked.

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
  Redis): **180 real fills** since Sept 11, running unattended every 15
  minutes on real cloud infrastructure (a GitHub Actions workflow, triggered
  externally so it never depends on any one machine being on) that self-gates
  on NYSE hours. Across the full decision history, **1,492 of 1,707 (87%)**
  decisions were generated directly by Qwen3.8-max (the remainder are the
  disclosed deterministic fallback, used only when a Qwen call is slow or
  fails). Every fill is marked to a real, live rToken price at decision time
  (see LLM role disclosure and "Execution model" below) - not synthetic or
  simulated prices.
- **Honest limitation, stated plainly rather than glossed over**: as of this
  draft, across several days of continuous real operation, no position has
  round-tripped to a close yet - the overnight premium has stayed
  one-directional long enough that risk controls capped total exposure at 60%
  of equity and have correctly rejected every new signal past that cap rather
  than let the book grow unbounded. A Sharpe/win-rate computed from the live
  log alone would still be statistically meaningless (zero closed trades, not
  just few), so the **backtest above remains the statistically grounded
  quantitative evidence** (84 real days); the live log is the running proof
  the same logic executes correctly and continuously against real prices,
  and that the risk layer holds under real, sustained one-sided conditions
  rather than only in a clean backtest. It keeps growing through the Sept 21
  deadline - check `gloaming_agent/decision_log/` or the live Desk for the
  current count at submission time.

### Progress / build status

Fully built and running live, unattended, right now:
- `engine/` - real market-data loaders, fair-value model, backtest
- `gloaming_agent/` - the agent loop, non-LLM risk gate, self-maintained
  paper ledger, Qwen integration, scheduled every 15 minutes on real cloud
  infrastructure (`.github/workflows/agent_loop.yml`), not a local machine
- `gloaming_desk/` - the companion AI Trading Desk submission, live at
  https://gloamingdesk.vercel.app
- Public repo: https://github.com/angelraph/gloaming, with every real
  15-minute cycle's decisions and ledger state committed straight into the
  repo's own history

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

Qwen sees its own book, not just one symbol's market data: every decision prompt
includes its position in that symbol, the book's net and gross exposure against
the caps, what the risk layer would approve right now, and its recent fills in the
symbol, and the system prompt tells it that managing the book (for example, not
treating nine correlated "cheap" signals as nine independent trades) is part of
its job. That exact context is stored on each logged snapshot, so the decision
log shows what Qwen saw when it decided. The call is made with the model's
thinking mode switched off (`enable_thinking: false`): with it on, a decision took
17-77 seconds of hidden reasoning and, once the book-aware prompt shipped, the
share of decisions Qwen actually made in production fell from 83% to about 14%
because calls timed out. With it off a call takes 5-8 seconds, and the rationale
still cites the book figures.

It is never the last word: `gloaming_agent/risk_controls.py` is a **separate,
deterministic, non-LLM** module that can reject or resize any decision
regardless of Qwen's confidence (position caps, a net directional exposure cap,
daily/per-trade circuit breakers, volatility-scaled sizing, no leverage), and only
an approved decision can reach execution. One disclosed exception to "the risk
layer only gates": if the book stays over its net directional cap for about 2
hours of market-closed time without Qwen bringing it back, a deterministic
backstop sells down at most 2% of equity per cycle until it is back inside the cap.
Those trades still pass through the same gate and ledger and are labeled
`risk_backstop_trim (deterministic risk layer, not the LLM)` in `decision_source`
(see docs/risk_controls.md, control #10). A fixed-threshold rule (`decide_rule_based()`)
is the disclosed automatic fallback used only when Qwen is unconfigured or a
call fails or times out (30s per call, one retry, and a 4-minute cap on total LLM
time per cycle so a slow Qwen day cannot push the job past its 10-minute limit;
symbols beyond the cap use the fallback and say so in `decision_source`) - never a
parallel second opinion - and every logged decision
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
