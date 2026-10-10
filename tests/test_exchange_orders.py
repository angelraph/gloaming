"""
The opt-in demo-exchange leg: an approved decision also sent to Bitget's demo matching engine as
an order on the stock perpetual. Everything runs against a scripted fake exchange (no network,
no credentials): the point is the splitting around an existing position in hedge mode, the
exchange minimums, that nothing here can raise into the cycle, and that the ledger is untouched.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "gloaming_agent"))

import agent_loop  # noqa: E402
import execution  # noqa: E402
import paper_ledger  # noqa: E402
from fairvalue.config import RTOKEN_UNIVERSE  # noqa: E402
from risk_controls import TradeDecision  # noqa: E402

PRICE = 336.70


class FakeExchange:
    """Just enough of Bitget's UTA v3 demo API: instruments, tickers, positions, place and detail."""

    def __init__(self, long=0.0, short=0.0, fail_place=False, bad_positions=False):
        self.pos = {"long": long, "short": short}
        self.fail_place = fail_place
        self.bad_positions = bad_positions
        self.placed = []
        self.reads = 0

    def read(self, args):
        self.reads += 1
        tool, action = args[0], args[args.index("--action") + 1]
        if tool == "market" and action == "instruments":
            return {"data": [{"symbol": "AAPLUSDT", "minOrderQty": "0.01", "quantityPrecision": "2", "minOrderAmount": "5"}]}
        if tool == "market" and action == "tickers":
            return {"data": [{"symbol": "AAPLUSDT", "lastPrice": str(PRICE)}]}
        if tool == "position":
            if self.bad_positions:
                return {"data": {"list": [{"symbol": "AAPLUSDT", "posSide": "long", "weird": "x"}]}}
            rows = [{"symbol": "AAPLUSDT", "posSide": s, "total": str(q)} for s, q in self.pos.items() if q]
            return {"data": {"list": rows}} if rows else {"data": {}}
        if tool == "order" and action == "detail":
            oid = args[args.index("--orderId") + 1]
            o = next(p for p in self.placed if p["orderId"] == oid)
            return {"data": {"orderId": oid, "orderStatus": "filled", "avgPrice": str(PRICE + 0.05),
                             "cumExecQty": str(o["qty"]), "fee": "0.0123"}}
        raise AssertionError(f"unexpected read {args}")

    def write(self, args):
        assert "--posSide" in args, "hedge mode needs a posSide on every futures order"
        if self.fail_place:
            raise execution.ExecutionError("HTTP 400 from Bitget: Insufficient margin")
        side = args[args.index("--side") + 1]
        pos_side = args[args.index("--posSide") + 1]
        qty = float(args[args.index("--qty") + 1])
        oid = str(1000 + len(self.placed))
        self.placed.append({"orderId": oid, "side": side, "posSide": pos_side, "qty": qty})
        opening = (side == "buy") == (pos_side == "long")
        self.pos[pos_side] += qty if opening else -qty
        return {"data": {"orderId": oid, "clientOid": "x"}}


@pytest.fixture
def exchange(monkeypatch):
    def install(**kw):
        fx = FakeExchange(**kw)
        monkeypatch.setattr(execution, "_run_bgc_read", fx.read)
        monkeypatch.setattr(execution, "_run_bgc_write", fx.write)
        monkeypatch.setattr(execution.time, "sleep", lambda s: None)
        monkeypatch.setenv("GLOAMING_EXCHANGE_ORDERS", "demo")
        execution._instrument_cache.clear()
        return fx
    return install


def test_it_is_off_unless_explicitly_enabled(monkeypatch):
    monkeypatch.delenv("GLOAMING_EXCHANGE_ORDERS", raising=False)
    monkeypatch.setattr(execution, "_run_bgc_write", lambda a: pytest.fail("an order was sent while disabled"))
    monkeypatch.setattr(execution, "_run_bgc_read", lambda a: pytest.fail("the exchange was read while disabled"))
    r = execution.mirror_decision_on_exchange("AAPL", "buy", 500.0)
    assert r["enabled"] is False and "off" in r["skipped_reason"]


def test_every_underlying_maps_to_its_stock_perpetual():
    assert execution.perp_symbol("AAPL") == "AAPLUSDT"
    assert {execution.perp_symbol(u) for u in RTOKEN_UNIVERSE} == {f"{u}USDT" for u in RTOKEN_UNIVERSE}


def test_a_buy_with_a_flat_book_opens_a_long_sized_to_the_precision(exchange):
    fx = exchange()
    r = execution.mirror_decision_on_exchange("AAPL", "buy", 1000.0)
    assert r["ok"] is True and len(r["orders"]) == 1
    assert fx.placed == [{"orderId": "1000", "side": "buy", "posSide": "long", "qty": 2.97}]  # floor(1000 / 336.70, 2)
    o = r["orders"][0]
    assert o["orderId"] == "1000" and o["status"] == "filled"
    assert o["avg_price"] == pytest.approx(336.75) and o["filled_qty"] == pytest.approx(2.97) and o["fee"] == pytest.approx(0.0123)
    assert "raw_place" in o and "raw_detail" in o  # the exchange's own words are kept


def test_a_sell_first_closes_the_long_then_opens_a_short_with_the_rest(exchange):
    fx = exchange(long=1.5)
    r = execution.mirror_decision_on_exchange("AAPL", "sell", 1000.0)  # 2.97 total
    assert r["ok"] is True
    assert [(p["side"], p["posSide"], p["qty"]) for p in fx.placed] == [("sell", "long", 1.5), ("sell", "short", 1.47)]


