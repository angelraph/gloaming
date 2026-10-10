"""
Bitget Agent CLI execution wrapper for Gloaming Agent.

Hardcodes --paper-trading on every write call, regardless of any config passed in
- per docs/risk_controls.md control #6, this is not an env toggle an LLM output
could ever influence. Needs BITGET_API_KEY / BITGET_SECRET_KEY / BITGET_PASSPHRASE
in the environment (see .env.example); everything here fails loudly, not silently,
if those aren't set.

Calls the CLI's real entry file directly with `node` rather than through `npx bgc`
- npx's per-invocation resolution overhead (multiple seconds) is a non-issue for
market-data reads, but the Bitget Agentic OAuth session flow (authorize_start /
authorize_wait) proved to expire within that overhead during Day 4 setup, so the
faster direct-node path is used everywhere in this module on general principle.
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]  # .../gloaming
CLI_ENTRY = REPO_ROOT / "node_modules" / "@bitget-ai" / "bitget-agent-cli" / "lib" / "index.js"

load_dotenv(REPO_ROOT / ".env")  # no-op if the file doesn't exist yet


class ExecutionError(RuntimeError):
    pass


class NotConfiguredError(ExecutionError):
    """Raised when BITGET_API_KEY/SECRET/PASSPHRASE aren't set - distinct from a
    generic ExecutionError so callers (agent_loop) can log a clear, specific reason
    rather than a raw CLI failure."""


def _require_credentials() -> None:
    missing = [
        name for name in ("BITGET_API_KEY", "BITGET_SECRET_KEY", "BITGET_PASSPHRASE")
        if not os.environ.get(name)
    ]
    if missing:
        raise NotConfiguredError(
            f"Missing {', '.join(missing)} - copy .env.example to .env and fill in your "
            f"Bitget API credentials (spot-trading-only, withdrawals disabled) before the "
            f"Agent can execute paper trades."
        )


def _run_bgc_write(args: list[str]) -> dict:
    """Every write call goes through here. --paper-trading and --confirm are always
    appended and can never be overridden by a caller-supplied arg list."""
    _require_credentials()
    full_args = [*args, "--paper-trading", "--confirm", "--pretty"]
    proc = subprocess.run(
        ["node", str(CLI_ENTRY), *full_args],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise ExecutionError(
            f"bgc {' '.join(full_args)} returned non-JSON output "
            f"(stdout={proc.stdout[:300]!r}, stderr={proc.stderr[:300]!r})"
        ) from e
    if proc.returncode != 0 or payload.get("ok") is False:
        raise ExecutionError(f"bgc {' '.join(full_args)} failed: {payload}")
    return payload


def _run_bgc_read(args: list[str]) -> dict:
    """Read-only calls also need credentials for account-scoped data (positions,
    balances). --confirm is never added (nothing is written), but --paper-trading
    IS added here too - confirmed live Sept 11: Bitget's demo/paper trading isn't a
    header trick on your live key, it requires a genuinely separate Demo API Key
    (https://www.bitget.com/api-doc/classic/demotrading/restapi), and once BITGET_*
    in .env holds Demo credentials (see .env.example), EVERY call against this
    account - reads included - must carry the paptrading header or Bitget rejects
    it with 'exchange environment is incorrect'. Since this whole module is
    permanently paper-trading-only by design, there's no scenario where a read
    here should ever hit the live account instead."""
    _require_credentials()
    proc = subprocess.run(
        ["node", str(CLI_ENTRY), *args, "--paper-trading", "--pretty"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise ExecutionError(
            f"bgc {' '.join(args)} returned non-JSON output "
            f"(stdout={proc.stdout[:300]!r}, stderr={proc.stderr[:300]!r})"
        ) from e
    if proc.returncode != 0 or payload.get("ok") is False:
        raise ExecutionError(f"bgc {' '.join(args)} failed: {payload}")
    return payload


@dataclass
class OrderResult:
    symbol: str
    side: str
    qty: str
    raw_response: dict


def place_market_order(symbol: str, side: str, qty: float) -> OrderResult:
    """Places a market SPOT order. ALWAYS routed to Bitget's paper-trading/demo
    environment (see _run_bgc_write) - there is no code path in this module that
    can send a live order."""
    if side not in ("buy", "sell"):
        raise ValueError(f"side must be 'buy' or 'sell', got {side!r}")
    if qty <= 0:
        raise ValueError(f"qty must be positive, got {qty}")

    payload = _run_bgc_write([
        "order", "--action", "place", "--category", "SPOT", "--symbol", symbol,
        "--side", side, "--orderType", "market", "--qty", str(qty),
    ])
    return OrderResult(symbol=symbol, side=side, qty=str(qty), raw_response=payload)


def get_account_overview(coin: str = "USDT") -> dict:
    """Raw account_overview payload - see risk_controls.PortfolioState for the
    normalized shape agent_loop.py actually consumes.

    Deliberately omits --category: passing category=SPOT here also triggers the
    composite call's positions sub-fetch, which errors under UTA ("Parameter SPOT
    does not exist" - positions apply to futures categories, not spot, confirmed
    live Sept 11). We don't need positions from this call anyway; Gloaming tracks
    its own book from the decision log."""
    return _run_bgc_read(["account_overview", "--coin", coin])


# --- exchange-side orders on Bitget's DEMO engine (stock perpetuals) ---------------------------
#
# Bitget's demo environment does not list rToken SPOT symbols (HTTP 400 "symbolId is not exist",
# re-confirmed 2026-10-10), but it does list perpetual futures on the same nine US stocks
# (AAPLUSDT ... TSLAUSDT, USDT-FUTURES). So an approved decision can ALSO be sent as a real order
# to the demo matching engine: real order book, real fills, real fees and funding, virtual funds.
# This is additive: the paper ledger stays the book of record, and a failure here never touches it.
#
# Off by default. It runs only when GLOAMING_EXCHANGE_ORDERS=demo, and every call below goes
# through _run_bgc_write / _run_bgc_read, which hardcode --paper-trading: a live key is rejected
# by Bitget ("exchange environment is incorrect"), so no path here can reach a live account.

PERP_CATEGORY = "USDT-FUTURES"
_instrument_cache: dict = {}


def exchange_orders_enabled() -> bool:
    return os.environ.get("GLOAMING_EXCHANGE_ORDERS", "").strip().lower() == "demo"


def perp_symbol(underlying: str) -> str:
    """Bitget's US-stock perpetual for an underlying: AAPL -> AAPLUSDT."""
    return f"{underlying}USDT"


