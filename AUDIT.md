# Gloaming internal review

This is an **internal review**, not a professional third-party audit. Gloaming was built and reviewed with an AI coding assistant (Claude Code) working with the project owner. The findings below came from three places: reading the agent's own public decision log while it ran, comparing its numbers against real market data, and tests. Nobody outside the project reviewed the code.

It is a record of what was found, how, what it cost and what was changed, including the findings that are not flattering. Everything is dated, and each fix names the commit that made it and the test that keeps it fixed.

Last updated 2026-10-10.

## 1. Scope

**Owned and reviewed**

| Component | Path | What could go wrong |
|---|---|---|
| Signal | `engine/data/overnight_anchor.py`, `gloaming_agent/agent_loop.py` (`build_snapshot`) | Wrong anchor close, mismatched windows, stale data presented as a gap |
| Decision layer | `gloaming_agent/llm_client.py`, `gloaming_agent/prompts/system_prompt.md` | Timeouts, the model ignoring its book or its costs, reasoning that does not match the evidence |
| Risk layer | `gloaming_agent/risk_controls.py` | A cap that blocks de-risking, a breaker that cannot fire, a hole around the net cap |
| Paper ledger | `gloaming_agent/paper_ledger.py` | Fills that cost nothing, state overwritten by a test run |
| Verification | `gloaming_agent/verify_fills.py` | A check that cannot fail, or that hides what it cannot confirm |
| Mirror | `gloaming_agent/kv_sync.py` | The public Desk showing something the agent did not do |
| Workflow | `.github/workflows/agent_loop.yml` | Missed cycles, lost records, push conflicts |
| Desk | `gloaming_desk/` | Numbers that read better than the record, claims the data does not back |

**Not owned (out of scope)**

- Bitget's market data and rToken prices, Yahoo Finance (daily closes, hourly futures and dollar index), Qwen's endpoint, GitHub Actions, Upstash Redis and Vercel. Gloaming records when they fail and degrades without inventing data, but it cannot make them reliable.
- Bitget's demo trading, which does not list rToken symbols (confirmed live on 2026-09-11: an order for `RAAPLUSDT` is rejected while `BTCUSDT` works). Every fill is therefore a ledger entry at a live price, and nothing here exercises Bitget's order matching.

No code path in the repository can place a real order or move funds. The Bitget key used for reads has withdrawals disabled at the account level.

## 2. Method

1. **Live monitoring.** Every cycle's records are committed to the repository, so the log can be read like a flight recorder. Most findings below came from asking why a number in it looked wrong.
2. **Comparison with real data.** Spreads, closes and fills were checked against real closes, Bitget's own candles and the rToken's own hourly history.
3. **Tests.** Each fix added a regression test. The suite is 172 tests in 12 files, run with `python -m pytest tests/` and all passing at the time of writing.
4. **A backtest of the live definition.** The thesis was tested on 65 real sessions of hourly data with the same definitions the agent uses ([`engine/backtest/since_close_backtest.py`](engine/backtest/since_close_backtest.py)).

## 3. Findings and resolutions

### Execution and operations

**F1. Bitget's demo cannot trade rTokens (2026-09-11).** Found by trying: `RAAPLUSDT` is rejected by the demo environment while `BTCUSDT` works. Impact: no exchange-side paper trading is possible. Resolution: a self-maintained virtual ledger marked to real live rToken prices (`paper_ledger.py`), disclosed everywhere as simulation. Commit `4f862ce`.

**F2. A sleeping laptop silently dropped cycles and records (2026-09-12).** Found from gaps in the log that lined up with lid-close events. Cycles were also written in one batch at the end, so a stall lost every record already computed. Resolution: each record is written and mirrored the moment it exists (`560370d`), and the schedule moved to GitHub Actions (`5e783ae`). Test: `tests/test_run_once_incremental.py`.

**F3. GitHub's own cron was too unreliable at this cadence (2026-09-12 and 13).** Found by watching: no runs for 45 minutes after the schedule was added, runs every 1.5 to 3 hours after offsetting it, and runs piling up and cancelling when it ran next to an external trigger. Resolution: only an external trigger (cron-job.org calling the workflow dispatch API every 15 minutes) remains (`4ac9fde`, `87a73fa`). A push failure that dropped a decision log was recovered by hand (`7462c6e`).

**F4. A local dry run overwrote the public ledger mirror (2026-09-26).** Found when the public Desk showed 623 fills while the real ledger had 735. A dry run on the owner's machine loaded the production Redis credentials from `.env` and pushed a stale ledger and its own records over the live ones. Impact: the public Desk was wrong until repaired by hand. Resolution: dry runs now disable every Redis write and log to a git-ignored folder, and every live cycle re-asserts the ledger mirror so a bad push heals within 15 minutes. Commit `97aaf0d`. Tests: `test_a_dry_run_never_writes_to_redis_even_with_credentials_configured`, `test_sync_mirror_pushes_the_local_ledger_unchanged`.

