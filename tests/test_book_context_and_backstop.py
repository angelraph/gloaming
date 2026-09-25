"""
Tests for what the LLM is shown about its own book (build_book_context and the
prompt built from it), the re-mark of that book after each real fill within a
cycle, and the deterministic net-exposure backstop (_net_backstop_pass).

Everything runs against a temp ledger and decision log with every network-capable
dependency stubbed, same isolation as test_run_once_incremental.py.
"""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "gloaming_agent"))

import agent_loop  # noqa: E402
import paper_ledger  # noqa: E402
from fairvalue.config import RTOKEN_UNIVERSE  # noqa: E402
from risk_controls import PortfolioState, RiskConfig, TradeDecision  # noqa: E402

SYMBOLS = [cfg["rtoken_symbol"] for cfg in RTOKEN_UNIVERSE.values()]


def _fake_snapshot(underlying, anchor, bitget_signal_context=None):
    cfg = RTOKEN_UNIVERSE[underlying]
    return {
        "underlying": underlying,
        "rtoken_symbol": cfg["rtoken_symbol"],
        "rtoken_last_price": 100.0,
        "signal_spec": "since_last_close_v2",
        "real_close_price": 100.0,
        "real_close_time": "2026-09-25T20:00:00+00:00",
        "hours_since_close": 1.0,
        "rtoken_return_since_close": 0.0,
        "rtoken_pcnt_24h": 0.0,
        "futures_proxy_return_since_close": 0.0,
        "crypto_beta_return_since_close": 0.0,
        "fx_risk_sentiment_return_since_close": 0.0,
        "fair_value_return_since_close": 0.0,
        "fair_value_price": 100.0,
        "spread": 0.0,
        "recent_daily_volatility": 0.02,
        "missing_proxies": [],
        "bitget_signal_context": bitget_signal_context,
    }


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(agent_loop, "DECISION_LOG_DIR", tmp_path)
    monkeypatch.setattr(paper_ledger, "LEDGER_PATH", tmp_path / "paper_ledger.json")
    monkeypatch.setattr(paper_ledger.kv_sync, "push_ledger_state", lambda *a, **kw: None)
    monkeypatch.setattr(agent_loop.kv_sync, "push_decision_records", lambda records: None)
    monkeypatch.setattr(agent_loop.llm_client, "is_configured", lambda: False)
    monkeypatch.setattr(agent_loop, "is_nyse_closed", lambda: True)
    monkeypatch.setattr(agent_loop, "fetch_overnight_anchor", lambda underlyings, futures_tickers: object())
    monkeypatch.setattr(agent_loop.bitget_signal, "get_signal_context", lambda: None)
    monkeypatch.setattr(agent_loop, "build_snapshot", _fake_snapshot)
    yield


def _state(equity=10_000.0, positions=None, daily_pnl=0.0):
    return PortfolioState(
        equity_usd=equity,
        positions_notional_usd=positions or {},
        daily_realized_pnl_usd=daily_pnl,
    )


def _build_net_long_book(symbols_and_notional):
    """Real fills into the temp ledger at $100 a share, so the book is genuinely long."""
    for symbol, notional in symbols_and_notional.items():
        paper_ledger.record_fill(symbol, "buy", notional / 100.0, 100.0, "setup")


MARKS = {symbol: 100.0 for symbol in SYMBOLS}


# --- build_book_context ---

def test_book_context_reports_the_position_the_net_and_gross_exposure_and_the_caps():
    state = _state(positions={"A": 1_500.0, "B": -500.0})
    book = agent_loop.build_book_context(state, "A", [])
    assert book["symbol_position_usd"] == 1_500.0
    assert book["net_exposure_usd"] == 1_000.0
    assert book["gross_exposure_usd"] == 2_000.0
    assert book["net_exposure_pct"] == pytest.approx(0.10)
    assert book["net_cap_pct"] == 0.25 and book["gross_cap_pct"] == 0.60 and book["symbol_cap_pct"] == 0.15
    assert book["over_net_cap"] is False


def test_book_context_flags_an_over_cap_book_and_shows_real_capacity():
    state = _state(positions={"A": 1_400.0, "B": 1_400.0, "C": 1_400.0})  # net +4,200 = 42%
    book = agent_loop.build_book_context(state, "A", [])
    assert book["over_net_cap"] is True
    assert book["buy_capacity_usd"] == 0.0
    assert book["sell_capacity_usd"] > 0.0


def test_book_context_includes_recent_fills_with_their_age():
    an_hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    fills = [{"timestamp": an_hour_ago, "symbol": "A", "side": "buy", "notional_usd": 400.0}]
    book = agent_loop.build_book_context(_state(positions={"A": 400.0}), "A", fills)
    assert book["recent_fills_this_symbol"][0]["side"] == "buy"
    assert book["recent_fills_this_symbol"][0]["hours_ago"] == pytest.approx(1.0, abs=0.1)


# --- what the prompt actually tells Qwen ---

def _snapshot_with_book(book):
    snap = _fake_snapshot("AAPL", None)
    snap["book_context"] = book
    return snap


