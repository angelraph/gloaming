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


def notional_to_qty(rtoken_symbol: str, notional_usd: float, last_price: float) -> float:
    """Converts a risk-controls-approved USD notional into an order quantity using
    the live price already fetched by the caller (avoids a second network round
    trip inside the execution step)."""
    if last_price <= 0:
        raise ValueError(f"last_price must be positive, got {last_price}")
    return round(notional_usd / last_price, 4)  # matches rToken quantityPrecision=4 (confirmed Day 1)


if __name__ == "__main__":
    import sys

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
