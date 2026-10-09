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

## Why Gloaming exists

### The problem

Tokenized stocks never close, but the markets behind them do. A Bitget rToken can be
bought and sold at 3 a.m. on a Sunday, while the share it tracks last traded on Friday
afternoon. For about 17.5 hours every weekday, and all weekend, three things are true at
once:

- **Nothing pins the price.** There is no live share to arbitrage against, so an rToken
  can drift away from where its stock would plausibly be.
- **Nobody is watching.** A human trader is asleep, and a traditional desk is closed.
- **Holders have only two bad choices.** Close rToken positions before the bell and give
  up the overnight period entirely, or hold them unmanaged and accept risk nobody is
  steering.

The automated tools that do exist tend to be black boxes: they act, but they cannot say
why, and their limits live in a prompt rather than in code.

### Who it is for

*Assumed target users, from the hackathon submission; not yet validated with real users.*

- **Gloaming Agent:** crypto-native traders and small funds holding roughly $50k to $500k
  of rToken exposure, with medium risk appetite, who want the overnight and weekend hours
  managed inside hard limits instead of ignored.
- **Gloaming Desk:** discretionary traders and portfolio managers holding roughly $25k to
  $250k in rTokens, who check positions once or twice a day and start every session
  reconstructing what moved overnight. Today that is a manual, many-tab job.

### What Gloaming does about it

- **It watches the gap.** Every 15 minutes, for nine rTokens, it estimates where each
  should be trading from its real close and what live proxies have done since, and
  measures the spread.
- **It acts only when acting is worth it.** Qwen decides, knowing the trading costs and
  its own book, and a hard-coded risk layer can veto or shrink anything. Most nights the
  right answer is to hold, and it says why.
- **It explains everything.** Every decision, with its inputs and reasoning, is written to
  a public log and can be opened on the Desk. The Desk turns "what happened overnight"
  from a research task into one page and one conversation.

### The vision

Gloaming is meant to be **the night shift for tokenized equities**: an agent that covers
every hour the real market is closed, acts only when a gap can pay for itself, and leaves
a plain-language record anyone can check. Tokenized markets run 24/7; the tools that
manage risk in them should too, and they should be accountable for every move.

Where it goes next, as intentions rather than promises (the live list is on the
[roadmap page](https://gloamingdesk.vercel.app/roadmap)):

1. **Sharpen the signal.** Fit the proxy weights on since-close history, model early closes
   and holidays, and add company-specific context such as news and earnings.
2. **Widen the coverage.** Bitget lists over a thousand rTokens; the same method applies
   to any of them with a liquid proxy.
3. **Move from paper to real execution, carefully.** Bitget's demo environment does not
   support rTokens today, so every fill is simulated at live prices. Real orders would
   come only with tight caps, the same risk layer and the same public record.
4. **Make the Desk useful to any holder.** Open it in the morning and see, for your own
   positions, what moved overnight and why.

## Since submission: we keep shipping

The hackathon deadline was not the finish line. Shipped after submission:

- **Every fill checked against Bitget.** All 797 paper fills compared with Bitget's own
  public 1-minute candles: 795 sit inside a range Bitget really traded, the 2 misses are
  under 0.2 basis points, and 33 matched only an hours-old price on quiet nights. All
  listed, none hidden, rerun after every cycle by
  [`gloaming_agent/verify_fills.py`](gloaming_agent/verify_fills.py); no API key needed.
- **The Night Console** on the landing page: four live views of the real data. The book,
  Bitget's hourly candles against the agent's fair value with the closed hours shaded, an
  hour-by-hour spread map of all nine symbols, and every position against its cap.
- **The Dusk Dial**, a live 24-hour New York clock showing when the agent may act.
- **Qwen's reasoning in full** everywhere it appears, never cut off.
- **A new brand**, a lighter and smoother site, and a narrated demo video.

## What is running

- **An unattended agent.** A GitHub Actions workflow runs a cycle every 15 minutes,
  around the clock, and the code itself only trades while NYSE is closed. The paper record
  starts Sept 11; since Sept 13 the cycles run on GitHub's infrastructure rather than a
  laptop. Every cycle's decisions and ledger are committed straight into this repository,
  so the history is public and checkable.
- **Qwen3.8-max as the decision-maker.** For each of nine symbols it reads a live
  snapshot, Bitget's own signal context and its own book, and returns buy, sell or hold
  with a size, a stop and a written reason. About 95% of all logged decisions (16,368 of
  17,200 through Oct 7) came from Qwen; the rest are the disclosed rule-based fallback.
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
python -m pytest tests/            # 172 tests: risk layer, signal window arithmetic, ledger, cycle behavior, fill verification
cd gloaming_desk && npm run build && npm run lint
```

## License

MIT - see [LICENSE](LICENSE).
