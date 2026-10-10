# Agent instructions

- Gloaming is a Bitget rToken overnight trading agent (`gloaming_agent/`, Python), a shared engine (`engine/`) and a read-only Next.js desk (`gloaming_desk/`). It is **paper trading only**: fills are ledger entries in `gloaming_agent/paper_ledger.py`. There is no real-money order path, and none may be added without an explicit request. The one exchange leg is opt-in (GLOAMING_EXCHANGE_ORDERS=demo), goes to Bitget's demo engine on the stock perpetuals through a wrapper that hardcodes --paper-trading, and is off by default.
- Never read or print `.env` or `.env.local`, and never commit them. Secrets live in GitHub Actions secrets and the Vercel project.
- Production is the GitHub Actions workflow `.github/workflows/agent_loop.yml`, triggered every 15 minutes by an external cron. Each cycle commits `paper_ledger.json`, `decision_log/*.jsonl` and `fill_verification.json` to `master`, so always `git pull --rebase` before pushing.
- `paper_ledger.json` and `decision_log/` are the public record. Never edit or delete them by hand. A bad record is flagged in the code or the docs, not removed.
- Local runs: `python gloaming_agent/agent_loop.py --smoke-test` is a dry run. It writes nothing to Redis and logs to the git-ignored `decision_log/dry_run/`. Do not run a non-dry cycle locally.
- The Desk is published by hand with the Vercel CLI, not from git. Code on GitHub can be ahead of what is live.
- The system prompt cites backtest figures. A test ties them to `alpha_factory/results/since_close_backtest.json`: regenerate both together (`python -m backtest.fetch_hourly && python -m backtest.since_close_backtest` from `engine/`).
- Live trading behaviour (the prompt, `risk_controls.py`, the signal, fees) changes only after the owner has been told how it will change the trading.
- Facts live in [README.md](README.md), [docs/architecture.md](docs/architecture.md), [docs/risk_controls.md](docs/risk_controls.md), [SUBMISSION.md](SUBMISSION.md) and [AUDIT.md](AUDIT.md).
- Checks: `python -m pytest tests/`; `cd gloaming_desk && npx next typegen && npx tsc --noEmit && npm run build` (`typegen` first, because Next generates the `PageProps` and `LayoutProps` types and `tsc` fails on a clean checkout without them).
- Copy style: no em dashes, ever (use a comma, a colon, a hyphen with spaces or two sentences). Say "paper trading". Label figures observed, estimated or targeted, and never state a result the record does not show.
