"""
Gloaming Agent's hard, deterministic, non-LLM risk layer - see
docs/risk_controls.md. Every trade decision (rule-based today, Qwen-generated from
Day 5 onward) passes through evaluate_decision() before execution.py ever sees it.
This module knows nothing about LLMs and never will; that separation is the point.

The per-symbol and aggregate notional caps are net-exposure aware: a trade that
reduces an existing position's size is exempt from those caps up to the point of
fully flattening it, since a cap that can never let the book de-risk itself once
it is already at cap would be a bug, not a safety feature. A trade that adds
exposure (opens new, or grows an existing position further) is still capped
exactly as before. See evaluate_decision()'s de-risk exemption for the mechanics.

A separate net directional cap (max_net_notional_pct, 25% of equity) bounds how
one-sided the whole book can be, since the gross caps alone allow a full-size
bet in a single direction. The cap itself limits new exposure only and never forces
a trade. The LLM is shown its book and the cap, and is the primary way an over-cap
book comes back under it; plan_net_trim() is a deterministic backstop that agent_loop
only engages after the LLM has failed to make progress for several active cycles.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RiskConfig:
    max_position_notional_pct: float = 0.15   # cap per-symbol notional as % of equity
    max_aggregate_notional_pct: float = 0.60   # cap total book notional as % of equity
    max_net_notional_pct: float = 0.25         # cap |net long minus net short| as % of equity
    net_trim_max_pct_per_cycle: float = 0.02   # auto-trim sells/buys back at most this % of equity per cycle
    net_trim_tolerance_pct: float = 0.01       # no trim until net is over the cap by more than this % of equity
    net_trim_min_order_usd: float = 5.0        # skip trim orders smaller than this
    net_trim_backstop_cycles: int = 8          # active cycles the LLM gets to bring net under the cap before the backstop trims
    net_trim_progress_pct: float = 0.01        # excess shrinking by this % of equity restarts that clock
    max_trade_loss_pct: float = 0.02           # reject if stop-loss-implied loss > this % of equity
    max_daily_loss_pct: float = 0.05           # halt new positions once daily loss crosses this
    vol_scaling_reference: float = 0.02         # "typical" daily vol; sizing scales down above this
    max_vol_scale_reduction: float = 0.75       # sizing never cut by more than this fraction


@dataclass
class TradeDecision:
    """A proposed trade, before risk gating. `rationale` is what gets written to the
    decision log's event->decision->execution trail regardless of outcome."""
    symbol: str
    side: str  # "buy" | "sell"
    notional_usd: float
    rationale: str
    stop_loss_pct: float = 0.02  # distance to stop, as a fraction of entry price
    confidence: float = 0.5      # 0-1, informational only - never used to bypass a hard cap


@dataclass
class PortfolioState:
    equity_usd: float
    positions_notional_usd: dict = field(default_factory=dict)  # symbol -> current notional
    daily_realized_pnl_usd: float = 0.0
    daily_unrealized_pnl_usd: float = 0.0


@dataclass
class RiskResult:
    approved: bool
    adjusted_notional_usd: float
    reasons: list  # human-readable notes: resizing applied, or why rejected


def _aggregate_notional(state: PortfolioState) -> float:
    return sum(abs(v) for v in state.positions_notional_usd.values())


