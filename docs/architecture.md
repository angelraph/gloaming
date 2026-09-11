# Gloaming - Architecture

## One engine, two submissions

```
                     ┌─────────────────────────────┐
                     │  ENGINE (Python, shared)     │
                     │  data/ → fairvalue/ → api/    │
                     │  - rToken price ingestion     │
                     │  - futures/crypto/FX proxies  │
                     │  - synthetic fair-value model │
                     │  - SQLite store + FastAPI     │
                     └──────────────┬───────────────┘
                        ┌───────────┴────────────┐
                        ▼                         ▼
        GLOAMING AGENT (loop, submits:      GLOAMING DESK (web, submits:
        Agentic Trading)                    AI Trading Desk)
        Qwen3.8-max reasoning +             Next.js dashboard + chat,
        non-LLM risk controls →             reads engine API + Agent's
        fills via paper_ledger.py,          decision log; narrates,
        marked to live rToken prices        never auto-executes
```

## Why this mechanic, not a generic trading bot

Bitget rTokens are 1:1-backed tokenized US stocks that trade 24/7 on-chain, but the
real NYSE/Nasdaq shares they track only trade ~6.5h/day on weekdays. Outside that
window there's no direct arbitrage pressure pinning the rToken price to the real
share - yet the rToken keeps trading. Gloaming's entire thesis is built on
estimating a synthetic fair value during that closed window from proxies that
*do* stay live overnight (index-futures proxies, crypto beta, FX risk sentiment),
and trading/reporting on the resulting spread. This is specific to how rToken
works, not a generic sentiment- or news-trading bot.

## Data flow

1. `engine/data/*` loaders pull rToken prices (via `bitget-agent-sdk`), underlying
   equity history (`yfinance`/stooq), futures proxies (`ES=F`/`NQ=F`), crypto beta
   (BTC/ETH klines), and FX (DXY) into `engine/data/cache/` and SQLite.
2. `engine/fairvalue/model.py` blends these into a synthetic fair value per rToken,
   weighted per `fairvalue/config.py` (heuristic prior → OLS-calibrated once enough
   overlapping history exists).
3. `engine/events/macro_store.py` ingests `bitget-signal` output (news-briefing,
   macro-analyst, sentiment-analyst) into a timeline table.
4. `gloaming_agent/agent_loop.py` runs only while NYSE is closed, reads engine state,
   calls Qwen3.8-max for event interpretation/decision, and passes every decision
   through `risk_controls.py`. Approved decisions execute via
   `gloaming_agent/paper_ledger.py` - a self-maintained virtual ledger marked to
   real, live rToken prices (see "Execution model" below for why, not
   `execution.py`'s Bitget CLI wrapper). Every cycle logs a full
   event→decision→execution record to `decision_log/`.
5. `gloaming_desk/` (Next.js) reads the engine API, the Agent's decision log, and
   `paper_ledger.json` to render the overnight timeline, fair-value-vs-actual
   charts, chat narration, and the decision-stress-test replay - read-only, no
   execution path.

## Execution model: why a self-maintained ledger, not Bitget's demo trading

Bitget's Agent Hub ships a `--paper-trading` flag intended to route order writes to
their demo/sandbox environment. Confirmed live Sept 11 while wiring this up: that
demo environment **does not list rToken symbols at all** - placing a demo order for
`RAAPLUSDT` returns `"Parameter RAAPLUSDT does not exist"`, while the identical call
against `BTCUSDT` succeeds up to a normal minimum-order-size check, isolating this
as an rToken-specific gap in Bitget's demo environment rather than a general
paper-trading failure or a bug in this codebase.

Since Gloaming's whole thesis is rToken execution during NYSE-closed hours, and
waiting on Bitget to add rToken coverage to their demo environment isn't viable on
a hackathon deadline, `gloaming_agent/paper_ledger.py` implements the standard
approach used by essentially every paper-trading system when a broker's own sandbox
doesn't cover an instrument: maintain a local ledger (cash, positions, fills) and
mark every fill to a REAL, LIVE price pulled from the same public Bitget market-data
feed used for every other part of this project - not synthetic or estimated data.
The only thing simulated is the "exchange accepting the order" step; the price, the
timing, the decision logic, and the risk gating are all real. `execution.py` (the
Bitget CLI wrapper, including live account reads and `--paper-trading` order calls)
is kept in the repo and still works correctly against tradable symbols like
`BTCUSDT` - it's simply no longer in the rToken decision path.

## Alpha Factory (stretch, not a formal 3rd submission)

`engine/backtest/` is reused directly to produce a ≥60-day/≥30-out-of-sample
Sharpe/Sortino/max-drawdown report as supplementary validation evidence embedded in
the Agentic Trading and AI Trading Desk write-ups - built only if time remains after
Day 9 feature freeze.
