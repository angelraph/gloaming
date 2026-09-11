"""
Vectorized mean-reversion backtest core for Gloaming's "Overnight NAV Convergence"
thesis: when an rToken's actual price diverges from its synthetic fair value (per
fairvalue/model.py), bet on convergence.

Shared by:
  - the offline Alpha Factory backtest (run_backtest.py, full historical window)
  - anything the Agentic Trading write-up wants to show as supporting quant evidence
    alongside the live paper-trading log

Strategy (v1, deliberately simple and disclosed as such):
  1. Each day t, compute the rolling z-score of the actual-vs-fair-value spread.
  2. Form a position for day t+1 sized inversely to that z-score, clipped to
     [-1, 1]: short when the rToken trades rich (positive spread), long when it
     trades cheap (negative spread) - betting on reversion toward fair value.
  3. Realize strategy_return[t+1] = position[t] * rtoken_return[t+1] - the signal
     is fully known before the return it trades is realized (no lookahead).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from backtest import metrics
from fairvalue.model import rolling_zscore, spread_pct


def build_positions(
    actual_price: pd.Series,
    fair_value_price: pd.Series,
    zscore_window: int = 14,
    max_abs_zscore: float = 2.0,
) -> pd.DataFrame:
    """Returns a DataFrame with spread_pct, spread_zscore, and position columns,
    aligned on the shared index of actual_price/fair_value_price."""
    spread = spread_pct(actual_price, fair_value_price)
    zscore = rolling_zscore(spread, window=zscore_window)
    position = (-zscore / max_abs_zscore).clip(-1, 1)
    return pd.DataFrame({
        "spread_pct": spread,
        "spread_zscore": zscore,
        "position": position,
    })


def run_backtest(
    actual_price: pd.Series,
    fair_value_price: pd.Series,
    zscore_window: int = 14,
    max_abs_zscore: float = 2.0,
    periods_per_year: int = 365,
) -> dict:
    """Runs the full vectorized backtest for one symbol and returns a dict with the
    positions/returns/equity DataFrame plus a metrics.summarize() report."""
    signal_df = build_positions(actual_price, fair_value_price, zscore_window, max_abs_zscore)

    rtoken_return = actual_price.pct_change().rename("rtoken_return")
    df = signal_df.join(rtoken_return, how="inner").dropna(subset=["position"])

    # Position formed at close of day t (using that day's signal) trades day t+1's
    # realized return - shift(1) enforces no lookahead.
    df["position_lagged"] = df["position"].shift(1)
    df["strategy_return"] = df["position_lagged"] * df["rtoken_return"]
    df = df.dropna(subset=["strategy_return"])

    report = metrics.summarize(df["strategy_return"], df["position_lagged"], periods_per_year)
    df["equity"] = metrics.equity_curve_from_returns(df["strategy_return"])

    return {"data": df, "report": report}


def run_portfolio_backtest(per_symbol_results: dict[str, dict], periods_per_year: int = 365) -> dict:
    """Equal-weight combine several run_backtest() outputs (keyed by rToken symbol)
    into one portfolio-level return series + report - the number that actually goes
    in the submission write-up, with per-symbol figures as supporting detail."""
    returns = pd.DataFrame({
        sym: res["data"]["strategy_return"] for sym, res in per_symbol_results.items()
    })
    portfolio_returns = returns.mean(axis=1, skipna=True).dropna().rename("portfolio_return")
    positions = pd.DataFrame({
        sym: res["data"]["position_lagged"] for sym, res in per_symbol_results.items()
    })
    portfolio_positions = positions.mean(axis=1, skipna=True).reindex(portfolio_returns.index)

    report = metrics.summarize(portfolio_returns, portfolio_positions, periods_per_year)
    equity = metrics.equity_curve_from_returns(portfolio_returns)
    return {"returns": portfolio_returns, "equity": equity, "report": report}


def split_in_out_sample(df: pd.DataFrame, out_of_sample_days: int = 30) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Chronological split - the LAST `out_of_sample_days` rows are out-of-sample,
    matching the hackathon's '>=30 days out-of-sample' requirement."""
    if len(df) <= out_of_sample_days:
        return df.iloc[0:0], df
    return df.iloc[:-out_of_sample_days], df.iloc[-out_of_sample_days:]