def _data(payload: dict):
    """The 'data' member of a bgc payload, unwrapping one extra level if present."""
    d = payload.get("data") if isinstance(payload, dict) else None
    if isinstance(d, dict) and set(d) == {"data"}:
        d = d["data"]
    return d


def _find_dicts(obj) -> list[dict]:
    """Every dict nested anywhere in a payload, so response shapes (a list, a {'list': [...]},
    or a single object) all parse the same way."""
    found = []
    if isinstance(obj, dict):
        found.append(obj)
        for v in obj.values():
            found.extend(_find_dicts(v))
    elif isinstance(obj, list):
        for v in obj:
            found.extend(_find_dicts(v))
    return found


def _first_float(d: dict, keys: tuple) -> float | None:
    for k in keys:
        v = d.get(k)
        if v not in (None, "", "0", 0):
            try:
                return float(v)
            except (TypeError, ValueError):
                continue
    return None


def get_perp_instrument(symbol: str) -> dict:
    if symbol not in _instrument_cache:
        rows = _find_dicts(_data(_run_bgc_read(["market", "--action", "instruments", "--category", PERP_CATEGORY, "--symbol", symbol])))
        row = next((r for r in rows if r.get("symbol") == symbol), None)
        if not row:
            raise ExecutionError(f"{symbol} is not listed as a {PERP_CATEGORY} instrument")
        _instrument_cache[symbol] = row
    return _instrument_cache[symbol]


def get_perp_last_price(symbol: str) -> float:
    rows = _find_dicts(_data(_run_bgc_read(["market", "--action", "tickers", "--category", PERP_CATEGORY, "--symbol", symbol])))
    for r in rows:
        if r.get("symbol") == symbol:
            px = _first_float(r, ("lastPrice", "markPrice"))
            if px:
                return px
    raise ExecutionError(f"no price for {symbol}")


