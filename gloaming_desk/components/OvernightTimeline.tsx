"use client";

type TimelineEvent = {
  timestamp: string;
  underlying: string | null;
  decision_source?: string;
  snapshot?: {
    rtoken_symbol: string;
    rtoken_last_price: number;
    spread: number;
    // Since Sept 25 the signal is anchored to the real share's last regular-session
    // close ("since_last_close_v2"); older records carry the earlier rolling-24h fields.
    signal_spec?: string;
    real_close_price?: number;
    hours_since_close?: number;
    rtoken_return_since_close?: number;
    fair_value_return_since_close?: number;
    fair_value_return_24h?: number;
    rtoken_pcnt_24h?: number;
  };
  decision?: {
    side: string;
    notional_usd: number;
    rationale: string;
  } | null;
  hold_rationale?: string;
  execution?: unknown;
  error?: string;
};

function fmtPct(n: number) {
  return `${(n * 100).toFixed(2)}%`;
}

function fmtTime(iso: string) {
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function OvernightTimeline({ events }: { events: TimelineEvent[] }) {
  // Every trade and error, plus each symbol's MOST RECENT hold with the reasoning Qwen gave.
  // With the signal anchored to the real close, holds are the normal outcome (a spread of a
  // few tenths of a percent is noise), so a timeline of trades alone would sit stale for days
  // and hide the agent's actual, ongoing judgment. Only the latest hold per symbol is shown,
  // so 9 holds every 15 minutes do not bury the trades. `events` arrive newest first.
  const latestHoldBySymbol = new Map<string, TimelineEvent>();
  for (const e of events) {
    if (!e.decision && !e.error && e.hold_rationale && e.underlying && !latestHoldBySymbol.has(e.underlying)) {
      latestHoldBySymbol.set(e.underlying, e);
    }
  }
  const withSignals = [
    ...events.filter((e) => e.decision || e.error),
    ...latestHoldBySymbol.values(),
  ].sort((a, b) => b.timestamp.localeCompare(a.timestamp));

  if (withSignals.length === 0) {
    return (
      <div className="rounded-lg border border-border-subtle bg-layer-1 p-4 text-sm text-text-tertiary">
        No decisions yet in the recent window - the Agent only trades while NYSE is
        closed, and needs at least one cycle to show anything here.
      </div>
    );
  }

  return (
    <ul className="flex max-h-[520px] flex-col gap-2.5 overflow-y-auto pr-1">
      {withSignals.map((e, i) => {
        const isBuy = e.decision?.side === "buy";
        const isHold = !e.decision && !e.error;
        return (
          <li
            key={`${e.timestamp}-${e.underlying}-${i}`}
            className="rounded-lg border border-border-subtle bg-layer-1 p-3.5"
            style={{
              borderLeft: `3px solid ${
                e.error ? "var(--warning)" : isHold ? "var(--text-tertiary)" : isBuy ? "var(--positive)" : "var(--negative)"
              }`,
            }}
          >
            <div className="flex items-center justify-between gap-2 text-xs text-text-tertiary">
              <span className="tabular-nums">{fmtTime(e.timestamp)}</span>
              <span className="rounded bg-layer-2 px-2 py-0.5 font-mono text-[11px]">
                {e.decision_source ?? "unknown"}
              </span>
            </div>

            {e.error ? (
              <p className="mt-2 text-sm text-warning">Error: {e.error}</p>
            ) : e.decision ? (
              <>
                <div className="mt-1.5 flex flex-wrap items-baseline gap-2">
                  <span className="font-semibold tracking-tight">{e.underlying}</span>
                  <span
                    className={
                      isBuy
                        ? "rounded bg-positive-soft px-2 py-0.5 font-mono text-xs font-medium text-positive"
                        : "rounded bg-negative-soft px-2 py-0.5 font-mono text-xs font-medium text-negative"
                    }
                  >
                    {e.decision.side.toUpperCase()} ${e.decision.notional_usd.toFixed(0)}
                  </span>
                  {e.snapshot && (
                    <span className="font-mono text-xs text-text-tertiary">
                      spread {fmtPct(e.snapshot.spread)}
                    </span>
                  )}
                </div>
                <p className="mt-2 text-sm leading-relaxed text-text-secondary">{e.decision.rationale}</p>
              </>
            ) : (
              <>
                <div className="mt-1.5 flex flex-wrap items-baseline gap-2">
                  <span className="font-semibold tracking-tight">{e.underlying}</span>
                  <span className="rounded bg-layer-2 px-2 py-0.5 font-mono text-xs font-medium text-text-secondary">
                    HOLD
                  </span>
                  {e.snapshot && (
                    <span className="font-mono text-xs text-text-tertiary">
                      spread {fmtPct(e.snapshot.spread)}
                      {e.snapshot.hours_since_close !== undefined &&
                        ` | ${e.snapshot.hours_since_close.toFixed(1)}h since close`}
                    </span>
                  )}
                </div>
                <p className="mt-2 text-sm leading-relaxed text-text-secondary">{e.hold_rationale}</p>
              </>
            )}
          </li>
        );
      })}
    </ul>
  );
}
