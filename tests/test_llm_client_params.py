"""
The Qwen call's request parameters: thinking off by default (measured 5-8s versus
30s+ with it on), one retry not two, and a fall back to a plain request only when the
endpoint rejects the parameter, never on a timeout. No real network calls: the OpenAI
client is replaced by a recording fake.
"""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "gloaming_agent"))

import llm_client  # noqa: E402


class _Message:
    def __init__(self, content):
        self.content = content


class _Choice:
    def __init__(self, content):
        self.message = _Message(content)


class _Response:
    def __init__(self, content):
        self.choices = [_Choice(content)]


class _HTTPError(Exception):
    def __init__(self, status_code):
        super().__init__(f"http {status_code}")
        self.status_code = status_code


class _FakeClient:
    """Records every create() call; each outcome is either a response or an exception."""

    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = []
        self.options = []

    def with_options(self, **options):
        self.options.append(options)
        return self

    @property
    def chat(self):
        return self

    @property
    def completions(self):
        return self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _ok():
    return _Response(json.dumps({"action": "hold"}))


@pytest.fixture
def install(monkeypatch):
    monkeypatch.setenv("QWEN_API_KEY", "test-key")
    monkeypatch.delenv("QWEN_ENABLE_THINKING", raising=False)

    def _install(outcomes):
        fake = _FakeClient(outcomes)
        monkeypatch.setattr(llm_client, "_client", lambda: fake)
        return fake

    return _install


def test_thinking_is_off_by_default_and_uses_one_retry(install):
    fake = install([_ok()])
    assert llm_client.get_decision_json("sys", "user") == {"action": "hold"}
    assert fake.calls[0]["extra_body"] == {"enable_thinking": False}
    assert fake.options == [{"max_retries": 1}]
    assert fake.calls[0]["timeout"] == 30.0


def test_thinking_can_be_switched_back_on_by_environment(install, monkeypatch):
    monkeypatch.setenv("QWEN_ENABLE_THINKING", "1")
    fake = install([_ok()])
    llm_client.get_decision_json("sys", "user")
    assert "extra_body" not in fake.calls[0]


def test_a_rejected_parameter_is_retried_once_without_it(install):
    fake = install([_HTTPError(400), _ok()])
    assert llm_client.get_decision_json("sys", "user") == {"action": "hold"}
    assert len(fake.calls) == 2
    assert "extra_body" in fake.calls[0]
    assert "extra_body" not in fake.calls[1]


def test_a_timeout_is_not_retried_by_the_parameter_fallback(install):
    fake = install([TimeoutError("Request timed out.")])
    with pytest.raises(llm_client.LLMError):
        llm_client.get_decision_json("sys", "user")
    assert len(fake.calls) == 1


def test_a_server_error_is_not_mistaken_for_a_rejected_parameter(install):
    fake = install([_HTTPError(500)])
    with pytest.raises(llm_client.LLMError):
        llm_client.get_decision_json("sys", "user")
    assert len(fake.calls) == 1


def test_a_second_failure_after_the_fallback_still_raises_llm_error(install):
    fake = install([_HTTPError(400), _HTTPError(400)])
    with pytest.raises(llm_client.LLMError):
        llm_client.get_decision_json("sys", "user")
    assert len(fake.calls) == 2