def get_perp_positions(symbol: str) -> dict:
    """{'long': size, 'short': size} for the symbol. Raises if a non-empty answer cannot be read,
    so an order is never sized against a position we could not understand."""
    payload = _run_bgc_read(["position", "--action", "info", "--category", PERP_CATEGORY, "--symbol", symbol])
    out = {"long": 0.0, "short": 0.0}
    dicts = _find_dicts(_data(payload))
    if not any("symbol" in d for d in dicts):
        return out  # an empty answer ({} or an empty list) means no open positions
    size_keys = ("total", "size", "available", "qty", "holdQty")
    for r in (d for d in dicts if d.get("symbol") == symbol):
        side = str(r.get("posSide", "")).lower()
        if side not in out:
            raise ExecutionError(f"unrecognised posSide {r.get('posSide')!r} for {symbol}")
        if not any(k in r for k in size_keys):
            raise ExecutionError(f"could not read the position size for {symbol}: {sorted(r)}")
        out[side] += _first_float(r, size_keys) or 0.0
    return out


def _floor_to(value: float, decimals: int) -> float:
    f = 10 ** decimals
    return int(value * f + 1e-9) / f


def _send_perp_order(symbol: str, side: str, pos_side: str, qty: float) -> dict:
    """One market order on the demo perp, then a read-back of it. Never raises: returns a dict."""
    out = {"symbol": symbol, "side": side, "posSide": pos_side, "qty": qty}
    try:
        placed = _run_bgc_write([
            "order", "--action", "place", "--category", PERP_CATEGORY, "--symbol", symbol,
            "--side", side, "--orderType", "market", "--qty", str(qty), "--posSide", pos_side,
        ])
    except Exception as e:  # noqa: BLE001
        out.update(ok=False, error=str(e)[:400])
        return out
    out["raw_place"] = placed
    order_id = next((d.get("orderId") for d in _find_dicts(_data(placed)) if d.get("orderId")), None)
    out["orderId"] = order_id
    out["ok"] = bool(order_id)
    if not order_id:
        out["error"] = "the exchange accepted the call but returned no orderId"
        return out
    try:
        time.sleep(0.6)  # a market order can take a moment to show as filled
        detail = _run_bgc_read(["order", "--action", "detail", "--category", PERP_CATEGORY,
                                "--symbol", symbol, "--orderId", str(order_id)])
        out["raw_detail"] = detail
        rows = [d for d in _find_dicts(_data(detail)) if str(d.get("orderId", "")) == str(order_id)] or _find_dicts(_data(detail))
        row = rows[0] if rows else {}
        out["status"] = row.get("orderStatus") or row.get("status")
        out["avg_price"] = _first_float(row, ("avgPrice", "priceAvg", "fillPrice", "averagePrice"))
        out["filled_qty"] = _first_float(row, ("cumExecQty", "baseVolume", "filledQty", "execQty", "fillQty"))
        out["filled_value"] = _first_float(row, ("cumExecValue", "quoteVolume", "filledAmount"))
        # Bitget returns fees as feeDetail: [{"feeCoin": "USDT", "fee": "0.004"}]; older shapes use a flat key
        fee = _first_float(row, ("fee", "totalFee", "cumExecFee", "feeAmount"))
        detail_fees = [_first_float(d, ("fee",)) for d in (row.get("feeDetail") or []) if isinstance(d, dict)]
        if fee is None and any(f is not None for f in detail_fees):
            fee = sum(f for f in detail_fees if f is not None)
            coins = {d.get("feeCoin") for d in row["feeDetail"] if isinstance(d, dict)}
            out["fee_coin"] = coins.pop() if len(coins) == 1 else sorted(str(c) for c in coins)
        out["fee"] = fee
    except Exception as e:  # noqa: BLE001
        out["detail_error"] = str(e)[:300]
    return out


