# Submission form answers (paste-ready)

Form: https://forms.gle/GyWZCMCPocgJdJon6 (Bitget AI Trading Competition Submission Form).
**Deadline: October 8, 23:59 (UTC+8).** One response per project; this team enters two
independent projects, so submit this twice, once per section below.

Every figure is labeled **observed** (measured from the real record), **estimated** (a stated
assumption applied to observed data) or **targeted** (a goal, not a result). Numbers were
pulled Sept 26, 07:00 UTC; the live Performance page and the public repository hold the current
values, so refresh the figures below shortly before submitting.

Fields that only the team lead can answer (Team Name, Bitget UID, email, contact, background,
university, Demo Day, how you heard, S1 participation, Kimi credits, playbook review) are not
filled here.

---

# A. Agentic Trading: Gloaming Agent

**Competition Track:** Agentic Trading
**Competition Sub-theme:** Cross-Asset Execution Agent
**Project Name:** Gloaming Agent

**One-line Project Summary (140 characters max):**

    Qwen-driven agent for Bitget rTokens that trades only while NYSE is closed, risk-gated, every decision explained.

**Project Description**

**Part 1 - Thesis.** Bitget rTokens trade 24/7 while the real shares they track trade about
6.5 hours on weekdays. When NYSE is closed nothing directly pins an rToken to its share, so
overnight and weekend is the one window where the two can drift. Gloaming Agent measures, for
nine symbols (AAPL, AMZN, GOOGL, META, MSFT, NVDA, QQQ, SPY, TSLA), where each rToken trades
against where its real share last closed, adjusted for what live proxies (index futures, BTC/ETH,
the dollar index) have done since. Every input is measured over the same window, from the real
16:00 ET close to now: spread = rToken return since close minus blended proxy return since close.
Qwen3.8-max is the primary decision-maker: each cycle it sees the snapshot, Bitget's own signal
context (sentiment, positioning, news, yields via bitget-signal) and its own book, and returns
buy / sell / hold with a size, a stop and a written reason. A separate deterministic, non-LLM
risk layer can reject or resize any decision: per-symbol cap 15%, gross 60%, net 25%, daily loss
breaker -5%, per-trade loss limit 2%, volatility-scaled sizing, no leverage, $1,000 ceiling per
decision. It runs unattended on GitHub Actions every 15 minutes and only trades while NYSE is
closed. **We tested our own hypothesis and it is not supported as a standalone edge (Part 3):**
large spreads do not revert to the next open. The agent is therefore built to trade sparsely,
knows its costs, and treats a hold as the normal answer.

**Part 2 - Target user and product value.** *Target segment (assumed, not yet validated with
users):* Pro / VIP crypto-native traders and small funds holding roughly $50k to $500k of
tokenized-equity exposure, medium risk appetite, who want the overnight and weekend hours
managed within hard limits. Primary market: Bitget rTokens; use case: unattended, risk-bounded
coverage of hours a discretionary trader is asleep. Their pain: they either close rToken
positions before the real market shuts (giving up the overnight period entirely) or hold them
unmanaged (uncontrolled overnight risk). What existing tools fail to give them is an agent whose
every decision is explained and auditable and whose limits are enforced in code, not by prompt.

**Part 3 - Validation data and key metrics.**
- *Observed, live paper record* (Sept 11 to Sept 26, 15 days, public per-cycle logs): 746 fills,
  about $243,549 traded (turnover roughly 2.4x starting equity); paper equity $98,014 (-1.99%);
  realized P&L -$1,823 over 332 position-reducing fills, 52 of which gained (15.7%); maximum
  drawdown 2.63% (marked at fills, so understated); daily Sharpe -6.4 over 16 days (indicative only,
  window too short). 735 of the 746 fills were made by the earlier signal specification.
- *Observed, why that record is weak and what we did:* on Sept 25 we found the first signal mostly
  measured each session's own move (reported spreads reached -4.6% while every rToken sat within
  about 0.25% of its real close) and rebuilt it. On Sept 26 monitoring caught a Yahoo data gap that
  made the agent anchor to Thursday's close for about 90 minutes and take 9 paper fills on a false
  4% spread; the anchor now comes from the calendar and a missing bar means no trades. Both fixes
  are regression-tested and the affected fills are flagged in the record, not removed. Under the
  corrected signal, spreads are 0.3% to 0.6% and nearly every decision is a hold (first eight
  cycles: 72 records, 0 trades).
