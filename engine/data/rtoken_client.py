"""
Thin wrapper over the Bitget Agent CLI (`bgc`) for rToken market data.

rTokens are regular Bitget SPOT pairs (confirmed Day 1): symbolType == "stock",
baseCoin prefixed "r", isReality == "yes", symbol convention R<TICKER>USDT
(e.g. AAPL -> RAAPLUSDT). Public market-data reads need no API credentials.

We shell out to `npx bgc ...` rather than reimplementing the signed REST client,
per the build plan's stated approach (call the CLI via subprocess from Python).
"""
from __future__ import annotations

import json
import platform
import subprocess
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]  # .../gloaming
_IS_WINDOWS = platform.system() == "Windows"


class BgcError(RuntimeError):
    pass


def run_bgc(args: list[str]) -> dict:
    """Run `npx bgc <args>` from the repo root and parse its JSON stdout.

    Public - other data loaders (crypto_beta.py, etc.) reuse this instead of
    each shelling out independently."""
    proc = subprocess.run(
        ["npx", "bgc", *args, "--pretty"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        # Windows: npx resolves via npx.cmd, which needs a shell to run directly.
        # POSIX (Linux/macOS, e.g. the GitHub Actions runner): shell=True with a
        # list of args is a documented footgun - only args[0] becomes the shell's
        # command and everything else becomes an argument to the shell itself, not
        # to npx, silently breaking every call. shell=False is correct there and
        # npx is resolved from PATH normally, same as any other subprocess call.
        shell=_IS_WINDOWS,
        timeout=30,
    )
    if proc.returncode != 0:
        raise BgcError(f"bgc {' '.join(args)} failed: {proc.stderr.strip()}")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise BgcError(f"bgc {' '.join(args)} returned non-JSON output: {proc.stdout[:500]}") from e


@dataclass
class RTokenTick:
    symbol: str
    last_price: float
    bid: float
    ask: float
    ts_ms: int


def get_ticker(rtoken_symbol: str) -> RTokenTick:
    """Live snapshot for one rToken SPOT symbol, e.g. 'RAAPLUSDT'."""
    payload = run_bgc(["market", "--action", "tickers", "--category", "SPOT", "--symbol", rtoken_symbol])
    row = payload["data"][0]
    return RTokenTick(
        symbol=row["symbol"],
        last_price=float(row["lastPrice"]),
        bid=float(row["bid1Price"]),
        ask=float(row["ask1Price"]),
        ts_ms=int(row["ts"]),
    )


def get_candles(rtoken_symbol: str, interval: str = "1H", limit: str = "200") -> list[dict]:
    """Recent klines for one rToken SPOT symbol (max ~1000 via `candles`;
    use `candlesHistory` for deeper backfill)."""
    payload = run_bgc(
        ["market", "--action", "candles", "--category", "SPOT", "--symbol", rtoken_symbol,
         "--interval", interval, "--limit", limit]
    )
    return payload["data"]


def get_candles_history(rtoken_symbol: str, interval: str = "1D", limit: str = "100",
                         start_time_ms: int | None = None, end_time_ms: int | None = None):
    """Historical klines via the `candlesHistory` action (max 90-day range per
    call, max 100 rows/page - sufficient for a single-page 90-day daily pull,
    confirmed Day 3: rToken launch-to-date history is ~90 daily bars).

    Returns a pandas DataFrame indexed by UTC timestamp with columns
    open/high/low/close/volume/turnover. Bitget kline row format confirmed via
    live probe: [ts_ms, open, high, low, close, baseVolume, quoteTurnover]."""
    import pandas as pd  # lazy import - keep this module's CLI-bridge parts dependency-free

    args = ["market", "--action", "candlesHistory", "--category", "SPOT",
            "--symbol", rtoken_symbol, "--interval", interval, "--limit", limit]
    if start_time_ms is not None:
        args += ["--startTime", str(start_time_ms)]
    if end_time_ms is not None:
        args += ["--endTime", str(end_time_ms)]
    payload = run_bgc(args)
    rows = payload["data"]
    df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume", "turnover"])
    df["ts"] = pd.to_datetime(df["ts"].astype("int64"), unit="ms", utc=True)
    for col in ["open", "high", "low", "close", "volume", "turnover"]:
        df[col] = df[col].astype(float)
    df = df.set_index("ts").sort_index()
    return df


def list_stock_symbols() -> list[dict]:
    """Full live rToken universe (symbol, baseCoin, status, launchTime) -
    refetches from Bitget; prefer the Day-1 cache at
    engine/data/cache/rtoken_universe.json for a stable snapshot."""
    payload = run_bgc(["market", "--action", "instruments", "--category", "SPOT"])
    return [row for row in payload["data"] if row.get("symbolType") == "stock"]


if __name__ == "__main__":
    import sys

    if "--smoke-test" in sys.argv:
        print("Fetching RAAPLUSDT ticker via bgc...")
        tick = get_ticker("RAAPLUSDT")
        print(tick)
        print("OK - live rToken feed reachable.")
    else:
        print("Usage: python rtoken_client.py --smoke-test")
