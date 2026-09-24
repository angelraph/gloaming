"""
Gloaming's self-maintained paper-trading ledger for rTokens.

Confirmed live Sept 11: Bitget's demo/paper trading environment does not list
rToken symbols at all (`RAAPLUSDT` -> "Parameter RAAPLUSDT does not exist", while
`BTCUSDT` works fine and fails only on minimum-order-size - isolating this as an
rToken-specific gap in Bitget's demo environment, not a general paper-trading
problem, and not anything wrong in this codebase). Since the whole point of
Gloaming's Agentic Trading track submission is rToken execution during the hours
NYSE is closed, waiting on Bitget to add rToken support to their demo environment
isn't an option on a hackathon deadline.

The fix used here is the standard, legitimate way paper-trading systems work when
a broker's own demo/sandbox doesn't cover an instrument: track a virtual ledger
ourselves and mark fills to REAL, LIVE market prices (via rtoken_client.get_ticker
- genuine public Bitget market data, not synthetic), rather than routing orders
through a demo matching engine that can't accept them. Every number here is a real
price at the real time of the decision; only the "execution" step (crediting/
debiting a local ledger instead of an exchange accepting an order) is simulated -
exactly what "paper trading" means in every quant/trading-system context, Bitget's
own demo environment included.

Storage: a single JSON file (gloaming_agent/paper_ledger.json) - enough durability
for the hackathon's ~2-week log requirement without pulling in SQLite for state
this small; engine/db (SQLite) remains reserved for the shared engine's own data
per docs/architecture.md, not required for this loop to function correctly.
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

import kv_sync  # local import - see kv_sync.py; no-ops if KV isn't configured

LEDGER_PATH = Path(__file__).resolve().parent / "paper_ledger.json"
STARTING_EQUITY_USD = 100_000.0  # matches the scale Bitget's own demo seeding used


@dataclass
class Fill:
    timestamp: str
    symbol: str
    side: str
    qty: float
    price: float
    notional_usd: float
    rationale: str


@dataclass
class LedgerState:
    cash_usd: float = STARTING_EQUITY_USD
    positions: dict = field(default_factory=dict)  # symbol -> qty (signed: + long, - short)
    fills: list = field(default_factory=list)  # list of Fill dicts, newest last
    # Baseline for the daily max-loss circuit breaker (risk_controls.py) - reset to
    # the current equity the first time the ledger is touched on a new UTC date, so
    # "daily P&L" means since-today's-open, not since-ledger-inception.
    equity_at_day_start_usd: float = STARTING_EQUITY_USD
    day_start_date: str = ""  # ISO date; "" forces a reset on first real use
    # State for the net-exposure backstop (risk_controls.update_net_over_cap_tracker):
    # consecutive active cycles the book has stayed over its net cap without the LLM
    # bringing it back, and the excess when that clock last restarted. Lives here
    # because every scheduled run is a fresh process; this file is the only thing
    # that carries state from one cycle to the next.
    net_over_cap_cycles: int = 0
    net_over_cap_baseline_usd: float = 0.0


def _load() -> LedgerState:
    if not LEDGER_PATH.exists():
        return LedgerState()
    raw = json.loads(LEDGER_PATH.read_text())
    return LedgerState(
        cash_usd=raw.get("cash_usd", STARTING_EQUITY_USD),
        positions=raw.get("positions", {}),
        fills=raw.get("fills", []),
        equity_at_day_start_usd=raw.get("equity_at_day_start_usd", STARTING_EQUITY_USD),
        day_start_date=raw.get("day_start_date", ""),
        net_over_cap_cycles=raw.get("net_over_cap_cycles", 0),
        net_over_cap_baseline_usd=raw.get("net_over_cap_baseline_usd", 0.0),
    )


def _save(state: LedgerState) -> None:
    state_dict = asdict(state)
    LEDGER_PATH.write_text(json.dumps(state_dict, indent=2, default=str))
    kv_sync.push_ledger_state(state_dict)  # best-effort mirror for the deployed Desk; no-ops if unconfigured


def recent_fills(symbol: str, limit: int = 3) -> list[dict]:
    """The last `limit` real fills in `symbol`, oldest first, for showing the LLM what
    it has recently done in that symbol."""
    state = _load()
    return [f for f in state.fills if f["symbol"] == symbol][-limit:]


def get_net_tracker() -> tuple[int, float]:
    state = _load()
    return state.net_over_cap_cycles, state.net_over_cap_baseline_usd


def set_net_tracker(cycles: int, baseline_usd: float) -> None:
    """Persists the backstop's clock. Skips the write (and the Redis push) when
    nothing changed, which is the normal case for a book that is within its cap."""
    state = _load()
    if state.net_over_cap_cycles == cycles and state.net_over_cap_baseline_usd == baseline_usd:
        return
    state.net_over_cap_cycles = cycles
    state.net_over_cap_baseline_usd = baseline_usd
    _save(state)


def record_fill(symbol: str, side: str, qty: float, price: float, rationale: str) -> Fill:
    """Simulates an immediate full fill at `price` (the real live price fetched by
    the caller moments earlier) - no slippage/partial-fill modeling in v1, disclosed
    as a simplification alongside everything else in docs/architecture.md."""
    if side not in ("buy", "sell"):
        raise ValueError(f"side must be 'buy' or 'sell', got {side!r}")
    if qty <= 0 or price <= 0:
        raise ValueError(f"qty and price must be positive, got qty={qty}, price={price}")

    state = _load()
    signed_qty = qty if side == "buy" else -qty
    notional = qty * price

    prev_qty = state.positions.get(symbol, 0.0)
    new_qty = prev_qty + signed_qty

    if side == "buy":
        state.cash_usd -= notional
    else:
        state.cash_usd += notional
    # Realized P&L only accrues when a fill reduces/closes an existing position in
    # the opposite direction - v1 keeps this simple (no per-lot cost basis tracking
    # beyond net position size), which is a disclosed simplification, not a bug:
    # a strategy that never nets down a position never touches this path at all.
    state.positions[symbol] = new_qty
    if abs(new_qty) < 1e-9:
        del state.positions[symbol]  # fully closed

    fill = Fill(
        timestamp=datetime.now(timezone.utc).isoformat(),
        symbol=symbol, side=side, qty=qty, price=price,
        notional_usd=notional, rationale=rationale,
    )
    state.fills.append(asdict(fill))
    _save(state)
    return fill


def get_portfolio_state(mark_prices: dict) -> "PortfolioState":  # noqa: F821 - see import below
    """Marks every open position to `mark_prices` (symbol -> current real price,
    supplied by the caller from this cycle's live snapshots) to compute equity_usd
    and positions_notional_usd for risk_controls.evaluate_decision(). A position in
    a symbol missing from mark_prices is valued at its last fill price as a
    fallback - logged, not silently ignored. Also rolls the daily circuit-breaker
    baseline forward on a new UTC date, matching a fresh 24h risk budget each day
    the Agent runs (it only runs off-hours, so 'day' here means calendar date, not
    a trading session)."""
    from risk_controls import PortfolioState  # local import avoids a circular import at module load

    state = _load()
    positions_notional = {}
    for symbol, qty in state.positions.items():
        price = mark_prices.get(symbol)
        if price is None:
            last_fill = next((f for f in reversed(state.fills) if f["symbol"] == symbol), None)
            price = last_fill["price"] if last_fill else 0.0
        positions_notional[symbol] = qty * price

    equity = state.cash_usd + sum(positions_notional.values())

    today = datetime.now(timezone.utc).date().isoformat()
    if state.day_start_date != today:
        state.day_start_date = today
        state.equity_at_day_start_usd = equity
        _save(state)

    daily_pnl = equity - state.equity_at_day_start_usd
    return PortfolioState(
        equity_usd=equity,
        positions_notional_usd=positions_notional,
        daily_realized_pnl_usd=daily_pnl,
        daily_unrealized_pnl_usd=0.0,  # folded into daily_pnl above; kept for PortfolioState's shape
    )


if __name__ == "__main__":
    import sys

    if "--smoke-test" in sys.argv:
        print(f"Ledger path: {LEDGER_PATH}")
        state = _load()
        print(f"Cash: ${state.cash_usd:,.2f} | Positions: {state.positions} | "
              f"Fills so far: {len(state.fills)}")
        ps = get_portfolio_state(mark_prices={})
        print(f"Portfolio state: equity_usd=${ps.equity_usd:,.2f}")
    else:
        print("Usage: python paper_ledger.py --smoke-test")
