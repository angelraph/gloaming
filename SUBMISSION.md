# Gloaming: hackathon submission

Bitget AI Base Camp Hackathon S2 (Genesis Season 2). Gloaming is entered twice, as two independent projects built on one engine, through the official Google Form: **Gloaming Agent** in the Agentic Trading track and **Gloaming Desk** in the AI Trading Desk track. The team's personal fields (team name, Bitget UID, contact) are held in the form and are not in this repository.

Every figure below is labelled **observed** (measured from the public record), **estimated** (a stated assumption applied to observed data) or **targeted** (a goal, not a result). Figures are as of 2026-10-10 and the live Performance page is the current source.

## Submission fields

| Field | Value |
|---|---|
| Project name | Gloaming (entries: Gloaming Agent, Gloaming Desk) |
| Track and sub-theme, entry 1 | Agentic Trading, **Cross-Asset Execution Agent** |
| Track and sub-theme, entry 2 | AI Trading Desk, **Decision Stress Testing** |
| One-liner, agent (113 characters) | Qwen-driven agent for Bitget rTokens that trades only while NYSE is closed, risk-gated, every decision explained. |
| One-liner, desk (120 characters) | A read-only overnight research desk for Bitget rTokens: live book, per-symbol research, decision inspector, stress test. |
| Live demo (no login) | https://gloamingdesk.vercel.app |
| Repository (public, MIT) | https://github.com/angelraph/gloaming |
| Paper-trading log, per cycle | [`gloaming_agent/decision_log/`](gloaming_agent/decision_log): one JSON record per symbol per cycle, committed by the workflow |
| Paper ledger with balance | [`gloaming_agent/paper_ledger.json`](gloaming_agent/paper_ledger.json); fills with running cash balance as CSV at https://gloamingdesk.vercel.app/api/export?dataset=fills&format=csv |
| Independent check of the fills | [`gloaming_agent/fill_verification.json`](gloaming_agent/fill_verification.json), written by [`verify_fills.py`](gloaming_agent/verify_fills.py) against Bitget's public candles |
| Unattended run history | https://github.com/angelraph/gloaming/actions |
| Performance and method | https://gloamingdesk.vercel.app/performance and https://gloamingdesk.vercel.app/method |
| Backtest code and results | [`engine/backtest/since_close_backtest.py`](engine/backtest/since_close_backtest.py), [`alpha_factory/results/since_close_backtest.json`](alpha_factory/results/since_close_backtest.json) |
| Demo film | sources and method in [`video/`](video/README.md) (3:38, 1920x1080) |
| LLM | Qwen3.8-max through the hackathon's OpenAI-compatible endpoint |

## Eligibility

