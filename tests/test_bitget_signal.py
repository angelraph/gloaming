"""
Unit tests for gloaming_agent/bitget_signal.py - Bitget's own public bitget-signal
MCP server integration. Every test mocks the HTTP layer directly; none of these
ever make a real network call, matching the pattern used for every other external
dependency in this project (kv_sync, llm_client).
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "gloaming_agent"))

import bitget_signal  # noqa: E402


def _fake_init_response(session_id="test-session-id"):
    resp = MagicMock()
    resp.headers = {"mcp-session-id": session_id}
    resp.raise_for_status = lambda: None
    return resp


def _fake_call_response(sse_text):
    resp = MagicMock()
    resp.text = sse_text
    resp.raise_for_status = lambda: None
    return resp


def test_get_crypto_sentiment_returns_real_data_when_available(monkeypatch):
    sse = (
        ': ping - ignored\n\n'
        'event: message\n'
        'data: {"jsonrpc":"2.0","id":2,"result":{"content":[{"type":"text",'
        '"text":"{\\"value\\": 42, \\"label\\": \\"Fear\\"}"}],"isError":false}}\n'
    )

    with patch("bitget_signal.requests.post") as mock_post:
        mock_post.side_effect = [_fake_init_response(), _fake_call_response(sse)]
        result = bitget_signal.get_crypto_sentiment()

    assert result == {"value": 42, "label": "Fear"}


def test_returns_none_not_fabricated_data_when_source_has_nothing(monkeypatch):
    """Confirmed live Sept 22: the real server can respond successfully (isError
    stays false) while the underlying data source has nothing, represented as a
    lone *_error key with an empty string. That must resolve to None, never to a
    fabricated value standing in for real data."""
    sse = (
        'event: message\n'
        'data: {"jsonrpc":"2.0","id":2,"result":{"content":[{"type":"text",'
        '"text":"{\\"alt_me_error\\": \\"\\"}"}],"isError":false}}\n'
    )

    with patch("bitget_signal.requests.post") as mock_post:
        mock_post.side_effect = [_fake_init_response(), _fake_call_response(sse)]
        result = bitget_signal.get_crypto_sentiment()

    assert result is None


def test_returns_none_on_mcp_level_error(monkeypatch):
    sse = (
        'event: message\n'
        'data: {"jsonrpc":"2.0","id":2,"result":{"content":[{"type":"text",'
        '"text":"Error executing tool: ConnectTimeout"}],"isError":true}}\n'
    )

    with patch("bitget_signal.requests.post") as mock_post:
        mock_post.side_effect = [_fake_init_response(), _fake_call_response(sse)]
        result = bitget_signal.get_derivatives_sentiment()

    assert result is None


def test_never_raises_on_network_failure(monkeypatch):
    """A real connection failure must degrade to None, exactly like every other
    external call in this project - never break the Agent's actual trading loop."""
    with patch("bitget_signal.requests.post") as mock_post:
        mock_post.side_effect = ConnectionError("simulated network failure")
        result = bitget_signal.get_crypto_sentiment()

    assert result is None


def test_never_raises_when_session_id_missing(monkeypatch):
    resp = MagicMock()
    resp.headers = {}
    resp.raise_for_status = lambda: None

    with patch("bitget_signal.requests.post") as mock_post:
        mock_post.return_value = resp
        result = bitget_signal.get_crypto_sentiment()

    assert result is None


def test_get_signal_context_bundles_only_the_real_values_present(monkeypatch):
    monkeypatch.setattr(bitget_signal, "get_crypto_sentiment", lambda: {"value": 55})
    monkeypatch.setattr(bitget_signal, "get_derivatives_sentiment", lambda: None)

    context = bitget_signal.get_signal_context()

    assert context == {"fear_greed": {"value": 55}}
    assert "long_short" not in context


def test_get_signal_context_returns_none_when_both_sources_are_empty(monkeypatch):
    monkeypatch.setattr(bitget_signal, "get_crypto_sentiment", lambda: None)
    monkeypatch.setattr(bitget_signal, "get_derivatives_sentiment", lambda: None)

    assert bitget_signal.get_signal_context() is None
