# Gloaming Desk

The AI Trading Desk track submission: a read-only research dashboard over the
real data the Gloaming Agent produces overnight. Never places a trade - it
explains what happened and why, and the human decides.

## What it reads

No separate database or FastAPI layer. The API routes (`app/api/*`) read
directly from the same files `gloaming_agent/agent_loop.py` writes:

- `gloaming_agent/decision_log/*.jsonl` - the full event -> decision ->
  execution trail, one line per symbol per cycle
- `gloaming_agent/paper_ledger.json` - current cash, positions, and fills

See `../docs/architecture.md` for why this is simpler than standing up a
second service to re-serve data that already exists in real, verified form.

## What's on the page

- Equity, cash, today's P&L, and fill count, computed from the real ledger
- A bar chart of the latest fair-value spread per symbol
- An overnight timeline of every real decision, tagged with its source
  (`qwen3.8-max` or the rule-based fallback) and full rationale text
- A chat panel that answers questions about the real portfolio/decision data
  via Qwen3.8-max, grounded only in what's on the page - never invents numbers,
  never executes anything

## Run it

```bash
npm install
npm run dev
```

Needs the repo-root `.env` (`QWEN_API_KEY` etc.) to exist - `next.config.ts`
loads it directly rather than duplicating it into a second `.env.local`.
