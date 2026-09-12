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
import paper_ledger  # noqa: E402
from fairvalue.config import RTOKEN_UNIVERSE  # noqa: E402


def _fake_snapshot(underlying, crypto_pcnt, fx_pcnt, futures_pcnt_by_ticker):
    cfg = RTOKEN_UNIVERSE[underlying]
    return {
        "underlying": underlying,
        "rtoken_symbol": cfg["rtoken_symbol"],
        "rtoken_last_price": 100.0,
        "rtoken_pcnt_24h": 0.0,
        "futures_proxy_pcnt_24h": 0.0,
        "crypto_beta_pcnt_24h": 0.0,
        "fx_risk_sentiment_pcnt_24h": 0.0,
        "fair_value_return_24h": 0.0,
        "spread": 0.0,  # below any threshold - every symbol resolves to no-decision
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
    monkeypatch.setattr(agent_loop, "get_crypto_ticks", lambda: {})
    monkeypatch.setattr(agent_loop, "crypto_beta_return", lambda ticks: 0.0)
    monkeypatch.setattr(agent_loop, "fx_risk_sentiment_return", lambda: 0.0)
    monkeypatch.setattr(agent_loop, "_futures_proxy_pcnt_24h", lambda ticker: 0.0)
    monkeypatch.setattr(agent_loop, "build_snapshot", _fake_snapshot)
    yield


def test_each_record_is_written_to_disk_as_soon_as_it_is_finalized(tmp_path):
    # run_once defines its write-and-push step as a local closure called once per
    # record (see test_a_mid_cycle_crash_still_leaves_earlier_records_on_disk for
    # the test that actually proves the "as soon as" part) - here we just confirm
    # the end state matches "one line per record, in the same file".
    records = agent_loop.run_once(dry_run=True, force=True)

    log_files = list(tmp_path.glob("*.jsonl"))
    assert len(log_files) == 1
    lines = log_files[0].read_text().splitlines()
    assert len(lines) == len(records) == len(RTOKEN_UNIVERSE)

    for line, record in zip(lines, records):
        assert json.loads(line)["underlying"] == record["underlying"]


def test_kv_sync_is_pushed_once_per_record_not_once_per_cycle(monkeypatch):
    pushed_batches = []
    monkeypatch.setattr(agent_loop.kv_sync, "push_decision_records", lambda records: pushed_batches.append(records))

    agent_loop.run_once(dry_run=True, force=True)

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
        agent_loop.run_once(dry_run=True, force=True)

    log_files = list(tmp_path.glob("*.jsonl"))
    assert len(log_files) == 1
    lines = log_files[0].read_text().splitlines()
    # the first 3 symbols (before the simulated crash) must already be durable on disk
    assert len(lines) == 3
    logged_symbols = [json.loads(line)["underlying"] for line in lines]
    assert logged_symbols == universe[:3]