def plan_net_trim(state: PortfolioState, config: RiskConfig = RiskConfig()) -> list[TradeDecision]:
    """Deterministic, non-LLM BACKSTOP unwind for a book whose net directional
    exposure is over the net cap. The net cap only stops new exposure, it never
    forces a trade, so a book that is already over it (confirmed live Sept 24: net
    long about 60% of equity when the cap became 25%) stays put until a
    net-reducing decision arrives. The LLM is shown its book and the cap and is the
    primary way the book comes back under it; agent_loop only calls this once the
    LLM has failed to make progress for net_trim_backstop_cycles active cycles (see
    update_net_over_cap_tracker). This returns the sells (or buy-backs, for a net
    short book) that walk it back toward the cap, without dumping it in one cycle:

    - nothing until net is over the cap by more than net_trim_tolerance_pct of
      equity, so small mark-to-market drift around the cap does not cause churn;
    - at most net_trim_max_pct_per_cycle of equity is traded per cycle;
    - the amount is spread across the positions on the over-exposed side in
      proportion to their size, and never exceeds any one position.

    Every decision returned here still goes through evaluate_decision() like any
    other trade; this only proposes them."""
    if state.equity_usd <= 0:
        return []
    net = sum(state.positions_notional_usd.values())
    max_net = config.max_net_notional_pct * state.equity_usd
    excess = abs(net) - max_net
    if excess <= config.net_trim_tolerance_pct * state.equity_usd:
        return []

    trim_total = min(excess, config.net_trim_max_pct_per_cycle * state.equity_usd)
    side = "sell" if net > 0 else "buy"
    candidates = {
        symbol: abs(value)
        for symbol, value in state.positions_notional_usd.items()
        if value != 0.0 and (value > 0) == (net > 0)
    }
    pool = sum(candidates.values())
    if pool <= 0:
        return []
    fraction = min(trim_total / pool, 1.0)

    decisions = []
    for symbol, size in sorted(candidates.items()):
        amount = size * fraction
        if amount < config.net_trim_min_order_usd:
            continue
        decisions.append(TradeDecision(
            symbol=symbol,
            side=side,
            notional_usd=amount,
            rationale=(
                f"Backstop trim (deterministic risk layer, not the LLM, engaged because the "
                f"LLM did not bring the book back under its net cap): book net exposure "
                f"{net:+,.0f} ({net / state.equity_usd:+.1%} of equity) is over the "
                f"{config.max_net_notional_pct:.0%} net directional cap, so {side} "
                f"{amount:,.0f} of {symbol}, its proportional share of {trim_total:,.0f} "
                f"this cycle (at most {config.net_trim_max_pct_per_cycle:.0%} of equity per cycle)."
            ),
            stop_loss_pct=0.02,
            confidence=1.0,
        ))
    return decisions


def update_net_over_cap_tracker(
    cycles: int,
    baseline_excess_usd: float,
    excess_usd: float,
    equity_usd: float,
    config: RiskConfig = RiskConfig(),
) -> tuple[int, float]:
    """Counts consecutive active cycles the book has stayed over its net cap without
    the LLM making real progress, so the backstop only engages when it has actually
    failed to bring the book back. Returns the new (cycles, baseline_excess_usd).

    - Within the tolerance band of the cap: clock resets to zero.
    - First cycle over: clock starts at 1, baseline is that excess.
    - Before the backstop has engaged: if the excess has shrunk by at least
      net_trim_progress_pct of equity since the baseline, the LLM is making
      progress, so the clock restarts from this cycle.
    - Once the backstop has engaged (cycles >= net_trim_backstop_cycles) it stays
      engaged until the book is back inside the band - its own trims shrink the
      excess and must not count as the LLM making progress."""
    if excess_usd <= config.net_trim_tolerance_pct * equity_usd:
        return 0, 0.0
    if cycles <= 0:
        return 1, excess_usd
    if cycles >= config.net_trim_backstop_cycles:
        return cycles, baseline_excess_usd
    if excess_usd <= baseline_excess_usd - config.net_trim_progress_pct * equity_usd:
        return 1, excess_usd
    return cycles + 1, baseline_excess_usd


def trade_capacity_usd(state: PortfolioState, symbol: str, side: str, config: RiskConfig = RiskConfig()) -> float:
    """The largest notional evaluate_decision() would currently approve for this
    symbol and side, by asking the real gate rather than re-deriving its rules.
    Ignores volatility scaling and the per-trade stop-loss cap (probed with zero
    volatility and a tiny stop). Shown to the LLM so it sees the same limits the
    risk layer will enforce instead of proposing sizes into a wall."""
    if state.equity_usd <= 0:
        return 0.0
    probe = TradeDecision(symbol, side, state.equity_usd, "capacity probe", stop_loss_pct=0.0001)
    return evaluate_decision(probe, state, recent_volatility=0.0, config=config).adjusted_notional_usd


