"""
Crypto market-beta loader for Gloaming's overnight fair-value model.

BTC/ETH are the truest 24/7 signal available (unlike futures proxies, they never
close), used as a risk-sentiment leading indicator for rToken fair value while
NYSE is shut. Pulled straight from Bitget's own public market data via `bgc` —
same client used for rToken data, so no second exchange integration is needed.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

if __name__ == "__main__" and __package__ is None:
    # allow `python data/crypto_beta.py` in addition to `python -m data.crypto_beta`
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data.rtoken_client import get_candles_history, run_bgc  # reuse the same CLI bridge

CRYPTO_BETA_SYMBOLS = ["BTCUSDT", "ETHUSDT"]


@dataclass
class CryptoTick:
    symbol: str
    last_price: float
    pcnt_change_24h: float
    ts_ms: int


def get_crypto_ticks(symbols: list[str] = CRYPTO_BETA_SYMBOLS) -> list[CryptoTick]:
    ticks = []
    for symbol in symbols:
        payload = run_bgc(["market", "--action", "tickers", "--category", "SPOT", "--symbol", symbol])
        row = payload["data"][0]
        ticks.append(CryptoTick(
            symbol=row["symbol"],
            last_price=float(row["lastPrice"]),
            pcnt_change_24h=float(row["price24hPcnt"]),
            ts_ms=int(row["ts"]),
        ))
    return ticks


def crypto_beta_return(ticks: list[CryptoTick] | None = None) -> float:
    """Simple blended 24h return across BTC/ETH as a single risk-sentiment scalar.
    v1: equal-weighted average. Day 3 replaces with OLS-calibrated weights."""
    ticks = ticks or get_crypto_ticks()
    return sum(t.pcnt_change_24h for t in ticks) / len(ticks)


def get_crypto_beta_history(symbols: list[str] = CRYPTO_BETA_SYMBOLS, interval: str = "1D",
                             limit: str = "100"):
    """Historical daily blended BTC/ETH return series for backtesting — equal-weighted
    average of each symbol's close-to-close % return. Returns a pandas Series indexed
    by UTC timestamp, named 'crypto_beta_return'."""
    import pandas as pd

    closes = {}
    for symbol in symbols:
        df = get_candles_history(symbol, interval=interval, limit=limit)
        closes[symbol] = df["close"]
    wide = pd.DataFrame(closes)
    returns = wide.pct_change()
    blended = returns.mean(axis=1).rename("crypto_beta_return")
    return blended.dropna()


if __name__ == "__main__":
    import sys

    if "--smoke-test" in sys.argv:
        print(f"Fetching {CRYPTO_BETA_SYMBOLS} via bgc...")
        ticks = get_crypto_ticks()
        for t in ticks:
            print(t)
        print(f"Blended crypto-beta 24h return: {crypto_beta_return(ticks):.4%}")
        print("OK — crypto beta feed reachable.")
    else:
        print("Usage: python crypto_beta.py --smoke-test")
