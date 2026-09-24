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
    # aggregate cap is 60% of 10,000 = 6,000; already holding 5,900 gross across other
    # symbols. Mixed-sign so the net directional cap (tested separately below) is not
    # what binds here: net is only 100.
    state = _state(equity=10_000.0, positions={"RTSLAUSDT": 3_000.0, "RNVDAUSDT": -2_900.0})
    decision = TradeDecision("RAAPLUSDT", "buy", notional_usd=1_000.0, rationale="test", stop_loss_pct=0.01)
    result = evaluate_decision(decision, state, recent_volatility=0.01)
    assert result.approved
    assert result.adjusted_notional_usd == pytest.approx(100.0, abs=1e-6)


def test_invalid_equity_is_rejected_not_crashed():
    decision = TradeDecision("RAAPLUSDT", "buy", notional_usd=100.0, rationale="test")
    result = evaluate_decision(decision, _state(equity=0.0), recent_volatility=0.01)
    assert not result.approved
    assert result.adjusted_notional_usd == 0.0


def test_derisking_trade_is_exempt_from_aggregate_cap_when_book_is_over_it():
    # Confirmed live Sept 22: a real book sitting over its own aggregate cap
    # rejected every decision for 8 straight days, including ones that would have
    # reduced its risk. A buy against an existing short must still go through.
    state = _state(equity=10_000.0, positions={"RAAPLUSDT": -8_000.0})  # already over the 60% cap
    decision = TradeDecision("RAAPLUSDT", "buy", notional_usd=500.0, rationale="test", stop_loss_pct=0.01)
    result = evaluate_decision(decision, state, recent_volatility=0.01)
    assert result.approved
    assert result.adjusted_notional_usd == pytest.approx(500.0)
    assert any("de-risking" in r for r in result.reasons)


def test_derisking_trade_is_exempt_from_per_symbol_cap_when_already_full():
    # Same idea at the per-symbol level: already "full" per the 15% cap, but a
    # sell against an existing long must still be allowed to reduce it.
    state = _state(equity=10_000.0, positions={"RAAPLUSDT": 1_500.0})  # at the per-symbol cap
    decision = TradeDecision("RAAPLUSDT", "sell", notional_usd=300.0, rationale="test", stop_loss_pct=0.01)
    result = evaluate_decision(decision, state, recent_volatility=0.01)
    assert result.approved
    assert result.adjusted_notional_usd == pytest.approx(300.0)


def test_derisking_exemption_caps_out_at_fully_flattening_the_position():
    # A trade larger than the existing position flips it to the other side -
    # only the de-risking portion (up to flat) is exempt; the flip portion is a
    # normal new-risk trade and goes through the caps like any other.
    state = _state(equity=10_000.0, positions={"RAAPLUSDT": -400.0})
    decision = TradeDecision("RAAPLUSDT", "buy", notional_usd=1_000.0, rationale="test", stop_loss_pct=0.01)
    result = evaluate_decision(decision, state, recent_volatility=0.01)
    assert result.approved
    # 400 exempt (flattens the short) + up to 1,500 room left on the now-empty
    # per-symbol cap for the remaining 600 - the full 1,000 goes through here.
    assert result.adjusted_notional_usd == pytest.approx(1_000.0)


def test_trade_that_adds_to_existing_exposure_is_not_treated_as_derisking():
    # Same direction as the existing position - this must be capped exactly as
    # before, not exempted.
    state = _state(equity=10_000.0, positions={"RAAPLUSDT": -8_000.0})  # already over the 60% cap
    decision = TradeDecision("RAAPLUSDT", "sell", notional_usd=500.0, rationale="test", stop_loss_pct=0.01)
    result = evaluate_decision(decision, state, recent_volatility=0.01)
    assert not result.approved
    assert result.adjusted_notional_usd == 0.0


def test_daily_circuit_breaker_still_allows_a_derisking_trade_through():
    # docs/risk_controls.md control #3 promises existing positions may still be
    # closed/hedged during a daily halt - confirmed live Sept 22 the code did
    # not actually do that. A buy against an existing short must go through.
    state = _state(equity=10_000.0, positions={"RAAPLUSDT": -1_000.0}, daily_realized=-600.0)  # -6% breached
    decision = TradeDecision("RAAPLUSDT", "buy", notional_usd=300.0, rationale="test", stop_loss_pct=0.01)
    result = evaluate_decision(decision, state, recent_volatility=0.01)
    assert result.approved
    assert result.adjusted_notional_usd == pytest.approx(300.0)


def test_daily_circuit_breaker_still_blocks_the_risk_increasing_portion_of_a_flip():
    # A trade larger than the existing position both de-risks (up to flat) and
    # then adds new risk on the other side - only the de-risking part may
    # proceed while the breaker is active, the flip portion is still blocked.
    state = _state(equity=10_000.0, positions={"RAAPLUSDT": -1_000.0}, daily_realized=-600.0)
    decision = TradeDecision("RAAPLUSDT", "buy", notional_usd=1_500.0, rationale="test", stop_loss_pct=0.01)
    result = evaluate_decision(decision, state, recent_volatility=0.01)
    assert result.approved
    assert result.adjusted_notional_usd == pytest.approx(1_000.0)  # flattens, no further