def mirror_decision_on_exchange(underlying: str, side: str, notional_usd: float) -> dict:
    """Send an approved decision to Bitget's demo engine as an order on the stock perpetual.

    Never raises and never changes the ledger: the returned dict is stored on the decision
    record. In hedge mode (the demo account's mode) a buy first closes any short, then opens a
    long with the rest; a sell does the mirror image. Orders below the exchange's minimums are
    skipped and the reason recorded."""
    result = {"venue": "bitget_demo_perp", "enabled": exchange_orders_enabled()}
    if not result["enabled"]:
        result["skipped_reason"] = "exchange orders are off (GLOAMING_EXCHANGE_ORDERS is not 'demo')"
        return result
    if side not in ("buy", "sell"):
        result["skipped_reason"] = f"unsupported side {side!r}"
        return result
    symbol = perp_symbol(underlying)
    result["symbol"] = symbol
    try:
        inst = get_perp_instrument(symbol)
        price = get_perp_last_price(symbol)
        decimals = int(inst.get("quantityPrecision") or 2)
        min_qty = float(inst.get("minOrderQty") or 0)
        min_amount = float(inst.get("minOrderAmount") or 0)
        qty = _floor_to(notional_usd / price, decimals)
        result.update(reference_price=price, requested_notional_usd=round(notional_usd, 2), qty=qty)
        if qty < min_qty or qty * price < min_amount:
            result["skipped_reason"] = (
                f"below the exchange minimum (qty {qty} vs {min_qty}, ${qty * price:.2f} vs ${min_amount:.0f})"
            )
            return result
        pos = get_perp_positions(symbol)
        result["position_before"] = pos
        opposite = "short" if side == "buy" else "long"
        close_qty = _floor_to(min(qty, pos[opposite]), decimals)
        open_qty = _floor_to(qty - close_qty, decimals)
        orders = []
        if close_qty >= min_qty and close_qty > 0:
            orders.append(_send_perp_order(symbol, side, opposite, close_qty))
        if open_qty >= min_qty and open_qty > 0:
            orders.append(_send_perp_order(symbol, side, "long" if side == "buy" else "short", open_qty))
        result["orders"] = orders
        result["ok"] = bool(orders) and all(o.get("ok") for o in orders)
        if not orders:
            result["skipped_reason"] = "nothing left to send after splitting around the existing position"
    except Exception as e:  # noqa: BLE001 - the exchange leg must never cost the cycle its records
        result["ok"] = False
        result["error"] = str(e)[:400]
    return result


def notional_to_qty(rtoken_symbol: str, notional_usd: float, last_price: float) -> float:
    """Converts a risk-controls-approved USD notional into an order quantity using
    the live price already fetched by the caller (avoids a second network round
    trip inside the execution step)."""
    if last_price <= 0:
        raise ValueError(f"last_price must be positive, got {last_price}")
    return round(notional_usd / last_price, 4)  # matches rToken quantityPrecision=4 (confirmed Day 1)


def exchange_selftest(underlying: str = "AAPL") -> int:
    """Open and close the minimum position on the demo perp and print what the exchange said.
    Run this once the demo account has USDT in its trading wallet:
        GLOAMING_EXCHANGE_ORDERS=demo python gloaming_agent/execution.py --exchange-selftest
    Prints raw payloads so the parsers above can be checked against real responses."""
    os.environ["GLOAMING_EXCHANGE_ORDERS"] = "demo"
    symbol = perp_symbol(underlying)
    inst = get_perp_instrument(symbol)
    price = get_perp_last_price(symbol)
    decimals = int(inst.get("quantityPrecision") or 2)
    step = 10 ** -decimals
    need = max(float(inst.get("minOrderQty") or 0), float(inst.get("minOrderAmount") or 5) / price)
    qty = -(-need // step) * step  # smallest multiple of the quantity step that clears both minimums
    min_notional = qty * price * 1.002  # a hair over, so rounding down in the mirror cannot undercut it
    print(f"{symbol}: price {price}, quantity {qty:.{decimals}f}, testing with about ${min_notional:.2f}")
    opened = mirror_decision_on_exchange(underlying, "buy", min_notional)
    print("OPEN :", json.dumps(opened, ensure_ascii=False, indent=2)[:3000])
    closed = mirror_decision_on_exchange(underlying, "sell", min_notional)
    print("CLOSE:", json.dumps(closed, ensure_ascii=False, indent=2)[:3000])
    return 0 if opened.get("ok") and closed.get("ok") else 1


if __name__ == "__main__":
    import sys

    if "--exchange-selftest" in sys.argv:
        sys.exit(exchange_selftest())
    if "--smoke-test" in sys.argv:
        try:
            _require_credentials()
        except NotConfiguredError as e:
            print(f"NOT CONFIGURED (expected until .env is set up): {e}")
            sys.exit(0)
        print("Credentials found - fetching account overview...")
        print(get_account_overview())
    else:
        print("Usage: python execution.py --smoke-test")
