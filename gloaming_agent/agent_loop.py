"""
Gloaming Agent — the off-hours-only autonomous loop (Agentic Trading track).

Day 4 status: rule-based decision-making (fixed spread threshold, no LLM yet).
Day 5 swaps the decide() step for Qwen3.8-max reasoning over the same snapshot +
bitget-signal event data — everything else here (risk gating, execution, logging)
stays as-is, since that separation is the point of this architecture.

Runs ONLY while NYSE is closed (see is_nyse_closed) — that off-hours window is the
entire thesis this project is built on. Every cycle is appended to
decision_log/*.jsonl as a full event->decision->execution record.

Execution note (confirmed live Sept 11): Bitget's demo/paper trading environment
does not list rToken symbols at all — only standard crypto pairs. Order execution
here therefore goes through gloaming_agent/paper_ledger.py's self-maintained
virtual ledger, marked to real live rToken prices from the SAME public market-data
feed used everywhere else in this file (not synthetic data), rather than Bitget's
own demo order-matching engine. See paper_ledger.py's docstring for the full
reasoning. execution.py (the Bitget CLI wrapper) is kept for account-level reads/
future crypto-side execution but is no longer in the rToken decision path.
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

REPO_ROOT = Path(__file__).resolve().parents[1]
ENGINE_DIR = REPO_ROOT / "engine"
sys.path.insert(0, str(ENGINE_DIR))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from data.crypto_beta import crypto_beta_return, get_crypto_ticks  # noqa: E402
from data.fx import fx_risk_sentiment_return  # noqa: E402
from data.rtoken_client import run_bgc  # noqa: E402
from fairvalue.config import FAIRVALUE_WEIGHTS, RTOKEN_UNIVERSE  # noqa: E402

import paper_ledger  # noqa: E402
from risk_controls import TradeDecision, evaluate_decision  # noqa: E402

DECISION_LOG_DIR = Path(__file__).resolve().parent / "decision_log"
NYSE_TZ = ZoneInfo("America/New_York")
SPREAD_THRESHOLD = 0.015  # 1.5% — crude Day 4 fixed threshold; Day 5's Qwen replaces this


def is_nyse_closed(now_utc: datetime | None = None) -> bool:
    """True outside 9:30-16:00 America/New_York on weekdays, and all day on
    Sat/Sun. Does NOT account for US market holidays yet (flagged as a known gap —
    worst case the Agent stays idle on a trading day it could have run, which is
    the safe direction for a risk-gated system to be wrong in)."""
    now_utc = now_utc or datetime.now(timezone.utc)
    local = now_utc.astimezone(NYSE_TZ)
    if local.weekday() >= 5:  # Saturday=5, Sunday=6
        return True
    market_open = local.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = local.replace(hour=16, minute=0, second=0, microsecond=0)
    return not (market_open <= local < market_close)


def _get_rtoken_tick_with_pcnt(rtoken_symbol: str) -> dict:
    """rtoken_client.get_ticker() doesn't carry price24hPcnt (Day 1 design only
    needed last/bid/ask) — fetched directly here since the live rule-based signal
    needs a 24h-change proxy, unlike the backtest which uses full daily history."""
    payload = run_bgc(["market", "--action", "tickers", "--category", "SPOT", "--symbol", rtoken_symbol])
    row = payload["data"][0]
    return {
        "symbol": row["symbol"],
        "last_price": float(row["lastPrice"]),
        "pcnt_change_24h": float(row["price24hPcnt"]),
    }


def _futures_proxy_pcnt_24h(futures_ticker: str) -> float:
    """Live 24h-ish proxy return: latest close vs. close ~24h/1-trading-day back.
    Falls back to 0.0 (treated as 'no new information') if the feed is unavailable
    — matches the weekend zero-fill convention from the Day 3 backtest."""
    sys.path.insert(0, str(ENGINE_DIR / "data"))
    from futures_proxy import fetch_futures_history  # local import: yfinance is a soft dependency

    try:
        df = fetch_futures_history(tickers=[futures_ticker], period="5d", interval="1h")
        closes = df[futures_ticker].dropna()
        if len(closes) < 2:
            return 0.0
        return float(closes.iloc[-1] / closes.iloc[0] - 1)
    except Exception:
        return 0.0


def build_snapshot(underlying: str, crypto_pcnt: float, fx_pcnt: float,
                     futures_pcnt_by_ticker: dict) -> dict:
    """crypto_pcnt/fx_pcnt/futures_pcnt_by_ticker are fetched ONCE per run_once()
    cycle by the caller and shared across all symbols — these proxies don't vary
    per-underlying (only the futures ticker choice does, and even that's shared
    across the handful of symbols using the same index), so refetching them per
    symbol was pure waste (9 symbols x redundant yfinance/bgc calls each cycle)."""
    cfg = RTOKEN_UNIVERSE[underlying]
    rtoken = _get_rtoken_tick_with_pcnt(cfg["rtoken_symbol"])
    futures_pcnt = futures_pcnt_by_ticker[cfg["futures_proxy"]]

    fair_value_return = (
        futures_pcnt * FAIRVALUE_WEIGHTS["futures_proxy_return"]
        + crypto_pcnt * FAIRVALUE_WEIGHTS["crypto_beta_return"]
        + fx_pcnt * FAIRVALUE_WEIGHTS["fx_risk_sentiment_return"]
    )
    spread = rtoken["pcnt_change_24h"] - fair_value_return

    return {
        "underlying": underlying,
        "rtoken_symbol": cfg["rtoken_symbol"],
        "rtoken_last_price": rtoken["last_price"],
        "rtoken_pcnt_24h": rtoken["pcnt_change_24h"],
        "futures_proxy_pcnt_24h": futures_pcnt,
        "crypto_beta_pcnt_24h": crypto_pcnt,
        "fx_risk_sentiment_pcnt_24h": fx_pcnt,
        "fair_value_return_24h": fair_value_return,
        "spread": spread,
    }


def decide(snapshot: dict) -> TradeDecision | None:
    """Crude Day 4 rule: rToken trading meaningfully rich vs. the blended proxy
    signal -> sell/reduce; meaningfully cheap -> buy. No position otherwise. This
    is intentionally simple and disclosed as a placeholder for Day 5's Qwen-driven
    reasoning, which sees this same snapshot dict plus bitget-signal event context."""
    spread = snapshot["spread"]
    if abs(spread) < SPREAD_THRESHOLD:
        return None

    side = "sell" if spread > 0 else "buy"
    rationale = (
        f"{snapshot['rtoken_symbol']} 24h return {snapshot['rtoken_pcnt_24h']:.2%} vs. blended "
        f"proxy fair-value estimate {snapshot['fair_value_return_24h']:.2%} "
        f"(futures {snapshot['futures_proxy_pcnt_24h']:.2%}, crypto {snapshot['crypto_beta_pcnt_24h']:.2%}, "
        f"fx {snapshot['fx_risk_sentiment_pcnt_24h']:.2%}) -> spread {spread:.2%}, "
        f"{'above' if spread > 0 else 'below'} the {SPREAD_THRESHOLD:.1%} threshold -> {side} "
        f"(bet on reversion toward fair value)."
    )
    return TradeDecision(
        symbol=snapshot["rtoken_symbol"], side=side, notional_usd=250.0,  # fixed size, Day 4 placeholder
        rationale=rationale, stop_loss_pct=0.03, confidence=min(abs(spread) / (2 * SPREAD_THRESHOLD), 1.0),
    )


def run_once(dry_run: bool = False) -> list[dict]:
    """One full pass over the universe: snapshot -> decide -> risk-gate -> execute
    (or skip) -> log. Returns the list of log records written this cycle.

    Two passes over RTOKEN_UNIVERSE: the first builds every symbol's live snapshot
    (needed regardless of whether a signal fires, both for the decision and to
    have a real mark price for paper_ledger's portfolio valuation); the second
    applies decide() -> risk-gate -> execute using ONE portfolio_state snapshot
    computed after pass one. Risk caps this cycle are therefore evaluated against
    the book as it stood at the start of the cycle, not updated fill-by-fill within
    the same cycle — a disclosed simplification, not a bug (see docs/risk_controls.md)."""
    DECISION_LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = DECISION_LOG_DIR / f"{datetime.now(timezone.utc):%Y-%m-%d}.jsonl"

    # Fetch the shared, symbol-independent proxies exactly once per cycle.
    crypto_pcnt = crypto_beta_return(get_crypto_ticks())
    fx_pcnt = fx_risk_sentiment_return()
    distinct_futures_tickers = {cfg["futures_proxy"] for cfg in RTOKEN_UNIVERSE.values()}
    futures_pcnt_by_ticker = {t: _futures_proxy_pcnt_24h(t) for t in distinct_futures_tickers}

    snapshots: dict[str, dict] = {}
    snapshot_errors: dict[str, str] = {}
    mark_prices: dict[str, float] = {}
    for underlying in RTOKEN_UNIVERSE:
        try:
            snapshot = build_snapshot(underlying, crypto_pcnt, fx_pcnt, futures_pcnt_by_ticker)
            snapshots[underlying] = snapshot
            mark_prices[snapshot["rtoken_symbol"]] = snapshot["rtoken_last_price"]
        except Exception as e:  # noqa: BLE001 - one symbol's data failure shouldn't kill the cycle
            snapshot_errors[underlying] = f"snapshot failed: {e}"

    portfolio_state = paper_ledger.get_portfolio_state(mark_prices)

    records = []
    for underlying in RTOKEN_UNIVERSE:
        record = {"timestamp": datetime.now(timezone.utc).isoformat(), "underlying": underlying}

        if underlying in snapshot_errors:
            record["error"] = snapshot_errors[underlying]
            records.append(record)
            continue

        snapshot = snapshots[underlying]
        record["snapshot"] = snapshot

        decision = decide(snapshot)
        if decision is None:
            record["decision"] = None
            records.append(record)
            continue
        record["decision"] = asdict(decision)

        risk_result = evaluate_decision(decision, portfolio_state, recent_volatility=abs(snapshot["spread"]))
        record["risk_result"] = asdict(risk_result)

        if not risk_result.approved:
            record["execution"] = "SKIPPED: rejected by risk controls"
            records.append(record)
            continue

        if dry_run:
            record["execution"] = "SKIPPED: dry_run=True"
            records.append(record)
            continue

        try:
            qty = round(risk_result.adjusted_notional_usd / snapshot["rtoken_last_price"], 4)
            fill = paper_ledger.record_fill(
                decision.symbol, decision.side, qty, snapshot["rtoken_last_price"], decision.rationale
            )
            record["execution"] = asdict(fill)
        except Exception as e:  # noqa: BLE001 - log and move on, never crash the loop over one fill
            record["execution"] = f"FAILED: {e}"

        records.append(record)

    with open(log_path, "a") as f:
        for record in records:
            f.write(json.dumps(record, default=str) + "\n")

    return records


if __name__ == "__main__":
    if "--smoke-test" in sys.argv:
        print(f"is_nyse_closed() right now: {is_nyse_closed()}")
        print("Running one cycle (dry_run=True — no orders will be placed)...")
        records = run_once(dry_run=True)
        for r in records:
            u = r["underlying"]
            if r.get("error"):
                print(f"  {u}: ERROR — {r['error']}")
            elif r["decision"] is None:
                spread = r["snapshot"]["spread"]
                print(f"  {u}: no signal (spread {spread:.2%} within threshold)")
            else:
                print(f"  {u}: {r['decision']['side']} ${r['decision']['notional_usd']:.0f} "
                      f"— {r['execution']}")
        print(f"\nLogged to {DECISION_LOG_DIR}")
    else:
        print("Usage: python agent_loop.py --smoke-test")
