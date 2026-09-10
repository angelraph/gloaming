"""
Gloaming Agent's hard, deterministic, non-LLM risk layer — see
docs/risk_controls.md. Every trade decision (rule-based today, Qwen-generated from
Day 5 onward) passes through evaluate_decision() before execution.py ever sees it.
This module knows nothing about LLMs and never will; that separation is the point.
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
    confidence: float = 0.5      # 0-1, informational only — never used to bypass a hard cap


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
        return RiskResult(False, 0.0, ["invalid equity or notional — rejected"])

    # --- Control: no leverage. Spot/paper exposure only. ---
    if decision.notional_usd > state.equity_usd:
        reasons.append(
            f"requested notional {decision.notional_usd:.2f} exceeds account equity "
            f"{state.equity_usd:.2f} — no-leverage control rejects (spot only)"
        )
        return RiskResult(False, 0.0, reasons)

    # --- Control: daily max-loss circuit breaker. ---
    daily_pnl_pct = (state.daily_realized_pnl_usd + state.daily_unrealized_pnl_usd) / state.equity_usd
    if daily_pnl_pct <= -config.max_daily_loss_pct:
        reasons.append(
            f"daily P&L {daily_pnl_pct:.2%} breached -{config.max_daily_loss_pct:.2%} circuit "
            f"breaker — new positions halted for the remainder of this window"
        )
        return RiskResult(False, 0.0, reasons)

    # --- Control: per-trade max-loss circuit breaker. ---
    implied_loss_pct = (decision.notional_usd * decision.stop_loss_pct) / state.equity_usd
    if implied_loss_pct > config.max_trade_loss_pct:
        reasons.append(
            f"stop-loss-implied loss {implied_loss_pct:.2%} of equity exceeds "
            f"{config.max_trade_loss_pct:.2%} per-trade cap — rejected outright"
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
                f"{config.vol_scaling_reference:.2%} — sizing scaled by {scale:.2f}x"
            )
            notional *= scale

    # --- Control: per-symbol position cap. ---
    max_symbol_notional = config.max_position_notional_pct * state.equity_usd
    current_symbol_notional = abs(state.positions_notional_usd.get(decision.symbol, 0.0))
    room_left = max(max_symbol_notional - current_symbol_notional, 0.0)
    if notional > room_left:
        reasons.append(
            f"resized from {notional:.2f} to {room_left:.2f} to respect per-symbol cap "
            f"({config.max_position_notional_pct:.0%} of equity)"
        )
        notional = room_left

    # --- Control: aggregate book notional cap. ---
    max_aggregate = config.max_aggregate_notional_pct * state.equity_usd
    room_left_aggregate = max(max_aggregate - _aggregate_notional(state), 0.0)
    if notional > room_left_aggregate:
        reasons.append(
            f"resized from {notional:.2f} to {room_left_aggregate:.2f} to respect aggregate "
            f"book cap ({config.max_aggregate_notional_pct:.0%} of equity)"
        )
        notional = room_left_aggregate

    if notional <= 0:
        reasons.append("resized to zero by position/aggregate caps — effectively rejected")
        return RiskResult(False, 0.0, reasons)

    if not reasons:
        reasons.append("approved at full requested size — no controls binding")

    return RiskResult(True, notional, reasons)
