"""
Qwen3.8-max client for Gloaming Agent, via the hackathon's OpenAI-compatible
endpoint. Deliberately a plain `openai` client pointed at a custom base_url - NOT
wired through Claude Code/Cursor-specific tooling, since the hackathon's own docs
say Claude Code isn't officially supported by that endpoint (confirmed Day 1
research). Configuration comes entirely from .env (see .env.example):
QWEN_BASE_URL, QWEN_API_KEY, QWEN_MODEL.

Mirrors execution.py's pattern from Day 4: fail loudly and specifically
(NotConfiguredError) rather than silently, so agent_loop.py can log a clear reason
and fall back to the rule-based decision path instead of crashing the cycle.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(REPO_ROOT / ".env")  # no-op if the file doesn't exist yet

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


class LLMError(RuntimeError):
    pass


class NotConfiguredError(LLMError):
    """Raised when QWEN_API_KEY isn't set - distinct from other LLMError so
    callers can log 'falling back to rule-based decisions' specifically."""


def is_configured() -> bool:
    return bool(os.environ.get("QWEN_API_KEY"))


def _require_configured() -> None:
    if not is_configured():
        raise NotConfiguredError(
            "QWEN_API_KEY is not set - copy .env.example to .env and fill in your "
            "Qwen hackathon credit key before the Agent can use LLM reasoning."
        )


def _client():
    """Lazy import + construction so this module stays importable (and
    is_configured() callable) even before `openai` is installed/configured."""
    from openai import OpenAI

    return OpenAI(
        base_url=os.environ.get("QWEN_BASE_URL", "https://hackathon.bitgetops.com/v1"),
        api_key=os.environ["QWEN_API_KEY"],
    )


def get_decision_json(system_prompt: str, user_prompt: str, timeout_s: float = 30.0) -> dict:
    """Calls Qwen with a system + user prompt and parses the response as JSON.
    Raises LLMError (not a bare exception) on any failure - network, non-JSON
    response, or malformed schema - so callers have one exception type to catch
    for 'the LLM step failed, fall back to rule-based decide()'.

    Latency, measured Sept 24 (real calls, real prompt): with the model's thinking
    mode on, a decision call took 17-36s (up to 77s) and ~500-3,000 completion tokens
    of hidden reasoning for a three-sentence JSON answer. Production Qwen success was
    83% at a 20s timeout, and collapsed to 11-22% the hour the longer book-aware
    prompt shipped (it makes the model reason longer). With thinking off
    (`enable_thinking: false`, on by default here; QWEN_ENABLE_THINKING=1 turns it
    back on) the same call takes 5-8s and ~150-180 tokens, and the rationale still
    cites the book. If the endpoint ever rejects that parameter, the call is retried
    once without it rather than losing the LLM entirely. 30s with one retry (the SDK
    default was two) bounds a symbol's worst case at about a minute; agent_loop
    separately caps the total LLM time per cycle so a bad Qwen day cannot push the job
    past the workflow's 10-minute limit."""
    _require_configured()
    model = os.environ.get("QWEN_MODEL", "qwen3.8-max")
    thinking_on = os.environ.get("QWEN_ENABLE_THINKING", "").strip().lower() in ("1", "true", "yes")

    def _create(extra_body: dict | None):
        return _client().with_options(max_retries=1).chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,  # low temperature: this drives real position sizing, not creative writing
            timeout=timeout_s,
            **({"extra_body": extra_body} if extra_body else {}),
        )

    try:
        if thinking_on:
            response = _create(None)
        else:
            try:
                response = _create({"enable_thinking": False})
            except Exception as first_error:  # noqa: BLE001
                # Only a rejected request (HTTP 400) means "this endpoint does not accept
                # the parameter"; a timeout or connection error would fail the same way
                # again, so it is not retried here.
                if getattr(first_error, "status_code", None) != 400:
                    raise
                response = _create(None)
    except Exception as e:  # noqa: BLE001 - any transport/API failure funnels into one LLMError type
        raise LLMError(f"Qwen API call failed: {e}") from e

    content = response.choices[0].message.content
    try:
        return json.loads(content)
    except (json.JSONDecodeError, TypeError) as e:
        raise LLMError(f"Qwen response was not valid JSON: {content!r}") from e


def load_prompt(filename: str) -> str:
    path = PROMPTS_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path.read_text(encoding="utf-8")


if __name__ == "__main__":
    import sys

    if "--smoke-test" in sys.argv:
        if not is_configured():
            print("NOT CONFIGURED (expected until Qwen credentials arrive): QWEN_API_KEY not set.")
            sys.exit(0)
        print("QWEN_API_KEY found - sending a trivial test prompt...")
        result = get_decision_json(
            system_prompt='Respond with ONLY this exact JSON, nothing else: {"ok": true}',
            user_prompt="ping",
        )
        print("Response:", result)
        assert result.get("ok") is True, f"unexpected response: {result}"
        print("OK - Qwen endpoint reachable and returning valid JSON.")
    else:
        print("Usage: python llm_client.py --smoke-test")
