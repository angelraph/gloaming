"""
Checks every paper fill against Bitget's own public market data, so the paper record
can be verified by anyone rather than taken on trust.

A fill's price is the rToken's lastPrice from the live Bitget ticker, taken at the start
of the cycle; the fill's timestamp is written a little later, after Qwen has answered.
So for each fill this script asks Bitget's public 1-minute candle endpoint for the
WINDOW_MINUTES most recent traded minutes up to and including the fill's minute, and
records the most recent minute whose traded range [low, high] contains the fill price.
Bitget omits minutes with no trades, so on a quiet symbol that window can reach back
hours; a match older than STALE_MINUTES is counted as stale: the price was really traded,
but not recently, so a real order at that moment might not have filled there.

Results, one per fill:
  matched   - the price sits inside a real Bitget minute's traded range in the window;
              `lag_minutes` says how many minutes before the fill's own minute that was,
              and `stale` is true when that is more than STALE_MINUTES
  mismatch  - no minute in the window traded at that price; `nearest_bp` is how far the
              price sits outside the closest minute's range, in basis points
  no_data   - Bitget returned no candles for the window

Nothing is hidden: mismatches and gaps are kept and counted next to the matches.

The candle endpoint is public (no API key), so the check can be rerun by anyone:
    python gloaming_agent/verify_fills.py           # check new fills, write the file
    python gloaming_agent/verify_fills.py --push    # also mirror the result to the Desk
Results are cached in fill_verification.json; a rerun only checks fills not yet in it.
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
LEDGER_PATH = HERE / "paper_ledger.json"
VERIFICATION_PATH = HERE / "fill_verification.json"

CANDLES_URL = "https://api.bitget.com/api/v2/spot/market/history-candles"
WINDOW_MINUTES = 20
STALE_MINUTES = 15  # one agent cycle
MIN_AGE_SECONDS = 120  # the fill's own minute candle must be closed before it is checked
REQUEST_PAUSE_SECONDS = 0.12  # well under Bitget's public rate limit
RETRIES = 4
MAX_CHECKS_PER_RUN = 250  # keeps a backfill inside the workflow's 10-minute limit; the rest wait a cycle


def fill_key(fill: dict) -> str:
    return f"{fill['timestamp']}|{fill['symbol']}|{fill['side']}|{fill['qty']}"


def _fill_ms(fill: dict) -> int:
    return int(datetime.fromisoformat(fill["timestamp"]).timestamp() * 1000)


def fetch_candles(symbol: str, end_minute_ms: int) -> list[dict]:
    """The WINDOW_MINUTES one-minute candles ending with the minute that starts at
    end_minute_ms, oldest first. Raises after RETRIES failed attempts."""
    params = {
        "symbol": symbol,
        "granularity": "1min",
        "endTime": str(end_minute_ms + 60_000),
        "limit": str(WINDOW_MINUTES),
    }
    last_error: Exception | None = None
    for attempt in range(RETRIES):
        try:
            resp = requests.get(CANDLES_URL, params=params, timeout=20)
            payload = resp.json()
            if payload.get("code") != "00000":
                raise RuntimeError(f"Bitget error {payload.get('code')}: {payload.get('msg')}")
            rows = [
                {"minute_ms": int(r[0]), "open": float(r[1]), "high": float(r[2]),
                 "low": float(r[3]), "close": float(r[4])}
                for r in payload.get("data", [])
            ]
            return sorted(
                (r for r in rows if r["minute_ms"] <= end_minute_ms),
                key=lambda r: r["minute_ms"],
            )
        except Exception as exc:  # network hiccups are common here; retry with backoff
            last_error = exc
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"candles for {symbol} unavailable after {RETRIES} attempts: {last_error}")


def classify(price: float, fill_minute_ms: int, candles: list[dict]) -> dict:
    """Pure: compares one fill price with the candles in its window."""
    if not candles:
        return {"status": "no_data"}
    for c in reversed(candles):  # most recent minute first
        if c["low"] <= price <= c["high"]:
            lag = (fill_minute_ms - c["minute_ms"]) // 60_000
            return {
                "status": "matched",
                "lag_minutes": lag,
                "stale": lag > STALE_MINUTES,
                "candle_minute": datetime.fromtimestamp(c["minute_ms"] / 1000, timezone.utc).isoformat(),
                "candle_low": c["low"],
                "candle_high": c["high"],
            }
    nearest = min(candles, key=lambda c: min(abs(price - c["low"]), abs(price - c["high"])))
    gap = min(abs(price - nearest["low"]), abs(price - nearest["high"]))
    return {
        "status": "mismatch",
        "nearest_bp": round(gap / price * 10_000, 2),
        "candle_minute": datetime.fromtimestamp(nearest["minute_ms"] / 1000, timezone.utc).isoformat(),
        "candle_low": nearest["low"],
        "candle_high": nearest["high"],
    }


def summarize(rows: list[dict], total_fills: int) -> dict:
    counts = {"matched": 0, "mismatch": 0, "no_data": 0}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    lags = sorted(r["lag_minutes"] for r in rows if r["status"] == "matched")
    return {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "source": CANDLES_URL + " (granularity=1min, public)",
        "window_traded_minutes": WINDOW_MINUTES,
        "stale_after_minutes": STALE_MINUTES,
        "total_fills": total_fills,
        "checked": len(rows),
        "pending": total_fills - len(rows),
        **counts,
        "stale": sum(1 for r in rows if r["status"] == "matched" and r["lag_minutes"] > STALE_MINUTES),
        "median_lag_minutes": lags[len(lags) // 2] if lags else None,
        "max_lag_minutes": lags[-1] if lags else None,
    }


def run(push: bool = False) -> dict:
    fills = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))["fills"]
    now_ms = int(time.time() * 1000)
    existing: dict[str, dict] = {}
    if VERIFICATION_PATH.exists():
        for row in json.loads(VERIFICATION_PATH.read_text(encoding="utf-8")).get("fills", []):
            # a gap on a recent fill is worth asking Bitget about again; after a day it stands
            if row["status"] != "no_data" or now_ms - _fill_ms(row) > 86_400_000:
                existing[row["key"]] = row

    rows: list[dict] = []
    checks = 0
    for fill in fills:
        key = fill_key(fill)
        if key in existing:
            rows.append(existing[key])
            continue
        fill_ms = _fill_ms(fill)
        if now_ms - fill_ms < MIN_AGE_SECONDS * 1000:
            continue  # too fresh: its minute candle is not closed yet; next run picks it up
        if checks >= MAX_CHECKS_PER_RUN:
            continue
        checks += 1
        fill_minute_ms = fill_ms - fill_ms % 60_000
        try:
            candles = fetch_candles(fill["symbol"], fill_minute_ms)
        except RuntimeError as exc:
            print(f"skipped for now: {fill['symbol']} {fill['timestamp']}: {exc}", file=sys.stderr)
            continue
        rows.append({
            "key": key,
            "timestamp": fill["timestamp"],
            "symbol": fill["symbol"],
            "side": fill["side"],
            "price": fill["price"],
            **classify(fill["price"], fill_minute_ms, candles),
        })
        time.sleep(REQUEST_PAUSE_SECONDS)

    rows.sort(key=lambda r: r["timestamp"])
    if VERIFICATION_PATH.exists() and [r["key"] for r in rows] == list(existing) and len(rows) == len(fills):
        # nothing new to check: keep the file byte-identical so the cycle commits no churn
        return json.loads(VERIFICATION_PATH.read_text(encoding="utf-8"))
    result = {"summary": summarize(rows, len(fills)), "fills": rows}
    VERIFICATION_PATH.write_text(json.dumps(result, indent=1), encoding="utf-8")

    if push:
        import kv_sync
        kv_sync.push_fill_verification(result)
    return result


if __name__ == "__main__":
    summary = run(push="--push" in sys.argv)["summary"]
    print(json.dumps(summary, indent=2))
