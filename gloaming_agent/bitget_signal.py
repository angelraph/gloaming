"""
Real integration with Bitget's own public bitget-signal MCP server (part of Bitget
Agent Hub's research Skills, documented in the Hackathon S2 developer toolkit:
https://bitget-ai.gitbook.io/bitgetai_hackathons2 under "Research Skills
(bitget-signal)"). No API key, no account, no credentials - it's a public HTTP MCP
endpoint anyone can call, confirmed live by reading the package's own installer
script (node_modules/@bitget-ai/bitget-signal/scripts/install.js).

This adds four real, additional context signals to the Agent's overnight
reasoning: crypto Fear & Greed sentiment, BTC derivatives positioning (long/short
ratio), crypto/market news headlines, and a Treasury yield-curve snapshot - the
same four data sources the bitget-signal package's sentiment-analyst,
news-briefing, and macro-analyst Skills are built around. All four are genuinely
optional enrichment, not a new dependency the core loop needs - same
graceful-degradation philosophy as kv_sync.py and llm_client.py in this same
package. Confirmed live Sept 22: the server's JSON-RPC layer works correctly, but
its own upstream data fetches (CoinGecko, alternative.me, mempool.space, the news
aggregator, the Treasury yield feed) were failing across the board at the time of
writing - that is disclosed honestly here and handled the same way every other
external dependency in this project is handled: never let it break the cycle,
never fabricate a value when the real source has nothing to give, and never let a
canned description string or a computed-from-nothing default (rates_yields'
spread_10y2y: 0.0, inverted: false) be mistaken for a real reading.
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


def _has_real_data(value) -> bool:
    """True if `value` contains at least one real, non-placeholder leaf, checked
    recursively. Confirmed live Sept 22 across sentiment_index, derivatives_sentiment,
    macro_indicators, and rates_yields: Bitget's server can report success
    (isError: false) while a dict is only per-field error placeholders (e.g.
    {"alt_me_error": ""}), a list is empty, or a dict's only non-error fields are
    values *derived from* an all-error sub-block (rates_yields returns
    spread_10y2y: 0.0 and inverted: false even when every underlying yield in
    yield_curve is {"error": ""} - those are defaults computed from missing
    inputs, not a real reading, and treating them as real would be exactly the
    kind of placeholder-as-data fabrication this project never does). A plain
    0, 0.0, or False leaf is therefore treated as inconclusive on its own, not
    proof of real data - only a nonempty string or a nonzero number counts."""
    if isinstance(value, dict):
        if not value:
            return False
        if all(k.endswith("_error") or k == "error" for k in value):
            return False
        return any(_has_real_data(v) for v in value.values())
    if isinstance(value, list):
        return any(_has_real_data(v) for v in value)
    if value is None or value == "" or value is False or value == 0:
        return False
    return True


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


def _mcp_call(tool_name: str, arguments: dict) -> dict | list | None:
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
        # layer treating it as a hard error (isError stays false) - see
        # _has_real_data() for exactly what this catches and why, confirmed
        # against several real empty/degraded responses live Sept 22.
        if not _has_real_data(payload):
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


def get_news_briefing(feeds: str = "cointelegraph,coindesk,decrypt,blockworks", limit: int = 5) -> list | None:
    """Real crypto/market news headlines, matching the news-briefing Skill's Quick
    News Update pattern (references/feed-routing.md in the bitget-signal package).
    Not wired in until today - the earlier assumption (docs/architecture.md, "Day
    5") was that this Skill needed an MCP-client host environment, not a plain
    HTTP client. Confirmed live Sept 22 that assumption was simply wrong: it is
    the exact same kind of MCP tool call as sentiment_index/derivatives_sentiment,
    already proven to work from a plain Python client.

    Returns None if every requested feed came back empty. Confirmed live: the
    server can respond isError: false with each feed shaped
    {"feed": ..., "error": "", "items": []} - a real "nothing new" answer, not a
    failure, but still not real content worth passing to Qwen."""
    payload = _mcp_call("news_feed", {"action": "latest", "feeds": feeds, "limit": limit})
    if not isinstance(payload, list):
        return None
    if not any(isinstance(entry, dict) and entry.get("items") for entry in payload):
        print(
            f"bitget_signal: news_feed had no real headlines this cycle (every "
            f"feed returned empty): {payload}",
            file=sys.stderr,
        )
        return None
    return payload


def get_macro_context() -> dict | None:
    """Real yield-curve snapshot, matching the macro-analyst Skill's "Yield Curve &
    Rate Environment Only" workflow. Same "wrong Day 5 assumption" history as
    get_news_briefing() above.

    Confirmed live Sept 22: the server can return isError: false with every
    individual yield tenor in yield_curve errored out
    ({"t3m": {"error": ""}, ...}), while still including top-level fields
    (spread_10y2y, inverted) computed from that missing data - those are
    defaults, not a real reading (0.0 spread / not-inverted is exactly what you
    would compute from nothing), so this checks the actual underlying
    yield_curve block rather than trusting the derived scalars sitting next to
    it, which would otherwise pass _has_real_data() and fabricate a signal."""
    payload = _mcp_call("rates_yields", {"action": "yield_curve"})
    if not isinstance(payload, dict):
        return None
    if not _has_real_data(payload.get("yield_curve", {})):
        print(
            f"bitget_signal: rates_yields had no real underlying yield data: "
            f"{payload.get('yield_curve')}",
            file=sys.stderr,
        )
        return None
    return payload


def get_signal_context() -> dict | None:
    """Bundles all four calls into the shape agent_loop.py passes through to every
    symbol's snapshot this cycle (fetched once, not once per symbol, same as the
    other shared proxies). Returns None only if every real source had nothing -
    if only some came back, the dict still carries those real values, with the
    other keys simply absent rather than filled with a placeholder."""
    fear_greed = get_crypto_sentiment()
    long_short = get_derivatives_sentiment()
    news = get_news_briefing()
    macro = get_macro_context()
    if fear_greed is None and long_short is None and news is None and macro is None:
        return None
    context: dict = {}
    if fear_greed is not None:
        context["fear_greed"] = fear_greed
    if long_short is not None:
        context["long_short"] = long_short
    if news is not None:
        context["news"] = news
    if macro is not None:
        context["macro"] = macro
    return context


if __name__ == "__main__":
    if "--smoke-test" in sys.argv:
        print("Calling bitget-signal's real public MCP server (no API key needed)...")
        sentiment = get_crypto_sentiment()
        print("Fear & Greed:", sentiment if sentiment is not None else "unavailable right now (source returned no data)")
        derivs = get_derivatives_sentiment()
        print("BTC long/short:", derivs if derivs is not None else "unavailable right now (source returned no data)")
        news = get_news_briefing()
        print("News:", news if news is not None else "unavailable right now (source returned no data)")
        macro = get_macro_context()
        print("Macro (yield curve):", macro if macro is not None else "unavailable right now (source returned no data)")
    else:
        print("Usage: python bitget_signal.py --smoke-test")