def test_daily_circuit_breaker_rejects_outright_when_theres_nothing_to_derisk():
    # No existing position in this symbol to reduce - must still hard-reject,
    # exactly like before this fix.
    state = _state(equity=10_000.0, daily_realized=-600.0)
    decision = TradeDecision("RAAPLUSDT", "buy", notional_usd=100.0, rationale="test")
    result = evaluate_decision(decision, state, recent_volatility=0.01)
    assert not result.approved
    assert result.adjusted_notional_usd == 0.0
    assert "circuit breaker" in result.reasons[0]


# --- Net directional exposure cap (25% of equity) ---

def test_net_cap_rejects_a_buy_when_the_book_is_already_net_long_at_the_cap():
    # net long 2,500 = exactly 25% of 10,000, gross well under every gross cap
    state = _state(equity=10_000.0, positions={"RTSLAUSDT": 1_300.0, "RNVDAUSDT": 1_200.0})
    decision = TradeDecision("RAAPLUSDT", "buy", notional_usd=300.0, rationale="test", stop_loss_pct=0.01)
    result = evaluate_decision(decision, state, recent_volatility=0.01)
    assert not result.approved
    assert result.adjusted_notional_usd == 0.0


def test_net_cap_resizes_a_buy_to_the_room_left_under_the_cap():
    state = _state(equity=10_000.0, positions={"RTSLAUSDT": 1_500.0, "RNVDAUSDT": 800.0})  # net 2,300
    decision = TradeDecision("RAAPLUSDT", "buy", notional_usd=500.0, rationale="test", stop_loss_pct=0.01)
    result = evaluate_decision(decision, state, recent_volatility=0.01)
    assert result.approved
    assert result.adjusted_notional_usd == pytest.approx(200.0)  # 2,500 - 2,300


def test_net_cap_applies_the_same_way_on_the_short_side():
    state = _state(equity=10_000.0, positions={"RTSLAUSDT": -1_300.0, "RNVDAUSDT": -1_200.0})  # net -2,500
    decision = TradeDecision("RAAPLUSDT", "sell", notional_usd=300.0, rationale="test", stop_loss_pct=0.01)
    result = evaluate_decision(decision, state, recent_volatility=0.01)
    assert not result.approved


def test_net_cap_lets_a_trade_that_reduces_net_exposure_through_even_when_over_the_cap():
    # net long 5,600 = 56% of equity, far over the 25% net cap. A sell that trims
    # a long must still go through - the cap limits new exposure, it never traps the book.
    state = _state(equity=10_000.0, positions={"A": 1_400.0, "B": 1_400.0, "C": 1_400.0, "D": 1_400.0})
    decision = TradeDecision("A", "sell", notional_usd=300.0, rationale="test", stop_loss_pct=0.01)
    result = evaluate_decision(decision, state, recent_volatility=0.01)
    assert result.approved
    assert result.adjusted_notional_usd == pytest.approx(300.0)


def test_net_cap_lets_a_new_short_through_when_the_book_is_net_long():
    # opening a short in a fresh symbol reduces net long exposure - allowed
    state = _state(equity=10_000.0, positions={"A": 1_400.0, "B": 1_400.0, "C": 1_400.0, "D": 1_400.0})
    decision = TradeDecision("E", "sell", notional_usd=300.0, rationale="test", stop_loss_pct=0.01)
    result = evaluate_decision(decision, state, recent_volatility=0.01)
    assert result.approved
    assert result.adjusted_notional_usd == pytest.approx(300.0)


def test_net_cap_limits_how_far_a_single_trade_can_flip_the_book_past_zero():
    config = RiskConfig(max_net_notional_pct=0.05)  # 500 on 10,000 equity
    state = _state(equity=10_000.0, positions={"A": 300.0})  # net +300
    decision = TradeDecision("A", "sell", notional_usd=1_000.0, rationale="test", stop_loss_pct=0.01)
    result = evaluate_decision(decision, state, recent_volatility=0.01, config=config)
    assert result.approved
    # 300 flattens net, then at most 500 the other way
    assert result.adjusted_notional_usd == pytest.approx(800.0)


def test_net_cap_does_not_touch_a_balanced_book():
    # long 1,400 / short 1,400: gross 2,800, net 0 - room for a full-size trade
    state = _state(equity=10_000.0, positions={"A": 1_400.0, "B": -1_400.0})
    decision = TradeDecision("C", "buy", notional_usd=500.0, rationale="test", stop_loss_pct=0.01)
    result = evaluate_decision(decision, state, recent_volatility=0.01)
    assert result.approved
    assert result.adjusted_notional_usd == pytest.approx(500.0)


# --- Backstop trim planner, the tracker that decides when it engages, capacity probe ---

from risk_controls import plan_net_trim, trade_capacity_usd, update_net_over_cap_tracker  # noqa: E402


