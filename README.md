# Gloaming

**Gloaming trades the hours the market can't.**

Bitget rTokens (tokenized US stocks) trade 24/7, but the real NYSE/Nasdaq they're
pegged to closes every night and all weekend. In that gap — 16:00–09:30 ET on
weekdays, and all weekend/holiday hours, "gloaming": the dim in-between light after
sunset before full dark — there is no direct arbitrage pressure holding the on-chain
rToken price to the real share price. Gloaming is one shared "overnight fair-value"
engine, surfaced as two coordinated products, built for Bitget's AI & Crypto
Hackathon — Genesis Season 2 (submission deadline Sept 21, 2026).

## Modules

- **`gloaming_agent/`** — autonomous LLM agent (Qwen3.8-max) that runs *only* while
  NYSE is closed: estimates a synthetic fair value per rToken from proxies that stay
  live overnight (index-futures proxy, crypto beta, FX), trades the spread expecting
  convergence at the next open, watches for weekend macro shocks, and is gated by
  hard non-LLM risk controls. Runs in Bitget `--paper-trading` mode.
  → submits to the **Agentic Trading** track.
- **`gloaming_desk/`** — natural-language research dashboard over the same data: an
  overnight event timeline, fair-value-vs-actual charts, plain-English narration, and
  a decision-stress-test replay tool. Never auto-executes — human makes the call.
  → submits to the **AI Trading Desk** track.
- **`engine/`** — the shared Python core (data ingestion, fair-value model, backtest,
  FastAPI) both modules are built on.
- **`alpha_factory/`** — optional stretch: reuses the engine's backtest core as
  supplementary quant validation embedded in the other two write-ups (not a formal
  3rd submission — see [docs/architecture.md](docs/architecture.md)).

## Status

Day 1 of an ~11-day build (Sept 10 → Sept 21, 2026). See the full build plan at
`C:\Users\Admin\.claude\plans\read-carefully-and-make-twinkling-marshmallow.md`.

## Setup

```bash
# 1. Bitget Agent Hub (SDK, CLI, MCP, research skills)
npx @bitget-ai/bitget-agent-installer upgrade-all --target all

# 2. Python engine
cd engine && python -m venv .venv && .venv/Scripts/activate && pip install -r requirements.txt

# 3. Desk frontend
cd gloaming_desk && npm install
```

Copy `.env.example` to `.env` and fill in credentials — **never commit `.env`**.

## Safety

Every execution path runs with `--paper-trading` (and `--read-only` where
applicable) hardcoded. The Bitget Agentic Account used has withdrawals disabled.
No real funds are ever at risk. See [docs/risk_controls.md](docs/risk_controls.md).
