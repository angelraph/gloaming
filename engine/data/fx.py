"""
FX / risk-sentiment loader for Gloaming's overnight fair-value model.

DXY (US Dollar Index) is used as a cheap risk-on/risk-off proxy: dollar strength
overnight typically correlates with risk-off sentiment (bearish for equities/rTokens),
dollar weakness with risk-on. Inverted DXY return is blended into fair value per
fairvalue/config.py FAIRVALUE_WEIGHTS.
"""
from __future__ import annotations

import sys
from pathlib import Path

if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd

DXY_TICKER = "DX-Y.NYB"


def fetch_dxy_history(period: str = "90d", interval: str = "1h") -> pd.DataFrame:
    import yfinance as yf

    df = yf.download(DXY_TICKER, period=period, interval=interval, auto_adjust=True, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)  # flatten (Price, Ticker) -> Price
    return df[["Close"]].rename(columns={"Close": "dxy_close"})


def get_fx_returns_daily(period: str = "6mo") -> pd.Series:
    """Daily inverted DXY % returns for backtesting (positive == risk-on). period='6mo'
    comfortably covers rToken's ~90-day live history."""
    df = fetch_dxy_history(period=period, interval="1d")
    ret = -df["dxy_close"].pct_change().dropna()
    return ret.rename("fx_risk_sentiment_return")


def fx_risk_sentiment_return(df: pd.DataFrame | None = None) -> float:
    """Inverted latest-vs-prior-bar DXY return: positive value == risk-on (dollar
    weakening), consistent sign convention with crypto_beta_return()."""
    df = df if df is not None else fetch_dxy_history(period="5d", interval="1h")
    closes = df["dxy_close"].dropna()
    if len(closes) < 2:
        return 0.0
    ret = (closes.iloc[-1] / closes.iloc[-2]) - 1
    return float(-ret)  # invert: dollar down -> risk-on -> positive signal


if __name__ == "__main__":
    if "--smoke-test" in sys.argv:
        print(f"Fetching {DXY_TICKER} via yfinance (period=5d, interval=1h)...")
        df = fetch_dxy_history(period="5d", interval="1h")
        print(df.tail())
        if df["dxy_close"].dropna().empty:
            print("WARNING: no DXY data returned - see docs/architecture.md fallback plan.")
        else:
            print(f"FX risk-sentiment signal: {fx_risk_sentiment_return(df):.4%}")
            print("OK - FX proxy data reachable.")
    else:
        print("Usage: python fx.py --smoke-test")
