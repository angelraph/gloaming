"""
Gloaming's core thesis, as code: while NYSE is closed there is no direct arbitrage
pressure holding an rToken's on-chain price to its real-share value. This module
estimates what that value *should* be from proxies that stay live overnight -
index-futures proxy, crypto beta, FX risk sentiment - and measures the spread
between that synthetic fair value and the rToken's actual traded price.

Design: everything here works on daily return series (pandas Series, aligned by
UTC date) so the same functions serve both the live Agent loop (evaluated once per
tick) and the offline backtest (evaluated vectorized over history).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from fairvalue.config import FAIRVALUE_WEIGHTS


def blended_fair_value_return(
    futures_proxy_return: pd.Series,
    crypto_beta_return: pd.Series,
    fx_risk_sentiment_return: pd.Series,
    weights: dict = FAIRVALUE_WEIGHTS,
) -> pd.Series:
    """Weighted blend of the three overnight-live proxy return series into a single
    synthetic 'what the rToken should have returned' series. Inputs are aligned on
    their shared index (inner join) - callers should already have same-frequency
    (typically daily) series before calling this."""
    df = pd.DataFrame({
        "futures_proxy_return": futures_proxy_return,
        "crypto_beta_return": crypto_beta_return,
        "fx_risk_sentiment_return": fx_risk_sentiment_return,
    }).dropna()
    blended = (
        df["futures_proxy_return"] * weights["futures_proxy_return"]
        + df["crypto_beta_return"] * weights["crypto_beta_return"]
        + df["fx_risk_sentiment_return"] * weights["fx_risk_sentiment_return"]
    )
    return blended.rename("fair_value_return")


def fair_value_price_path(anchor_price: float, fair_value_returns: pd.Series) -> pd.Series:
    """Compound a fair-value return series into a price path, anchored to a known
    starting price (e.g. the rToken's price at the start of the backtest window)."""
    return (anchor_price * (1 + fair_value_returns.fillna(0)).cumprod()).rename("fair_value_price")


def spread_pct(actual_price: pd.Series, fair_value_price: pd.Series) -> pd.Series:
    """(actual - fair) / fair, aligned on shared index. Positive == rToken trading
    rich vs. synthetic fair value; negative == trading cheap."""
    df = pd.DataFrame({"actual": actual_price, "fair": fair_value_price}).dropna()
    return ((df["actual"] - df["fair"]) / df["fair"]).rename("spread_pct")


def rolling_zscore(series: pd.Series, window: int = 14, min_periods: int = 5) -> pd.Series:
    """Rolling z-score of a series - used to turn the raw spread into a bounded,
    comparable-across-symbols mean-reversion signal."""
    mean = series.rolling(window, min_periods=min_periods).mean()
    std = series.rolling(window, min_periods=min_periods).std(ddof=1)
    z = (series - mean) / std
    return z.replace([np.inf, -np.inf], np.nan).rename("spread_zscore")


def calibrate_weights(
    rtoken_return: pd.Series,
    futures_proxy_return: pd.Series,
    crypto_beta_return: pd.Series,
    fx_risk_sentiment_return: pd.Series,
) -> dict:
    """OLS-calibrate the three proxy weights against realized rToken returns over
    an in-sample window (unconstrained least squares - no sum-to-1 or non-negativity
    constraint, so a negative or >1 weight is a legitimate, disclosed output, not a
    bug). Falls back to the heuristic FAIRVALUE_WEIGHTS prior if there isn't enough
    overlapping history to regress (needs at least 10 aligned observations).

    This is intentionally a plain numpy.linalg.lstsq regression, not sklearn -
    one dependency less, and the hackathon judges just need transparent, reproducible
    signal logic, not a specific ML library."""
    df = pd.DataFrame({
        "y": rtoken_return,
        "futures_proxy_return": futures_proxy_return,
        "crypto_beta_return": crypto_beta_return,
        "fx_risk_sentiment_return": fx_risk_sentiment_return,
    }).dropna()

    if len(df) < 10:
        return dict(FAIRVALUE_WEIGHTS)

    X = df[["futures_proxy_return", "crypto_beta_return", "fx_risk_sentiment_return"]].to_numpy()
    y = df["y"].to_numpy()
    coeffs, *_ = np.linalg.lstsq(X, y, rcond=None)
    return {
        "futures_proxy_return": float(coeffs[0]),
        "crypto_beta_return": float(coeffs[1]),
        "fx_risk_sentiment_return": float(coeffs[2]),
    }
