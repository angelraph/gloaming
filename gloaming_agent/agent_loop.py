"""
Gloaming Agent - the off-hours-only autonomous loop (Agentic Trading track).

Decision-making: Qwen3.8-max reasons over each symbol's live snapshot
(decide_llm) and is the primary decision-maker whenever QWEN_API_KEY is
configured (see llm_client.py). decide_rule_based's fixed-threshold logic from
Day 4 is kept as an automatic fallback, used only when the LLM call fails or
isn't configured yet - every decision record says which path produced it (see
"decision_source" in run_once's output), which is the disclosure the Agentic
Trading track's LLM-role requirement asks for.

Runs ONLY while NYSE is closed (see is_nyse_closed) - that off-hours window is the
entire thesis this project is built on. Every cycle is appended to
decision_log/*.jsonl as a full event->decision->execution record.

Execution note (confirmed live Sept 11): Bitget's demo/paper trading environment
does not list rToken symbols at all - only standard crypto pairs. Order execution
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
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

REPO_ROOT = Path(__file__).resolve().parents[1]
ENGINE_DIR = REPO_ROOT / "engine"
sys.path.insert(0, str(ENGINE_DIR))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from data.overnight_anchor import AnchorUnavailable, OvernightAnchor, fetch_overnight_anchor  # noqa: E402
from data.rtoken_client import run_bgc  # noqa: E402
from fairvalue.config import FAIRVALUE_WEIGHTS, RTOKEN_UNIVERSE  # noqa: E402

import bitget_signal  # noqa: E402
import kv_sync  # noqa: E402
import llm_client  # noqa: E402
import paper_ledger  # noqa: E402
from risk_controls import (  # noqa: E402
    RiskConfig,
    TradeDecision,
    evaluate_decision,
    plan_net_trim,
    trade_capacity_usd,
    update_net_over_cap_tracker,
)

DECISION_LOG_DIR = Path(__file__).resolve().parent / "decision_log"
NYSE_TZ = ZoneInfo("America/New_York")
# The rule-based FALLBACK's threshold (Qwen is the primary decision-maker). The spread is
# now the dislocation since the real share's close, which is normally a few tenths of a
# percent, so this fallback fires only on a genuine gap: rarely, which is the safe side
# to be wrong on for a path that runs unattended when Qwen is unavailable.
SPREAD_THRESHOLD = 0.015
# Total wall-clock the LLM may use across one cycle's per-symbol decisions. The
# scheduled workflow is killed at 10 minutes (.github/workflows/agent_loop.yml), and
# a killed job loses that cycle's ledger commit. With thinking off a call takes 5-8s
# (nine symbols in about a minute); this is only a safety net for a bad Qwen day where
# every call hits its timeout and retry (about a minute a symbol). Measured Sept 24:
# a 360s cap left runs at 8.3-9.4 minutes of the 10 allowed, too close, so it is 240s
# now: worst case is about 1.5 min of setup and data + 240s + one last call, roughly
# 7 minutes. Once the budget is spent the remaining symbols use the disclosed
# rule-based fallback, labeled as such in decision_source.
LLM_CYCLE_BUDGET_S = 240.0


def is_nyse_closed(now_utc: datetime | None = None) -> bool:
    """True outside 9:30-16:00 America/New_York on weekdays, and all day on
    Sat/Sun. Does NOT account for US market holidays yet (flagged as a known gap -
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
    needed last/bid/ask) - fetched directly here since the live rule-based signal
    needs a 24h-change proxy, unlike the backtest which uses full daily history."""
    payload = run_bgc(["market", "--action", "tickers", "--category", "SPOT", "--symbol", rtoken_symbol])
    row = payload["data"][0]
    return {
        "symbol": row["symbol"],
        "last_price": float(row["lastPrice"]),
        "pcnt_change_24h": float(row["price24hPcnt"]),
    }


def _pct(value, signed: bool = False) -> str:
    """Percent formatting that says so when a proxy was unavailable instead of
    printing a number that was never measured."""
    if value is None:
        return "unavailable"
    return f"{value:+.2%}" if signed else f"{value:.2%}"


def build_snapshot(underlying: str, anchor: OvernightAnchor,
                   bitget_signal_context: dict | None = None) -> dict:
    """One symbol's live signal, anchored to where the REAL share last closed.

        fair value = real close x (1 + blended proxy return since that close)
        spread     = rToken return since that close - blended proxy return since it

    `anchor` (the real closes, the futures / crypto / FX moves since the close, and
    each share's realized volatility) is fetched ONCE per run_once() cycle and shared
    across all symbols. Every term is measured over the same window. The previous
    version compared the rToken's rolling 24h return, which contains the whole regular
    session, with a ~5-day futures return, a 24h crypto return and a 1-hour FX return;
    its spreads (up to -4.6%) were the session's own move, not a gap, while the real
    overnight dislocation was about 0.1% (see engine/data/overnight_anchor.py).

    A proxy that was unavailable this cycle contributes nothing (the same "no new
    information" convention as before) and is listed in `missing_proxies`; a missing
    real close raises, so that symbol gets no decision this cycle instead of one made
    on an invented anchor.

    bitget_signal_context is real, additional macro/crypto context from Bitget's own
    public bitget-signal MCP server, genuinely optional enrichment (None whenever that
    server has nothing to give, see bitget_signal.py); the model never depends on it."""
    cfg = RTOKEN_UNIVERSE[underlying]
    if underlying not in anchor.close_prices:
        raise ValueError(f"no real-share close for {underlying} on the anchor session {anchor.session_date}")
    rtoken = _get_rtoken_tick_with_pcnt(cfg["rtoken_symbol"])

    close = anchor.close_prices[underlying]
    futures_return = anchor.futures_return.get(cfg["futures_proxy"])
    fair_value_return = (
        (futures_return or 0.0) * FAIRVALUE_WEIGHTS["futures_proxy_return"]
        + (anchor.crypto_return or 0.0) * FAIRVALUE_WEIGHTS["crypto_beta_return"]
        + (anchor.fx_return or 0.0) * FAIRVALUE_WEIGHTS["fx_risk_sentiment_return"]
    )
    rtoken_return = rtoken["last_price"] / close - 1.0
    relevant_missing = {f"futures:{cfg['futures_proxy']}", "crypto_beta", "fx_risk_sentiment"}

    return {
        "underlying": underlying,
        "rtoken_symbol": cfg["rtoken_symbol"],
        "rtoken_last_price": rtoken["last_price"],
        "signal_spec": "since_last_close_v2",
        "real_close_price": close,
        "real_close_time": anchor.session_close_utc.isoformat(),
        "hours_since_close": round(anchor.hours_since_close, 2),
        "rtoken_return_since_close": rtoken_return,
        "rtoken_pcnt_24h": rtoken["pcnt_change_24h"],  # rolling 24h, context only: it contains the whole session
        "futures_proxy_return_since_close": futures_return,
        "crypto_beta_return_since_close": anchor.crypto_return,
        "fx_risk_sentiment_return_since_close": anchor.fx_return,
        "fair_value_return_since_close": fair_value_return,
        "fair_value_price": close * (1.0 + fair_value_return),
        "spread": rtoken_return - fair_value_return,
        "recent_daily_volatility": anchor.daily_volatility.get(underlying),
        "missing_proxies": [m for m in anchor.missing if m in relevant_missing],
        "bitget_signal_context": bitget_signal_context,
    }


def decide_rule_based(snapshot: dict) -> TradeDecision | None:
    """Day 4's fixed-threshold rule: rToken trading meaningfully rich vs. the
    blended proxy signal -> sell/reduce; meaningfully cheap -> buy. No position
    otherwise. Kept as the automatic fallback for when Qwen isn't configured or
    its call fails - never the primary path once QWEN_API_KEY is set (see
    decide() below)."""
    spread = snapshot["spread"]
    if abs(spread) < SPREAD_THRESHOLD:
        return None

    side = "sell" if spread > 0 else "buy"
    rationale = (
        f"{snapshot['rtoken_symbol']} return since the real share's last close "
        f"{_pct(snapshot['rtoken_return_since_close'], signed=True)} vs. blended proxy fair-value "
        f"return {_pct(snapshot['fair_value_return_since_close'], signed=True)} "
        f"(futures {_pct(snapshot['futures_proxy_return_since_close'], signed=True)}, "
        f"crypto {_pct(snapshot['crypto_beta_return_since_close'], signed=True)}, "
        f"fx {_pct(snapshot['fx_risk_sentiment_return_since_close'], signed=True)}) -> spread "
        f"{spread:+.2%}, {'above' if spread > 0 else 'below'} the {SPREAD_THRESHOLD:.1%} threshold -> {side} "
        f"(bet on reversion toward fair value)."
    )
    return TradeDecision(
        symbol=snapshot["rtoken_symbol"], side=side, notional_usd=250.0,  # fixed size, Day 4 placeholder
        rationale=rationale, stop_loss_pct=0.03, confidence=min(abs(spread) / (2 * SPREAD_THRESHOLD), 1.0),
    )


def build_book_context(state, symbol: str, fills: list[dict], config: RiskConfig | None = None) -> dict:
    """What the LLM needs to know about its own book to be a real decision-maker
    rather than a per-symbol signal reader: its position in this symbol, the
    book's net and gross exposure against the caps, what the risk layer would
    approve right now (asked of the real gate, not re-derived), and its own recent
    fills in this symbol. Everything here is real ledger state; it is also stored
    on the logged snapshot, so the decision log shows exactly what Qwen saw."""
    config = config or RiskConfig()
    equity = state.equity_usd
    positions = state.positions_notional_usd
    net = sum(positions.values())
    gross = sum(abs(v) for v in positions.values())
    symbol_position = positions.get(symbol, 0.0)
    now = datetime.now(timezone.utc)

    recent = []
    for f in fills:
        try:
            hours_ago = (now - datetime.fromisoformat(f["timestamp"])).total_seconds() / 3600
        except (KeyError, ValueError):
            hours_ago = None
        recent.append({"side": f["side"], "notional_usd": round(f["notional_usd"], 2),
                       "hours_ago": None if hours_ago is None else round(hours_ago, 1)})

    return {
        "equity_usd": round(equity, 2),
        "daily_pnl_pct": round(state.daily_realized_pnl_usd / equity, 4) if equity > 0 else 0.0,
        "symbol_position_usd": round(symbol_position, 2),
        "symbol_position_pct": round(symbol_position / equity, 4) if equity > 0 else 0.0,
        "net_exposure_usd": round(net, 2),
        "net_exposure_pct": round(net / equity, 4) if equity > 0 else 0.0,
        "gross_exposure_usd": round(gross, 2),
        "gross_exposure_pct": round(gross / equity, 4) if equity > 0 else 0.0,
        "net_cap_pct": config.max_net_notional_pct,
        "gross_cap_pct": config.max_aggregate_notional_pct,
        "symbol_cap_pct": config.max_position_notional_pct,
        "over_net_cap": equity > 0 and abs(net) > config.max_net_notional_pct * equity,
        "buy_capacity_usd": round(trade_capacity_usd(state, symbol, "buy", config), 2),
        "sell_capacity_usd": round(trade_capacity_usd(state, symbol, "sell", config), 2),
        "recent_fills_this_symbol": recent,
    }


def _book_prompt_lines(book: dict) -> str:
    """Formats build_book_context() for the prompt."""
    position = book["symbol_position_usd"]
    if abs(position) < 0.5:
        position_text = "flat (no position)"
    else:
        position_text = f"{'long' if position > 0 else 'short'} ${abs(position):,.0f} ({abs(book['symbol_position_pct']):.1%} of equity)"

    lines = [
        "\nYour current book (real, from the paper ledger, as of this decision):",
        f"- Equity ${book['equity_usd']:,.0f}; P&L today {book['daily_pnl_pct']:+.2%} "
        f"(new risk is halted by a circuit breaker at -5%)",
        f"- Your position in this symbol: {position_text}; per-symbol cap {book['symbol_cap_pct']:.0%} of equity",
        f"- Book net exposure (long minus short): {book['net_exposure_usd']:+,.0f} = "
        f"{book['net_exposure_pct']:+.1%} of equity; net cap {book['net_cap_pct']:.0%} either way"
        + ("  ** OVER THE NET CAP **" if book["over_net_cap"] else ""),
        f"- Book gross exposure: ${book['gross_exposure_usd']:,.0f} = {book['gross_exposure_pct']:.1%} of equity; "
        f"gross cap {book['gross_cap_pct']:.0%}",
        f"- What the risk layer would approve for this symbol right now: buy up to "
        f"${book['buy_capacity_usd']:,.0f}, sell up to ${book['sell_capacity_usd']:,.0f} "
        f"(you may propose at most $1,000 per decision)",
    ]
    if book["recent_fills_this_symbol"]:
        fills = ", ".join(
            f"{f['side']} ${f['notional_usd']:,.0f}"
            + (f" ({f['hours_ago']}h ago)" if f["hours_ago"] is not None else "")
            for f in book["recent_fills_this_symbol"]
        )
        lines.append(f"- Your last fills in this symbol: {fills}")
    if book["over_net_cap"]:
        lines.append(
            "- The book is over its net directional cap. The risk layer rejects any trade that pushes net "
            "exposure further from zero and approves trades that reduce it. Bringing net exposure back "
            "under the cap is part of your job; weigh it against this symbol's spread."
        )
    return "\n".join(lines) + "\n"


def build_user_prompt(snapshot: dict) -> str:
    """Turns one symbol's live snapshot into the user message Qwen reasons over.
    Every number here is real and live, fetched moments earlier in build_snapshot -
    nothing in this prompt is synthetic or estimated on the LLM's behalf."""
    book_lines = _book_prompt_lines(snapshot["book_context"]) if snapshot.get("book_context") else ""
    signal_lines = ""
    signal_context = snapshot.get("bitget_signal_context")
    if signal_context:
        # Passed through verbatim from Bitget's own bitget-signal MCP server (see
        # bitget_signal.py) rather than mapped to guessed field names - the real
        # response shape wasn't confirmed at integration time (the upstream
        # source was returning empty results when this was built and tested), so
        # showing Qwen the real keys/values as they actually come back is honest;
        # inventing a specific schema before ever seeing a real payload would not be.
        fear_greed = signal_context.get("fear_greed")
        long_short = signal_context.get("long_short")
        news = signal_context.get("news")
        macro = signal_context.get("macro")
        parts = []
        if fear_greed:
            parts.append(f"- Fear & Greed Index (raw data): {fear_greed}")
        if long_short:
            parts.append(f"- BTC long/short ratio (raw data): {long_short}")
        if news:
            parts.append(f"- Recent crypto/market news (raw data): {news}")
        if macro:
            parts.append(f"- Treasury yield curve (raw data): {macro}")
        if parts:
            signal_lines = (
                "\nAdditional real-time context (Bitget's own public bitget-signal "
                "MCP server):\n" + "\n".join(parts) + "\n"
            )
    close_et = datetime.fromisoformat(snapshot["real_close_time"]).astimezone(NYSE_TZ)
    missing = snapshot.get("missing_proxies") or []
    missing_line = (
        f"- Unavailable this cycle (counted as no information, not as zero movement): {', '.join(missing)}\n"
        if missing else ""
    )
    return (
        f"rToken: {snapshot['rtoken_symbol']}\n"
        f"Last price: ${snapshot['rtoken_last_price']:.2f}\n"
        f"The real share's last regular-session close: ${snapshot['real_close_price']:.2f} "
        f"({close_et:%a %Y-%m-%d} 16:00 ET, {snapshot['hours_since_close']:.1f} hours ago)\n"
        f"rToken vs that close: {snapshot['rtoken_return_since_close']:+.2%} "
        f"(its rolling 24h return, {snapshot['rtoken_pcnt_24h']:+.2%}, is for context only: it contains "
        f"the whole regular session, which the rToken already priced)\n"
        f"\n"
        f"Moves since that close, from proxies that stay live while NYSE is closed:\n"
        f"- Index-futures proxy: {_pct(snapshot['futures_proxy_return_since_close'], signed=True)}\n"
        f"- Crypto beta (BTC/ETH): {_pct(snapshot['crypto_beta_return_since_close'], signed=True)}\n"
        f"- FX risk sentiment (inverted DXY): {_pct(snapshot['fx_risk_sentiment_return_since_close'], signed=True)}\n"
        f"- Blended synthetic fair-value return since the close: "
        f"{snapshot['fair_value_return_since_close']:+.2%} (fair value ${snapshot['fair_value_price']:.2f})\n"
        f"{missing_line}"
        f"{signal_lines}"
        f"{book_lines}"
        f"\n"
        f"Spread (rToken return since the close minus fair-value return since the close): "
        f"{snapshot['spread']:+.2%}\n"
        f"\n"
        + (
            "Decide whether this spread is an actionable mispricing, and whether trading it "
            "makes sense given your book."
            if book_lines else "Decide whether this spread is an actionable mispricing."
        )
    )


def decide_llm(snapshot: dict) -> TradeDecision | None:
    """Qwen3.8-max reasons over the same snapshot decide_rule_based uses and
    returns a structured decision per prompts/system_prompt.md's output contract.
    Raises llm_client.LLMError on any failure (API, parsing, invalid schema) -
    callers must catch that and fall back, never let it crash the cycle."""
    system_prompt = llm_client.load_prompt("system_prompt.md")
    user_prompt = build_user_prompt(snapshot)
    result = llm_client.get_decision_json(system_prompt, user_prompt)

    action = result.get("action")
    if action not in ("buy", "sell", "hold"):
        raise llm_client.LLMError(f"Qwen returned an invalid action: {action!r}")
    rationale = str(result.get("rationale") or "Qwen provided no rationale.")
    if action == "hold":
        # A hold used to throw its reasoning away. With an anchored signal most decisions
        # are holds, so an unexplained hold would leave most of the log without the
        # "why". run_once() moves this onto the record.
        snapshot["hold_rationale"] = f"[Qwen3.8-max] {rationale}"
        return None

    try:
        notional = float(result.get("notional_usd", 0))
        stop_loss_pct = float(result.get("stop_loss_pct", 0.02))
        confidence = float(result.get("confidence", 0.5))
    except (TypeError, ValueError) as e:
        raise llm_client.LLMError(f"Qwen returned non-numeric fields: {result}") from e

    if notional <= 0:
        snapshot["hold_rationale"] = f"[Qwen3.8-max] {rationale}"
        return None

    return TradeDecision(
        symbol=snapshot["rtoken_symbol"], side=action,
        notional_usd=min(notional, 1000.0),  # hard ceiling regardless of what Qwen suggests
        rationale=f"[Qwen3.8-max] {rationale}",
        stop_loss_pct=max(stop_loss_pct, 0.001),
        confidence=min(max(confidence, 0.0), 1.0),
    )


def decide(snapshot: dict) -> tuple[TradeDecision | None, str]:
    """The actual dispatcher run_once() calls. Qwen is the primary decision-maker
    whenever QWEN_API_KEY is configured; decide_rule_based is the disclosed,
    automatic fallback for when it isn't configured yet or a call fails - this
    mirrors the credential-guard pattern used throughout this project (Bitget
    creds in execution.py, Qwen creds here) rather than crashing the cycle.
    Returns (decision, source) so run_once() can log which path produced it, which
    is exactly what the Agentic Trading track's LLM-role disclosure asks for."""
    if not llm_client.is_configured():
        return decide_rule_based(snapshot), "rule_based (Qwen not configured)"
    try:
        return decide_llm(snapshot), "qwen3.8-max"
    except llm_client.LLMError as e:
        return decide_rule_based(snapshot), f"rule_based (Qwen call failed: {e})"


def _net_backstop_pass(mark_prices: dict, snapshots: dict, emit, dry_run: bool) -> list[dict]:
    """The deterministic backstop for the net directional cap. The LLM is shown its
    book and is the primary way an over-cap book comes back under the cap; this only
    trims if it has not made progress for RiskConfig.net_trim_backstop_cycles active
    cycles (risk_controls.update_net_over_cap_tracker), and then only a slice of
    equity per cycle (risk_controls.plan_net_trim). Every trim goes through
    evaluate_decision, the ledger and the decision log like any other trade, and is
    labeled with its own decision_source so it is never mistaken for an LLM decision.
    Skipped entirely on a dry run (no ledger state is touched)."""
    if dry_run:
        return []
    try:
        config = RiskConfig()
        state = paper_ledger.get_portfolio_state(mark_prices)
        if state.equity_usd <= 0:
            return []
        net = sum(state.positions_notional_usd.values())
        excess = abs(net) - config.max_net_notional_pct * state.equity_usd

        cycles, baseline = paper_ledger.get_net_tracker()
        cycles, baseline = update_net_over_cap_tracker(cycles, baseline, excess, state.equity_usd, config)
        paper_ledger.set_net_tracker(cycles, baseline)
        if cycles < config.net_trim_backstop_cycles:
            return []

        symbol_to_underlying = {cfg["rtoken_symbol"]: u for u, cfg in RTOKEN_UNIVERSE.items()}
        trim_records = []
        for decision in plan_net_trim(state, config):
            price = mark_prices.get(decision.symbol)
            if price is None:  # no fresh price this cycle, never trade on a stale one
                continue
            underlying = symbol_to_underlying.get(decision.symbol)
            record = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "underlying": underlying,
                "snapshot": snapshots.get(underlying),
                "decision_source": "risk_backstop_trim (deterministic risk layer, not the LLM)",
                "decision": asdict(decision),
            }
            # recent_volatility=0: vol scaling shrinks new risk, and a trim is the opposite
            risk_result = evaluate_decision(decision, state, recent_volatility=0.0, config=config)
            record["risk_result"] = asdict(risk_result)
            if not risk_result.approved:
                record["execution"] = "SKIPPED: rejected by risk controls"
            else:
                try:
                    qty = round(risk_result.adjusted_notional_usd / price, 4)
                    record["execution"] = asdict(
                        paper_ledger.record_fill(decision.symbol, decision.side, qty, price, decision.rationale)
                    )
                except Exception as e:  # noqa: BLE001
                    record["execution"] = f"FAILED: {e}"
            trim_records.append(record)
            emit(record)
        return trim_records
    except Exception as e:  # noqa: BLE001 - the backstop must never cost the cycle its records
        print(f"net backstop pass failed: {e}", file=sys.stderr)
        return []


def run_once(dry_run: bool = False, force: bool = False) -> list[dict]:
    """One full pass over the universe: snapshot -> decide -> risk-gate -> execute
    (or skip) -> log. Returns the list of log records written this cycle.

    Enforces is_nyse_closed() itself (not just as an informational check in the
    smoke-test print) - this is the actual safety guarantee behind "runs only
    off-hours," not merely documentation. If the market is open, logs one record
    and returns immediately without touching any data source. `force=True` bypasses
    this for manual debugging only (e.g. inspecting the pipeline mid-day) - never
    pass it from the scheduled entry point (see scheduled_run() below).

    Two passes over RTOKEN_UNIVERSE: the first builds every symbol's live snapshot
    (needed regardless of whether a signal fires, both for the decision and to
    have a real mark price for paper_ledger's portfolio valuation); the second
    applies decide() -> risk-gate -> execute against a portfolio_state computed
    after pass one and re-marked after every real fill, so each decision, its risk
    gate, and the book context shown to the LLM reflect fills already made this
    cycle (previously the book was frozen at the start of the cycle). A third step,
    _net_backstop_pass(), then runs the deterministic net-exposure backstop.

    Each record is written to the local log and pushed to Redis the moment it is
    finalized, not batched until the whole cycle finishes. Confirmed live Sept 12:
    this machine can stall for a long stretch mid-cycle (Windows power management
    suspending the process, observed correlating with lid-close events in the
    system power log), and the old batch-at-the-end write meant a cycle cut short
    lost every record it had already computed, even ones from minutes earlier.
    Writing incrementally bounds the loss to at most the one record in flight."""
    if dry_run:
        # A dry run must not touch anything the public Desk or the committed record reads:
        # no Redis writes, and its records go to a git-ignored folder the Desk never lists.
        kv_sync.disable()
        log_dir = DECISION_LOG_DIR / "dry_run"
    else:
        log_dir = DECISION_LOG_DIR
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{datetime.now(timezone.utc):%Y-%m-%d}.jsonl"

    def _emit(record: dict) -> None:
        """Writes one record to disk and mirrors it to Redis immediately, so a
        record is durable the moment it exists rather than at the end of the cycle."""
        with open(log_path, "a") as f:
            f.write(json.dumps(record, default=str) + "\n")
        kv_sync.push_decision_records([record])  # best-effort; no-ops if unconfigured

    if not force and not is_nyse_closed():
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "underlying": None,
            "decision": None,
            "execution": "SKIPPED: NYSE is open - Agent only trades off-hours",
        }
        _emit(record)
        return [record]

    # Fetch the shared, symbol-independent anchor exactly once per cycle: where each real
    # share last closed, and what the futures / crypto / FX proxies have done since. If
    # the real closes cannot be established there is no anchor at all: every symbol is
    # logged as an error and nothing trades this cycle, rather than trading on stale
    # numbers.
    distinct_futures_tickers = sorted({cfg["futures_proxy"] for cfg in RTOKEN_UNIVERSE.values()})
    try:
        anchor = fetch_overnight_anchor(list(RTOKEN_UNIVERSE), distinct_futures_tickers)
        anchor_error = None
    except (AnchorUnavailable, Exception) as e:  # noqa: BLE001 - a data outage must not crash the cycle
        anchor, anchor_error = None, f"real-close anchor unavailable: {e}"
    # Real, optional enrichment from Bitget's own public bitget-signal MCP server
    # (see bitget_signal.py) - never fabricated, None whenever that source has
    # nothing to give, and the fair-value model above never depends on it.
    try:
        bitget_signal_context = bitget_signal.get_signal_context()
    except Exception:  # noqa: BLE001 - this is pure enrichment, never worth risking the cycle over
        bitget_signal_context = None

    snapshots: dict[str, dict] = {}
    snapshot_errors: dict[str, str] = {}
    mark_prices: dict[str, float] = {}
    for underlying in RTOKEN_UNIVERSE:
        try:
            if anchor is None:
                raise RuntimeError(anchor_error)
            snapshot = build_snapshot(underlying, anchor, bitget_signal_context)
            snapshots[underlying] = snapshot
            mark_prices[snapshot["rtoken_symbol"]] = snapshot["rtoken_last_price"]
        except Exception as e:  # noqa: BLE001 - one symbol's data failure shouldn't kill the cycle
            snapshot_errors[underlying] = f"snapshot failed: {e}"

    portfolio_state = paper_ledger.get_portfolio_state(mark_prices)

    records = []
    llm_time_spent = 0.0
    for underlying in RTOKEN_UNIVERSE:
        record = {"timestamp": datetime.now(timezone.utc).isoformat(), "underlying": underlying}

        if underlying in snapshot_errors:
            record["error"] = snapshot_errors[underlying]
            records.append(record)
            _emit(record)
            continue

        snapshot = snapshots[underlying]
        record["snapshot"] = snapshot

        # Show the LLM its own book (see build_book_context) - stored on the logged
        # snapshot so the record shows exactly what it saw. Context is enrichment:
        # failing to build it must never cost the cycle a decision.
        try:
            snapshot["book_context"] = build_book_context(
                portfolio_state, snapshot["rtoken_symbol"],
                paper_ledger.recent_fills(snapshot["rtoken_symbol"], 3),
            )
        except Exception as e:  # noqa: BLE001
            print(f"book context unavailable for {underlying}: {e}", file=sys.stderr)

        if llm_time_spent > LLM_CYCLE_BUDGET_S:
            decision = decide_rule_based(snapshot)
            decision_source = "rule_based (LLM time budget for this cycle exhausted)"
        else:
            llm_started = time.monotonic()
            decision, decision_source = decide(snapshot)
            llm_time_spent += time.monotonic() - llm_started
        record["decision_source"] = decision_source
        hold_rationale = snapshot.pop("hold_rationale", None)
        if decision is None:
            record["decision"] = None
            if hold_rationale:
                record["hold_rationale"] = hold_rationale
            records.append(record)
            _emit(record)
            continue
        record["decision"] = asdict(decision)

        # Realized daily volatility of the real share feeds the risk layer's volatility-scaled
        # sizing (control #4). It used to be |spread|, which only worked while the "spread"
        # was a multi-percent number; a dislocation of a few tenths of a percent is not a
        # volatility, and using it would have quietly switched the control off.
        recent_volatility = snapshot.get("recent_daily_volatility")
        if recent_volatility is None:
            recent_volatility = abs(snapshot["spread"])  # no realized vol this cycle: previous fallback
        risk_result = evaluate_decision(decision, portfolio_state, recent_volatility=recent_volatility)
        record["risk_result"] = asdict(risk_result)

        if not risk_result.approved:
            record["execution"] = "SKIPPED: rejected by risk controls"
            records.append(record)
            _emit(record)
            continue

        if dry_run:
            record["execution"] = "SKIPPED: dry_run=True"
            records.append(record)
            _emit(record)
            continue

        try:
            qty = round(risk_result.adjusted_notional_usd / snapshot["rtoken_last_price"], 4)
            fill = paper_ledger.record_fill(
                decision.symbol, decision.side, qty, snapshot["rtoken_last_price"], decision.rationale
            )
            record["execution"] = asdict(fill)
        except Exception as e:  # noqa: BLE001 - log and move on, never crash the loop over one fill
            record["execution"] = f"FAILED: {e}"

        # Re-mark the book after a real fill so the next symbol's decision, its risk
        # gate, and the book context the LLM sees all reflect it, instead of the
        # book as it stood when the cycle began.
        if isinstance(record["execution"], dict):
            try:
                portfolio_state = paper_ledger.get_portfolio_state(mark_prices)
            except Exception as e:  # noqa: BLE001
                print(f"portfolio refresh after fill failed: {e}", file=sys.stderr)

        records.append(record)
        _emit(record)

    records.extend(_net_backstop_pass(mark_prices, snapshots, _emit, dry_run))
    return records


