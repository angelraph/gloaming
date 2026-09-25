import Link from "next/link";
import type { DecisionRecord } from "@/lib/data";
import { fmtSignedPct } from "@/lib/format";
import { UNIVERSE } from "@/lib/universe";

// Each symbol's most recent record: the verdict and the spread behind it. Every card links to
// that symbol's own page, which is also the keyboard/screen-reader route into the data the
// bar chart shows.
export default function LatestCycleGrid({ events }: { events: DecisionRecord[] }) {
  const latest = new Map<string, DecisionRecord>();
  for (const e of events) {
    if (e.underlying && !latest.has(e.underlying)) latest.set(e.underlying, e); // events are newest first
  }

  return (
    <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
      {UNIVERSE.map((u) => {
        const e = latest.get(u);
        const verdict = !e ? null : e.error ? "ERROR" : e.decision ? `${e.decision.side.toUpperCase()}` : "HOLD";
        return (
          <li key={u}>
            <Link
              href={`/desk/${u}`}
              className="block min-h-11 rounded-xl border border-border-subtle bg-layer-1 p-4 transition-colors hover:border-border-strong hover:bg-layer-2"
            >
              <span className="flex items-baseline justify-between gap-2">
                <span className="text-sm font-medium text-heading">{u}</span>
                <span
                  className={`text-[11px] font-medium tracking-wide ${
                    verdict === "BUY" ? "text-mint" : verdict === "SELL" ? "text-negative" : verdict === "ERROR" ? "text-warning" : "text-text-tertiary"
                  }`}
                >
                  {verdict ?? "no data"}
                </span>
              </span>
              <span className="font-display mt-3 block text-[22px] leading-none tabular-nums text-heading">
                {e?.snapshot ? fmtSignedPct(e.snapshot.spread, 2) : "n/a"}
              </span>
              <span className="mt-1.5 block text-xs text-text-tertiary">spread vs fair value</span>
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
