"""
Unit tests for gloaming_agent/risk_controls.py - one forced test case per control
in docs/risk_controls.md, asserting an over-cap/over-loss decision is blocked
before it could ever reach execution.py.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "gloaming_agent"))

from risk_controls import PortfolioState, RiskConfig, TradeDecision, evaluate_decision  # noqa: E402


def _state(equity=10_000.0, positions=None, daily_realized=0.0, daily_unrealized=0.0):
    return PortfolioState(
        equity_usd=equity,
        positions_notional_usd=positions or {},
        daily_realized_pnl_usd=daily_realized,
        daily_unrealized_pnl_usd=daily_unrealized,
    )


def test_approves_a_small_reasonable_trade_unmodified():
    decision = TradeDecision("RAAPLUSDT", "buy", notional_usd=500.0, rationale="test", stop_loss_pct=0.02)
    result = evaluate_decision(decision, _state(), recent_volatility=0.01)
    assert result.approved
    assert result.adjusted_notional_usd == pytest.approx(500.0)


def test_no_leverage_control_rejects_notional_above_equity():
    decision = TradeDecision("RAAPLUSDT", "buy", notional_usd=15_000.0, rationale="test")
    result = evaluate_decision(decision, _state(equity=10_000.0), recent_volatility=0.01)
    assert not result.approved
    assert result.adjusted_notional_usd == 0.0
    assert "no-leverage" in result.reasons[0]


def test_daily_max_loss_circuit_breaker_blocks_new_positions():
    state = _state(equity=10_000.0, daily_realized=-600.0)  # -6% > 5% threshold
    decision = TradeDecision("RAAPLUSDT", "buy", notional_usd=100.0, rationale="test")
    result = evaluate_decision(decision, state, recent_volatility=0.01)
    assert not result.approved
    assert "circuit breaker" in result.reasons[0]


def test_per_trade_max_loss_circuit_breaker_rejects_oversized_stop():
    # notional 5000 * stop 10% = 500 implied loss = 5% of 10,000 equity > 2% cap
    decision = TradeDecision("RAAPLUSDT", "buy", notional_usd=5_000.0, rationale="test", stop_loss_pct=0.10)
    result = evaluate_decision(decision, _state(), recent_volatility=0.01)
    assert not result.approved
    assert "per-trade cap" in result.reasons[0]


def test_volatility_scaled_sizing_reduces_notional_in_high_vol():
    decision = TradeDecision("RAAPLUSDT", "buy", notional_usd=500.0, rationale="test", stop_loss_pct=0.02)
    result = evaluate_decision(decision, _state(), recent_volatility=0.08)  # 4x reference vol
    assert result.approved
    assert result.adjusted_notional_usd < 500.0


def test_volatility_scaling_never_exceeds_max_reduction():
    config = RiskConfig(max_vol_scale_reduction=0.75, max_trade_loss_pct=1.0)  # loosen unrelated cap
    decision = TradeDecision("RAAPLUSDT", "buy", notional_usd=500.0, rationale="test", stop_loss_pct=0.02)
    result = evaluate_decision(decision, _state(), recent_volatility=10.0, config=config)  # extreme vol
    assert result.approved
    assert result.adjusted_notional_usd == pytest.approx(500.0 * 0.25, rel=1e-6)


def test_per_symbol_position_cap_resizes_down():
    # cap is 15% of 10,000 = 1,500; already holding 1,400 -> only 100 of room left
    state = _state(equity=10_000.0, positions={"RAAPLUSDT": 1_400.0})
    decision = TradeDecision("RAAPLUSDT", "buy", notional_usd=1_000.0, rationale="test", stop_loss_pct=0.01)
    result = evaluate_decision(decision, state, recent_volatility=0.01)
    assert result.approved
    assert result.adjusted_notional_usd == pytest.approx(100.0, abs=1e-6)


def test_per_symbol_position_cap_rejects_when_already_full():
    state = _state(equity=10_000.0, positions={"RAAPLUSDT": 1_500.0})  # already at cap
    decision = TradeDecision("RAAPLUSDT", "buy", notional_usd=200.0, rationale="test", stop_loss_pct=0.01)
    result = evaluate_decision(decision, state, recent_volatility=0.01)
    assert not result.approved
    assert result.adjusted_notional_usd == 0.0


def test_aggregate_book_cap_resizes_down_across_symbols():
    # aggregate cap is 60% of 10,000 = 6,000; already holding 5,900 across other symbols
    state = _state(equity=10_000.0, positions={"RTSLAUSDT": 3_000.0, "RNVDAUSDT": 2_900.0})
    decision = TradeDecision("RAAPLUSDT", "buy", notional_usd=1_000.0, rationale="test", stop_loss_pct=0.01)
    result = evaluate_decision(decision, state, recent_volatility=0.01)
    assert result.approved
    assert result.adjusted_notional_usd == pytest.approx(100.0, abs=1e-6)


def test_invalid_equity_is_rejected_not_crashed():
    decision = TradeDecision("RAAPLUSDT", "buy", notional_usd=100.0, rationale="test")
    result = evaluate_decision(decision, _state(equity=0.0), recent_volatility=0.01)
    assert not result.approved
    assert result.adjusted_notional_usd == 0.0
