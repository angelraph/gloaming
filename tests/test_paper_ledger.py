"""
Unit tests for gloaming_agent/paper_ledger.py. Every test monkeypatches LEDGER_PATH
to an isolated tmp file so these never touch the real running ledger, and stubs out
kv_sync so a real KV_REST_API_URL/TOKEN in the environment (once configured) never
causes a test run to fire live network calls at production Redis.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "gloaming_agent"))

import paper_ledger  # noqa: E402


@pytest.fixture(autouse=True)
def isolated_ledger(tmp_path, monkeypatch):
    monkeypatch.setattr(paper_ledger, "LEDGER_PATH", tmp_path / "paper_ledger.json")
    # these tests are about position and cash mechanics, so they run cost-free; the cost
    # behavior has its own tests at the end of this file
    monkeypatch.setattr(paper_ledger, "TRADING_COST_RATE", 0.0)
    monkeypatch.setattr(paper_ledger.kv_sync, "push_ledger_state", lambda *a, **kw: None)
    yield


def test_fresh_ledger_starts_at_starting_equity():
    state = paper_ledger.get_portfolio_state(mark_prices={})
    assert state.equity_usd == pytest.approx(paper_ledger.STARTING_EQUITY_USD)
    assert state.positions_notional_usd == {}


def test_buy_fill_reduces_cash_and_opens_position():
    paper_ledger.record_fill("RAAPLUSDT", "buy", qty=10, price=300.0, rationale="test")
    state = paper_ledger._load()
    assert state.cash_usd == pytest.approx(paper_ledger.STARTING_EQUITY_USD - 3000.0)
    assert state.positions["RAAPLUSDT"] == pytest.approx(10.0)


def test_sell_fill_increases_cash_and_opens_short():
    paper_ledger.record_fill("RAAPLUSDT", "sell", qty=5, price=300.0, rationale="test")
    state = paper_ledger._load()
    assert state.cash_usd == pytest.approx(paper_ledger.STARTING_EQUITY_USD + 1500.0)
    assert state.positions["RAAPLUSDT"] == pytest.approx(-5.0)


def test_closing_a_position_removes_it():
    paper_ledger.record_fill("RAAPLUSDT", "buy", qty=10, price=300.0, rationale="open")
    paper_ledger.record_fill("RAAPLUSDT", "sell", qty=10, price=310.0, rationale="close")
    state = paper_ledger._load()
    assert "RAAPLUSDT" not in state.positions


def test_closing_a_position_at_a_profit_increases_equity():
    paper_ledger.record_fill("RAAPLUSDT", "buy", qty=10, price=300.0, rationale="open")
    paper_ledger.record_fill("RAAPLUSDT", "sell", qty=10, price=310.0, rationale="close")
    state = paper_ledger.get_portfolio_state(mark_prices={})
    # bought 10 @ 300 (-3000 cash), sold 10 @ 310 (+3100 cash) -> net +100 vs starting
    assert state.equity_usd == pytest.approx(paper_ledger.STARTING_EQUITY_USD + 100.0)


def test_get_portfolio_state_marks_open_position_to_live_price():
    paper_ledger.record_fill("RAAPLUSDT", "buy", qty=10, price=300.0, rationale="test")
    state = paper_ledger.get_portfolio_state(mark_prices={"RAAPLUSDT": 320.0})
    assert state.positions_notional_usd["RAAPLUSDT"] == pytest.approx(3200.0)
    # cash after buy: 100,000 - 3,000 = 97,000; + mark-to-market 3,200 = 100,200
    assert state.equity_usd == pytest.approx(97_000.0 + 3_200.0)


def test_get_portfolio_state_falls_back_to_last_fill_price_when_no_mark_given():
    paper_ledger.record_fill("RAAPLUSDT", "buy", qty=10, price=300.0, rationale="test")
    state = paper_ledger.get_portfolio_state(mark_prices={})  # no live price supplied
    assert state.positions_notional_usd["RAAPLUSDT"] == pytest.approx(3000.0)


def test_invalid_side_raises():
    with pytest.raises(ValueError):
        paper_ledger.record_fill("RAAPLUSDT", "hold", qty=1, price=300.0, rationale="bad")


def test_nonpositive_qty_or_price_raises():
    with pytest.raises(ValueError):
        paper_ledger.record_fill("RAAPLUSDT", "buy", qty=0, price=300.0, rationale="bad")
    with pytest.raises(ValueError):
        paper_ledger.record_fill("RAAPLUSDT", "buy", qty=1, price=0, rationale="bad")


def test_daily_baseline_resets_on_new_day(monkeypatch):
    import datetime as dt

    paper_ledger.record_fill("RAAPLUSDT", "buy", qty=10, price=300.0, rationale="day1")

    class FrozenDatetime(dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return dt.datetime(2026, 1, 1, tzinfo=tz)

    monkeypatch.setattr(paper_ledger, "datetime", FrozenDatetime)
    paper_ledger.get_portfolio_state(mark_prices={"RAAPLUSDT": 300.0})
    assert paper_ledger._load().day_start_date == "2026-01-01"

    class FrozenDatetimeNextDay(dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return dt.datetime(2026, 1, 2, tzinfo=tz)

    monkeypatch.setattr(paper_ledger, "datetime", FrozenDatetimeNextDay)
    # First call of the new day establishes the new baseline - daily P&L is
    # correctly 0 at that exact instant, same as it was at day1's own start.
    state2_at_open = paper_ledger.get_portfolio_state(mark_prices={"RAAPLUSDT": 300.0})
    day2_state = paper_ledger._load()
    assert day2_state.day_start_date == "2026-01-02"  # the rollover actually happened
    assert state2_at_open.daily_realized_pnl_usd == pytest.approx(0.0)

    # A price move later the SAME day should move daily P&L away from zero,
    # measured against day2's own baseline - not day1's.
    state2_after_move = paper_ledger.get_portfolio_state(mark_prices={"RAAPLUSDT": 350.0})
    assert state2_after_move.daily_realized_pnl_usd == pytest.approx(10 * (350.0 - 300.0))


# --- trading costs ---

def test_each_fill_charges_fee_and_slippage_against_cash_and_records_the_cost(monkeypatch):
    monkeypatch.setattr(paper_ledger, "TRADING_COST_RATE", paper_ledger.FEE_RATE + paper_ledger.SLIPPAGE_RATE)
    fill = paper_ledger.record_fill("RAAPLUSDT", "buy", qty=10, price=300.0, rationale="cost test")
    assert fill.cost_usd == pytest.approx(3000.0 * 0.0015)  # $4.50
    state = paper_ledger._load()
    assert state.cash_usd == pytest.approx(100_000.0 - 3000.0 - 4.5)
    assert state.fills[-1]["cost_usd"] == pytest.approx(4.5)


def test_a_round_trip_at_an_unchanged_price_loses_the_cost_of_both_legs(monkeypatch):
    monkeypatch.setattr(paper_ledger, "TRADING_COST_RATE", paper_ledger.FEE_RATE + paper_ledger.SLIPPAGE_RATE)
    paper_ledger.record_fill("RAAPLUSDT", "buy", qty=10, price=300.0, rationale="open")
    paper_ledger.record_fill("RAAPLUSDT", "sell", qty=10, price=300.0, rationale="close")
    state = paper_ledger._load()
    assert state.positions == {}
    assert state.cash_usd == pytest.approx(100_000.0 - 2 * 4.5)


def test_the_stated_cost_assumption_is_ten_bps_fee_plus_five_bps_slippage():
    assert paper_ledger.FEE_RATE == pytest.approx(0.0010)
    assert paper_ledger.SLIPPAGE_RATE == pytest.approx(0.0005)
