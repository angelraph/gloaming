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
      <div className="rounded-xl border border-border-subtle bg-layer-1 p-5 text-sm text-text-tertiary">
        No decisions yet in the recent window. The agent only works while NYSE is closed, and needs
        at least one cycle to show anything here.
      </div>
    );
  }

  return (
    <ul className="flex max-h-[560px] flex-col gap-3 overflow-y-auto pr-1">
      {withSignals.map((e, i) => {
        const isBuy = e.decision?.side === "buy";
        const isHold = !e.decision && !e.error;
        return (
          <li
            key={`${e.timestamp}-${e.underlying}-${i}`}
            className="rounded-xl border border-border-subtle bg-layer-1 p-4 sm:p-5"
          >
            <div className="flex items-center justify-between gap-3">
              <span className="micro-label tabular-nums">{fmtTime(e.timestamp)}</span>
              <span className="truncate rounded-full border border-border-subtle px-2.5 py-1 text-[11px] text-text-tertiary">
                {e.decision_source ?? "unknown"}
              </span>
            </div>

            {e.error ? (
              <p className="mt-3 text-sm text-warning">Error: {e.error}</p>
            ) : (
              <>
                <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-2">
                  <span className="text-base font-medium text-heading">{e.underlying}</span>
                  {e.decision ? (
                    <span
                      className={`rounded-full border px-3 py-1 text-xs font-medium tracking-wide tabular-nums ${
                        isBuy
                          ? "border-mint/40 bg-mint-soft text-mint"
                          : "border-negative/40 bg-negative-soft text-negative"
                      }`}
                    >
                      {e.decision.side.toUpperCase()} ${e.decision.notional_usd.toFixed(0)}
                    </span>
                  ) : (
                    <span className="rounded-full border border-border px-3 py-1 text-xs font-medium tracking-wide text-text-secondary">
                      HOLD
                    </span>
                  )}
                  {e.snapshot && (
                    <span className="text-xs text-text-tertiary tabular-nums">
                      spread {fmtPct(e.snapshot.spread)}
                      {e.snapshot.hours_since_close !== undefined &&
                        ` · ${e.snapshot.hours_since_close.toFixed(1)}h since close`}
                    </span>
                  )}
                </div>
                <p className="mt-3 text-sm leading-relaxed text-text-secondary">
                  {isHold ? e.hold_rationale : e.decision?.rationale}
                </p>
              </>
            )}
          </li>
        );
      })}
    </ul>
  );
}
