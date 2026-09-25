"""
The window arithmetic behind the since-close signal, plus how build_snapshot and the
cycle behave when data is missing. Pure functions over hand-built price series, so no
network: the point is to prove every input is measured over the SAME window (from the
real share's last close), which the previous version did not do.
"""
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "gloaming_agent"))

import agent_loop  # noqa: E402  (also puts engine/ on sys.path)
from data.overnight_anchor import (  # noqa: E402
    OvernightAnchor,
    daily_volatility,
    last_completed_session,
    return_since,
    session_close_utc,
)

UTC = timezone.utc


def _hourly(start, closes):
    """Hourly bars indexed by bar START (UTC), the layout return_since expects."""
    idx = pd.date_range(start=start, periods=len(closes), freq="h", tz="UTC")
    return pd.Series(closes, index=idx, dtype=float)


# --- the session close ---

def test_session_close_is_1600_eastern_expressed_in_utc():
    # September is daylight time, so 16:00 ET is 20:00 UTC; in winter it is 21:00 UTC
    assert session_close_utc(date(2026, 9, 25)) == datetime(2026, 9, 25, 20, 0, tzinfo=UTC)
    assert session_close_utc(date(2026, 12, 15)) == datetime(2026, 12, 15, 21, 0, tzinfo=UTC)


def test_a_session_still_in_progress_is_never_the_anchor():
    dates = [date(2026, 9, 24), date(2026, 9, 25)]
    during_friday = datetime(2026, 9, 25, 15, 0, tzinfo=UTC)  # 11:00 ET, Friday's session is open
    assert last_completed_session(dates, during_friday) == date(2026, 9, 24)


def test_after_the_close_the_same_days_session_is_the_anchor():
    dates = [date(2026, 9, 24), date(2026, 9, 25)]
    assert last_completed_session(dates, datetime(2026, 9, 25, 20, 30, tzinfo=UTC)) == date(2026, 9, 25)


def test_over_a_weekend_the_anchor_stays_fridays_close():
    dates = [date(2026, 9, 24), date(2026, 9, 25)]
    assert last_completed_session(dates, datetime(2026, 9, 27, 12, 0, tzinfo=UTC)) == date(2026, 9, 25)


def test_no_completed_session_gives_none_not_a_guess():
    assert last_completed_session([date(2026, 9, 25)], datetime(2026, 9, 25, 15, 0, tzinfo=UTC)) is None


# --- return since the close ---

def test_return_is_measured_from_the_price_at_the_close_to_the_latest_price():
    # bars start 15:00, 16:00, 17:00, 18:00 UTC-equivalent hours; close at the end of the second
    prices = _hourly("2026-09-25 19:00", [100.0, 101.0, 103.0, 104.0])
    close = datetime(2026, 9, 25, 21, 0, tzinfo=UTC)  # the 20:00-21:00 bar (2nd) has just ended
    assert return_since(prices, close) == pytest.approx(104.0 / 101.0 - 1)


def test_a_bar_that_has_not_ended_by_the_close_is_not_used_as_the_base():
    prices = _hourly("2026-09-25 19:00", [100.0, 101.0, 103.0])
    close = datetime(2026, 9, 25, 20, 30, tzinfo=UTC)  # mid-way through the 2nd bar
    assert return_since(prices, close) == pytest.approx(103.0 / 100.0 - 1)  # base is the 1st bar's close


def test_no_bar_before_the_close_gives_none_not_zero():
    prices = _hourly("2026-09-25 22:00", [100.0, 101.0])
    assert return_since(prices, datetime(2026, 9, 25, 20, 0, tzinfo=UTC)) is None


def test_a_base_bar_far_from_the_close_means_a_data_gap_and_gives_none():
    prices = pd.concat([_hourly("2026-09-24 00:00", [100.0, 101.0]), _hourly("2026-09-25 22:00", [102.0])])
    assert return_since(prices, datetime(2026, 9, 25, 20, 0, tzinfo=UTC)) is None


def test_a_closed_market_simply_has_no_newer_bars():
    # futures over a weekend: the last bar is Friday's, so the return ends there
    prices = _hourly("2026-09-25 19:00", [100.0, 100.5, 100.8])
    monday = datetime(2026, 9, 25, 21, 0, tzinfo=UTC)
    assert return_since(prices, monday) == pytest.approx(100.8 / 100.5 - 1)


def test_naive_and_non_utc_indexes_are_handled():
    eastern = pd.Series([100.0, 102.0], index=pd.date_range("2026-09-25 15:00", periods=2, freq="h", tz="America/New_York"))
    assert return_since(eastern, datetime(2026, 9, 25, 20, 0, tzinfo=UTC)) == pytest.approx(0.02)


# --- realized volatility ---

def test_daily_volatility_needs_enough_observations():
    closes = pd.Series([100.0, 101.0, 102.0], index=pd.to_datetime(["2026-09-22", "2026-09-23", "2026-09-24"]))
    assert daily_volatility(closes, date(2026, 9, 24)) is None


def test_daily_volatility_ignores_days_after_the_anchor_session():
    idx = pd.to_datetime([f"2026-09-{d}" for d in range(15, 26)])
    closes = pd.Series([100, 101, 99, 102, 100, 101, 100, 102, 99, 101, 150], index=idx, dtype=float)
    with_spike = daily_volatility(closes, date(2026, 9, 25))
    without = daily_volatility(closes, date(2026, 9, 24))
    assert without < with_spike


