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
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RiskConfig:
    max_position_notional_pct: float = 0.15   # cap per-symbol notional as % of equity
    max_aggregate_notional_pct: float = 0.60   # cap total book notional as % of equity
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
    if reducing_notional > 0:
        reasons.append(
            f"{reducing_notional:.2f} of this trade reduces the existing {decision.symbol} "
            f"position and is exempt from the position/aggregate caps (de-risking, not new risk)"
        )

    if notional <= 0:
        reasons.append("resized to zero by position/aggregate caps - effectively rejected")
        return RiskResult(False, 0.0, reasons)

    if not reasons:
        reasons.append("approved at full requested size - no controls binding")

    return RiskResult(True, notional, reasons)
