# Gloaming

**Gloaming trades the hours the market can't.**

Built for Bitget's AI & Crypto Hackathon, Genesis Season 2, for the **Agentic Trading**
and **AI Trading Desk** tracks.

- Live Desk: https://gloamingdesk.vercel.app
- Source and full decision history: https://github.com/angelraph/gloaming

Bitget rTokens (tokenized US stocks) trade 24/7, but the real NYSE/Nasdaq shares they
track close every night and all weekend. In that gap (16:00 to 09:30 ET on weekdays and
all weekend and holiday hours, the "gloaming": the dim in-between light after sunset
before full dark) nothing directly pins an rToken to its share. Gloaming measures where
each rToken trades against where its real share last closed, adjusted for what live
proxies (index futures, crypto, FX) have done since, and acts on the resulting spread
only while NYSE is closed. See [docs/architecture.md](docs/architecture.md) for the
system and [docs/event_decision_execution_flow.md](docs/event_decision_execution_flow.md)
for how one decision moves from a live snapshot to a filled paper trade.

## What is running

- **An unattended agent.** A GitHub Actions workflow runs a cycle every 15 minutes,
  around the clock, and the code itself only trades while NYSE is closed. The paper record
  starts Sept 11; since Sept 13 the cycles run on GitHub's infrastructure rather than a
  laptop. Every cycle's decisions and ledger are committed straight into this repository,
  so the history is public and checkable.
- **Qwen3.8-max as the decision-maker.** For each of nine symbols it reads a live
  snapshot, Bitget's own signal context and its own book, and returns buy, sell or hold
  with a size, a stop and a written reason. About 91% of all logged decisions came from
  Qwen; the rest are the disclosed rule-based fallback.
- **A non-LLM risk layer.** Per-symbol, gross and net exposure caps, a daily loss
  breaker, a per-trade loss limit, volatility-scaled sizing and no leverage, enforced in
  code before any paper fill. See [docs/risk_controls.md](docs/risk_controls.md).
- **A desk that explains.** A multi-page, read-only Next.js app: the book against its
  limits, spreads against each real close, a page per symbol, an overnight timeline, chat
  grounded in the real data, a stress test that replays real historical nights, and a
  decision inspector that shows the market inputs, the book Qwen was shown, its
  reasoning and the risk verdict for any decision.

## Modules

- **[`gloaming_agent/`](gloaming_agent)** - the autonomous agent. Qwen decides, a
  separate deterministic risk layer gates, approved fills post to a self-maintained
  paper ledger marked to real live rToken prices. **Agentic Trading.**
- **[`gloaming_desk/`](gloaming_desk)** - the research desk, over the same real data.
  Pages: overview, desk, agent, performance, method, FAQ, roadmap and one per symbol.
  It never places a trade. **AI Trading Desk.**
- **[`engine/`](engine)** - the shared Python core: market-data loaders, the overnight
  anchor and fair-value model, and the backtest.
- **[`alpha_factory/`](alpha_factory)** - supplementary quantitative validation over
  real ~90-day history, embedded as evidence in the submissions rather than a third entry.

## The signal, and a correction made in the open

Every input is measured over the same window: from the real share's last regular-session
close to now.

    fair value = real close x (1 + blended proxy return since that close)
    spread     = rToken return since that close - blended proxy return since it

The blend is 0.5 index futures, 0.3 crypto (BTC and ETH), 0.2 the dollar index inverted.

The first version compared an rToken's rolling 24-hour move with proxies over mismatched
windows. Checking it against the real closes showed it mostly measured the regular
session's own move (reported spreads reached -4.6% and +2.8% while every rToken actually
sat within about a quarter of a percent of its real close). It was rebuilt on Sept 25.
Older records stay in the log, labeled by `signal_spec`.

A second failure was caught by monitoring the first weekend. From about 00:00 to 01:40 UTC
on Sept 26, Yahoo's daily data briefly lacked Friday's bar, the anchor fell back to
Thursday's close, and Friday's own move read as a 4% dislocation, producing 9 paper fills.
The anchor now comes from the calendar and the data must contain that day's bar, otherwise
the cycle makes no trades. Both are written up in
[docs/architecture.md](docs/architecture.md), and both are covered by regression tests.

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
[docs/architecture.md](docs/architecture.md)'s "Execution model" section for why) and a
Qwen API key.

Production runs on GitHub Actions (`.github/workflows/agent_loop.yml`), triggered every
15 minutes, with the ledger and decision log mirrored to Redis for the deployed Desk. To
try one cycle locally without side effects:

```bash
python gloaming_agent/agent_loop.py --smoke-test
```

A dry run writes nothing to Redis and logs to a git-ignored folder, so it cannot touch the
live Desk or the committed record.

Run the Desk locally:

```bash
cd gloaming_desk && npm run dev
```

## Safety

Every rToken fill goes through a self-maintained paper ledger, not a live or demo
exchange order - see [docs/architecture.md](docs/architecture.md)'s "Execution model"
section. `execution.py` (the Bitget CLI wrapper used for account reads) hardcodes
`--paper-trading` on every write path regardless of config, and the Bitget account used
has withdrawals disabled at the account level. No real funds are ever at risk. Full
control inventory in [docs/risk_controls.md](docs/risk_controls.md).

## Tests

```bash
python -m pytest tests/            # 158 tests: risk layer, signal window arithmetic, ledger, cycle behavior
cd gloaming_desk && npm run build && npm run lint
```

## License

MIT - see [LICENSE](LICENSE).
