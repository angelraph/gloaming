# Gloaming - Architecture

## One engine, two submissions

```mermaid
flowchart TB
    subgraph ext["External data, public, no auth needed"]
        bitget["Bitget market data<br/>rToken + crypto prices, via bgc CLI"]
        yahoo["Yahoo Finance<br/>ES=F / NQ=F futures, DXY"]
        qwen["Qwen3.8-max API<br/>hackathon endpoint"]
        signal["Bitget bitget-signal MCP server<br/>sentiment, derivatives, news, yields"]
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
    signal -. "optional enrichment, None if unavailable" .-> loop
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

There is no separate FastAPI or SQLite layer - that was considered and
deliberately not built (see "Deferred, not silently missing" below). The Agent
and the Desk each read the same on-disk files directly. `bitget-signal`
(sentiment, derivatives positioning, news, and yield-curve context) is wired in
directly to the Agent loop - see "Bitget-signal integration" below for details.

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
   not just documented - see `run_once()`'s `is_nyse_closed()` check). Once per
   cycle it also calls `bitget_signal.get_signal_context()` (real crypto
   sentiment, BTC derivatives positioning, news, and yield-curve context from
   Bitget's own public MCP server - see "Bitget-signal integration" below), then
   builds a live snapshot per symbol
   and calls Qwen3.8-max for the trade decision whenever `QWEN_API_KEY` is
   configured, falling back to a deterministic fixed-threshold rule otherwise
   (see `docs/event_decision_execution_flow.md` for the exact sequence). Every
   decision passes through `risk_controls.py` before execution.
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

## Bitget-signal integration: real sentiment and derivatives context

`gloaming_agent/bitget_signal.py` calls Bitget's own public `bitget-signal` MCP
server (`https://datahub.noxiaohao.com/mcp`, confirmed by reading the installer
script of the `@bitget-ai/bitget-signal` package already listed in
`package.json`) directly over Streamable HTTP/JSON-RPC - no API key, no account,
no credentials. It adds four real signals to the Agent's overnight reasoning,
matching the data sources behind the package's sentiment-analyst, news-briefing,
and macro-analyst Skills:

- `sentiment_index` - crypto Fear & Greed reading.
- `derivatives_sentiment` - BTC futures long/short positioning.
- `news_feed` - crypto/market news headlines.
- `rates_yields` - Treasury yield-curve snapshot.

All four are fetched once per cycle in `run_once()` (not once per symbol), bundled
by `get_signal_context()`, and passed through `build_snapshot()` as an optional
`bitget_signal_context` field. `build_user_prompt()` only adds a signal section to
the Qwen prompt when real values are present - it never fills in a placeholder for
a source that returned nothing, and the raw fields the API returns are passed
through unrenamed rather than mapped onto a guessed schema for a "successful"
response this project had not observed live at the time the first two of these
(`sentiment_index`, `derivatives_sentiment`) were wired in.

**The news/macro skills were originally skipped on Day 5 on a mistaken
assumption** - that they needed an MCP-client host environment (e.g. Claude
Desktop) rather than a plain HTTP client. That assumption was never revisited
until Sept 22, when it turned out to be simply wrong: `news_feed` and
`rates_yields` are plain callable MCP tools over the same public endpoint,
confirmed live by calling `tools/list` directly - no different from
`sentiment_index`/`derivatives_sentiment`, which were already proven to work
from this exact plain Python client. There was no real technical blocker; the
gap existed only because the original assumption was never checked against the
live server.

Every call is wrapped the same way every other external dependency in this
project is (`kv_sync.py`, `llm_client.py`): broad `try/except`, logs to `stderr`,
returns `None` on any failure, never raises into the trading loop. `_has_real_data()`
recursively detects the case where the MCP layer itself succeeds (`isError:
false`) but the signal server's own upstream source had nothing to return - both
the flat case (e.g. `{"alt_me_error": ""}`) and a nested one (`rates_yields`
returning every individual yield tenor as `{"error": ""}` while still including
top-level fields, like `spread_10y2y: 0.0`, computed from that missing data - a
default, not a real reading, and never treated as one). `news_feed`'s emptiness
is checked directly (every requested feed returning zero items is a real "nothing
new" answer, not a failure, but still not real content) since a generic structural
check cannot tell an empty feed apart from a real one by shape alone.

Confirmed live Sept 22: the signal server's JSON-RPC layer works correctly, but
every one of its four underlying data sources (alternative.me, mempool.space, its
news aggregator, and the Treasury yield feed) was returning empty results at call
time. Real production cycles on the actual GitHub Actions runner (not just local
testing) show the same graceful degradation, and the rest of each cycle completes
normally with no crash and no change in behavior. `tests/test_bitget_signal.py`
covers the real response shape for each source, every empty/degraded pattern
observed live (including the misleading `rates_yields` case above), MCP-level
errors, network failures, and the missing-session-id case, all mocking the HTTP
layer directly - CI never touches the real network.

## Deferred, not silently missing

One piece was designed early on and intentionally not built, rather than left as
an undocumented gap:

- **A separate FastAPI/SQLite service.** The Desk needs to read decision and
  portfolio data, but that data already exists in real, verified form as
  `decision_log/*.jsonl` and `paper_ledger.json` - standing up a second service to
  re-serve files that already exist would be an extra moving part with nothing to
  show for it. `gloaming_desk/lib/data.ts` reads them directly instead.

## Alpha Factory (stretch, not a formal 3rd submission)

`engine/backtest/` is reused directly to produce a >=60-day/>=30-out-of-sample
Sharpe/Sortino/max-drawdown report (`alpha_factory/backtest_report.md`) as
supplementary validation evidence embedded in the Agentic Trading and AI Trading
Desk write-ups, and its per-day history also powers the Desk's decision stress
test (`alpha_factory/results/historical_scenarios.json`).
