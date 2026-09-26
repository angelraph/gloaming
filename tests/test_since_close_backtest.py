"""
The window arithmetic and trade-sign convention of the since-close backtest, on hand-built
series with no network and no cached data: the point is that the backtest measures exactly
what the live signal measures.
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))

from backtest.since_close_backtest import blend, edge, price_at, ret  # noqa: E402

UTC = timezone.utc


def _hourly(start, closes):
    idx = pd.date_range(start=start, periods=len(closes), freq="h", tz="UTC")
    return pd.Series(closes, index=idx, dtype=float)


def test_price_at_uses_the_close_of_the_last_bar_that_has_ended():
    s = _hourly("2026-09-25 18:00", [100, 101, 102, 103])  # bars start 18,19,20,21
    # at 20:00 the 19:00 bar (ending 20:00) is the last ended: its close is 101
    assert price_at(s, datetime(2026, 9, 25, 20, 0, tzinfo=UTC), base=True) == 101


def test_a_stale_base_is_refused_but_a_stale_end_price_is_allowed():
    s = _hourly("2026-09-25 10:00", [100, 101])  # last bar ends 12:00
    late = datetime(2026, 9, 25, 20, 0, tzinfo=UTC)
    assert price_at(s, late, base=True) is None   # 8h stale as a base: the proxy is missing
    assert price_at(s, late, base=False) == 101   # a closed market just has no newer bars


def test_return_is_measured_between_the_two_times():
    s = _hourly("2026-09-25 18:00", [100, 100, 110, 121])
    r = ret(s, datetime(2026, 9, 25, 20, 0, tzinfo=UTC), datetime(2026, 9, 25, 22, 0, tzinfo=UTC))
    assert r == pytest.approx(121 / 100 - 1)  # 19:00 bar close (100) to 21:00 bar close (121)


def test_blend_uses_the_weights_it_is_given():
    df = pd.DataFrame({"fut": [0.01], "crypto": [0.02], "fx": [0.03]})
    assert blend(df, 0.5, 0.3, 0.2).iloc[0] == pytest.approx(0.005 + 0.006 + 0.006)


def test_trading_against_the_spread_earns_when_the_rtoken_reverts():
    # rToken fell 2% since the close while proxies are flat (spread -2%, "cheap"), then rose 1%
    # to the open: long, gross +1%. A rich rToken that then falls is a winning short.
    df = pd.DataFrame({
        "session": ["a", "b"], "h": [4, 4], "underlying": ["X", "X"],
        "r_tok": [-0.02, 0.02], "fwd": [0.01, -0.01],
        "fut": [0.0, 0.0], "crypto": [0.0, 0.0], "fx": [0.0, 0.0],
    })
    row = next(r for r in edge(df, (0.5, 0.3, 0.2)) if r["h"] == 4 and r["threshold"] == 0.010)
    assert row["n"] == 2 and row["hit_rate"] == 1.0
    assert row["mean_gross_bp"] == pytest.approx(100.0)
    assert row["mean_net_bp"] == pytest.approx(100.0 - 30.0)  # the 0.30% round trip
