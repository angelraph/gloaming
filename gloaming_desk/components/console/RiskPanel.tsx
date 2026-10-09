"use client";

import RiskMeters from "@/components/RiskMeters";
import type { Portfolio } from "@/lib/useDeskData";
import { UNIVERSE, rtokenSymbol } from "@/lib/universe";
import { fmtPct } from "@/lib/format";

// Mirrors gloaming_agent/risk_controls.py RiskConfig.max_symbol_exposure_pct.
const SYMBOL_CAP = 0.15;
const UP = "#3fe280";
const DOWN = "#e5786d";

// Each position as a share of equity, long to the right and short to the left, against the
// per-symbol cap that the deterministic risk layer enforces. The meters beside it are the
// book-wide caps.
export default function RiskPanel({ portfolio }: { portfolio: Portfolio | null }) {
  if (!portfolio?.configured) return <div aria-hidden className="h-[380px] animate-pulse rounded-xl bg-layer-1" />;
  const equity = portfolio.equityUsd ?? 0;
  const rows = UNIVERSE.map((u) => {
    const p = portfolio.positions?.find((x) => x.symbol === rtokenSymbol(u));
    const n = p?.notionalUsd ?? 0;
    return { u, n, pct: equity ? n / equity : 0 };
  });

  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
      <div className="rounded-xl border border-border-subtle bg-layer-1 p-4 sm:p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <span className="micro-label">Position by symbol, share of equity</span>
          <span className="flex items-center gap-3 text-xs text-text-secondary">
            <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-sm" style={{ background: DOWN }} />short</span>
            <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-sm" style={{ background: UP }} />long</span>
            <span className="flex items-center gap-1.5"><span className="h-3 w-px bg-copper" />cap ±{fmtPct(SYMBOL_CAP, 0)}</span>
          </span>
        </div>
        <ul className="mt-5 space-y-2.5">
          {rows.map((r, i) => {
            const w = Math.min(Math.abs(r.pct) / SYMBOL_CAP, 1) * 50;
            return (
              <li key={r.u} className="grid grid-cols-[48px_minmax(0,1fr)_88px] items-center gap-3 text-xs">
                <span className="text-text-secondary">{r.u}</span>
                <span className="relative h-5 rounded-md bg-layer-2">
                  <span aria-hidden className="absolute inset-y-0 left-0 w-px bg-copper/60" />
                  <span aria-hidden className="absolute inset-y-0 right-0 w-px bg-copper/60" />
                  <span aria-hidden className="absolute inset-y-0 left-1/2 w-px bg-border-strong" />
                  <span
                    className="risk-bar absolute inset-y-[3px] rounded-[4px]"
                    style={{
                      background: r.n >= 0 ? UP : DOWN,
                      left: r.n >= 0 ? "50%" : `${50 - w}%`,
                      width: `${w}%`,
                      transformOrigin: r.n >= 0 ? "left" : "right",
                      "--d": `${i * 60}ms`,
                    } as React.CSSProperties}
                  />
                </span>
                <span className="text-right tabular-nums text-text-primary">
                  {r.pct >= 0 ? "+" : ""}
                  {fmtPct(r.pct, 1)}
                </span>
              </li>
            );
          })}
        </ul>
      </div>
      <div className="rounded-xl border border-border-subtle bg-layer-1 p-4 sm:p-5">
        <RiskMeters compact equityUsd={equity} dailyPnlUsd={portfolio.dailyPnlUsd ?? 0} positions={portfolio.positions ?? []} />
      </div>
    </div>
  );
}
