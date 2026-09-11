# Gloaming - Architecture

## One engine, two submissions

```mermaid
flowchart TB
    subgraph ext["External data, public, no auth needed"]
        bitget["Bitget market data<br/>rToken + crypto prices, via bgc CLI"]
        yahoo["Yahoo Finance<br/>ES=F / NQ=F futures, DXY"]
        qwen["Qwen3.8-max API<br/>hackathon endpoint"]
    end

    subgraph engine["engine/ (Python, shared)"]
        data["data/*.py<br/>loaders"]
        fv["fairvalue/model.py<br/>synthetic fair value"]
        bt["backtest/*.py<br/>Alpha Factory backtest"]
    end

    bitget --> data
    yahoo --> data
    data --> fv
    data --> bt
    fv --> bt

    subgraph agent["gloaming_agent/  -  submits: Agentic Trading"]
        loop["agent_loop.py<br/>runs only while NYSE is closed"]
        risk["risk_controls.py<br/>non-LLM risk gate"]
        ledger["paper_ledger.py<br/>virtual fills, marked to real prices"]
        log[("decision_log/*.jsonl")]
    end

    fv --> loop
    data --> loop
    loop <--> qwen
    loop --> risk
    risk --> ledger
    loop --> log
    ledger --> log

    subgraph desk["gloaming_desk/  -  submits: AI Trading Desk"]
        api["app/api/*<br/>reads decision_log + ledger files directly"]
        ui["dashboard: chart, timeline,<br/>chat, decision stress test"]
    end

    log --> api
    ledger --> api
    bt -. "historical_scenarios.json" .-> api
    api --> ui
    ui <--> qwen
```

There is no separate FastAPI or SQLite layer, and no `bitget-signal` news/macro
skill integration - both were considered and deliberately not built (see
"Deferred, not silently missing" below). The Agent and the Desk each read the
same on-disk files directly.

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

1. `engine/data/*` loaders pull rToken prices (via the Bitget Agent CLI, `bgc`),
   futures proxies (`ES=F`/`NQ=F`), crypto beta (BTC/ETH klines), and FX (DXY).
2. `engine/fairvalue/model.py` blends these into a synthetic fair value per rToken,
   weighted per `fairvalue/config.py` (heuristic prior, OLS-calibrated once enough
   overlapping history exists - see `engine/backtest/run_backtest.py`).
3. `gloaming_agent/agent_loop.py` runs only while NYSE is closed (self-enforced,
   not just documented - see `run_once()`'s `is_nyse_closed()` check), builds a
   live snapshot per symbol, and calls Qwen3.8-max for the trade decision
   whenever `QWEN_API_KEY` is configured, falling back to a deterministic
   fixed-threshold rule otherwise (see `docs/event_decision_execution_flow.md`
   for the exact sequence). Every decision passes through `risk_controls.py`
   before execution.
4. Approved decisions execute via `gloaming_agent/paper_ledger.py` - a
   self-maintained virtual ledger marked to real, live rToken prices (see
   "Execution model" below for why, not `execution.py`'s Bitget CLI wrapper).
   Every cycle logs a full event -> decision -> execution record to
   `decision_log/`.
5. `gloaming_desk/` (Next.js) reads `decision_log/`, `paper_ledger.json`, and
   `alpha_factory/results/historical_scenarios.json` directly off disk to
   render the overnight timeline, fair-value-vs-actual chart, chat narration,
   and the decision-stress-test replay - read-only, no execution path.

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

## Deferred, not silently missing

Two pieces were designed early on and intentionally not built, rather than left as
an undocumented gap:

- **A separate FastAPI/SQLite service.** The Desk needs to read decision and
  portfolio data, but that data already exists in real, verified form as
  `decision_log/*.jsonl` and `paper_ledger.json` - standing up a second service to
  re-serve files that already exist would be an extra moving part with nothing to
  show for it. `gloaming_desk/lib/data.ts` reads them directly instead.
- **`bitget-signal` news/macro-event skills.** Investigated on Day 5: these ship as
  Claude-Code-style skill definitions backed by MCP tool calls (`news_feed`,
  `tradfi_news` against an MCP server), designed for an MCP-client agent
  environment (e.g. Claude Desktop), not for a Python subprocess calling a CLI.
  Wiring a minimal MCP client for one data source was a real scope decision against
  the hackathon deadline, made explicitly rather than silently skipped. Qwen's
  reasoning today is grounded entirely in the real numeric snapshot (rToken price,
  proxy returns, spread) - genuinely real market data, just not news headlines.
  Noted here as a concrete direction for future work, not hidden.

## Alpha Factory (stretch, not a formal 3rd submission)

`engine/backtest/` is reused directly to produce a >=60-day/>=30-out-of-sample
Sharpe/Sortino/max-drawdown report (`alpha_factory/backtest_report.md`) as
supplementary validation evidence embedded in the Agentic Trading and AI Trading
Desk write-ups, and its per-day history also powers the Desk's decision stress
test (`alpha_factory/results/historical_scenarios.json`).
