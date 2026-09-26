"""
Backtest of the LIVE signal specification (since_last_close_v2), on real hourly history.

The earlier Alpha Factory backtest works on daily close-to-close returns, a different signal
from the one the agent now trades. This one reproduces the live definitions exactly, on the
same kind of data:

    spread = rToken return since the real close - blended proxy return since that close
    blend  = 0.5 x index futures + 0.3 x BTC/ETH + 0.2 x inverted dollar index   (live weights)

For every session that has a following session, at several horizons after the 16:00 ET close
(and never later than the next 09:30 ET open), it records the spread and what the rToken did
from that moment to the next open. Two questions are answered from that:

  1. Calibration. How well does the proxy blend explain the rToken's own since-close move, and
     do other weights explain it better, measured out of sample (time-ordered split)?
  2. Edge. When the spread is large, does trading against it (long when cheap, short when rich)
     earn a positive return by the next open, gross and after the 0.30% round-trip cost?

Nothing here is tuned to look good: thresholds and horizons are fixed in advance, and the
result is reported whatever it shows. Regenerate with (from engine/):
    python -m backtest.fetch_hourly && python -m backtest.since_close_backtest
"""
from __future__ import annotations

import json
import sys
from datetime import date, datetime, time, timedelta, timezone
from itertools import product
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data.overnight_anchor import NYSE_HOLIDAYS, session_close_utc  # noqa: E402
from fairvalue.config import FAIRVALUE_WEIGHTS, RTOKEN_UNIVERSE  # noqa: E402

CACHE = Path(__file__).resolve().parents[1] / "data" / "cache" / "hourly"
OUT = Path(__file__).resolve().parents[2] / "alpha_factory" / "results" / "since_close_backtest.json"
NY = ZoneInfo("America/New_York")
HOURS = (2, 4, 8, 12)              # horizons after the close, fixed in advance
THRESHOLDS = (0.003, 0.005, 0.010)  # |spread| levels, fixed in advance
ROUND_TRIP_COST = 0.0030           # 2 x (0.10% fee + 0.05% slippage), the ledger's stated assumption
MAX_BASE_STALENESS = timedelta(hours=3)
BAR = timedelta(hours=1)


def _load_series(path: Path, col: str = "close") -> pd.Series:
    df = pd.read_csv(path, index_col=0)
    idx = pd.to_datetime(df.index, utc=True)
    s = pd.Series(df[col].values, index=idx, dtype=float).dropna().sort_index()
    return s[~s.index.duplicated(keep="first")]


def price_at(series: pd.Series, t: datetime, base: bool) -> float | None:
    """Close of the last bar that has ended by t. As in the live code, a stale BASE price is
    refused (the proxy is then missing and contributes nothing), but an END price may be old:
    a closed market simply has no newer bars."""
    ended = series[(series.index + BAR) <= pd.Timestamp(t)]
    if ended.empty:
        return None
    if base and pd.Timestamp(t) - (ended.index[-1] + BAR) > MAX_BASE_STALENESS:
        return None
    return float(ended.iloc[-1])


def ret(series: pd.Series, t0: datetime, t1: datetime, strict_base: bool = True) -> float | None:
    a, b = price_at(series, t0, base=strict_base), price_at(series, t1, base=False)
    if a is None or b is None or a == 0:
        return None
    return b / a - 1.0


def next_open_utc(d: date) -> datetime:
    return datetime.combine(d, time(9, 30), tzinfo=NY).astimezone(timezone.utc)


def build_events() -> pd.DataFrame:
    daily = pd.read_csv(CACHE / "yahoo_daily_closes.csv", index_col=0, parse_dates=True)
    sessions = [d.date() for d in daily.index if d.weekday() < 5 and d.date() not in NYSE_HOLIDAYS]
    dxy = _load_series(CACHE / "yahoo_DX-Y.NYB.csv")
    fut = {t: _load_series(CACHE / f"yahoo_{t.replace('=', '_')}.csv") for t in {c["futures_proxy"] for c in RTOKEN_UNIVERSE.values()}}
    crypto = [_load_series(CACHE / f"bitget_{s}.csv") for s in ("BTCUSDT", "ETHUSDT")]
    rtok = {u: _load_series(CACHE / f"bitget_{c['rtoken_symbol']}.csv") for u, c in RTOKEN_UNIVERSE.items()}
    w = FAIRVALUE_WEIGHTS

    rows = []
    for i, d in enumerate(sessions[:-1]):
        c_utc = session_close_utc(d)
        o_utc = next_open_utc(sessions[i + 1])
        for h in HOURS:
            t = c_utc + timedelta(hours=h)
            if t + BAR > o_utc:
                continue  # never sample inside the last hour before the open
            cry = [ret(s, c_utc, t) for s in crypto]
            crypto_r = None if any(x is None for x in cry) else sum(cry) / len(cry)
            dx = ret(dxy, c_utc, t)
            fx_r = None if dx is None else -dx
            for u, cfg in RTOKEN_UNIVERSE.items():
                r_tok = ret(rtok[u], c_utc, t)
                fwd = ret(rtok[u], t, o_utc, strict_base=False)
                f_r = ret(fut[cfg["futures_proxy"]], c_utc, t)
                if r_tok is None or fwd is None:
                    continue
                rows.append({
                    "session": str(d), "h": h, "underlying": u, "r_tok": r_tok, "fwd": fwd,
                    "fut": f_r, "crypto": crypto_r, "fx": fx_r,
                })
    df = pd.DataFrame(rows)
    for col in ("fut", "crypto", "fx"):
        df[col + "_missing"] = df[col].isna()
        df[col] = df[col].fillna(0.0)  # missing proxy = no information, as in the live signal
    return df


