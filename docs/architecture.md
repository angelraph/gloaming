# Gloaming — Architecture

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
        rule-based risk controls →          reads engine API + Agent's
        paper trades via Bitget Agent       decision log; narrates,
        SDK --paper-trading                 never auto-executes
```

## Why this mechanic, not a generic trading bot

Bitget rTokens are 1:1-backed tokenized US stocks that trade 24/7 on-chain, but the
real NYSE/Nasdaq shares they track only trade ~6.5h/day on weekdays. Outside that
window there's no direct arbitrage pressure pinning the rToken price to the real
share — yet the rToken keeps trading. Gloaming's entire thesis is built on
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
   calls Qwen3.8-max for event interpretation/decision, passes every decision through
   `risk_controls.py`, and executes via `execution.py` (`--paper-trading` only),
   logging each event→decision→execution cycle to `decision_log/`.
5. `gloaming_desk/` (Next.js) reads the engine API and the Agent's decision log to
   render the overnight timeline, fair-value-vs-actual charts, chat narration, and
   the decision-stress-test replay — read-only, no execution path.

## Alpha Factory (stretch, not a formal 3rd submission)

`engine/backtest/` is reused directly to produce a ≥60-day/≥30-out-of-sample
Sharpe/Sortino/max-drawdown report as supplementary validation evidence embedded in
the Agentic Trading and AI Trading Desk write-ups — built only if time remains after
Day 9 feature freeze.