def evaluate_decision(
    decision: TradeDecision,
    state: PortfolioState,
    recent_volatility: float,
    config: RiskConfig = RiskConfig(),
) -> RiskResult:
    """Runs every control from docs/risk_controls.md in order. A decision can be
    APPROVED-BUT-RESIZED (vol scaling, position cap) or outright REJECTED (daily
    circuit breaker, trade-loss circuit breaker, no-leverage violation). Rejection
    is always the safe default on ambiguous input (e.g. non-finite numbers)."""
    reasons: list[str] = []

    if state.equity_usd <= 0 or decision.notional_usd <= 0:
        return RiskResult(False, 0.0, ["invalid equity or notional - rejected"])

    # --- Control: no leverage. Spot/paper exposure only. ---
    if decision.notional_usd > state.equity_usd:
        reasons.append(
            f"requested notional {decision.notional_usd:.2f} exceeds account equity "
            f"{state.equity_usd:.2f} - no-leverage control rejects (spot only)"
        )
        return RiskResult(False, 0.0, reasons)

    # Direction check, needed by the daily circuit breaker below as well as the
    # per-symbol/aggregate caps further down - computed once, early, since a
    # trade opposite in sign to an existing position reduces the book's risk
    # rather than adding to it (see module docstring).
    existing_notional = state.positions_notional_usd.get(decision.symbol, 0.0)
    decision_sign = 1.0 if decision.side == "buy" else -1.0
    existing_sign = 1.0 if existing_notional > 0 else -1.0
    is_reducing = existing_notional != 0.0 and decision_sign != existing_sign

    # --- Control: daily max-loss circuit breaker. ---
    # docs/risk_controls.md control #3 promises new positions halt but "existing
    # positions may still be closed/hedged" - confirmed live Sept 22 the code did
    # not actually honor that: it rejected every decision outright, including
    # ones that would reduce risk. A de-risking decision is now still allowed
    # through (sized down to zero risk-increasing notional below); a
    # risk-increasing one is rejected outright exactly as before.
    daily_pnl_pct = (state.daily_realized_pnl_usd + state.daily_unrealized_pnl_usd) / state.equity_usd
    daily_breaker_triggered = daily_pnl_pct <= -config.max_daily_loss_pct
    if daily_breaker_triggered and not is_reducing:
        reasons.append(
            f"daily P&L {daily_pnl_pct:.2%} breached -{config.max_daily_loss_pct:.2%} circuit "
            f"breaker - new positions halted for the remainder of this window"
        )
        return RiskResult(False, 0.0, reasons)
    if daily_breaker_triggered:
        reasons.append(
            f"daily P&L {daily_pnl_pct:.2%} breached -{config.max_daily_loss_pct:.2%} circuit "
            f"breaker - only the de-risking portion of this trade can proceed"
        )

    # --- Control: per-trade max-loss circuit breaker. ---
    implied_loss_pct = (decision.notional_usd * decision.stop_loss_pct) / state.equity_usd
    if implied_loss_pct > config.max_trade_loss_pct:
        reasons.append(
            f"stop-loss-implied loss {implied_loss_pct:.2%} of equity exceeds "
            f"{config.max_trade_loss_pct:.2%} per-trade cap - rejected outright"
        )
        return RiskResult(False, 0.0, reasons)

    notional = decision.notional_usd

    # --- Control: volatility-scaled sizing. ---
    if recent_volatility > config.vol_scaling_reference > 0:
        scale = config.vol_scaling_reference / recent_volatility
        scale = max(scale, 1 - config.max_vol_scale_reduction)
        if scale < 1.0:
            reasons.append(
                f"recent volatility {recent_volatility:.2%} > reference "
                f"{config.vol_scaling_reference:.2%} - sizing scaled by {scale:.2f}x"
            )
            notional *= scale

    # --- De-risk exemption: split off the portion of this trade that reduces the
    # existing position (already known from is_reducing, computed above) from the
    # portion that would grow exposure. A cap that blocks a trade shrinking the
    # book's own risk exactly like one growing it is a gap, not a safety feature -
    # confirmed live Sept 22, the book sat over the aggregate cap for 8 straight
    # days rejecting every decision, including ones proposing to cover the
    # existing shorts. Only the de-risking amount, up to fully flattening the
    # existing position, is exempt; anything beyond that (flipping to a new
    # position on the other side) is still a normal new-risk trade and goes
    # through the caps below unchanged.
    reducing_notional = min(notional, abs(existing_notional)) if is_reducing else 0.0
    at_risk_notional = notional - reducing_notional
    if daily_breaker_triggered and at_risk_notional > 0:
        reasons.append(
            f"daily circuit breaker also zeroes the risk-increasing portion "
            f"({at_risk_notional:.2f}) of this trade - only de-risking can proceed"
        )
        at_risk_notional = 0.0

    # --- Control: per-symbol position cap (only the risk-increasing portion). ---
    max_symbol_notional = config.max_position_notional_pct * state.equity_usd
    current_symbol_notional = abs(existing_notional)
    room_left = max(max_symbol_notional - current_symbol_notional, 0.0)
    if at_risk_notional > room_left:
        reasons.append(
            f"resized the risk-increasing portion from {at_risk_notional:.2f} to {room_left:.2f} "
            f"to respect per-symbol cap ({config.max_position_notional_pct:.0%} of equity)"
        )
        at_risk_notional = room_left

    # --- Control: aggregate book notional cap (only the risk-increasing portion). ---
    max_aggregate = config.max_aggregate_notional_pct * state.equity_usd
    room_left_aggregate = max(max_aggregate - _aggregate_notional(state), 0.0)
    if at_risk_notional > room_left_aggregate:
        reasons.append(
            f"resized the risk-increasing portion from {at_risk_notional:.2f} to {room_left_aggregate:.2f} "
            f"to respect aggregate book cap ({config.max_aggregate_notional_pct:.0%} of equity)"
        )
        at_risk_notional = room_left_aggregate

    notional = reducing_notional + at_risk_notional

    # --- Control: net directional exposure cap (applies to the whole trade). ---
    # The gross caps above allow a full-size one-way bet: confirmed live Sept 23-24,
    # the book went from about 60% net short to about 60% net long, all inside
    # every gross cap. This bounds |net long minus net short|. A trade pushing net
    # further from zero gets only the room left under the cap. A trade toward zero
    # is allowed up to fully flattening net, plus at most the cap on the other
    # side. Unlike the per-symbol/aggregate exemption, this is checked against the
    # whole trade, because it constrains the book's direction, not one symbol.
    net_now = sum(state.positions_notional_usd.values())
    max_net = config.max_net_notional_pct * state.equity_usd
    same_direction = net_now == 0.0 or (net_now > 0) == (decision_sign > 0)
    net_allowed = max(max_net - abs(net_now), 0.0) if same_direction else abs(net_now) + max_net
    if notional > net_allowed:
        reasons.append(
            f"resized from {notional:.2f} to {net_allowed:.2f} to respect net directional "
            f"cap ({config.max_net_notional_pct:.0%} of equity; book net is {net_now:.2f})"
        )
        notional = net_allowed
        reducing_notional = min(reducing_notional, notional)

    if reducing_notional > 0:
        reasons.append(
            f"{reducing_notional:.2f} of this trade reduces the existing {decision.symbol} "
            f"position and is exempt from the position/aggregate caps (de-risking, not new risk)"
        )

    if notional <= 0:
        reasons.append("resized to zero by position/aggregate/net caps - effectively rejected")
        return RiskResult(False, 0.0, reasons)

    if not reasons:
        reasons.append("approved at full requested size - no controls binding")

    return RiskResult(True, notional, reasons)
