// Surfaces gloaming_agent/bitget_signal.py's real output: crypto sentiment, BTC
// derivatives positioning, news headlines, and yield-curve context from Bitget's
// own public bitget-signal MCP server, fetched once per Agent cycle. This card
// renders exactly what the most recent cycle's snapshot carried - raw key/value
// pairs, not a guessed schema, because no successful sentiment/derivatives
// payload has been observed live yet (see docs/architecture.md). When a source
// has nothing, this shows that honestly instead of a placeholder value.

type NewsFeedEntry = { feed?: string; error?: string; items?: unknown[] };
type SignalContext = {
  fear_greed?: Record<string, unknown>;
  long_short?: Record<string, unknown>;
  news?: NewsFeedEntry[];
  macro?: { yield_curve?: Record<string, unknown> } & Record<string, unknown>;
} | null | undefined;

function fmtEntries(obj: Record<string, unknown>) {
  return Object.entries(obj)
    .map(([k, v]) => `${k}: ${typeof v === "number" || typeof v === "string" ? v : JSON.stringify(v)}`)
    .join("  |  ");
}

// Only the tenors that actually came back with something, not the error
// placeholders sitting alongside them - see bitget_signal.get_macro_context().
function realYieldEntries(yieldCurve: Record<string, unknown> | undefined) {
  if (!yieldCurve) return {};
  return Object.fromEntries(
    Object.entries(yieldCurve).filter(([, v]) => {
      if (v && typeof v === "object" && "error" in (v as Record<string, unknown>)) return false;
      return v !== null && v !== undefined && v !== "";
    })
  );
}

export default function SignalContextCard({ context }: { context: SignalContext }) {
  const hasFearGreed = !!context?.fear_greed && Object.keys(context.fear_greed).length > 0;
  const hasLongShort = !!context?.long_short && Object.keys(context.long_short).length > 0;

  const newsWithItems = (context?.news ?? []).filter((e) => Array.isArray(e.items) && e.items.length > 0);
  const hasNews = newsWithItems.length > 0;

  const realYields = realYieldEntries(context?.macro?.yield_curve);
  const hasMacro = Object.keys(realYields).length > 0;

  const hasData = hasFearGreed || hasLongShort || hasNews || hasMacro;

  return (
    <div className="h-full rounded-xl border border-border-subtle bg-layer-1 p-5 sm:p-6">
      <div className="flex items-center justify-between gap-3">
        <p className="eyebrow">Bitget signal</p>
        <span className="rounded-full border border-border-subtle px-2.5 py-1 text-[11px] text-text-tertiary">
          bitget-signal MCP
        </span>
      </div>

      {hasData ? (
        <dl className="mt-5 space-y-4 text-sm">
          {hasFearGreed && (
            <div>
              <dt className="micro-label">Crypto sentiment</dt>
              <dd className="mt-2 tabular-nums text-heading">{fmtEntries(context!.fear_greed!)}</dd>
            </div>
          )}
          {hasLongShort && (
            <div>
              <dt className="micro-label">BTC long/short</dt>
              <dd className="mt-2 tabular-nums text-heading">{fmtEntries(context!.long_short!)}</dd>
            </div>
          )}
          {hasMacro && (
            <div>
              <dt className="micro-label">Yield curve</dt>
              <dd className="mt-2 tabular-nums text-heading">{fmtEntries(realYields)}</dd>
            </div>
          )}
          {hasNews && (
            <div>
              <dt className="micro-label">News</dt>
              <dd className="mt-2 text-heading">
                {newsWithItems.reduce((n, e) => n + (e.items?.length ?? 0), 0)} real item(s) across{" "}
                {newsWithItems.map((e) => e.feed).join(", ")}
              </dd>
            </div>
          )}
        </dl>
      ) : (
        <>
          <h3 className="font-display mt-5 text-[24px] leading-tight text-heading">Nothing to report.</h3>
          <p className="mt-3 text-sm leading-relaxed text-text-secondary">
            No sentiment, derivatives, news or yield-curve data this cycle. Bitget&apos;s public
            signal server responded, but its own upstream sources had nothing to return. Shown
            as-is, never filled in with a placeholder.
          </p>
        </>
      )}
    </div>
  );
}
