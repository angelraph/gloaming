"""
Unit tests for the incremental write/push behavior added to agent_loop.run_once()
on Sept 12: each record is written to disk and pushed to Redis the moment it is
finalized, instead of the whole cycle's records being batched until the end.

Added after confirming live that this machine can stall for hours mid-cycle
(Windows power management suspending the process, correlating exactly with
lid-close events in the system power log every time it happened) - the old
batch-at-the-end write meant a cycle cut short lost every record it had already
computed. These tests verify the new behavior at the unit level, fully isolated
from the real ledger, log directory, and network (Redis, market data, Qwen).
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "gloaming_agent"))

import agent_loop  # noqa: E402
import kv_sync  # noqa: E402
import paper_ledger  # noqa: E402

# The real functions, captured before the autouse fixture stubs them, so the dry-run guard
# test below can exercise the real write path.
_REAL_PUSH_RECORDS = kv_sync.push_decision_records
_REAL_PUSH_LEDGER = kv_sync.push_ledger_state
from fairvalue.config import RTOKEN_UNIVERSE  # noqa: E402


def _fake_snapshot(underlying, anchor, bitget_signal_context=None):
    cfg = RTOKEN_UNIVERSE[underlying]
    return {
        "underlying": underlying,
        "rtoken_symbol": cfg["rtoken_symbol"],
        "rtoken_last_price": 100.0,
        "signal_spec": "since_last_close_v2",
        "real_close_price": 100.0,
        "real_close_time": "2026-09-25T20:00:00+00:00",
        "hours_since_close": 1.0,
        "rtoken_return_since_close": 0.0,
        "rtoken_pcnt_24h": 0.0,
        "futures_proxy_return_since_close": 0.0,
        "crypto_beta_return_since_close": 0.0,
        "fx_risk_sentiment_return_since_close": 0.0,
        "fair_value_return_since_close": 0.0,
        "fair_value_price": 100.0,
        "spread": 0.0,  # below any threshold - every symbol resolves to no-decision
        "recent_daily_volatility": 0.02,
        "missing_proxies": [],
        "bitget_signal_context": bitget_signal_context,
    }


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    # Every network-capable dependency is stubbed here, unconditionally, for every
    # test in this file - added after an early version of this file briefly pushed
    # 9 placeholder ($100 flat price) records to the real production Redis log by
    # only mocking kv_sync in one test instead of in this shared autouse fixture.
    # decide_llm() calls Qwen regardless of spread size (it can decide "hold"),
    # so a snapshot's spread value alone does not stop it from reaching the network.
    monkeypatch.setattr(agent_loop, "DECISION_LOG_DIR", tmp_path)
    monkeypatch.setattr(paper_ledger, "LEDGER_PATH", tmp_path / "paper_ledger.json")
    monkeypatch.setattr(paper_ledger.kv_sync, "push_ledger_state", lambda *a, **kw: None)
    monkeypatch.setattr(agent_loop.kv_sync, "push_decision_records", lambda records: None)
    monkeypatch.setattr(agent_loop.llm_client, "is_configured", lambda: False)
    monkeypatch.setattr(agent_loop, "is_nyse_closed", lambda: True)
    monkeypatch.setattr(agent_loop, "fetch_overnight_anchor", lambda underlyings, futures_tickers: object())
    monkeypatch.setattr(agent_loop.bitget_signal, "get_signal_context", lambda: None)
    monkeypatch.setattr(agent_loop, "build_snapshot", _fake_snapshot)
    yield


def test_each_record_is_written_to_disk_as_soon_as_it_is_finalized(tmp_path):
    # run_once defines its write-and-push step as a local closure called once per
    # record (see test_a_mid_cycle_crash_still_leaves_earlier_records_on_disk for
    # the test that actually proves the "as soon as" part) - here we just confirm
    # the end state matches "one line per record, in the same file".
    records = agent_loop.run_once(dry_run=False, force=True)  # spread 0: no trade, so nothing fills

    log_files = list(tmp_path.glob("*.jsonl"))
    assert len(log_files) == 1
    lines = log_files[0].read_text().splitlines()
    assert len(lines) == len(records) == len(RTOKEN_UNIVERSE)

    for line, record in zip(lines, records):
        assert json.loads(line)["underlying"] == record["underlying"]


def test_kv_sync_is_pushed_once_per_record_not_once_per_cycle(monkeypatch):
    pushed_batches = []
    monkeypatch.setattr(agent_loop.kv_sync, "push_decision_records", lambda records: pushed_batches.append(records))

    agent_loop.run_once(dry_run=False, force=True)

    assert len(pushed_batches) == len(RTOKEN_UNIVERSE)
    assert all(len(batch) == 1 for batch in pushed_batches)


def test_a_mid_cycle_crash_still_leaves_earlier_records_on_disk(monkeypatch, tmp_path):
    """Simulates the real failure mode this change fixes: something kills the
    process partway through the universe loop. Records for symbols already
    processed must already be safely on disk, not held in memory awaiting a
    final batch write that never happens."""
    universe = list(RTOKEN_UNIVERSE)
    real_decide = agent_loop.decide

    def _crash_partway(snapshot):
        if snapshot["underlying"] == universe[3]:
            raise KeyboardInterrupt("simulated hard interruption mid-cycle")
        return real_decide(snapshot)

    monkeypatch.setattr(agent_loop, "decide", _crash_partway)

    with pytest.raises(KeyboardInterrupt):
        agent_loop.run_once(dry_run=False, force=True)

    log_files = list(tmp_path.glob("*.jsonl"))
    assert len(log_files) == 1
    lines = log_files[0].read_text().splitlines()
    # the first 3 symbols (before the simulated crash) must already be durable on disk
    assert len(lines) == 3
    logged_symbols = [json.loads(line)["underlying"] for line in lines]
    assert logged_symbols == universe[:3]


def _arm_redis_spy(monkeypatch):
    """Real kv_sync write functions, configured with fake credentials, over a spy in place of
    the network. Returns the list of every request that would have left the process."""
    calls = []
    monkeypatch.setenv("KV_REST_API_URL", "https://example.invalid")
    monkeypatch.setenv("KV_REST_API_TOKEN", "test-token")
    monkeypatch.setattr(kv_sync, "_disabled", False)
    monkeypatch.setattr(kv_sync, "push_decision_records", _REAL_PUSH_RECORDS)
    monkeypatch.setattr(kv_sync, "push_ledger_state", _REAL_PUSH_LEDGER)

    class _Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"result": "OK"}

    monkeypatch.setattr(kv_sync.requests, "post", lambda *a, **kw: calls.append((a, kw)) or _Resp())
    return calls


def test_a_dry_run_never_writes_to_redis_even_with_credentials_configured(monkeypatch, tmp_path):
    # Regression for Sept 25: a local dry run with production KV credentials in .env pushed a
    # stale ledger and its own records over the live ones.
    calls = _arm_redis_spy(monkeypatch)

    agent_loop.run_once(dry_run=True, force=True)
    paper_ledger.record_fill("RAAPLUSDT", "buy", 1.0, 100.0, "dry-run guard test")  # any ledger save

    assert calls == []
    # and its records went to the git-ignored dry_run folder, not the committed log
    assert list(tmp_path.glob("*.jsonl")) == []
    assert len(list((tmp_path / "dry_run").glob("*.jsonl"))) == 1


def test_a_real_run_still_mirrors_to_redis(monkeypatch):
    calls = _arm_redis_spy(monkeypatch)

    agent_loop.run_once(dry_run=False, force=True)

    assert len(calls) >= len(RTOKEN_UNIVERSE)  # one RPUSH per record, plus the LTRIMs


def test_sync_mirror_pushes_the_local_ledger_unchanged(monkeypatch):
    calls = _arm_redis_spy(monkeypatch)
    paper_ledger.record_fill("RAAPLUSDT", "buy", 1.0, 100.0, "seed")
    calls.clear()

    paper_ledger.sync_mirror()

    assert len(calls) == 1
    args = calls[0][1]["json"]
    assert args[0] == "SET" and args[1] == kv_sync.LEDGER_KEY
    assert json.loads(args[2])["positions"]["RAAPLUSDT"] == 1.0
