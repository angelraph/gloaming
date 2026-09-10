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
import subprocess
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]  # .../gloaming


class BgcError(RuntimeError):
    pass


def run_bgc(args: list[str]) -> dict:
    """Run `npx bgc <args>` from the repo root and parse its JSON stdout.

    Public — other data loaders (crypto_beta.py, etc.) reuse this instead of
    each shelling out independently."""
    proc = subprocess.run(
        ["npx", "bgc", *args, "--pretty"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        shell=True,  # Windows: npx resolves via npx.cmd, needs a shell
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


def list_stock_symbols() -> list[dict]:
    """Full live rToken universe (symbol, baseCoin, status, launchTime) —
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
        print("OK — live rToken feed reachable.")
    else:
        print("Usage: python rtoken_client.py --smoke-test")
