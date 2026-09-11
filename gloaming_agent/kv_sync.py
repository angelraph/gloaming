"""
Mirrors the Agent's real decision records and paper-ledger state to Upstash Redis
(via Vercel's KV storage integration, created Sept 11) so the deployed Gloaming
Desk on Vercel - which has no access to this machine's local filesystem - shows
the same live data the local dashboard shows, instead of "not available."

Local files (decision_log/*.jsonl, paper_ledger.json) remain the source of truth
and are always written first; this is a best-effort mirror on top. Every function
here is wrapped so a network hiccup can never break the Agent's actual trading
loop - same graceful-degradation pattern as execution.py and llm_client.py: no
KV_REST_API_URL/TOKEN configured means these functions silently no-op, not raise.

Uses Upstash's plain REST command API directly (POST the base URL with a JSON
array body, e.g. ["SET", "key", "value"]) rather than an SDK - one dependency
(requests, already used elsewhere) instead of a new one, for four call sites.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import requests
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(REPO_ROOT / ".env")

DECISION_LOG_KEY = "gloaming:decision_log"
LEDGER_KEY = "gloaming:paper_ledger"
HISTORICAL_SCENARIOS_KEY = "gloaming:historical_scenarios"
MAX_DECISION_LOG_ENTRIES = 500  # bounds Redis memory; local .jsonl keeps full history


def is_configured() -> bool:
    return bool(os.environ.get("KV_REST_API_URL") and os.environ.get("KV_REST_API_TOKEN"))


def _command(*args) -> dict | None:
    """Runs one Upstash REST command. Returns None (never raises) on any
    failure - network issues here must never break the Agent's trading loop."""
    if not is_configured():
        return None
    url = os.environ["KV_REST_API_URL"]
    token = os.environ["KV_REST_API_TOKEN"]
    try:
        resp = requests.post(
            url, headers={"Authorization": f"Bearer {token}"}, json=list(args), timeout=10
        )
        resp.raise_for_status()
        return resp.json()
    except Exception:  # noqa: BLE001 - deliberately broad: this is a best-effort mirror
        return None


def push_decision_records(records: list[dict]) -> None:
    """Appends this cycle's records to a bounded Redis list, newest last -
    mirrors decision_log/*.jsonl's append-only shape."""
    if not records:
        return
    for record in records:
        _command("RPUSH", DECISION_LOG_KEY, json.dumps(record, default=str))
    _command("LTRIM", DECISION_LOG_KEY, -MAX_DECISION_LOG_ENTRIES, -1)


def push_ledger_state(ledger_dict: dict) -> None:
    """Overwrites the single ledger snapshot key - the ledger is a point-in-time
    state (cash/positions/fills), not an append log, so SET (not RPUSH) is
    correct here, called every time the local paper_ledger.json is saved."""
    _command("SET", LEDGER_KEY, json.dumps(ledger_dict, default=str))


def push_historical_scenarios(scenarios: dict) -> None:
    """Overwrites the historical-scenarios snapshot - unlike the decision log and
    ledger, this only changes when engine/backtest/run_backtest.py is re-run
    (roughly static day to day), so it's pushed once at the end of that script
    rather than every Agent cycle."""
    _command("SET", HISTORICAL_SCENARIOS_KEY, json.dumps(scenarios, default=str))


if __name__ == "__main__":
    import sys

    if "--smoke-test" in sys.argv:
        if not is_configured():
            print("NOT CONFIGURED (expected until KV_REST_API_URL/TOKEN are in .env): "
                  "copy them from Vercel's Storage tab.")
            sys.exit(0)
        print("KV configured - pushing a test record...")
        push_decision_records([{"underlying": "TEST", "note": "kv_sync smoke test"}])
        result = _command("LRANGE", DECISION_LOG_KEY, -1, -1)
        print("Read back:", result)
        assert result and result.get("result"), f"smoke test push/read failed: {result}"
        print("OK - Upstash Redis reachable, write and read both verified.")
    else:
        print("Usage: python kv_sync.py --smoke-test")