SCHEDULER_LOG_PATH = Path(__file__).resolve().parent / "scheduler.log"


def scheduled_run() -> None:
    """The actual entry point Windows Task Scheduler invokes on a recurring
    interval (see scripts/setup_scheduled_task.ps1). Deliberately does NOT pass
    force=True - every invocation re-checks is_nyse_closed() itself and silently
    no-ops the ~26/168 hours a week the market is open, which is exactly the
    intended behavior for a timer that fires every 15 minutes around the clock.
    Appends one line to scheduler.log per invocation for operational visibility
    (distinct from decision_log/, which is the structured per-decision record)."""
    records = run_once(dry_run=False, force=False)
    n_decisions = sum(1 for r in records if r.get("decision"))
    n_fills = sum(1 for r in records if isinstance(r.get("execution"), dict) and "qty" in r["execution"])
    skipped_market_open = len(records) == 1 and records[0].get("underlying") is None
    if not skipped_market_open:
        # Re-assert the ledger mirror every active cycle, so a stale or missed push heals on
        # its own within 15 minutes instead of waiting for the next fill to overwrite it.
        paper_ledger.sync_mirror()
    summary = (
        "market open, skipped" if skipped_market_open
        else f"{len(records)} symbols checked, {n_decisions} signals, {n_fills} fills"
    )
    with open(SCHEDULER_LOG_PATH, "a") as f:
        f.write(f"{datetime.now(timezone.utc).isoformat()} - {summary}\n")


if __name__ == "__main__":
    if "--smoke-test" in sys.argv:
        print(f"is_nyse_closed() right now: {is_nyse_closed()}")
        print("Running one cycle (dry_run=True, force=True - no orders will be "
              "placed, and this runs regardless of market hours for demo purposes)...")
        records = run_once(dry_run=True, force=True)
        for r in records:
            u = r["underlying"]
            if r.get("error"):
                print(f"  {u}: ERROR - {r['error']}")
            elif r["decision"] is None:
                spread = r.get("snapshot", {}).get("spread")
                print(f"  {u}: no signal" + (f" (spread {spread:.2%})" if spread is not None else ""))
            else:
                print(f"  {u}: {r['decision']['side']} ${r['decision']['notional_usd']:.0f} "
                      f"[{r.get('decision_source', '?')}] - {r['execution']}")
        print(f"\nLogged to {DECISION_LOG_DIR / 'dry_run'} (git-ignored; nothing was written to Redis)")
    elif "--run" in sys.argv:
        # The scheduled-task entry point - quiet on purpose (no stdout expected
        # under Task Scheduler), all output goes to scheduler.log.
        scheduled_run()
    else:
        print("Usage: python agent_loop.py --smoke-test | --run")
