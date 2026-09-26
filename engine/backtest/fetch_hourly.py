"""
Fetches and caches the real hourly history the since-close backtest needs, so the analysis can
be re-run without another ~10 minutes of paging.

Sources are the same ones the live signal uses (engine/data/overnight_anchor.py):
  - rToken hourly candles and BTC/ETH hourly candles from Bitget (paged back in 100-bar pages)
  - index futures, the dollar index (hourly) and the real shares' daily closes from Yahoo

Cached under engine/data/cache/hourly/ (git-ignored, regenerable):
    python -m backtest.fetch_hourly            # from engine/
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data.crypto_beta import CRYPTO_BETA_SYMBOLS  # noqa: E402
from data.rtoken_client import get_candles_history  # noqa: E402
from fairvalue.config import RTOKEN_UNIVERSE  # noqa: E402

CACHE = Path(__file__).resolve().parents[1] / "data" / "cache" / "hourly"
LOOKBACK_DAYS = 90
PAGE_HOURS = 100


def fetch_bitget_hourly(symbol: str, days: int = LOOKBACK_DAYS) -> pd.DataFrame:
    end = datetime.now(timezone.utc)
    stop = end - timedelta(days=days)
    frames = []
    while end > stop:
        start = end - timedelta(hours=PAGE_HOURS)
        df = get_candles_history(symbol, interval="1H", limit="100",
                                 start_time_ms=int(start.timestamp() * 1000), end_time_ms=int(end.timestamp() * 1000))
        if len(df) == 0:
            break  # ran off the start of the instrument's history
        frames.append(df)
        end = start
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames)
    return out[~out.index.duplicated(keep="first")].sort_index()


def main() -> None:
    import yfinance as yf

    CACHE.mkdir(parents=True, exist_ok=True)
    for symbol in [c["rtoken_symbol"] for c in RTOKEN_UNIVERSE.values()] + list(CRYPTO_BETA_SYMBOLS):
        df = fetch_bitget_hourly(symbol)
        df.to_csv(CACHE / f"bitget_{symbol}.csv")
        print(f"{symbol}: {len(df)} hourly bars, {df.index.min()} -> {df.index.max()}" if len(df) else f"{symbol}: none", flush=True)

    tickers = sorted({c["futures_proxy"] for c in RTOKEN_UNIVERSE.values()} | {"DX-Y.NYB"})
    for t in tickers:
        d = yf.download(t, period="6mo", interval="1h", progress=False, auto_adjust=True)
        col = d["Close"] if not isinstance(d.columns, pd.MultiIndex) else d["Close"][t]
        col.dropna().to_csv(CACHE / f"yahoo_{t.replace('=', '_').replace('^', '')}.csv", header=["close"])
        print(f"{t}: {len(col.dropna())} hourly bars", flush=True)

    shares = sorted(set(RTOKEN_UNIVERSE) | {"SPY"})
    d = yf.download(shares, period="6mo", interval="1d", group_by="ticker", auto_adjust=True, progress=False)
    frames = {t: d[t]["Close"] for t in shares}
    pd.DataFrame(frames).dropna(how="all").to_csv(CACHE / "yahoo_daily_closes.csv")
    print("daily closes:", len(d), "sessions", flush=True)


if __name__ == "__main__":
    main()
