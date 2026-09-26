# Gloaming Desk - AI Trading Desk track submission draft

Copy each section into the corresponding field on the submission form
(https://forms.gle/GyWZCMCPocgJdJon6).

## Track + Sub-theme

**AI Trading Desk** - **Decision Stress Testing** (its own description is
"historical scenario retrieval" - an exact match to the Desk's stress-test
panel, which replays real historical overnight moves, retrieved from the same
~90-day price history the backtest uses, against the current live book, and
now sits alongside per-symbol research pages and a decision inspector).

This is a stronger categorical fit than the "Personalized Research Workbench"
framing an earlier draft of this doc used - that undersold the one feature
that maps onto a named sub-theme almost by name. The chat/narrative and
overnight-timeline features still support the submission narrative even
though they don't drive the sub-theme choice.

## Project description

### Thesis

Traders holding Bitget rToken exposure need a fast, explainable answer to
"what happened to my book overnight and why" - not another black-box
auto-trader deciding for them. Gloaming Desk is a read-only, multi-page app over
the exact same real data Gloaming Agent (the companion Agentic Trading
submission) produces:

- **Desk**: the live book against each risk cap, a positions table, a spread-vs-
  real-close chart with a text-table alternative, the overnight timeline, a chat
  panel grounded only in the real data, and a stress test that replays real
  historical overnight moves against the current book.
- **A page per symbol** (`/desk/TSLA` and eight more): the rToken against the
  real share's last close, spread history, the position, every recent decision
  with its reasoning, and every paper fill. This is the worked research task
  as a page.
- **Decision inspector**: open any decision to see the market inputs recorded,
  the exact book context the model was shown, its written reasoning, the risk
  layer's verdict and what execution did.
- **Agent, Performance and Method pages**: the loop and its hard limits, a
  paper-trading record derived only from real fills with its method and limits
  stated beside the numbers, and how the signal works, including two failures
  the project found in its own data and fixed in the open.
- **Downloads and verification**: fills and decisions as CSV or JSON, and links
  to the public repository, the per-cycle logs and the unattended run history.

It never places a trade - the human always makes the final call. Built to be
usable by everyone: keyboard navigation, a skip link, chart data available as
tables, modal dialogs with focus trapping, and 44px touch targets.

### Target user & product value

Discretionary traders and portfolio managers holding rToken positions who
start their day needing to reconstruct what moved overnight, across price
action, proxy signals, and any automated activity - normally a manual,
multi-tab exercise. The Desk turns that into one page and one conversation.

### Validation data & key metrics

One complete worked research task, verified line-by-line against the
underlying data rather than taken on faith: asked the Desk's chat "what
happened in the market at night," and cross-checked every figure in its
answer against the real decision log independently.

- Claimed total sell notional across 6 symbols: **$3,771.87** - recomputed
  independently from the raw fill records: **exact match**.
- Claimed AAPL figures (24h return 2.21% -> 2.35%, fair-value estimate
  -0.91% -> -1.04%, spread 3.12% -> 3.39%, futures proxy -1.42% -> -1.47%,
  crypto beta -0.63% -> -1.01%) - checked against the logged snapshot data for
  those exact timestamps: **exact match on every figure**.

Nothing in the chat's answer was invented; every number traced back to a real
logged event. (That check was run on Sept 14 against the decision log as it
stood then; the method is repeatable against the current log.)

A second, structural check: the Performance page reconstructs paper equity
from the ledger's fills alone, and its final figure matches the live portfolio
figure to the cent (verified Sept 25: $98,046.16 from fills, $98,046.16 from the
portfolio endpoint). The Desk's numbers are derived, not asserted, and the
inspector shows the recorded inputs behind any single decision.

Reading the same decision records the Desk displays is also how two real
problems in the underlying data were found: the first signal mostly measured
each session's own move (Sept 25), and a Yahoo data gap made the agent anchor to
Thursday's close on the first Saturday (Sept 26). Both are disclosed in
`docs/architecture.md`, and the second is why `hours_since_close` is shown on
every decision and in the inspector.

### Progress / build status

Fully built and deployed, live right now at https://gloamingdesk.vercel.app,
reading real-time data from the same source the Agent writes to (Upstash
Redis, synced from the Agent's every cycle, which runs on GitHub Actions rather
than a local machine - see `docs/architecture.md` for why there is no separate
FastAPI/SQLite layer underneath either side). Dry runs are structurally
prevented from writing to that mirror, and each live cycle re-asserts the
ledger mirror so a missed push heals itself within 15 minutes.
Public repo: https://github.com/angelraph/gloaming

### Deliverables

- Deployed, working app: https://gloamingdesk.vercel.app
- Source: `gloaming_desk/` (this repo)
- Worked research-task transcript: see "Validation data & key metrics" above
  and the live chat panel itself
- Architecture note: `docs/architecture.md`
- Demo video: [ADD LINK]

### AI trading perspective (optional)

The Desk deliberately narrates rather than recommends specific trade
adjustments - it explains the "why" behind the Agent's real decisions and
lets the stress-test panel show hypothetical outcomes, but the interface
never presents an "execute this" action. That boundary is structural (no
execution code path exists in `gloaming_desk/`), not just a prompt
instruction.

## LLM role disclosure

**Qwen3.8-max** generates the chat panel's narrative answers and the
dashboard's plain-language framing, grounded **only** in the real portfolio
and decision data passed to it as context on every request (current ledger
positions/fills, recent decision records) - it is explicitly instructed
never to invent figures, and independent verification (above) confirms it
doesn't. It never executes trades, never has access to any execution
capability, and never recommends the Desk auto-execute anything - every
decision stays with the human viewing the page.

## Submission materials link

https://github.com/angelraph/gloaming (public repo)
Live app: https://gloamingdesk.vercel.app
