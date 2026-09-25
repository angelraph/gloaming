"use client";

import { useMemo, useState } from "react";
import type { DecisionRecord } from "@/lib/data";
import { fmtSignedPct, fmtTime } from "@/lib/format";
import DecisionInspector from "@/components/DecisionInspector";

type Filter = "all" | "trades" | "holds" | "errors";
const FILTERS: Array<{ id: Filter; label: string }> = [
  { id: "all", label: "All" },
  { id: "trades", label: "Trades" },
  { id: "holds", label: "Holds" },
  { id: "errors", label: "Errors" },
];
const PAGE = 20;

function kind(e: DecisionRecord): Filter {
  return e.error ? "errors" : e.decision ? "trades" : "holds";
}

// The full trail, newest first: every record the live mirror holds, filterable, with each row
// opening the inspector. Nothing is collapsed to "latest per symbol" here (the Desk page does
// that), so a quiet night still shows its 15-minute rhythm.
export default function DecisionFeed({ events, symbols }: { events: DecisionRecord[]; symbols?: string[] }) {
  const [filter, setFilter] = useState<Filter>("all");
  const [symbol, setSymbol] = useState<string>("all");
  const [shown, setShown] = useState(PAGE);
  const [open, setOpen] = useState<DecisionRecord | null>(null);

  const rows = useMemo(
    () => events.filter((e) => (filter === "all" || kind(e) === filter) && (symbol === "all" || e.underlying === symbol)),
    [events, filter, symbol]
  );

  return (
    <div>
      <div className="flex flex-wrap items-center gap-3">
        <div role="group" aria-label="Filter by outcome" className="flex flex-wrap gap-2">
          {FILTERS.map((f) => (
            <button
              key={f.id}
              type="button"
              aria-pressed={filter === f.id}
              onClick={() => {
                setFilter(f.id);
                setShown(PAGE);
              }}
              className={`min-h-11 rounded-full border px-5 text-sm transition-colors ${
                filter === f.id
                  ? "border-heading bg-heading text-background"
                  : "border-border text-text-secondary hover:border-border-strong hover:text-heading"
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
        {symbols && (
          <label className="ml-auto flex items-center gap-2 text-sm text-text-secondary">
            <span>Symbol</span>
            <select
              value={symbol}
              onChange={(e) => {
                setSymbol(e.target.value);
                setShown(PAGE);
              }}
              className="min-h-11 rounded-full border border-border bg-layer-1 px-4 text-sm text-heading"
            >
              <option value="all">All</option>
              {symbols.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </label>
        )}
      </div>

      <p className="mt-4 text-xs text-text-tertiary" aria-live="polite">
        Showing {Math.min(shown, rows.length)} of {rows.length} records
      </p>

      {rows.length === 0 ? (
        <p className="mt-4 rounded-xl border border-border-subtle bg-layer-1 p-5 text-sm text-text-tertiary">
          No records match. The agent works only while NYSE is closed, so a quiet window is normal.
        </p>
      ) : (
        <ul className="mt-4 divide-y divide-border-subtle overflow-hidden rounded-xl border border-border-subtle bg-layer-1">
          {rows.slice(0, shown).map((e, i) => {
            const k = kind(e);
            const text = e.error ?? e.decision?.rationale ?? e.hold_rationale ?? "No reasoning recorded.";
            return (
              <li key={`${e.timestamp}-${e.underlying}-${i}`}>
                <button
                  type="button"
                  onClick={() => setOpen(e)}
                  className="block min-h-11 w-full px-4 py-4 text-left transition-colors hover:bg-layer-2 sm:px-5"
                >
                  <span className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
                    <span className="text-xs tabular-nums text-text-tertiary">{fmtTime(e.timestamp)}</span>
                    <span className="text-sm font-medium text-heading">{e.underlying}</span>
                    <span
                      className={`rounded-full border px-2.5 py-0.5 text-[11px] font-medium tracking-wide ${
                        k === "trades"
                          ? e.decision?.side === "buy"
                            ? "border-mint/40 bg-mint-soft text-mint"
                            : "border-negative/40 bg-negative-soft text-negative"
                          : k === "errors"
                            ? "border-warning/40 bg-warning-soft text-warning"
                            : "border-border text-text-secondary"
                      }`}
                    >
                      {k === "trades" ? `${e.decision?.side.toUpperCase()} $${e.decision?.notional_usd.toFixed(0)}` : k === "errors" ? "ERROR" : "HOLD"}
                    </span>
                    {e.snapshot && (
                      <span className="text-xs tabular-nums text-text-tertiary">spread {fmtSignedPct(e.snapshot.spread, 3)}</span>
                    )}
                    <span className="ml-auto text-xs text-text-tertiary">Inspect</span>
                  </span>
                  <span className="mt-2 line-clamp-2 block text-sm leading-relaxed text-text-secondary">{text}</span>
                </button>
              </li>
            );
          })}
        </ul>
      )}

      {shown < rows.length && (
        <button
          type="button"
          onClick={() => setShown((n) => n + PAGE)}
          className="mt-4 min-h-11 rounded-full border border-border px-6 text-sm text-heading transition-colors hover:bg-layer-2"
        >
          Show more
        </button>
      )}

      <DecisionInspector record={open} onClose={() => setOpen(null)} />
    </div>
  );
}
