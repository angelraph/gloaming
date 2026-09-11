# Gloaming

**Gloaming trades the hours the market can't.**

Built for Bitget's AI & Crypto Hackathon, Genesis Season 2 (submission deadline
Sept 21, 2026) - submitting to the **Agentic Trading** and **AI Trading Desk**
tracks.

Bitget rTokens (tokenized US stocks) trade 24/7, but the real NYSE/Nasdaq they're
pegged to closes every night and all weekend. In that gap - 16:00-09:30 ET on
weekdays, and all weekend/holiday hours, "gloaming": the dim in-between light after
sunset before full dark - there is no direct arbitrage pressure holding the on-chain
rToken price to the real share price. Gloaming estimates a synthetic fair value from
proxies that stay live overnight (an index-futures proxy, crypto beta, FX risk
sentiment), and trades and reports on the resulting spread. See
[docs/architecture.md](docs/architecture.md) for the full system, and
[docs/event_decision_execution_flow.md](docs/event_decision_execution_flow.md) for
exactly how one decision moves from a live market snapshot to a filled paper trade.

## Modules

- **[`gloaming_agent/`](gloaming_agent)** - autonomous agent that runs *only* while
  NYSE is closed. Qwen3.8-max is the primary decision-maker over a live snapshot per
  symbol (a deterministic fixed-threshold rule is the disclosed fallback when Qwen
  isn't configured or a call fails), every decision is gated by a separate non-LLM
  risk layer, and approved fills post to a self-maintained virtual ledger marked to
  real live rToken prices. Runs unattended every 15 minutes via a scheduled task.
  -> submits to **Agentic Trading**.
- **[`gloaming_desk/`](gloaming_desk)** - a Next.js research dashboard over the same
  real data: an overnight decision timeline, a fair-value-vs-actual spread chart, a
  decision-stress-test that replays real historical overnight moves against the
  current book, and a chat panel that answers questions grounded only in that real
  data. Never auto-executes - the human stays in control.
  -> submits to **AI Trading Desk**.
- **[`engine/`](engine)** - the shared Python core: market-data loaders, the
  fair-value model, and the backtest used both to calibrate that model and to
  produce Alpha Factory's supplementary validation report.
- **[`alpha_factory/`](alpha_factory)** - supplementary quantitative validation
  (Sharpe/Sortino/max-drawdown over real ~90-day history), embedded as evidence in
  the other two submissions rather than a formal third entry.

## Setup

```bash
# 1. Bitget Agent Hub (SDK, CLI, MCP, research skills) - the official installer has
#    a Windows bug (spawn npm ENOENT), so install the packages directly instead:
npm install --save-dev @bitget-ai/bitget-agent-sdk @bitget-ai/bitget-agent-cli \
  @bitget-ai/bitget-agent-mcp @bitget-ai/bitget-agent-skill @bitget-ai/bitget-signal

# 2. Python engine
cd engine && python -m venv .venv && .venv/Scripts/activate && pip install -r requirements.txt

# 3. Desk frontend
cd gloaming_desk && npm install
```

Copy `.env.example` to `.env` and fill in your own credentials - **never commit
`.env`**. Needs a Bitget **Demo Trading** API key (not a live-account key - see
[docs/architecture.md](docs/architecture.md)'s "Execution model" section for why)
and a Qwen API key.

Run the Agent unattended (Windows Task Scheduler, every 15 minutes, 24/7 -
`agent_loop.py` itself checks NYSE hours and no-ops while the market is open):

```powershell
powershell -File scripts/setup_scheduled_task.ps1
```

This survives sleep (configured to wake the machine) but **not a shutdown** - the
machine needs to stay powered on for the paper-trading log to stay continuous.

Run the Desk locally:

```bash
cd gloaming_desk && npm run dev
```

## Safety

Every rToken fill goes through a self-maintained paper ledger, not a live or demo
exchange order - see [docs/architecture.md](docs/architecture.md)'s "Execution
model" section. `execution.py` (the Bitget CLI wrapper used for account reads)
hardcodes `--paper-trading` on every write path regardless of config, and the
Bitget account used has withdrawals disabled at the account level. No real funds
are ever at risk. Full control inventory in
[docs/risk_controls.md](docs/risk_controls.md).

## Tests

```bash
cd engine && .venv/Scripts/activate && cd .. && python -m pytest tests/
cd gloaming_desk && npm run build && npm run lint
```

## License

MIT - see [LICENSE](LICENSE).