def test_a_buy_smaller_than_the_short_only_closes_part_of_it(exchange):
    fx = exchange(short=5.0)
    r = execution.mirror_decision_on_exchange("AAPL", "buy", 200.0)  # 0.59
    assert r["ok"] is True
    assert [(p["side"], p["posSide"], p["qty"]) for p in fx.placed] == [("buy", "short", 0.59)]


def test_below_the_exchange_minimum_nothing_is_sent_and_the_reason_is_recorded(exchange):
    fx = exchange()
    r = execution.mirror_decision_on_exchange("AAPL", "buy", 3.0)
    assert fx.placed == [] and "below the exchange minimum" in r["skipped_reason"]


def test_a_rejected_order_is_recorded_not_raised(exchange):
    exchange(fail_place=True)
    r = execution.mirror_decision_on_exchange("AAPL", "buy", 500.0)
    assert r["ok"] is False
    assert "Insufficient margin" in r["orders"][0]["error"]


def test_a_position_it_cannot_read_stops_the_order_instead_of_guessing(exchange):
    fx = exchange(bad_positions=True)
    r = execution.mirror_decision_on_exchange("AAPL", "buy", 500.0)
    assert fx.placed == [] and r["ok"] is False and "could not read the position size" in r["error"]


def test_an_exchange_outage_never_raises_into_the_cycle(monkeypatch):
    monkeypatch.setenv("GLOAMING_EXCHANGE_ORDERS", "demo")
    execution._instrument_cache.clear()

    def boom(args):
        raise execution.ExecutionError("connection reset")

    monkeypatch.setattr(execution, "_run_bgc_read", boom)
    r = execution.mirror_decision_on_exchange("AAPL", "buy", 500.0)
    assert r["ok"] is False and "connection reset" in r["error"]


# --- inside a cycle: the ledger is untouched and the record carries the exchange's answer ---

@pytest.fixture
def cycle(tmp_path, monkeypatch):
    def _fake_snapshot(underlying, anchor, bitget_signal_context=None):
        cfg = RTOKEN_UNIVERSE[underlying]
        return {
            "underlying": underlying, "rtoken_symbol": cfg["rtoken_symbol"], "rtoken_last_price": 100.0,
            "signal_spec": "since_last_close_v2", "real_close_price": 100.0,
            "real_close_time": "2026-09-25T20:00:00+00:00", "hours_since_close": 1.0,
            "rtoken_return_since_close": 0.0, "rtoken_pcnt_24h": 0.0,
            "futures_proxy_return_since_close": 0.0, "crypto_beta_return_since_close": 0.0,
            "fx_risk_sentiment_return_since_close": 0.0, "fair_value_return_since_close": 0.0,
            "fair_value_price": 100.0, "spread": 0.0, "recent_daily_volatility": 0.02,
            "missing_proxies": [], "bitget_signal_context": bitget_signal_context,
        }

    monkeypatch.setattr(agent_loop, "DECISION_LOG_DIR", tmp_path)
    monkeypatch.setattr(paper_ledger, "LEDGER_PATH", tmp_path / "paper_ledger.json")
    monkeypatch.setattr(paper_ledger, "TRADING_COST_RATE", 0.0)
    monkeypatch.setattr(paper_ledger.kv_sync, "push_ledger_state", lambda *a, **kw: None)
    monkeypatch.setattr(agent_loop.kv_sync, "push_decision_records", lambda records: None)
    monkeypatch.setattr(agent_loop.llm_client, "is_configured", lambda: False)
    monkeypatch.setattr(agent_loop, "is_nyse_closed", lambda: True)
    monkeypatch.setattr(agent_loop, "fetch_overnight_anchor", lambda u, f: object())
    monkeypatch.setattr(agent_loop.bitget_signal, "get_signal_context", lambda: None)
    monkeypatch.setattr(agent_loop, "build_snapshot", _fake_snapshot)

    def buy_aapl_only(snapshot):
        if snapshot["underlying"] != "AAPL":
            return None, "test"
        return TradeDecision(snapshot["rtoken_symbol"], "buy", 500.0, "test buy", stop_loss_pct=0.02), "test"

    monkeypatch.setattr(agent_loop, "decide", buy_aapl_only)


def test_a_filled_decision_also_carries_the_exchange_answer_and_the_ledger_is_unchanged(cycle, exchange):
    fx = exchange()
    records = agent_loop.run_once(dry_run=False, force=True)
    aapl = next(r for r in records if r["underlying"] == "AAPL")
    assert isinstance(aapl["execution"], dict)  # the paper fill happened as before
    assert aapl["exchange"]["ok"] is True and aapl["exchange"]["orders"][0]["orderId"] == "1000"
    assert len(fx.placed) == 1
    assert paper_ledger._load().positions["RAAPLUSDT"] > 0


def test_if_the_exchange_leg_blows_up_the_fill_and_the_cycle_survive(cycle, exchange, monkeypatch):
    exchange()
    monkeypatch.setattr(execution, "mirror_decision_on_exchange", lambda *a: (_ for _ in ()).throw(RuntimeError("boom")))
    records = agent_loop.run_once(dry_run=False, force=True)
    aapl = next(r for r in records if r["underlying"] == "AAPL")
    assert isinstance(aapl["execution"], dict)
    assert aapl["exchange"]["ok"] is False and "boom" in aapl["exchange"]["error"]
    assert len(records) == len(RTOKEN_UNIVERSE)


def test_a_dry_run_sends_nothing_to_the_exchange(cycle, exchange):
    fx = exchange()
    records = agent_loop.run_once(dry_run=True, force=True)
    assert fx.placed == [] and all("exchange" not in r for r in records)
