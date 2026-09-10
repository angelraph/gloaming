"""Unit tests for engine/backtest/metrics.py — deterministic, known-value checks."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))

from backtest import metrics  # noqa: E402


def test_sharpe_ratio_zero_vol_returns_zero():
    returns = pd.Series([0.0, 0.0, 0.0, 0.0])
    assert metrics.sharpe_ratio(returns) == 0.0


def test_sharpe_ratio_known_value():
    # Constant positive return with tiny alternating noise -> finite, positive Sharpe
    returns = pd.Series([0.01, 0.02, 0.01, 0.02, 0.01, 0.02] * 10)
    sharpe = metrics.sharpe_ratio(returns, periods_per_year=365)
    assert sharpe > 0
    assert np.isfinite(sharpe)


def test_sortino_ignores_upside_volatility():
    # All positive returns, no downside deviation -> Sortino should be 0 (no downside)
    returns = pd.Series([0.01, 0.05, 0.02, 0.08, 0.01])
    assert metrics.sortino_ratio(returns) == 0.0


def test_sortino_penalizes_downside_only():
    returns = pd.Series([0.05, -0.10, 0.05, -0.02, 0.05])
    sortino = metrics.sortino_ratio(returns)
    assert sortino != 0.0
    assert np.isfinite(sortino)


def test_max_drawdown_known_curve():
    # Equity: 1.0 -> 1.2 -> 0.9 -> 1.1. Peak 1.2, trough 0.9 -> drawdown = 0.9/1.2 - 1 = -0.25
    equity = pd.Series([1.0, 1.2, 0.9, 1.1])
    dd = metrics.max_drawdown(equity)
    assert dd == pytest.approx(-0.25, abs=1e-9)


def test_max_drawdown_monotonic_increase_is_zero():
    equity = pd.Series([1.0, 1.1, 1.2, 1.3])
    assert metrics.max_drawdown(equity) == pytest.approx(0.0, abs=1e-9)


def test_turnover_known_value():
    # Position changes: |0.5-0|, |-0.5-0.5|, |0-(-0.5)| = 0.5, 1.0, 0.5 -> mean over 3 diffs = 0.667
    positions = pd.Series([0.0, 0.5, -0.5, 0.0])
    assert metrics.turnover(positions) == pytest.approx((0.5 + 1.0 + 0.5) / 3, abs=1e-9)


def test_win_rate_known_value():
    returns = pd.Series([0.01, -0.01, 0.02, -0.005, 0.0])  # 0.0 excluded, 2 wins / 4 nonzero
    assert metrics.win_rate(returns) == pytest.approx(0.5, abs=1e-9)


def test_win_rate_empty_series_is_zero():
    assert metrics.win_rate(pd.Series([0.0, 0.0])) == 0.0


def test_summarize_returns_all_expected_keys():
    returns = pd.Series([0.01, -0.02, 0.03, -0.01, 0.02])
    positions = pd.Series([0.1, 0.2, -0.1, 0.0, 0.3])
    report = metrics.summarize(returns, positions)
    for key in ["sharpe", "sortino", "max_drawdown", "turnover", "win_rate", "total_return", "n_periods"]:
        assert key in report
    assert report["n_periods"] == 5