### The signal

**F5. The first signal mostly measured each session's own move (2026-09-25).** Found by asking why one symbol's spread was not closing. Checked against real closes, every rToken sat within about 0.25% of its real share's last close, while the logged spreads reached -4.62% (META) and +2.80% (MSFT). The inputs were over different windows: an rToken 24-hour return against a futures term that was a 5-day return labelled "24h" (NQ +2.76% against a true +0.60%), a 24-hour crypto return and a one-hour FX return. Impact: 735 of the 797 fills were made on this specification, and the live record before 2026-09-25 should be read that way. Resolution: every input is now measured from the real share's last regular-session close (`28f9335`); records carry `signal_spec: "since_last_close_v2"` and older ones are left in place, labelled by the absence of it. Tests: `tests/test_overnight_anchor.py`.

**F6. The anchor fell back to the previous day's close (2026-09-26).** Found by watching the first weekend: `hours_since_close` read 28 where it should have read 4 to 5. Yahoo publishes a session's daily bar about 5 hours 45 minutes after the close, and until it lands the daily series ends at the previous session. The anchor was "the newest bar returned", so every symbol was priced against Thursday's close and Friday's own move read as a 4% dislocation. Impact: 9 paper fills (about $3,580 of notional, from 00:02 to 01:32 UTC) on a false spread. They remain in the ledger and are reported separately on the Performance page, in neither signal era. Resolution: the anchor comes from the calendar (the last completed weekday session, minus listed 2026 holidays) and the data must contain that session's bar, otherwise the cycle records an error per symbol and trades nothing (`21a90bb`). Tests: `test_a_missing_fridays_bar_refuses_to_anchor_to_thursday` and related.

This was first written up as a one-off data gap. It is not: see limitation L3, which is the same delay recurring every weekday.

**F7. The volatility input to sizing stopped meaning anything (2026-09-25).** `|spread|` was used as a volatility, which only worked while the "spread" was a multi-percent number. Resolution: sizing uses the real share's realized 10-day daily volatility (`28f9335`).

### Risk layer and decisions

**F8. The risk caps blocked risk-reducing trades and the book got stuck (2026-09-22).** Found when the book stayed stuck for eight days: the per-symbol and aggregate caps rejected a sell that would have reduced exposure as hard as a buy that added it, and the daily breaker had a gap that stopped de-risking. Resolution: caps are net-exposure aware and de-risking is always allowed (`bc930b6`, `40765bc`).

**F9. Nine correlated "cheap" signals were being bought as nine independent trades (2026-09-24).** Found from the decision log: the same direction on most symbols at once, because their spreads share the same proxies. Resolution: a 25% net directional cap (`206c5dc`), Qwen is shown its own book each cycle, and a deterministic backstop trims an over-cap book by at most 2% of equity per cycle, labelled `risk_backstop_trim` in the log so it is never mistaken for Qwen (`855ae11`). Tests: `tests/test_book_context_and_backstop.py`.

**F10. Qwen's share of decisions collapsed to about 14% (2026-09-24).** Found from `decision_source`: with a longer, book-aware prompt, the model's hidden reasoning took 17 to 77 seconds and calls timed out into the rule-based fallback. Resolution: thinking mode off, a 30-second call timeout with one retry, and a 4-minute cap on total model time per cycle (`d93665d`). Over the whole record Qwen made 95.5% of decisions (17,654 of 18,486).

**F11. Fills cost nothing, and the Performance page read better than the record (2026-09-26 and 28).** Found while reviewing the record: every one of the 746 fills to that point had been recorded at the last price with no fee or slippage, and the page's "realized P&L" was computed from price only. Resolution: every fill is charged a stated 0.10% fee plus 0.05% slippage (assumptions, not measured Bitget rates), recorded as `cost_usd` (`0237a75`); the page nets the costs it actually charged (`1840130`) and shows an estimate for earlier fills separately without adding it to the ledger. Qwen is told the cost.

**F12. The agent kept trading a spread our own backtest says loses (2026-09-28).** Found by reading why MSFT traded 27 times in a weekend on a 0.6% to 1.0% spread that never reverted. The backtest (65 sessions) shows trading against a spread of 0.5% or more averaging -7.6 bp gross and -37.6 bp after the 0.30% round trip, only 44% winning, and that larger spreads are worse, not better, at every horizon. The prompt had also told the model that an "unusually large dislocation" could justify a trade, which the data contradicts. Resolution: the prompt states the per-horizon table and requires each rationale to name its bucket and net return before giving a specific, checkable reason (`5ee9e24`, `0e39200`). A test ties the prompt's figures to the checked-in results file so they cannot drift. Impact since: no trades after 2026-09-29 12:02 UTC (see L2).