def blend(df: pd.DataFrame, wf: float, wc: float, wx: float) -> pd.Series:
    return df["fut"] * wf + df["crypto"] * wc + df["fx"] * wx


def calibration(df: pd.DataFrame) -> dict:
    sessions = sorted(df["session"].unique())
    cut = sessions[int(len(sessions) * 2 / 3)]
    train, test = df[df["session"] < cut], df[df["session"] >= cut]
    live = (w := FAIRVALUE_WEIGHTS)["futures_proxy_return"], w["crypto_beta_return"], w["fx_risk_sentiment_return"]

    def mse(d, wts):
        return float(((d["r_tok"] - blend(d, *wts)) ** 2).mean())

    grid = [(a / 10, b / 10, (10 - a - b) / 10) for a, b in product(range(11), range(11)) if a + b <= 10]
    best = min(grid, key=lambda g: mse(train, g))
    return {
        "train_sessions": int((train["session"].nunique())), "test_sessions": int(test["session"].nunique()),
        "split_at_session": cut, "live_weights": live, "fitted_weights_train": best,
        "test_mse_no_proxies": mse(test, (0, 0, 0)),
        "test_mse_live_weights": mse(test, live),
        "test_mse_fitted_weights": mse(test, best),
        "train_mse_live_weights": mse(train, live), "train_mse_fitted_weights": mse(train, best),
    }


def edge(df: pd.DataFrame, wts: tuple) -> list[dict]:
    d = df.copy()
    d["spread"] = d["r_tok"] - blend(d, *wts)
    out = []
    for h in HOURS:
        for thr in THRESHOLDS:
            x = d[(d["h"] == h) & (d["spread"].abs() >= thr)]
            if len(x) == 0:
                out.append({"h": h, "threshold": thr, "n": 0})
                continue
            gross = -np.sign(x["spread"]) * x["fwd"]  # long when cheap, short when rich
            out.append({
                "h": h, "threshold": thr, "n": int(len(x)), "sessions": int(x["session"].nunique()),
                "mean_gross_bp": float(gross.mean() * 1e4), "mean_net_bp": float((gross.mean() - ROUND_TRIP_COST) * 1e4),
                "hit_rate": float((gross > 0).mean()),
                "se_bp": float(gross.std(ddof=1) / np.sqrt(len(x)) * 1e4) if len(x) > 1 else None,
            })
    return out


def main() -> None:
    df = build_events()
    live = (FAIRVALUE_WEIGHTS["futures_proxy_return"], FAIRVALUE_WEIGHTS["crypto_beta_return"], FAIRVALUE_WEIGHTS["fx_risk_sentiment_return"])
    result = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "events": int(len(df)), "sessions": int(df["session"].nunique()),
        "first_session": df["session"].min(), "last_session": df["session"].max(),
        "share_missing": {k: float(df[k + "_missing"].mean()) for k in ("fut", "crypto", "fx")},
        "calibration": calibration(df),
        "edge_live_weights": edge(df, live),
        "edge_no_proxies_raw_move": edge(df, (0.0, 0.0, 0.0)),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, default=float), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k not in ("edge_live_weights", "edge_no_proxies_raw_move")}, indent=2, default=float))
    print("\nEDGE, live weights (bp per trade, by horizon after close and |spread| threshold):")
    for r in result["edge_live_weights"]:
        if r["n"]:
            print(f"  h={r['h']:>2}h thr={r['threshold']:.1%} n={r['n']:>4} sessions={r['sessions']:>2} gross={r['mean_gross_bp']:+7.1f} net={r['mean_net_bp']:+7.1f} hit={r['hit_rate']:.0%} se={r['se_bp']:.1f}")
        else:
            print(f"  h={r['h']:>2}h thr={r['threshold']:.1%} n=0")


if __name__ == "__main__":
    main()