# --- build_snapshot ---

def _anchor(**overrides):
    base = dict(
        session_date=date(2026, 9, 25),
        session_close_utc=datetime(2026, 9, 25, 20, 0, tzinfo=UTC),
        fetched_at_utc=datetime(2026, 9, 25, 21, 30, tzinfo=UTC),
        close_prices={"META": 751.66},
        daily_volatility={"META": 0.02},
        futures_return={"NQ=F": 0.001},
        crypto_return=-0.002,
        fx_return=-0.0003,
        missing=[],
    )
    base.update(overrides)
    return OvernightAnchor(**base)


@pytest.fixture
def rtoken_price(monkeypatch):
    def _set(price):
        monkeypatch.setattr(
            agent_loop, "_get_rtoken_tick_with_pcnt",
            lambda symbol: {"symbol": symbol, "last_price": price, "pcnt_change_24h": -0.0337},
        )
    return _set


def test_spread_is_the_rtoken_move_since_the_close_minus_the_proxy_blend_since_the_close(rtoken_price):
    rtoken_price(749.68)  # META on Sept 25: the rToken closed $2 under the real share, not 4.6% under fair value
    snap = agent_loop.build_snapshot("META", _anchor())
    expected_rtoken = 749.68 / 751.66 - 1
    expected_fair = 0.001 * 0.5 + (-0.002) * 0.3 + (-0.0003) * 0.2
    assert snap["rtoken_return_since_close"] == pytest.approx(expected_rtoken)
    assert snap["fair_value_return_since_close"] == pytest.approx(expected_fair)
    assert snap["spread"] == pytest.approx(expected_rtoken - expected_fair)
    assert abs(snap["spread"]) < 0.005  # the real overnight dislocation is tenths of a percent


def test_the_days_own_move_no_longer_shows_up_as_spread(rtoken_price):
    # the rToken fell 3.37% over 24h because the real share did; against the close it is flat
    rtoken_price(751.66)
    snap = agent_loop.build_snapshot("META", _anchor())
    assert snap["rtoken_pcnt_24h"] == pytest.approx(-0.0337)  # kept, for context only
    assert abs(snap["spread"]) < 0.001


def test_snapshot_records_which_specification_produced_it_and_the_anchor(rtoken_price):
    rtoken_price(752.0)
    snap = agent_loop.build_snapshot("META", _anchor())
    assert snap["signal_spec"] == "since_last_close_v2"
    assert snap["real_close_price"] == pytest.approx(751.66)
    assert snap["real_close_time"].startswith("2026-09-25T20:00")
    assert snap["hours_since_close"] == pytest.approx(1.5)
    assert snap["fair_value_price"] == pytest.approx(751.66 * (1 + snap["fair_value_return_since_close"]))
    assert snap["recent_daily_volatility"] == pytest.approx(0.02)


def test_a_missing_proxy_contributes_nothing_and_is_recorded(rtoken_price):
    rtoken_price(751.66)
    anchor = _anchor(futures_return={"NQ=F": None}, missing=["futures:NQ=F", "fx_risk_sentiment"], fx_return=None)
    snap = agent_loop.build_snapshot("META", anchor)
    assert snap["futures_proxy_return_since_close"] is None
    assert snap["fair_value_return_since_close"] == pytest.approx((-0.002) * 0.3)  # only crypto counted
    assert set(snap["missing_proxies"]) == {"futures:NQ=F", "fx_risk_sentiment"}


def test_a_symbol_with_no_close_on_the_anchor_session_gets_no_snapshot(rtoken_price):
    rtoken_price(100.0)
    with pytest.raises(ValueError, match="no real-share close"):
        agent_loop.build_snapshot("AAPL", _anchor())  # the anchor only has META


# --- the whole cycle when the anchor cannot be established ---

def test_no_anchor_means_no_decisions_and_an_error_per_symbol_never_a_trade(monkeypatch, tmp_path):
    import paper_ledger
    from fairvalue.config import RTOKEN_UNIVERSE

    monkeypatch.setattr(agent_loop, "DECISION_LOG_DIR", tmp_path)
    monkeypatch.setattr(paper_ledger, "LEDGER_PATH", tmp_path / "paper_ledger.json")
    monkeypatch.setattr(paper_ledger.kv_sync, "push_ledger_state", lambda *a, **kw: None)
    monkeypatch.setattr(agent_loop.kv_sync, "push_decision_records", lambda records: None)
    monkeypatch.setattr(agent_loop, "is_nyse_closed", lambda: True)
    monkeypatch.setattr(agent_loop.bitget_signal, "get_signal_context", lambda: None)

    def unavailable(underlyings, futures_tickers):
        raise RuntimeError("Yahoo unreachable")

    monkeypatch.setattr(agent_loop, "fetch_overnight_anchor", unavailable)
    records = agent_loop.run_once(dry_run=False, force=True)

    assert len(records) == len(RTOKEN_UNIVERSE)
    assert all("real-close anchor unavailable" in r["error"] for r in records)
    assert not any(r.get("decision") for r in records)
    assert paper_ledger._load().fills == []