def test_plan_net_trim_does_nothing_within_the_tolerance_band():
    # net long 2,550 = 25.5% of 10,000: over the 25% cap by 50, inside the 1% band
    state = _state(equity=10_000.0, positions={"A": 1_300.0, "B": 1_250.0})
    assert plan_net_trim(state) == []


def test_plan_net_trim_sells_a_bounded_proportional_slice_when_net_long_and_over_the_cap():
    # net long 5,000 (50%), cap 2,500, excess 2,500; per-cycle limit is 2% of equity = 200
    state = _state(equity=10_000.0, positions={"A": 3_000.0, "B": 2_000.0})
    decisions = plan_net_trim(state)
    assert {d.symbol for d in decisions} == {"A", "B"}
    assert all(d.side == "sell" for d in decisions)
    assert sum(d.notional_usd for d in decisions) == pytest.approx(200.0)
    by_symbol = {d.symbol: d.notional_usd for d in decisions}
    assert by_symbol["A"] == pytest.approx(120.0)  # 3,000 / 5,000 of the slice
    assert by_symbol["B"] == pytest.approx(80.0)
    assert "not the LLM" in decisions[0].rationale


def test_plan_net_trim_buys_back_when_the_book_is_net_short():
    state = _state(equity=10_000.0, positions={"A": -3_000.0, "B": -2_000.0})
    decisions = plan_net_trim(state)
    assert decisions and all(d.side == "buy" for d in decisions)


def test_plan_net_trim_only_touches_the_over_exposed_side():
    state = _state(equity=10_000.0, positions={"A": 4_000.0, "B": 2_000.0, "C": -500.0})
    symbols = {d.symbol for d in plan_net_trim(state)}
    assert symbols == {"A", "B"}


def test_plan_net_trim_never_trades_more_than_the_excess():
    # excess 1,100 (cap 2,500, net 3,600) is smaller than the 2% slice would allow
    config = RiskConfig(net_trim_max_pct_per_cycle=0.5)
    state = _state(equity=10_000.0, positions={"A": 3_600.0})
    total = sum(d.notional_usd for d in plan_net_trim(state, config))
    assert total == pytest.approx(1_100.0)


def test_plan_net_trim_skips_orders_below_the_minimum():
    config = RiskConfig(net_trim_min_order_usd=1_000.0)
    state = _state(equity=10_000.0, positions={"A": 3_000.0, "B": 2_000.0})
    assert plan_net_trim(state, config) == []


def test_plan_net_trim_handles_zero_equity_and_an_empty_book():
    assert plan_net_trim(_state(equity=0.0, positions={"A": 100.0})) == []
    assert plan_net_trim(_state(equity=10_000.0)) == []


def test_every_planned_trim_is_approved_by_the_real_gate_even_when_the_daily_breaker_is_on():
    state = _state(equity=10_000.0, positions={"A": 3_000.0, "B": 2_000.0}, daily_realized=-600.0)
    for d in plan_net_trim(state):
        result = evaluate_decision(d, state, recent_volatility=0.0)
        assert result.approved
        assert result.adjusted_notional_usd == pytest.approx(d.notional_usd)


def test_tracker_resets_when_the_book_is_within_the_band():
    assert update_net_over_cap_tracker(5, 3_000.0, 50.0, 10_000.0) == (0, 0.0)


def test_tracker_starts_a_clock_the_first_cycle_over_the_cap():
    assert update_net_over_cap_tracker(0, 0.0, 2_000.0, 10_000.0) == (1, 2_000.0)


def test_tracker_counts_cycles_without_progress():
    cycles, baseline = 1, 2_000.0
    for _ in range(3):
        cycles, baseline = update_net_over_cap_tracker(cycles, baseline, 1_950.0, 10_000.0)  # only 50 of progress
    assert cycles == 4
    assert baseline == 2_000.0


def test_tracker_restarts_the_clock_when_the_llm_makes_real_progress():
    # excess fell from 2,000 to 1,800: 200 of progress, over the 1% of equity (100) threshold
    assert update_net_over_cap_tracker(5, 2_000.0, 1_800.0, 10_000.0) == (1, 1_800.0)


def test_tracker_stays_engaged_once_the_backstop_has_started_even_as_its_own_trims_shrink_the_excess():
    config = RiskConfig()
    cycles, baseline = config.net_trim_backstop_cycles, 2_000.0
    cycles_after, baseline_after = update_net_over_cap_tracker(cycles, baseline, 1_000.0, 10_000.0, config)
    assert cycles_after == cycles  # the trim's own progress must not disengage it
    assert baseline_after == baseline


def test_trade_capacity_reflects_the_real_gate():
    at_cap_long = _state(equity=10_000.0, positions={"A": 1_300.0, "B": 1_200.0})  # net +2,500
    assert trade_capacity_usd(at_cap_long, "C", "buy") == 0.0
    assert trade_capacity_usd(at_cap_long, "A", "sell") > 0.0
    balanced = _state(equity=10_000.0, positions={"A": 1_000.0, "B": -1_000.0})
    assert trade_capacity_usd(balanced, "C", "buy") > 0.0
    assert trade_capacity_usd(_state(equity=0.0), "C", "buy") == 0.0
