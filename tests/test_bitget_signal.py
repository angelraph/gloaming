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
    monkeypatch.setattr(bitget_signal, "get_news_briefing", lambda: None)
    monkeypatch.setattr(bitget_signal, "get_macro_context", lambda: None)

    context = bitget_signal.get_signal_context()

    assert context == {"fear_greed": {"value": 55}}
    assert "long_short" not in context
    assert "news" not in context
    assert "macro" not in context


def test_get_signal_context_returns_none_when_every_source_is_empty(monkeypatch):
    monkeypatch.setattr(bitget_signal, "get_crypto_sentiment", lambda: None)
    monkeypatch.setattr(bitget_signal, "get_derivatives_sentiment", lambda: None)
    monkeypatch.setattr(bitget_signal, "get_news_briefing", lambda: None)
    monkeypatch.setattr(bitget_signal, "get_macro_context", lambda: None)

    assert bitget_signal.get_signal_context() is None


def test_get_signal_context_includes_news_and_macro_when_present(monkeypatch):
    monkeypatch.setattr(bitget_signal, "get_crypto_sentiment", lambda: None)
    monkeypatch.setattr(bitget_signal, "get_derivatives_sentiment", lambda: None)
    monkeypatch.setattr(
        bitget_signal, "get_news_briefing",
        lambda: [{"feed": "coindesk", "error": "", "items": [{"title": "real headline"}]}],
    )
    monkeypatch.setattr(
        bitget_signal, "get_macro_context",
        lambda: {"yield_curve": {"t10y": {"value": 4.1}}, "spread_10y2y": 0.3, "inverted": False},
    )

    context = bitget_signal.get_signal_context()

    assert "news" in context
    assert "macro" in context


def test_get_news_briefing_returns_none_when_every_feed_is_empty(monkeypatch):
    # Confirmed live Sept 22: real, non-error response shape, but zero items
    # everywhere - a genuine "nothing new" answer, not real content.
    with patch.object(bitget_signal, "_mcp_call") as mock_call:
        mock_call.return_value = [
            {"feed": "cointelegraph", "error": "", "items": []},
            {"feed": "coindesk", "error": "", "items": []},
        ]
        result = bitget_signal.get_news_briefing()

    assert result is None


def test_get_news_briefing_returns_real_data_when_at_least_one_feed_has_items():
    with patch.object(bitget_signal, "_mcp_call") as mock_call:
        mock_call.return_value = [
            {"feed": "cointelegraph", "error": "", "items": []},
            {"feed": "coindesk", "error": "", "items": [{"title": "real headline", "url": "https://..."}]},
        ]
        result = bitget_signal.get_news_briefing()

    assert result is not None
    assert result[1]["items"][0]["title"] == "real headline"


def test_get_news_briefing_never_crashes_on_a_non_list_payload():
    # This is the real crash this project hit live Sept 22 before the fix:
    # _has_real_data() iterating a list as if it were a dict.
    with patch.object(bitget_signal, "_mcp_call") as mock_call:
        mock_call.return_value = {"error": "unexpected shape"}
        result = bitget_signal.get_news_briefing()

    assert result is None


def test_get_macro_context_returns_none_when_yield_curve_is_all_errors():
    # Confirmed live Sept 22: the server computes spread_10y2y: 0.0 and
    # inverted: false from six all-missing yield tenors - those derived fields
    # must not be mistaken for a real reading.
    with patch.object(bitget_signal, "_mcp_call") as mock_call:
        mock_call.return_value = {
            "yield_curve": {tenor: {"error": ""} for tenor in ("t3m", "t1y", "t2y", "t5y", "t10y", "t30y")},
            "spread_10y2y": 0.0,
            "inverted": False,
            "note": "Inverted yield curve (10Y < 2Y) historically precedes recession",
        }
        result = bitget_signal.get_macro_context()

    assert result is None


def test_get_macro_context_returns_real_data_when_yield_curve_has_real_values():
    with patch.object(bitget_signal, "_mcp_call") as mock_call:
        mock_call.return_value = {
            "yield_curve": {"t10y": {"value": 4.12}, "t2y": {"error": ""}},
            "spread_10y2y": -0.3,
            "inverted": True,
        }
        result = bitget_signal.get_macro_context()

    assert result is not None
    assert result["yield_curve"]["t10y"]["value"] == 4.12


def test_has_real_data_basic_leaf_rules():
    assert bitget_signal._has_real_data(0) is False
    assert bitget_signal._has_real_data(0.0) is False
    assert bitget_signal._has_real_data(False) is False
    assert bitget_signal._has_real_data("") is False
    assert bitget_signal._has_real_data(None) is False
    assert bitget_signal._has_real_data("Fear") is True
    assert bitget_signal._has_real_data(42) is True
    assert bitget_signal._has_real_data(True) is True


def test_has_real_data_alone_cannot_tell_a_canned_note_from_real_content():
    # Documents exactly why get_macro_context() checks the yield_curve sub-block
    # specifically instead of trusting _has_real_data() on the whole payload: a
    # boilerplate description string sitting next to all-zero/false derived
    # fields looks like "real data" to a purely generic, structural check. This
    # is a known, disclosed limitation of the generic helper, not a bug - the
    # tool-specific callers work around it rather than pretending it doesn't exist.
    misleading_payload = {
        "yield_curve": {"t10y": {"error": ""}},
        "spread_10y2y": 0.0,
        "inverted": False,
        "note": "always-present boilerplate text",
    }
    assert bitget_signal._has_real_data(misleading_payload) is True  # known limitation


def test_has_real_data_handles_lists_without_crashing():
    assert bitget_signal._has_real_data([]) is False
    assert bitget_signal._has_real_data([{"error": ""}, {"error": ""}]) is False
    assert bitget_signal._has_real_data([{"error": ""}, {"title": "real"}]) is True
