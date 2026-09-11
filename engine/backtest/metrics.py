"""
Backtest performance metrics for Gloaming - shared by the Agentic Trading paper-log
report and any Alpha Factory stretch backtest.

All functions take a pandas Series of periodic (typically daily) strategy returns,
except max_drawdown (takes an equity curve) and turnover (takes a position series).
Deliberately hand-rolled and dependency-light (numpy/pandas only) rather than pulling
in a backtesting framework - the hackathon judges need runnable code + numbers, not a
specific library.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def sharpe_ratio(returns: pd.Series, periods_per_year: int = 365, risk_free: float = 0.0) -> float:
    """Annualized Sharpe ratio. periods_per_year=365 for daily rToken/crypto-style
    series that trade every calendar day (not 252, since the whole point of this
    project is that rTokens trade on weekends too)."""
    excess = returns - risk_free / periods_per_year
    std = excess.std(ddof=1)
    if std == 0 or np.isnan(std):
        return 0.0
    return float(excess.mean() / std * np.sqrt(periods_per_year))


def sortino_ratio(returns: pd.Series, periods_per_year: int = 365, risk_free: float = 0.0) -> float:
    """Annualized Sortino ratio - like Sharpe but only penalizes downside deviation."""
    excess = returns - risk_free / periods_per_year
    downside = excess[excess < 0]
    downside_std = downside.std(ddof=1)
    if downside_std == 0 or np.isnan(downside_std):
        return 0.0
    return float(excess.mean() / downside_std * np.sqrt(periods_per_year))


def equity_curve_from_returns(returns: pd.Series, starting_equity: float = 1.0) -> pd.Series:
    return starting_equity * (1 + returns.fillna(0)).cumprod()


def max_drawdown(equity_curve: pd.Series) -> float:
    """Maximum peak-to-trough drawdown as a negative fraction, e.g. -0.18 == -18%."""
    running_max = equity_curve.cummax()
    drawdown = equity_curve / running_max - 1
    return float(drawdown.min())


def turnover(positions: pd.Series) -> float:
    """Average absolute period-over-period change in position size - a proxy for
    trading activity/cost sensitivity, not a dollar turnover figure."""
    return float(positions.diff().abs().mean())


def win_rate(returns: pd.Series) -> float:
    nonzero = returns[returns != 0]
    if len(nonzero) == 0:
        return 0.0
    return float((nonzero > 0).mean())


def summarize(returns: pd.Series, positions: pd.Series, periods_per_year: int = 365) -> dict:
    """One-call report bundling every metric the hackathon's judging rubric asks
    for (Sharpe, Sortino, max drawdown, turnover) plus win rate for context."""
    equity = equity_curve_from_returns(returns)
    return {
        "sharpe": sharpe_ratio(returns, periods_per_year),
        "sortino": sortino_ratio(returns, periods_per_year),
        "max_drawdown": max_drawdown(equity),
        "turnover": turnover(positions),
        "win_rate": win_rate(returns),
        "total_return": float(equity.iloc[-1] - 1) if len(equity) else 0.0,
        "n_periods": int(len(returns)),
    }
