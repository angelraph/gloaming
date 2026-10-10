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
    AnchorUnavailable,
    OvernightAnchor,
    daily_volatility,
    expected_last_session,
    fetch_equity_closes,
    last_completed_session,
    last_regular_minute_close,
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


# --- the anchor comes from the calendar, and the data must prove it has that day ---

def test_expected_session_is_fridays_all_weekend_and_from_the_close_onward():
    fri = date(2026, 9, 25)
    assert expected_last_session(datetime(2026, 9, 25, 20, 1, tzinfo=UTC)) == fri
    assert expected_last_session(datetime(2026, 9, 26, 0, 30, tzinfo=UTC)) == fri  # the Sept 26 failure window
    assert expected_last_session(datetime(2026, 9, 27, 23, 0, tzinfo=UTC)) == fri
    assert expected_last_session(datetime(2026, 9, 25, 15, 0, tzinfo=UTC)) == date(2026, 9, 24)  # session still open


def test_expected_session_skips_a_holiday():
    # Monday Sept 7, 2026 is Labor Day: Tuesday evening's anchor is Friday Sept 4
    assert expected_last_session(datetime(2026, 9, 7, 23, 0, tzinfo=UTC)) == date(2026, 9, 4)


def _minute_series(session, last_minute="15:59", price=110.0, first_minute="15:30"):
    """1-minute closes for one session in New York time, from first_minute to last_minute."""
    start = pd.Timestamp(f"{session} {first_minute}", tz="America/New_York")
    end = pd.Timestamp(f"{session} {last_minute}", tz="America/New_York")
    idx = pd.date_range(start, end, freq="min")
    return pd.Series(price, index=idx, dtype=float)


def _fake_yahoo(monkeypatch, daily_dates, minutes=None, daily_missing=()):
    """Stubs yfinance.download. Daily calls return `daily_dates` (value 100.0) for SPY and META,
    with the (ticker, date) pairs in `daily_missing` dropped. 1-minute calls return the series
    in `minutes` ({ticker: Series}), or nothing. Returns the list of intervals requested."""
    import yfinance

    calls = []
    idx = pd.to_datetime([str(d) for d in daily_dates])
    daily = pd.DataFrame(100.0, index=idx, columns=pd.MultiIndex.from_product([["SPY", "META"], ["Close"]]))
    for t, d in daily_missing:
        daily.loc[pd.Timestamp(str(d)), (t, "Close")] = float("nan")

    def download(tickers, period=None, interval=None, **kw):
        calls.append(interval)
        if interval == "1d":
            return daily
        if not minutes:
            return pd.DataFrame()
        frame = pd.concat({t: pd.DataFrame({"Close": s}) for t, s in minutes.items()}, axis=1)
        return frame

    monkeypatch.setattr(yfinance, "download", download)
    return calls


def test_a_missing_fridays_bar_and_no_minute_bar_refuses_to_anchor_to_thursday(monkeypatch):
    # Regression for Sept 26 00:00-01:40 UTC: Yahoo had not yet published Friday's daily bar,
    # the newest bar was Thursday's, and the agent priced every symbol against Thursday's close.
    _fake_yahoo(monkeypatch, [date(2026, 9, 23), date(2026, 9, 24)])
    with pytest.raises(AnchorUnavailable):
        fetch_equity_closes(["META"], datetime(2026, 9, 26, 0, 30, tzinfo=UTC))


def test_with_fridays_bar_present_the_anchor_is_friday_and_no_minute_data_is_fetched(monkeypatch):
    calls = _fake_yahoo(monkeypatch, [date(2026, 9, 24), date(2026, 9, 25)])
    session, closes, _, sources = fetch_equity_closes(["META"], datetime(2026, 9, 26, 0, 30, tzinfo=UTC))
    assert session == date(2026, 9, 25) and closes == {"META": 100.0}
    assert sources == {"META": "official_daily"}
    assert calls == ["1d"]  # nothing extra is requested while the official bar exists


def test_before_the_daily_bar_lands_the_last_minute_bar_of_the_same_session_is_used_and_labelled(monkeypatch):
    friday = date(2026, 9, 25)
    _fake_yahoo(monkeypatch, [date(2026, 9, 23), date(2026, 9, 24)],
                minutes={"SPY": _minute_series(friday, price=500.0), "META": _minute_series(friday, price=110.0)})
    session, closes, _, sources = fetch_equity_closes(["META"], datetime(2026, 9, 26, 0, 30, tzinfo=UTC))
    assert session == friday
    assert closes == {"META": 110.0}
    assert sources == {"META": "provisional_1m"}


def test_a_minute_bar_from_an_older_session_is_never_used(monkeypatch):
    thursday = date(2026, 9, 24)
    _fake_yahoo(monkeypatch, [date(2026, 9, 23), date(2026, 9, 24)],
                minutes={"SPY": _minute_series(thursday), "META": _minute_series(thursday)})
    with pytest.raises(AnchorUnavailable):
        fetch_equity_closes(["META"], datetime(2026, 9, 26, 0, 30, tzinfo=UTC))


def test_a_minute_series_that_stops_before_the_end_of_the_session_is_refused(monkeypatch):
    friday = date(2026, 9, 25)
    partial = _minute_series(friday, last_minute="13:10", first_minute="12:00")
    _fake_yahoo(monkeypatch, [date(2026, 9, 24)], minutes={"SPY": partial, "META": partial})
    with pytest.raises(AnchorUnavailable):
        fetch_equity_closes(["META"], datetime(2026, 9, 26, 0, 30, tzinfo=UTC))


def test_one_symbol_missing_its_official_close_falls_back_to_its_own_minute_bar(monkeypatch):
    friday = date(2026, 9, 25)
    _fake_yahoo(monkeypatch, [date(2026, 9, 24), friday], daily_missing=[("META", friday)],
                minutes={"META": _minute_series(friday, price=123.0)})
    session, closes, _, sources = fetch_equity_closes(["META"], datetime(2026, 9, 26, 0, 30, tzinfo=UTC))
    assert closes == {"META": 123.0}
    assert sources == {"META": "provisional_1m"}


def test_the_minute_close_ignores_after_hours_bars_and_a_utc_index():
    friday = date(2026, 9, 25)
    regular = _minute_series(friday, last_minute="15:59", price=110.0)
    after_hours = _minute_series(friday, last_minute="16:20", first_minute="16:00", price=999.0)
    s = pd.concat([regular, after_hours])
    s.index = s.index.tz_convert("UTC")
    assert last_regular_minute_close(s, friday) == 110.0
    assert last_regular_minute_close(s, date(2026, 9, 24)) is None  # a different date has no bars


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


def test_the_snapshot_says_whether_the_close_is_official_or_provisional(rtoken_price):
    rtoken_price(752.0)
    assert agent_loop.build_snapshot("META", _anchor())["anchor_source"] == "official_daily"
    snap = agent_loop.build_snapshot("META", _anchor(close_sources={"META": "provisional_1m"}))
    assert snap["anchor_source"] == "provisional_1m"


def test_the_prompt_tells_the_model_when_the_close_is_provisional(rtoken_price):
    rtoken_price(752.0)
    official = agent_loop.build_snapshot("META", _anchor())
    provisional = agent_loop.build_snapshot("META", _anchor(close_sources={"META": "provisional_1m"}))
    assert "Provisional" not in agent_loop.build_user_prompt(official)
    text = agent_loop.build_user_prompt(provisional)
    assert "Provisional: the official close is not published yet" in text
    assert "1-minute bar" in text


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

