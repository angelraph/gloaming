"""Unit tests for engine/fairvalue/model.py — deterministic, known-value checks."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))

from fairvalue import model  # noqa: E402


def _dates(n):
    return pd.date_range("2026-01-01", periods=n, freq="D")


def test_blended_fair_value_return_known_weights():
    idx = _dates(3)
    futures = pd.Series([0.01, 0.02, -0.01], index=idx)
    crypto = pd.Series([0.02, 0.00, 0.01], index=idx)
    fx = pd.Series([0.00, 0.01, 0.00], index=idx)
    weights = {"futures_proxy_return": 0.5, "crypto_beta_return": 0.3, "fx_risk_sentiment_return": 0.2}

    blended = model.blended_fair_value_return(futures, crypto, fx, weights)

    expected_0 = 0.01 * 0.5 + 0.02 * 0.3 + 0.00 * 0.2
    assert blended.iloc[0] == pytest.approx(expected_0, abs=1e-9)


def test_blended_fair_value_return_drops_misaligned_rows():
    futures = pd.Series([0.01, 0.02], index=_dates(2))
    crypto = pd.Series([0.01], index=_dates(1))  # only 1 of 2 dates overlaps
    fx = pd.Series([0.01, 0.01], index=_dates(2))
    blended = model.blended_fair_value_return(futures, crypto, fx)
    assert len(blended) == 1


def test_fair_value_price_path_compounds_correctly():
    returns = pd.Series([0.10, -0.10], index=_dates(2))
    path = model.fair_value_price_path(100.0, returns)
    assert path.iloc[0] == pytest.approx(110.0, abs=1e-9)
    assert path.iloc[1] == pytest.approx(110.0 * 0.9, abs=1e-9)


def test_spread_pct_known_value():
    idx = _dates(2)
    actual = pd.Series([110.0, 90.0], index=idx)
    fair = pd.Series([100.0, 100.0], index=idx)
    spread = model.spread_pct(actual, fair)
    assert spread.iloc[0] == pytest.approx(0.10, abs=1e-9)
    assert spread.iloc[1] == pytest.approx(-0.10, abs=1e-9)


def test_rolling_zscore_constant_series_is_nan():
    # Zero variance -> std is 0 -> z-score is NaN, not a division error
    series = pd.Series([1.0] * 20)
    z = model.rolling_zscore(series, window=5)
    assert z.iloc[-1] != z.iloc[-1] or pd.isna(z.iloc[-1])  # NaN check without relying on np import quirks


def test_rolling_zscore_extreme_point_has_large_positive_z():
    series = pd.Series([1.0, 1.0, 1.0, 1.0, 1.0, 10.0])
    z = model.rolling_zscore(series, window=5, min_periods=5)
    assert z.iloc[-1] > 1.5


def test_calibrate_weights_recovers_known_linear_relationship():
    # y = 2*futures + 0*crypto + 0*fx exactly, no noise -> lstsq should recover [2, 0, 0]
    n = 20
    idx = _dates(n)
    rng = np.random.default_rng(42)
    futures = pd.Series(rng.normal(0, 0.01, n), index=idx)
    crypto = pd.Series(rng.normal(0, 0.01, n), index=idx)
    fx = pd.Series(rng.normal(0, 0.01, n), index=idx)
    y = pd.Series(2.0 * futures.values, index=idx)

    weights = model.calibrate_weights(y, futures, crypto, fx)

    assert weights["futures_proxy_return"] == pytest.approx(2.0, abs=1e-6)
    assert weights["crypto_beta_return"] == pytest.approx(0.0, abs=1e-6)
    assert weights["fx_risk_sentiment_return"] == pytest.approx(0.0, abs=1e-6)


def test_calibrate_weights_falls_back_to_heuristic_when_insufficient_data():
    idx = _dates(3)  # fewer than the 10-observation minimum
    futures = pd.Series([0.01, 0.02, 0.01], index=idx)
    crypto = pd.Series([0.01, 0.01, 0.01], index=idx)
    fx = pd.Series([0.0, 0.0, 0.0], index=idx)
    y = pd.Series([0.01, 0.01, 0.01], index=idx)

    weights = model.calibrate_weights(y, futures, crypto, fx)

    from fairvalue.config import FAIRVALUE_WEIGHTS
    assert weights == FAIRVALUE_WEIGHTS