def test_prompt_shows_qwen_its_position_the_net_exposure_and_the_capacity():
    state = _state(positions={"RAAPLUSDT": 1_500.0, "B": 500.0})
    book = agent_loop.build_book_context(state, "RAAPLUSDT", [])
    prompt = agent_loop.build_user_prompt(_snapshot_with_book(book))
    assert "Your current book" in prompt
    assert "long $1,500" in prompt
    assert "net exposure" in prompt and "net cap 25%" in prompt
    assert "buy up to" in prompt and "sell up to" in prompt
    assert "OVER THE NET CAP" not in prompt


def test_prompt_tells_qwen_when_the_book_is_over_its_net_cap():
    state = _state(positions={"RAAPLUSDT": 1_400.0, "B": 1_400.0, "C": 1_400.0})
    book = agent_loop.build_book_context(state, "RAAPLUSDT", [])
    prompt = agent_loop.build_user_prompt(_snapshot_with_book(book))
    assert "OVER THE NET CAP" in prompt
    assert "Bringing net exposure back under the cap is part of your job" in prompt


def test_prompt_says_flat_for_a_symbol_with_no_position():
    book = agent_loop.build_book_context(_state(positions={"B": 500.0}), "RAAPLUSDT", [])
    assert "flat (no position)" in agent_loop.build_user_prompt(_snapshot_with_book(book))


def test_prompt_is_unchanged_when_there_is_no_book_context():
    prompt = agent_loop.build_user_prompt(_fake_snapshot("AAPL", None))
    assert "Your current book" not in prompt
    assert prompt.rstrip().endswith("Decide whether this spread is an actionable mispricing.")


# --- the book context is attached and re-marked after each real fill ---

def test_each_symbols_snapshot_carries_the_book_context_qwen_saw():
    records = agent_loop.run_once(dry_run=True, force=True)
    assert len(records) == len(RTOKEN_UNIVERSE)
    for record in records:
        assert record["snapshot"]["book_context"]["equity_usd"] == pytest.approx(100_000.0)


def test_the_book_is_re_marked_after_each_real_fill_within_a_cycle(monkeypatch):
    def always_buy(snapshot):
        return TradeDecision(snapshot["rtoken_symbol"], "buy", 500.0, "test buy", stop_loss_pct=0.02), "test"

    monkeypatch.setattr(agent_loop, "decide", always_buy)
    records = agent_loop.run_once(dry_run=False, force=True)
    trade_records = [r for r in records if r.get("decision")]
    nets = [r["snapshot"]["book_context"]["net_exposure_usd"] for r in trade_records[:4]]
    # symbol 1 saw a flat book; each later symbol saw the fills made before it this cycle
    assert nets[0] == pytest.approx(0.0)
    assert nets[1] == pytest.approx(500.0, abs=1.0)
    assert nets[2] == pytest.approx(1_000.0, abs=1.0)
    assert nets[3] == pytest.approx(1_500.0, abs=1.0)


# --- holds keep their reasoning ---

def test_a_hold_is_logged_with_qwens_reasoning_on_the_record_not_buried_in_the_snapshot(monkeypatch):
    monkeypatch.setattr(agent_loop.llm_client, "is_configured", lambda: True)
    monkeypatch.setattr(
        agent_loop.llm_client, "get_decision_json",
        lambda system_prompt, user_prompt: {"action": "hold", "notional_usd": 0, "rationale": "inside tracking noise"},
    )
    records = agent_loop.run_once(dry_run=True, force=True)
    assert len(records) == len(RTOKEN_UNIVERSE)
    for record in records:
        assert record["decision"] is None
        assert record["hold_rationale"] == "[Qwen3.8-max] inside tracking noise"
        assert "hold_rationale" not in record["snapshot"]


# --- the per-cycle LLM time budget ---

def test_once_the_llm_time_budget_is_spent_remaining_symbols_use_the_labeled_fallback(monkeypatch):
    calls = []

    def fake_decide(snapshot):
        calls.append(snapshot["rtoken_symbol"])
        return None, "test-llm"

    monkeypatch.setattr(agent_loop, "decide", fake_decide)
    monkeypatch.setattr(agent_loop, "LLM_CYCLE_BUDGET_S", -1.0)  # already spent before the first symbol
    records = agent_loop.run_once(dry_run=True, force=True)
    assert calls == []  # the LLM was never called
    assert all("LLM time budget for this cycle exhausted" in r["decision_source"] for r in records)


def test_the_llm_is_called_for_every_symbol_while_the_budget_lasts(monkeypatch):
    calls = []

    def fake_decide(snapshot):
        calls.append(snapshot["rtoken_symbol"])
        return None, "test-llm"

    monkeypatch.setattr(agent_loop, "decide", fake_decide)
    records = agent_loop.run_once(dry_run=True, force=True)
    assert len(calls) == len(RTOKEN_UNIVERSE)
    assert all(r["decision_source"] == "test-llm" for r in records)


# --- the deterministic backstop ---

def _emitted():
    emitted = []
    return emitted, emitted.append


