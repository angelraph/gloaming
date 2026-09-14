# Gloaming Desk - AI Trading Desk track submission draft

Copy each section into the corresponding field on the submission form
(https://forms.gle/GyWZCMCPocgJdJon6).

## Track + Sub-theme

**AI Trading Desk** - **Decision Stress Testing** (its own description is
"historical scenario retrieval" - an exact match to the Desk's stress-test
panel, which replays real historical overnight moves, retrieved from the same
~90-day price history the backtest uses, against the current live book).

This is a stronger categorical fit than the "Personalized Research Workbench"
framing an earlier draft of this doc used - that undersold the one feature
that maps onto a named sub-theme almost by name. The chat/narrative and
overnight-timeline features still support the submission narrative even
though they don't drive the sub-theme choice.

## Project description

### Thesis

Traders holding Bitget rToken exposure need a fast, explainable answer to
"what happened to my book overnight and why" - not another black-box
auto-trader deciding for them. Gloaming Desk is a read-only dashboard over
the exact same real data Gloaming Agent (the companion Agentic Trading
submission) produces: a fair-value-vs-actual spread chart, a full overnight
decision timeline with the reasoning behind every signal, a decision stress
test that replays real historical overnight moves against the current book,
and a chat panel that answers follow-up questions grounded only in that real
data. It never places a trade - the human always makes the final call.

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
logged event.

### Progress / build status

Fully built and deployed, live right now at https://gloamingdesk.vercel.app,
reading real-time data from the same source the Agent writes to (Upstash
Redis, synced from the Agent's every cycle, which now runs on real cloud
infrastructure rather than a local machine - see `docs/architecture.md` for
why there is no separate FastAPI/SQLite layer underneath either side).
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
