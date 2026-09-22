"""
Real integration with Bitget's own public bitget-signal MCP server (part of Bitget
Agent Hub's research Skills, documented in the Hackathon S2 developer toolkit:
https://bitget-ai.gitbook.io/bitgetai_hackathons2 under "Research Skills
(bitget-signal)"). No API key, no account, no credentials - it's a public HTTP MCP
endpoint anyone can call, confirmed live by reading the package's own installer
script (node_modules/@bitget-ai/bitget-signal/scripts/install.js).

This adds two real, additional context signals to the Agent's overnight reasoning:
crypto Fear & Greed sentiment, and BTC derivatives positioning (long/short ratio).
Both are genuinely optional enrichment, not a new dependency the core loop needs -
same graceful-degradation philosophy as kv_sync.py and llm_client.py in this same
package. Confirmed live Sept 22: the server's JSON-RPC layer works correctly, but
its own upstream data fetches (CoinGecko, alternative.me, mempool.space) were
intermittently failing at the time of writing - that is disclosed honestly here
and handled the same way every other external dependency in this project is
handled: never let it break the cycle, never fabricate a value when the real
source has nothing to give.
"""
from __future__ import annotations

import sys

import requests

MCP_URL = "https://datahub.noxiaohao.com/mcp"
_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}
_TIMEOUT_S = 40.0  # the server sends SSE keepalive pings for 20-30s+ before some
# tool calls resolve (confirmed live), a short timeout here would cut off calls
# that were genuinely about to return - this only runs once per 15-min cycle, so
# there is no latency pressure to trade real data for a faster failure


def _parse_sse_json(raw_text: str) -> dict | None:
    """The MCP server responds as a Server-Sent Events stream (ping lines plus one
    "event: message" / "data: {...}" pair) rather than a single JSON body. Pull the
    JSON out of the last "data: " line."""
    data_line = None
    for line in raw_text.splitlines():
        if line.startswith("data: "):
            data_line = line[len("data: "):]
    if data_line is None:
        return None
    try:
        import json
        return json.loads(data_line)
    except json.JSONDecodeError:
        return None


def _mcp_call(tool_name: str, arguments: dict) -> dict | None:
    """One real MCP round trip: initialize a session, then call the named tool.
    Returns the tool's parsed JSON payload, or None on any failure - network
    issues here must never break the Agent's actual trading loop, same pattern
    as every other external call in this project."""
    import json

    try:
        init_resp = requests.post(
            MCP_URL,
            headers=_HEADERS,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "gloaming-agent", "version": "1.0"},
                },
            },
            timeout=_TIMEOUT_S,
        )
        init_resp.raise_for_status()
        session_id = init_resp.headers.get("mcp-session-id")
        if not session_id:
            print("bitget_signal: no session id in initialize response", file=sys.stderr)
            return None

        call_resp = requests.post(
            MCP_URL,
            headers={**_HEADERS, "mcp-session-id": session_id},
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": tool_name, "arguments": arguments},
            },
            timeout=_TIMEOUT_S,
        )
        call_resp.raise_for_status()
        envelope = _parse_sse_json(call_resp.text)
        if envelope is None:
            print(f"bitget_signal: could not parse response for {tool_name}", file=sys.stderr)
            return None

        result = envelope.get("result", {})
        if result.get("isError"):
            print(f"bitget_signal: {tool_name} returned an error: {result}", file=sys.stderr)
            return None

        content = result.get("content", [])
        if not content or content[0].get("type") != "text":
            return None
        payload = json.loads(content[0]["text"])

        # The upstream data source itself can report "no data" without the MCP
        # layer treating it as a hard error (isError stays false) - confirmed
        # live: alt_me_error/error keys present but empty means "nothing came
        # back", not "here is real data with these fields empty."
        if any(k.endswith("_error") or k == "error" for k in payload) and len(payload) <= 2:
            print(f"bitget_signal: {tool_name} had no real data available: {payload}", file=sys.stderr)
            return None

        return payload
    except Exception as e:  # noqa: BLE001 - deliberately broad, same as kv_sync.py
        print(f"bitget_signal: {tool_name} call failed: {e}", file=sys.stderr)
        return None


def get_crypto_sentiment() -> dict | None:
    """Real Fear & Greed Index reading from Bitget's public signal server. Returns
    None (not a fabricated neutral value) if the upstream source has nothing."""
    return _mcp_call("sentiment_index", {"action": "current"})


def get_derivatives_sentiment(symbol: str = "BTCUSDT", period: str = "1h") -> dict | None:
    """Real BTC futures long/short positioning from Bitget's public signal server.
    Returns None (not a fabricated neutral value) if the upstream source has
    nothing right now."""
    return _mcp_call("derivatives_sentiment", {"action": "long_short", "symbol": symbol, "period": period})


def get_signal_context() -> dict | None:
    """Bundles both calls into the shape agent_loop.py passes through to every
    symbol's snapshot this cycle (fetched once, not once per symbol, same as the
    other shared proxies). Returns None only if BOTH real sources had nothing -
    if just one came back, the dict still carries that one real value, with the
    other key simply absent rather than filled with a placeholder."""
    fear_greed = get_crypto_sentiment()
    long_short = get_derivatives_sentiment()
    if fear_greed is None and long_short is None:
        return None
    context: dict = {}
    if fear_greed is not None:
        context["fear_greed"] = fear_greed
    if long_short is not None:
        context["long_short"] = long_short
    return context


if __name__ == "__main__":
    if "--smoke-test" in sys.argv:
        print("Calling bitget-signal's real public MCP server (no API key needed)...")
        sentiment = get_crypto_sentiment()
        print("Fear & Greed:", sentiment if sentiment is not None else "unavailable right now (source returned no data)")
        derivs = get_derivatives_sentiment()
        print("BTC long/short:", derivs if derivs is not None else "unavailable right now (source returned no data)")
    else:
        print("Usage: python bitget_signal.py --smoke-test")
