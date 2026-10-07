"""
Unit tests for gloaming_agent/verify_fills.py's pure parts: how one fill price is
judged against Bitget's 1-minute candles, and how the results are counted. No network.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "gloaming_agent"))

import verify_fills  # noqa: E402

MIN = 60_000
FILL_MINUTE = 1_789_093_320_000  # 2026-09-11 02:22 UTC, the ledger's first fill


def candle(minutes_before: int, low: float, high: float) -> dict:
    return {"minute_ms": FILL_MINUTE - minutes_before * MIN, "open": low, "high": high, "low": low, "close": high}


def test_price_inside_fill_minute_matches_with_zero_lag():
    r = verify_fills.classify(325.50, FILL_MINUTE, [candle(1, 325.0, 325.2), candle(0, 325.48, 325.55)])
    assert r["status"] == "matched"
    assert r["lag_minutes"] == 0


def test_range_edges_count_as_traded():
    assert verify_fills.classify(325.48, FILL_MINUTE, [candle(0, 325.48, 325.55)])["status"] == "matched"
    assert verify_fills.classify(325.55, FILL_MINUTE, [candle(0, 325.48, 325.55)])["status"] == "matched"


def test_most_recent_matching_minute_wins():
    candles = [candle(6, 100.0, 101.0), candle(3, 100.0, 101.0), candle(0, 102.0, 103.0)]
    r = verify_fills.classify(100.5, FILL_MINUTE, candles)
    assert r["status"] == "matched"
    assert r["lag_minutes"] == 3


def test_price_never_traded_is_a_mismatch_with_distance():
    r = verify_fills.classify(101.0, FILL_MINUTE, [candle(2, 99.0, 99.5), candle(0, 100.0, 100.5)])
    assert r["status"] == "mismatch"
    assert r["nearest_bp"] == 49.5  # 0.5 above the closest high, over a 101 price


def test_no_candles_is_no_data():
    assert verify_fills.classify(100.0, FILL_MINUTE, []) == {"status": "no_data"}


def test_summary_counts_every_outcome_and_pending():
    rows = [
        {"status": "matched", "lag_minutes": 0},
        {"status": "matched", "lag_minutes": 4},
        {"status": "matched", "lag_minutes": 1},
        {"status": "mismatch"},
        {"status": "no_data"},
    ]
    s = verify_fills.summarize(rows, total_fills=7)
    assert (s["checked"], s["pending"]) == (5, 2)
    assert (s["matched"], s["mismatch"], s["no_data"]) == (3, 1, 1)
    assert (s["median_lag_minutes"], s["max_lag_minutes"]) == (1, 4)
