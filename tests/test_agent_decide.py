"""
Unit tests for gloaming_agent/agent_loop.py's decision dispatcher. All Qwen calls
are mocked (monkeypatched) - these tests never hit the real network, which is
exactly the point: they exercise the fallback logic itself, not Qwen's actual
output quality.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "gloaming_agent"))

import agent_loop  # noqa: E402
import llm_client  # noqa: E402


def _snapshot(spread=0.04):
    return {
        "underlying": "AAPL",
        "rtoken_symbol": "RAAPLUSDT",
        "rtoken_last_price": 300.0,
        "rtoken_pcnt_24h": 0.03,
        "futures_proxy_pcnt_24h": -0.01,
        "crypto_beta_pcnt_24h": -0.01,
        "fx_risk_sentiment_pcnt_24h": 0.0,
        "fair_value_return_24h": -0.01,
        "spread": spread,
    }


def test_decide_falls_back_to_rule_based_when_qwen_not_configured(monkeypatch):
    monkeypatch.setattr(llm_client, "is_configured", lambda: False)
    decision, source = agent_loop.decide(_snapshot())
    assert "rule_based" in source
    assert "not configured" in source
    assert decision is not None
    assert decision.side == "sell"  # positive spread -> rich -> sell, per decide_rule_based


def test_decide_uses_qwen_when_configured_and_call_succeeds(monkeypatch):
    monkeypatch.setattr(llm_client, "is_configured", lambda: True)
    monkeypatch.setattr(
        llm_client, "get_decision_json",
        lambda system_prompt, user_prompt: {
            "action": "buy", "notional_usd": 300.0, "stop_loss_pct": 0.02,
            "confidence": 0.7, "rationale": "spread looks like a genuine overnight gap",
        },
    )
    decision, source = agent_loop.decide(_snapshot())
    assert source == "qwen3.8-max"
    assert decision.side == "buy"
    assert decision.notional_usd == pytest.approx(300.0)
    assert decision.rationale.startswith("[Qwen3.8-max]")


def test_decide_falls_back_when_qwen_call_raises(monkeypatch):
    monkeypatch.setattr(llm_client, "is_configured", lambda: True)

    def _raise(*a, **kw):
        raise llm_client.LLMError("simulated network failure")

    monkeypatch.setattr(llm_client, "get_decision_json", _raise)
    decision, source = agent_loop.decide(_snapshot())
    assert "rule_based" in source
    assert "simulated network failure" in source
    assert decision is not None  # spread=0.04 is above threshold, rule-based still fires


def test_decide_llm_hold_returns_none(monkeypatch):
    monkeypatch.setattr(
        llm_client, "get_decision_json",
        lambda system_prompt, user_prompt: {"action": "hold", "notional_usd": 0, "rationale": "no edge"},
    )
    assert agent_loop.decide_llm(_snapshot()) is None


def test_decide_llm_invalid_action_raises_llmerror(monkeypatch):
    monkeypatch.setattr(
        llm_client, "get_decision_json",
        lambda system_prompt, user_prompt: {"action": "short_the_moon", "notional_usd": 100},
    )
    with pytest.raises(llm_client.LLMError):
        agent_loop.decide_llm(_snapshot())


def test_decide_llm_caps_notional_regardless_of_qwen_suggestion(monkeypatch):
    monkeypatch.setattr(
        llm_client, "get_decision_json",
        lambda system_prompt, user_prompt: {
            "action": "buy", "notional_usd": 50_000.0, "stop_loss_pct": 0.02,
            "confidence": 1.0, "rationale": "very confident",
        },
    )
    decision = agent_loop.decide_llm(_snapshot())
    assert decision.notional_usd == pytest.approx(1000.0)  # hard ceiling in decide_llm


def test_decide_llm_zero_notional_buy_treated_as_no_trade(monkeypatch):
    monkeypatch.setattr(
        llm_client, "get_decision_json",
        lambda system_prompt, user_prompt: {"action": "buy", "notional_usd": 0, "rationale": "weak signal"},
    )
    assert agent_loop.decide_llm(_snapshot()) is None


def test_build_user_prompt_includes_real_numbers_not_placeholders():
    prompt = agent_loop.build_user_prompt(_snapshot(spread=0.0386))
    assert "RAAPLUSDT" in prompt
    assert "3.86%" in prompt
    assert "$300.00" in prompt
