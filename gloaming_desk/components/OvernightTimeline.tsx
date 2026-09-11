"use client";

type TimelineEvent = {
  timestamp: string;
  underlying: string | null;
  decision_source?: string;
  snapshot?: {
    rtoken_symbol: string;
    rtoken_last_price: number;
    spread: number;
    fair_value_return_24h: number;
    rtoken_pcnt_24h: number;
  };
  decision?: {
    side: string;
    notional_usd: number;
    rationale: string;
  } | null;
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
  const withSignals = events.filter((e) => e.decision || e.error);

  if (withSignals.length === 0) {
    return (
      <div className="text-sm text-neutral-500">
        No decisions yet in the recent window - the Agent only trades while NYSE is
        closed, and needs at least one cycle with an actionable spread to show
        anything here.
      </div>
    );
  }

  return (
    <ul className="flex flex-col gap-3">
      {withSignals.map((e, i) => (
        <li
          key={`${e.timestamp}-${e.underlying}-${i}`}
          className="rounded-lg border border-neutral-800 bg-neutral-900/50 p-4"
        >
          <div className="flex items-center justify-between gap-2 text-xs text-neutral-400">
            <span>{fmtTime(e.timestamp)}</span>
            <span className="rounded bg-neutral-800 px-2 py-0.5 font-mono">
              {e.decision_source ?? "unknown"}
            </span>
          </div>

          {e.error ? (
            <p className="mt-2 text-sm text-red-400">Error: {e.error}</p>
          ) : e.decision ? (
            <>
              <div className="mt-1 flex items-baseline gap-2">
                <span className="text-lg font-semibold">{e.underlying}</span>
                <span
                  className={
                    e.decision.side === "buy"
                      ? "rounded bg-emerald-900/60 px-2 py-0.5 text-xs font-medium text-emerald-300"
                      : "rounded bg-rose-900/60 px-2 py-0.5 text-xs font-medium text-rose-300"
                  }
                >
                  {e.decision.side.toUpperCase()} ${e.decision.notional_usd.toFixed(0)}
                </span>
                {e.snapshot && (
                  <span className="text-xs text-neutral-500">
                    spread {fmtPct(e.snapshot.spread)}
                  </span>
                )}
              </div>
              <p className="mt-2 text-sm text-neutral-300">{e.decision.rationale}</p>
            </>
          ) : null}
        </li>
      ))}
    </ul>
  );
}