def test_backstop_does_nothing_and_starts_a_clock_the_first_cycle_the_book_is_over_the_cap():
    _build_net_long_book({s: 6_000.0 for s in SYMBOLS[:6]})  # net +36,000 of 100,000 equity, cap 25,000
    emitted, emit = _emitted()
    records = agent_loop._net_backstop_pass(MARKS, {}, emit, dry_run=False)
    assert records == [] and emitted == []
    cycles, baseline = paper_ledger.get_net_tracker()
    assert cycles == 1
    assert baseline == pytest.approx(11_000.0, abs=1.0)


def test_backstop_trims_once_the_llm_has_had_its_cycles_without_progress():
    _build_net_long_book({s: 6_000.0 for s in SYMBOLS[:6]})
    paper_ledger.set_net_tracker(RiskConfig().net_trim_backstop_cycles, 11_000.0)
    emitted, emit = _emitted()
    records = agent_loop._net_backstop_pass(MARKS, {}, emit, dry_run=False)

    assert records and records == emitted
    assert all("risk_backstop_trim" in r["decision_source"] for r in records)
    assert all("not the LLM" in r["decision_source"] for r in records)
    assert all(r["decision"]["side"] == "sell" for r in records)
    assert all(isinstance(r["execution"], dict) and r["execution"]["side"] == "sell" for r in records)
    assert sum(r["execution"]["notional_usd"] for r in records) == pytest.approx(2_000.0, abs=5.0)  # 2% of equity
    positions = paper_ledger._load().positions
    assert sum(positions.values()) * 100.0 < 36_000.0  # the book actually got smaller


def test_backstop_keeps_trimming_on_later_cycles_once_engaged():
    _build_net_long_book({s: 6_000.0 for s in SYMBOLS[:6]})
    paper_ledger.set_net_tracker(RiskConfig().net_trim_backstop_cycles, 11_000.0)
    _, emit = _emitted()
    first = agent_loop._net_backstop_pass(MARKS, {}, emit, dry_run=False)
    second = agent_loop._net_backstop_pass(MARKS, {}, emit, dry_run=False)
    assert first and second  # its own progress did not switch it off


def test_backstop_disengages_and_resets_once_the_book_is_back_inside_the_cap():
    _build_net_long_book({s: 3_000.0 for s in SYMBOLS[:6]})  # net +18,000, under the 25,000 cap
    paper_ledger.set_net_tracker(RiskConfig().net_trim_backstop_cycles, 11_000.0)
    _, emit = _emitted()
    assert agent_loop._net_backstop_pass(MARKS, {}, emit, dry_run=False) == []
    assert paper_ledger.get_net_tracker() == (0, 0.0)


def test_backstop_gives_the_llm_credit_for_real_progress_and_restarts_the_clock():
    _build_net_long_book({s: 6_000.0 for s in SYMBOLS[:6]})  # excess 11,000
    paper_ledger.set_net_tracker(5, 20_000.0)  # excess has fallen a lot since the clock started
    _, emit = _emitted()
    assert agent_loop._net_backstop_pass(MARKS, {}, emit, dry_run=False) == []
    assert paper_ledger.get_net_tracker()[0] == 1


def test_backstop_touches_nothing_on_a_dry_run():
    _build_net_long_book({s: 6_000.0 for s in SYMBOLS[:6]})
    paper_ledger.set_net_tracker(RiskConfig().net_trim_backstop_cycles, 11_000.0)
    before = json.loads(paper_ledger.LEDGER_PATH.read_text())
    _, emit = _emitted()
    assert agent_loop._net_backstop_pass(MARKS, {}, emit, dry_run=True) == []
    assert json.loads(paper_ledger.LEDGER_PATH.read_text()) == before


def test_backstop_never_trades_a_symbol_it_has_no_fresh_price_for():
    _build_net_long_book({s: 6_000.0 for s in SYMBOLS[:6]})
    paper_ledger.set_net_tracker(RiskConfig().net_trim_backstop_cycles, 11_000.0)
    stale_symbol = SYMBOLS[0]
    marks = {s: p for s, p in MARKS.items() if s != stale_symbol}
    _, emit = _emitted()
    records = agent_loop._net_backstop_pass(marks, {}, emit, dry_run=False)
    assert records
    assert all(r["decision"]["symbol"] != stale_symbol for r in records)


def test_backstop_failure_never_costs_the_cycle_its_records(monkeypatch):
    def boom(*a, **kw):
        raise RuntimeError("ledger unavailable")

    monkeypatch.setattr(agent_loop.paper_ledger, "get_portfolio_state", boom)
    _, emit = _emitted()
    assert agent_loop._net_backstop_pass(MARKS, {}, emit, dry_run=False) == []


def test_run_once_carries_the_backstop_records_alongside_the_llm_ones():
    _build_net_long_book({s: 6_000.0 for s in SYMBOLS[:6]})
    paper_ledger.set_net_tracker(RiskConfig().net_trim_backstop_cycles, 11_000.0)
    records = agent_loop.run_once(dry_run=False, force=True)
    sources = [r.get("decision_source", "") for r in records]
    assert any("risk_backstop_trim" in s for s in sources)
    assert any("rule_based" in s for s in sources)  # the per-symbol pass still ran
