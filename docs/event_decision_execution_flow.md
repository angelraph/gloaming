# Gloaming Agent - Event -> Decision -> Execution Flow

This is the exact sequence `gloaming_agent/agent_loop.py`'s `run_once()` runs on
every invocation (every 15 minutes, unattended, via the scheduled task - see
`scripts/setup_scheduled_task.ps1`), matching the code as written, not an
idealized version of it.

```mermaid
sequenceDiagram
    participant Sched as Scheduled task (every 15 min)
    participant Loop as run_once()
    participant Data as engine/data/*
    participant Qwen as Qwen3.8-max
    participant Rule as decide_rule_based()
    participant Risk as risk_controls.py
    participant Ledger as paper_ledger.py
    participant Log as decision_log/*.jsonl

    Sched->>Loop: --run
    Loop->>Loop: is_nyse_closed()?

    alt NYSE is open
        Loop->>Log: 1 record: "market open, skipped"
        Note over Loop: returns immediately, no data fetched
    else NYSE is closed
        Loop->>Data: fetch crypto beta, FX, futures proxy<br/>(shared once per cycle, not per symbol)
        loop each of 9 symbols
            Loop->>Data: live rToken price + 24h change
            Loop->>Loop: build_snapshot() -> spread vs. fair value
        end
        Loop->>Ledger: get_portfolio_state(mark_prices)
        Note over Ledger: equity + positions, marked to<br/>this cycle's live prices

        loop each symbol with a usable snapshot
            Loop->>Loop: build_book_context(): its position, net/gross<br/>exposure vs. caps, what the gate would approve,<br/>its recent fills (stored on the logged snapshot)
            alt QWEN_API_KEY configured
                Loop->>Qwen: system prompt + real snapshot numbers<br/>+ its own book
                alt call succeeds, valid schema
                    Qwen-->>Loop: action, notional_usd, stop_loss_pct,<br/>confidence, rationale
                else call fails or malformed response
                    Loop->>Rule: decide_rule_based(snapshot)
                    Rule-->>Loop: TradeDecision or None
                    Note over Loop: decision_source records WHY<br/>the fallback fired
                end
            else not configured
                Loop->>Rule: decide_rule_based(snapshot)
                Rule-->>Loop: TradeDecision or None
            end

            alt no actionable decision
                Loop->>Log: record: snapshot + decision=null
            else decision proposed
                Loop->>Risk: evaluate_decision(decision, portfolio_state, volatility)
                alt rejected outright
                    Risk-->>Loop: approved=false, reasons
                    Loop->>Log: record: decision + risk_result + "SKIPPED: rejected"
                else approved, possibly resized
                    Risk-->>Loop: approved=true, adjusted_notional_usd
                    Loop->>Ledger: record_fill(symbol, side, qty, price, rationale)
                    Ledger-->>Loop: Fill (persisted to paper_ledger.json)
                    Loop->>Ledger: get_portfolio_state(mark_prices)
                    Note over Ledger: book re-marked after every real fill,<br/>so the next symbol sees it
                    Loop->>Log: full record: snapshot + decision +<br/>risk_result + execution
                end
            end
        end
        Loop->>Risk: net-exposure backstop (only if book stayed over<br/>the net cap ~2h without the LLM bringing it back)
        Risk-->>Loop: at most 2% of equity of trims, each through<br/>evaluate_decision, logged as risk_backstop_trim
    end
```

## A real example, pulled from the running log

This is an unedited record from `decision_log/` (only the timestamp field is
omitted here for brevity):

- **Event**: `RAAPLUSDT` (Apple rToken) 24h return +2.68%, blended overnight
  fair-value proxy estimate -1.27% (futures -1.71%, crypto beta -1.34%, FX -0.06%)
- **Spread**: +3.95%, well above the model's threshold
- **Decision** (`decision_source: "qwen3.8-max"`): sell $400 notional, stop-loss
  3%, confidence derived from Qwen's own output
- **Rationale** (verbatim from Qwen): *"RAAPLUSDT is up 2.68% while the blended
  overnight fair-value proxy is down 1.27%, creating a +3.95% spread with all
  three proxies negative (-1.71%, -1.34%, -0.06%). This suggests the rToken is
  rich versus closed-market fair value, but I size conservatively because I
  cannot verify whether the strength is driven by idiosyncratic news."*
- **Risk result**: volatility-scaled sizing kicked in (recent volatility exceeded
  the 2% reference), resizing the requested notional down before execution
- **Execution**: `paper_ledger.record_fill("RAAPLUSDT", "sell", qty, price,
  rationale)` - a real fill at the real live price, persisted to
  `paper_ledger.json`

## Why this separation matters for the Agentic Trading track's LLM-role question

Qwen3.8-max is the **primary decision-maker** - it sees the real snapshot and its
own book (position, net/gross exposure against the caps, what the gate would
approve, its recent fills) and decides direction, size, and stop-loss. It is never
the last word, though: `risk_controls.py` is a separate, deterministic, non-LLM
module that can reject or resize any decision regardless of Qwen's confidence, and
it is the only thing that can authorize a fill. One disclosed exception to "the
risk layer only gates": if the book stays over its net directional cap for about 2
hours of market-closed time without Qwen bringing it back, a deterministic
backstop proposes trims of at most 2% of equity per cycle; those pass through the
same gate and are labeled `risk_backstop_trim` in `decision_source`. The
fixed-threshold rule in `decide_rule_based()` is not a
second opinion running alongside Qwen - it only fires when Qwen is unavailable or
its call fails, and every record says which path actually produced it
(`decision_source`), so the full history is auditable.
