"""
CME index-futures proxy loader for Gloaming's overnight fair-value model.

Real CME tick data isn't freely accessible in the hackathon time budget, so we use
Yahoo Finance's continuous front-month futures tickers as an accessible proxy:
  - ES=F : S&P 500 e-mini futures (broad-market overnight signal)
  - NQ=F : Nasdaq-100 e-mini futures (large-cap tech overnight signal)

These trade nearly 23h/day on non-US exchanges' data feeds, which is what makes them
useful during the NYSE-closed window this whole project targets. This is explicitly
disclosed as a proxy, not true CME tick data, in docs/architecture.md.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

CACHE_DIR = Path(__file__).resolve().parent / "cache"
FUTURES_TICKERS = ["ES=F", "NQ=F"]


def fetch_futures_history(tickers: list[str] = FUTURES_TICKERS, period: str = "90d",
                            interval: str = "1h") -> pd.DataFrame:
    """Pull recent futures-proxy history via yfinance. Returns a wide DataFrame
    (columns = tickers, index = timestamp, values = close price)."""
    import yfinance as yf  # imported lazily so this module is importable pre-install

    data = yf.download(tickers, period=period, interval=interval, group_by="ticker",
                        auto_adjust=True, progress=False)
    closes = pd.DataFrame({t: data[t]["Close"] for t in tickers})
    closes.index.name = "timestamp"
    return closes


def cache_futures_history(**kwargs) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    df = fetch_futures_history(**kwargs)
    out_path = CACHE_DIR / "futures_proxy.parquet"
    df.to_parquet(out_path)
    return out_path


if __name__ == "__main__":
    import sys

    if "--smoke-test" in sys.argv:
        print(f"Fetching {FUTURES_TICKERS} via yfinance (period=5d, interval=1h)...")
        df = fetch_futures_history(period="5d", interval="1h")
        print(df.tail())
        missing = [c for c in FUTURES_TICKERS if df[c].isna().all()]
        if missing:
            print(f"WARNING: no data returned for {missing} — proxy unavailable, "
                  f"see docs/architecture.md fallback plan.")
        else:
            print("OK — futures proxy data reachable.")
    else:
        print("Usage: python futures_proxy.py --smoke-test")