| Requirement (Chapter IV of the handbook) | How Gloaming meets it | Evidence |
|---|---|---|
| **Agentic Trading:** runnable demo | A live, login-free app reading the agent's own files | https://gloamingdesk.vercel.app |
| **Agentic Trading:** event to decision to execution flow | Written up with a worked real example | [docs/event_decision_execution_flow.md](docs/event_decision_execution_flow.md), [docs/architecture.md](docs/architecture.md) |
| **Agentic Trading:** paper-trading log, run during the competition period, 2 weeks or more recommended | 797 paper fills from 2026-09-11 to 2026-09-29, with cycles running every 15 minutes since 2026-09-11, all committed | [decision log](gloaming_agent/decision_log), [ledger](gloaming_agent/paper_ledger.json) |
| **AI Trading Desk:** accessible demo | The same live app, with a page per symbol, a decision inspector and a stress test | https://gloamingdesk.vercel.app/desk |
| **AI Trading Desk:** one complete research task, question to insight | Open a symbol, read its spread against the real close, open any decision, see its inputs, the book Qwen saw, its reasoning and the risk verdict | [/desk/META](https://gloamingdesk.vercel.app/desk/META), [/agent](https://gloamingdesk.vercel.app/agent) |
| Compliant X post (`#BitgetHackathon`, `@Bitget_AI`, quote of the official post) | Included with the form | held in the submission form |

## Judging criteria

**Agentic Trading** is scored half on quantitative results and half by judges, on paper-trading Sharpe, maximum drawdown and win rate, decision explainability, agent architecture and risk-control effectiveness.

| Criterion | What we show | Where it is weak |
|---|---|---|
| Paper Sharpe, drawdown, win rate | All computed from real fills and shown net of the costs charged ([Performance](https://gloamingdesk.vercel.app/performance)) | **They are not good.** Return -1.95%, realized P&L -$1,879 net of $33 in costs, 64 of 354 position-reducing fills gained (18.1%), maximum drawdown 2.63% marked at fills, daily Sharpe -4.52 over 30 days (indicative only). 735 of 797 fills came from the first signal, which the project itself found was mostly measuring the session's own move |
| Explainability | Every decision keeps its written reasoning, its recorded inputs, the book Qwen was shown and the risk verdict, openable in the Desk. Holds are explained as well as trades | Qwen's rationale is model text, not a proof |
| Agent architecture | Qwen decides, a deterministic non-LLM layer gates, a ledger records, a separate check compares fills with the exchange's own candles. Dry runs cannot touch the live mirror | Paper only; Bitget's demo does not list rTokens, so no order ever reaches an exchange |
| Risk-control effectiveness | Per-symbol 15%, gross 60%, net 25%, daily loss breaker -5%, per-trade loss 2%, volatility-scaled sizing, no leverage, $1,000 per decision; every control has tests and the log shows rejections ([docs/risk_controls.md](docs/risk_controls.md)) | An early version blocked risk-reducing trades and left the book stuck for eight days (found and fixed, see [AUDIT.md](AUDIT.md) F8) |

**AI Trading Desk** is scored by judges on feature depth, research quality, fluency of the language interface and a personalised thesis.

| Criterion | What we show | Where it is weak |
|---|---|---|
| Feature depth | Seven pages plus a page per symbol, and 11 API routes, over one real record: the book against its caps, spread against the real close, a page per symbol, the decision inspector, a stress test replaying real historical nights, a chat grounded in the real data, downloads, a Bitget check on every fill | The Bitget signal integration (sentiment, derivatives positioning, news, yields) is wired but its upstream sources returned nothing in any logged snapshot, so the Desk shows "no data" there |
| Research quality | Each number links back to a file anyone can open; the method page states the signal, the costs and its own corrections | The stress test uses about 90 days of history, so its scenarios are recent |
| Language interface | A chat that answers only from logged data and says so when it has none | Short on personalisation; there are no user accounts |
| Thesis | Tokenized shares never close and their reference does; the Desk makes "what moved overnight" one page | The thesis as a trading edge is not supported by our own backtest (below) |

## What the evidence says

- **Observed, live paper record** (2026-09-11 to 2026-09-29): 797 fills, about $265,800 traded (2.7 times starting equity), paper equity $98,048 (-1.95%). Split by the signal in force: earlier signal 735 fills, 42 of 322 closing fills gained, -$1,906; anchored signal 53 fills, 14 of 24 gained, -$43 net of its costs (too few to judge); 9 fills made against a wrong anchor on 2026-09-26 are counted in neither ([AUDIT.md](AUDIT.md) F6).
- **Observed, backtest of the live definition** (65 real sessions, 2026-06-24 to 2026-09-24, hourly rToken data from Bitget and proxies from Yahoo, horizons and thresholds fixed in advance): trading against a spread of 0.5% or more averaged -7.6 bp gross per trade (standard error 5.0, 490 events, 44% winning) and about -37.6 bp after a 0.30% round trip; on the last third of sessions, set aside, -3.0 bp gross. A bigger spread was worse, not better, at every horizon, and spreads slightly continue rather than revert (correlation +0.25). There is **no cost-covering edge at 2 to 12 hours after the close**, and we do not claim one.
- **Observed, behaviour since:** Qwen is told this, and after the tightened prompt on 2026-09-29 it has proposed no trade: no fill after 2026-09-29 12:02 UTC, and 980 of the last 1,133 hold rationales cite the backtest. The paper record has stopped growing.
- **Observed, outside check:** 797 of 797 fills checked against Bitget's public 1-minute candles: 795 inside a range Bitget really traded, 2 missing by under 0.2 bp, 33 matching only an old print and flagged stale.
- **Observed, an earlier daily backtest** ([`alpha_factory/`](alpha_factory)): Sharpe 2.09, maximum drawdown -3.51%, 57% win rate over 84 days. It uses daily close-to-close returns, a different specification, and the hourly test above does not corroborate it.
- **Estimated, costs:** each fill from 2026-09-26 is charged 0.10% fee plus 0.05% slippage ($33.33 so far). These are assumptions, not Bitget's measured rToken schedule. The same rate applied to earlier fills would be about $365, shown separately and not in the ledger.
- **Targeted:** none stated as results. Activation, volume, AUM and retention do not apply to a paper agent and are not claimed.

## Project description

### Thesis

Bitget rTokens trade around the clock while the real shares they track trade about 6.5 hours on a weekday. When NYSE is closed nothing directly pins an rToken to its share, so overnight and weekend is the one window where the two can drift. Gloaming measures, for nine symbols (AAPL, AMZN, GOOGL, META, MSFT, NVDA, QQQ, SPY, TSLA), where each rToken trades against where its real share last closed, adjusted for what index futures, BTC and ETH and the dollar index have done since:

    fair value = real close x (1 + blended proxy return since that close)
    spread     = rToken return since that close - blended proxy return since it

Qwen3.8-max reads that snapshot and its own book every 15 minutes while NYSE is closed and returns buy, sell or hold, a size, a stop and a written reason. A separate deterministic layer can reject or shrink any decision. What we then did is test our own thesis on real hourly data, found it does not pay for itself at the horizons tested, and told the model, so the agent now trades only when it can name a specific reason a spread should differ from that average, which is rare.

### Target user and product value

*Assumed segments, not validated with users.* **Agent:** crypto-native traders and small funds holding roughly $50k to $500k of rToken exposure, medium risk appetite, who want the overnight and weekend hours covered inside hard limits instead of ignored. **Desk:** discretionary traders and portfolio managers with roughly $25k to $250k in rTokens who check positions once or twice a day and start each session reconstructing what moved overnight. What existing tools fail to give them is an agent whose every decision is explained and whose limits are in code, and a desk that can show the exact inputs behind one decision.

### Progress

Built and running: the signal, the agent loop and Qwen integration, the non-LLM risk layer, the paper ledger, the fill check, the Redis mirror, the Desk, 191 automated tests and an unattended GitHub Actions workflow. Problems found and fixed in the open, each with a test: a mismeasured first signal, an anchor that fell back to the previous day's close, a risk layer that blocked de-risking, a model call that timed out, a dry run that overwrote the public mirror, a performance page that read better than the record ([AUDIT.md](AUDIT.md)). Built and confirmed with two real fills in a self-test, and switched on in production: sending approved trades to Bitget's demo engine on the stock perpetuals. Not built: real-money execution, calibrated weights, early-close handling.

### Role of the LLM

Qwen3.8-max is the primary decision-maker for direction and size (trading-signal reasoning and agent decision-making), and it writes the Desk chat's answers from logged data (conversational interaction). It decided 95.5% of all logged decisions (17,654 of 18,486); the rest are a disclosed rule-based fallback used only when a call fails or times out, and every record says which path decided. It never executes trades and has no execution capability. A deterministic backstop that trims an over-cap book is labelled as rule-based in the log.

## Since submission

- Every fill checked against Bitget's own public candles, with the 2 misses and 33 stale matches listed.
- The Night Console and the Dusk Dial on the landing page, a new brand, Qwen's reasoning shown in full, and a narrated demo film ([`video/`](video/README.md)).
- The repository documentation reorganised around one evidence-first README, this file, an internal review and instructions for coding agents: [README.md](README.md), [AUDIT.md](AUDIT.md) and [AGENTS.md](AGENTS.md).