### Verification

**F13. Fills were only checked against themselves (2026-10-07).** The record had no outside check. Resolution: `verify_fills.py` compares every fill with Bitget's own public 1-minute candles (no key needed) and the workflow reruns it. Result at the last run (797 of 797 checked): 795 sit inside a range Bitget really traded, 2 miss by under 0.2 basis points, and 33 matched only a trade that was more than 15 minutes old, which is flagged as stale rather than counted as clean (`21db256`, `fdac92e`). This verifies that a fill's price was one the market actually printed. It does not verify that an order would have been accepted or filled at size.

## 4. Test and check results

| Check | Result |
|---|---|
| Unit and regression tests | 172 passed, 12 files (`python -m pytest tests/`) |
| Desk | `npx tsc --noEmit` clean and `npm run build` succeeds for all 8 pages and 11 routes |
| Workflow | the last 100 consecutive runs succeeded |
| Fill verification | 797 checked, 795 matched, 2 mismatched, 33 stale |
| Em-dash policy | none in tracked files |
| Prompt against backtest | numbers cited in `system_prompt.md` match `alpha_factory/results/since_close_backtest.json` (test) |

## 5. Known limitations (open)

**L1. Paper trading, with assumed costs.** Fills are at the last price plus a stated 0.15%. Real execution on rTokens could cost more, and size was never tested against real depth.

**L2. No demonstrated edge, and the agent has stopped trading.** The live definition has no edge at 2 to 12 hours after the close in the project's own backtest: -7.6 bp gross per trade at spreads of 0.5% or more (standard error 5.0, so statistically indistinguishable from zero) and about -37.6 bp after the assumed 0.30% round trip, which is clearly negative. After the prompt was tightened the agent made no trade after 2026-09-29 12:02 UTC: over the last 48 hours all 131 records with a spread of 0.5% or more were held, and 980 of 1,133 hold rationales cite the backtest. The paper record therefore stopped growing at 797 fills. This is the intended behaviour given the evidence, and it also means no new evidence is being collected on the corrected signal.

**L3. A recurring blind window each weekday evening.** Because of F6's behaviour, between about 00:00 and 01:45 UTC on weekdays (20:00 to 21:45 New York) the daily bar for the session is not yet published, the agent refuses to anchor, and the whole cycle is logged as an error. That is 66 whole-cycle skips since 2026-09-28, about 7 of the 96 cycles on a weekday; 4 of the 66 were Yahoo returning no bars at all. Nothing is traded on bad data, but the public log shows these as errors, which they are not in spirit. Not yet fixed: it needs either a provisional anchor from the last regular-session hourly bar, clearly labelled, or an explicit "waiting for the official close" state. Either changes live behaviour, so it was left for an explicit decision.

**L4. About 0.5% of symbol records miss their close.** Yahoo's batch download occasionally lacks one ticker; that symbol records an error for the cycle and the others carry on.

**L5. The blend weights are a prior.** 0.5 futures, 0.3 crypto, 0.2 inverted dollar index. A fit on the first two thirds of sessions suggested 0.7, 0, 0.3, which explained the held-out third about 6% better in mean squared error. It was not adopted, because the edge test above says better weights would not create an edge.

**L6. Calendar.** The close is modelled as 16:00 ET every trading day. Full-day 2026 holidays are listed; early closes are not modelled and a closure that is not listed is treated as a trading day (which then skips trading, never trades on an older close).

**L7. Equity is marked at fills.** Between fills it does not move, so intraday drawdown is understated; the page says so. Sharpe uses one equity value per UTC day over a short window and is indicative only.

**L8. Hand-published Desk.** The Desk is deployed by hand with the Vercel CLI, not from git, so code on GitHub can be ahead of what is live.

**L9. Best-effort mirror.** Redis is a mirror. The git files are the source of truth, and the Desk falls back to them if Redis fails.

**L10. Placeholder packages.** `engine/api`, `engine/db` and `engine/events` contain only an empty `__init__.py`. They are leftovers of a layer that was considered and deliberately not built (see [docs/architecture.md](docs/architecture.md), "Deferred, not silently missing").

## 6. What this is not

Not an audit by anyone outside the project. Not evidence of a profitable strategy: the record is a loss of about 1.95% on paper, and the project's own backtest does not support the thesis as a standalone edge. Not investment advice. What it is: a system whose every decision, input and failure is on a public record, with the problems it found in itself written down.