- *Observed, backtest of the live specification* (`engine/backtest/since_close_backtest.py`, code
  and results in the repository): 65 real sessions (Jun 24 to Sep 24), 2,300 symbol-horizon events,
  rToken hourly data from Bitget and proxies from Yahoo, fixed horizons (2/4/8/12h after the close)
  and thresholds. Trading against a spread of 0.5% or more earned -7.6 bp gross per trade (standard
  error 5.0, n = 490, 44% hit rate), about -37.6 bp after a 0.30% round trip; the same on the
  out-of-sample last third of sessions was -3.0 bp gross. Spreads slightly continue rather than
  revert (correlation +0.25 with the rToken's move to the open). No cost-covering edge in either
  direction at these horizons, so we do not claim one.
- *Observed, earlier daily backtest* (`alpha_factory/`): Sharpe 2.09, max drawdown -3.51%, win rate
  57%, +4.65% over 84 days. It uses daily close-to-close returns, a different specification from the
  live signal, and the hourly test above does not corroborate it; we report it for completeness.
- *Costs:* fills before Sept 26 carry no cost (*estimated* at 0.15% of notional, about $365, shown
  separately and not in the ledger). From Sept 26 each fill is charged 0.10% fee plus 0.05% slippage,
  *estimated assumptions* not yet checked against Bitget's rToken schedule, and Qwen is told a
  round trip costs about 0.30%. No funding cost applies to spot-style rTokens.
- *Targeted (goals, not results):* accumulate a clean, cost-inclusive record on the corrected signal
  through the deadline and publish it unedited. Activation, trading volume, AUM and retention do not
  apply to a paper-trading agent and are not claimed.

**Part 4 - Progress.** Built and running: the signal (`engine/data/overnight_anchor.py`), the agent
loop, Qwen integration (thinking mode off, 5-8 s calls, 91.3% of 9,606 logged decisions made by Qwen,
the rest the disclosed rule-based fallback), the non-LLM risk layer, a self-maintained paper ledger
marked to real live rToken prices (Bitget's demo environment does not list rToken symbols,
confirmed live), Redis mirror, and 158 automated tests. Problems hit and solved: the mismeasured
first signal; a risk layer that blocked risk-reducing trades and left the book stuck for eight days
(now net-exposure aware with a labeled backstop); Qwen timing out (fixed by turning thinking off);
Yahoo data gaps (calendar-based anchor); a local dry run once overwrote the public ledger mirror
(dry runs now cannot write to it, and each live cycle re-asserts the mirror). Not built: real
Bitget execution (rTokens have no demo market), calibrated signal weights (the 0.5/0.3/0.2 blend is
a prior; the hourly data suggests futures and dollar-index terms carry the signal), early-close
handling. Tools: Qwen3.8-max (hackathon endpoint), bitget-signal MCP, Bitget market-data CLI, Yahoo
Finance, GitHub Actions, Upstash Redis, Next.js on Vercel.

**Part 5 - Your take on AI trading (optional).** The useful discipline was to distrust our own
results: the most valuable finds (a mismeasured signal, a data gap, a stuck risk layer) came from
reading the agent's own decision log, not from its P&L. An agent worth trusting keeps a complete,
public, per-cycle trail and puts hard limits in code that the model cannot argue with.

**Submission Material Links**

    Project link: https://gloamingdesk.vercel.app
    Repository (public, README): https://github.com/angelraph/gloaming
    Run records - paper-trading log, per cycle (timestamp, instrument, direction, price, quantity): https://github.com/angelraph/gloaming/tree/master/gloaming_agent/decision_log
    Run records - paper ledger with account balance: https://github.com/angelraph/gloaming/blob/master/gloaming_agent/paper_ledger.json
    Run records - downloadable fills with running balance (CSV): https://gloamingdesk.vercel.app/api/export?dataset=fills&format=csv
    Performance and method: https://gloamingdesk.vercel.app/performance
    Backtest code and results: https://github.com/angelraph/gloaming/blob/master/engine/backtest/since_close_backtest.py
    Unattended run history: https://github.com/angelraph/gloaming/actions
    Demo video: [ADD LINK: public X post or YouTube, 3 minutes or less]

**Role of the LLM / AI in Your Project:** Qwen3.8-max (via the hackathon's OpenAI-compatible
endpoint) is the primary autonomous decision-maker: trading-signal reasoning and agent
decision-making. Each cycle, for each of nine symbols, it reads a live snapshot, Bitget signal
context and its own book, and returns buy/sell/hold, size, stop, confidence and a written
rationale. It is told its trading costs. It is never the last word: a separate deterministic
risk layer can reject or resize any decision, and a deterministic backstop trims an over-cap book,
labeled as rule-based in the log. A fixed-threshold rule is the disclosed fallback when a Qwen call
fails or times out; every record states which path decided.

**X Project Post URL:** [ADD LINK] (draft in docs/x_post_draft.md)

---

# B. AI Trading Desk: Gloaming Desk

**Competition Track:** AI Trading Desk
**Competition Sub-theme:** Decision Stress Testing
**Project Name:** Gloaming Desk

**One-line Project Summary (140 characters max):**

    A read-only overnight research desk for Bitget rTokens: live book, per-symbol research, decision inspector, stress test.

**Project Description**

**Part 1 - Thesis.** A trader holding rToken exposure needs a fast, explainable answer to "what
happened to my book overnight and why", not a black box deciding for them. Gloaming Desk is a
read-only app over the same real data as the companion agent: the live book against each risk cap;
a spread-against-real-close chart; a page per symbol (price against the real close, spread history,
position, every decision, every fill); a decision inspector that shows, for any decision, the market
inputs recorded, the exact book context the model was shown, its reasoning, the risk verdict and
the execution; a chat grounded only in the real data; and a stress test that replays each held
symbol's worst historical night against today's book. It never places a trade; the human decides.
That boundary is structural: no execution code path exists in the Desk.

**Part 2 - Target user and product value.** *Target segment (assumed, not yet validated with
users):* Pro / retail-plus discretionary traders and portfolio managers with roughly $25k to
$250k in rToken positions, medium risk appetite, who check positions once or twice a day and
start each session needing to reconstruct what moved overnight across price action, proxy signals
and any automated activity. That is normally a manual, multi-tab job. The Desk makes it one page
and one conversation, and lets them open any single decision to see exactly why it was made.

**Part 3 - Validation data and key metrics.**
- *Observed, worked research task (Sept 14):* asked the chat "what happened in the market at night",
  then checked its answer against the decision log independently. The claimed total sell notional
  across 6 symbols, $3,771.87, matched a from-scratch recomputation exactly, and every claimed AAPL
  figure (return, fair value, spread, each proxy, at both timestamps) matched the logged snapshots.
  Nothing was invented; every number traced to a real event.
- *Observed, derived not asserted:* the Performance page rebuilds paper equity from the ledger's
  fills alone, and its final figure matches the live portfolio to the cent (Sept 25: $98,046.16 both
  ways; Sept 26: $98,013.35 both ways, after costs were added).
- *Observed, the Desk exposes real defects:* reading the same records is how two data problems were
  found (a mismeasured signal on Sept 25; a Yahoo data gap on Sept 26). Both are disclosed on the
  Method page, and the Performance page splits the record by signal era and keeps the affected fills
  out of both eras instead of blending them.
- *Observed, engineering checks:* 158 automated tests, every page verified with no horizontal
  overflow at 375 px, keyboard-operable dialog with focus trapping, chart data available as tables.
- *Not measured:* there are no external users yet, so no task-completion or retention data exists and
  none is claimed. *Targeted:* put the Desk in front of a small number of real rToken traders before
  the deadline and report what they could and could not do; result unknown.

**Part 4 - Progress.** Built and live at https://gloamingdesk.vercel.app: overview, desk, agent,
performance, method, FAQ and roadmap pages, a page per symbol, the decision inspector, fills and
decisions as CSV/JSON, a verify-it-yourself panel linking to the public repository, per-page
metadata and share image. Data comes from the agent's Redis mirror with local-file fallback.
Problems hit and solved: a local dry run once overwrote the public ledger mirror (now impossible,
with a self-healing re-push); a server component reading data exported from a client module
(moved to a shared file). Not built: user accounts or personalization; the stress test uses ~90 days
of history, so its scenarios are recent. Tools: Next.js 16, Tailwind 4, Recharts, Qwen3.8-max,
Upstash Redis, Vercel.

**Part 5 - Your take on AI trading (optional).** Explainability is the product. A desk that can
show the exact inputs, the book context and the risk verdict behind one decision earns more trust
than one that summarizes well.

**Submission Material Links**

    Project link: https://gloamingdesk.vercel.app
    Repository (public, README): https://github.com/angelraph/gloaming
    Research-task walkthrough: https://gloamingdesk.vercel.app/desk/META (a page per symbol) and https://gloamingdesk.vercel.app/agent (decision inspector)
    Method and limits: https://gloamingdesk.vercel.app/method
    Performance derived from real fills: https://gloamingdesk.vercel.app/performance
    Demo video: [ADD LINK: public X post or YouTube, 3 minutes or less]

**Role of the LLM / AI in Your Project:** Qwen3.8-max generates the chat's narrative answers and
the plain-language framing, grounded only in the real portfolio and decision data passed as context
on every request (positions, fills, recent decisions); it is instructed never to invent figures, and
the Sept 14 check above found it did not. It is conversational interaction and summarization, not
trading: it never executes, never has an execution capability, and never recommends auto-execution.
The decisions the Desk displays were made by the companion agent's Qwen3.8-max.

**X Project Post URL:** [ADD LINK] (draft in docs/x_post_draft.md)
