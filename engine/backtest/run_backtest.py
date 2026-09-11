"""
Gloaming Alpha Factory backtest - orchestrates real historical data into the
fair-value model + backtest engine and writes a report.

Usage (from engine/, with the venv active):
    python -m backtest.run_backtest

Pulls ~90 days of real daily history (the full live span of Bitget rTokens as of
this build) for the starter universe in fairvalue/config.py, calibrates fair-value
weights via OLS on the first N-30 days (in-sample), evaluates on the last 30 days
(out-of-sample) to satisfy the hackathon's ">=60 days total, >=30 out-of-sample"
requirement, and writes results to alpha_factory/results/.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backtest.engine import run_backtest, run_portfolio_backtest, split_in_out_sample
from data.crypto_beta import get_crypto_beta_history
from data.futures_proxy import get_futures_returns_daily
from data.fx import get_fx_returns_daily
from data.rtoken_client import get_candles_history
from fairvalue.config import RTOKEN_UNIVERSE
from fairvalue.model import blended_fair_value_return, calibrate_weights, fair_value_price_path

RESULTS_DIR = Path(__file__).resolve().parents[2] / "alpha_factory" / "results"
OUT_OF_SAMPLE_DAYS = 30


def _to_date_index(series: pd.Series) -> pd.Series:
    """Normalize any tz-aware/naive daily-timestamp index down to a plain calendar
    date so rToken (Bitget), futures-proxy/FX (yfinance) and crypto (Bitget) series
    - each with their own timestamp convention - align on the join."""
    out = series.copy()
    out.index = pd.to_datetime(out.index).tz_localize(None).normalize()
    return out


def build_symbol_dataset(underlying: str, futures_daily: pd.DataFrame,
                           crypto_beta_daily: pd.Series, fx_daily: pd.Series) -> pd.DataFrame:
    cfg = RTOKEN_UNIVERSE[underlying]
    rtoken_df = get_candles_history(cfg["rtoken_symbol"], interval="1D", limit="100")
    actual_price = _to_date_index(rtoken_df["close"])
    rtoken_return = actual_price.pct_change().rename("rtoken_return")

    # rTokens trade all 7 days/week (confirmed Day 3: bars land evenly Mon-Sun) -
    # that IS the project's whole thesis. The free futures/FX proxies only carry
    # weekday bars, because CME index futures and most FX venues are themselves
    # genuinely closed over the weekend - an inner join would silently drop every
    # weekend day, which is exactly the window this project is about. Reindexing
    # to the rToken's full daily calendar and filling weekend gaps with 0 ("no new
    # proxy information since Friday's close") is a deliberate modeling choice, not
    # a data-cleaning hack: on weekends, crypto_beta_return (which IS live 24/7)
    # becomes the sole driver of the synthetic fair value, which matches reality.
    futures_col = cfg["futures_proxy"]
    futures_return = (
        _to_date_index(futures_daily[futures_col])
        .reindex(actual_price.index, fill_value=0.0)
        .rename("futures_proxy_return")
    )
    fx_return = (
        _to_date_index(fx_daily)
        .reindex(actual_price.index, fill_value=0.0)
        .rename("fx_risk_sentiment_return")
    )

    df = pd.DataFrame({
        "actual_price": actual_price,
        "rtoken_return": rtoken_return,
        "futures_proxy_return": futures_return,
        "crypto_beta_return": crypto_beta_daily,
        "fx_risk_sentiment_return": fx_return,
    }).dropna(subset=["actual_price", "rtoken_return", "crypto_beta_return"])
    return df


def run_for_symbol(underlying: str, futures_daily: pd.DataFrame,
                     crypto_beta_daily: pd.Series, fx_daily: pd.Series) -> dict:
    df = build_symbol_dataset(underlying, futures_daily, crypto_beta_daily, fx_daily)
    in_sample, out_sample = split_in_out_sample(df, OUT_OF_SAMPLE_DAYS)

    weights = calibrate_weights(
        in_sample["rtoken_return"], in_sample["futures_proxy_return"],
        in_sample["crypto_beta_return"], in_sample["fx_risk_sentiment_return"],
    )
    fair_value_return = blended_fair_value_return(
        df["futures_proxy_return"], df["crypto_beta_return"], df["fx_risk_sentiment_return"], weights,
    )
    fv_price = fair_value_price_path(df["actual_price"].iloc[0], fair_value_return)

    full_result = run_backtest(df["actual_price"], fv_price)
    oos_index = out_sample.index
    oos_df = full_result["data"].loc[full_result["data"].index.isin(oos_index)]
    from backtest import metrics as m
    oos_report = (
        m.summarize(oos_df["strategy_return"], oos_df["position_lagged"])
        if len(oos_df) > 0 else {}
    )

    return {
        "underlying": underlying,
        "rtoken_symbol": RTOKEN_UNIVERSE[underlying]["rtoken_symbol"],
        "calibrated_weights": weights,
        "n_days_total": int(len(df)),
        "n_days_in_sample": int(len(in_sample)),
        "n_days_out_of_sample": int(len(out_sample)),
        "full_window_report": full_result["report"],
        "out_of_sample_report": oos_report,
        "_full_result": full_result,
    }


def main() -> None:
    print("Fetching shared proxy history (futures, crypto beta, FX)...")
    futures_daily = get_futures_returns_daily(period="6mo")
    crypto_beta_daily = _to_date_index(get_crypto_beta_history(limit="100"))
    fx_daily = _to_date_index(get_fx_returns_daily(period="6mo"))

    per_symbol = {}
    for underlying in RTOKEN_UNIVERSE:
        print(f"Backtesting {underlying} ({RTOKEN_UNIVERSE[underlying]['rtoken_symbol']})...")
        try:
            per_symbol[underlying] = run_for_symbol(underlying, futures_daily, crypto_beta_daily, fx_daily)
        except Exception as e:  # noqa: BLE001 - report and continue with remaining symbols
            print(f"  SKIPPED {underlying}: {e}")

    if not per_symbol:
        print("No symbols produced usable backtest data - aborting report.")
        return

    portfolio = run_portfolio_backtest({u: r["_full_result"] for u, r in per_symbol.items()})

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        "out_of_sample_days": OUT_OF_SAMPLE_DAYS,
        "portfolio_report": portfolio["report"],
        "per_symbol": {
            u: {k: v for k, v in r.items() if k != "_full_result"} for u, r in per_symbol.items()
        },
    }
    with open(RESULTS_DIR / "backtest_summary.json", "w") as f:
        json.dump(summary, f, indent=2, default=float)
    portfolio["equity"].to_csv(RESULTS_DIR / "portfolio_equity.csv")
    export_historical_scenarios(per_symbol)

    print("\n=== Portfolio report (equal-weight, full window) ===")
    for k, v in portfolio["report"].items():
        print(f"  {k}: {v}")
    print(f"\nSaved: {RESULTS_DIR / 'backtest_summary.json'}")
    print(f"Saved: {RESULTS_DIR / 'portfolio_equity.csv'}")
    print(f"Saved: {RESULTS_DIR / 'historical_scenarios.json'}")


def export_historical_scenarios(per_symbol: dict[str, dict]) -> None:
    """Real per-day (return, spread) history per symbol, for the Gloaming Desk's
    Decision Stress Test feature - it replays an actual historical overnight move
    against the CURRENT paper portfolio rather than a synthetic/invented shock.
    Reuses full_result['data'] (rtoken_return, spread_pct), already computed by
    run_backtest() above - no separate data pull needed."""
    scenarios: dict[str, list[dict]] = {}
    for underlying, result in per_symbol.items():
        df = result["_full_result"]["data"]
        rows = []
        for date, row in df.iterrows():
            if pd.isna(row.get("rtoken_return")) or pd.isna(row.get("spread_pct")):
                continue
            rows.append({
                "date": date.strftime("%Y-%m-%d"),
                "rtoken_return": float(row["rtoken_return"]),
                "spread_pct": float(row["spread_pct"]),
            })
        scenarios[underlying] = {
            "rtoken_symbol": RTOKEN_UNIVERSE[underlying]["rtoken_symbol"],
            "history": rows,
        }
    with open(RESULTS_DIR / "historical_scenarios.json", "w") as f:
        json.dump(scenarios, f, indent=2)


if __name__ == "__main__":
    main()
