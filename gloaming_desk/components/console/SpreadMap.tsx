"use client";

import { useMemo, useState } from "react";
import type { HistoryPoint } from "@/app/api/history/route";
import { UNIVERSE } from "@/lib/universe";
import { fmtSignedPct } from "@/lib/format";
import { useWidth } from "./useWidth";

const HOUR = 3_600_000;
const HOURS = 72;
const LABEL_W = 56;
const ROW_H = 26;
const GAP = 2;
// Diverging: copper where the rToken traded above its fair value, blue where below, and the
// panel's own neutral at zero. Checked for colour-blind separation (CVD dE 19).
const RICH = [204, 145, 102];
const CHEAP = [111, 156, 232];
const NEUTRAL = [28, 29, 34];

function mix(to: number[], k: number) {
  const c = NEUTRAL.map((n, i) => Math.round(n + (to[i] - n) * k));
  return `rgb(${c[0]}, ${c[1]}, ${c[2]})`;
}

// Every symbol's spread against fair value, hour by hour over the last three days, from the
// agent's own snapshots. Blank cells are hours the agent did not act: NYSE was open.
export default function SpreadMap({ history }: { history: HistoryPoint[] | null }) {
  const { ref, width } = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<{ u: string; h: number; v: number; n: number } | null>(null);

  const { grid, start, scale } = useMemo(() => {
    // the window ends at the newest record, so it always shows the latest real hours
    const points = history ?? [];
    const newest = points.reduce((m, p) => Math.max(m, Date.parse(p.t) || 0), 0);
    const end = Math.ceil(newest / HOUR) * HOUR;
    const start = end - HOURS * HOUR;
    const acc = new Map<string, { sum: number; n: number }>();
    for (const p of points) {
      const t = Date.parse(p.t);
      if (t < start) continue;
      const k = `${p.u}|${Math.floor((t - start) / HOUR)}`;
      const a = acc.get(k) ?? { sum: 0, n: 0 };
      a.sum += p.s;
      a.n += 1;
      acc.set(k, a);
    }
    const grid = new Map<string, { v: number; n: number }>();
    const abs: number[] = [];
    acc.forEach((a, k) => {
      grid.set(k, { v: a.sum / a.n, n: a.n });
      abs.push(Math.abs(a.sum / a.n));
    });
    abs.sort((a, b) => a - b);
    // the scale saturates at the 95th percentile so one outlier can't wash out the rest
    const scale = Math.max(abs[Math.floor(abs.length * 0.95)] ?? 0.003, 0.002);
    return { grid, start, scale };
  }, [history]);

  const cellW = width > LABEL_W ? (width - LABEL_W) / HOURS : 0;
  const filled = grid.size;
  // a time label every 12 hours, or every 24 when the map is narrow (phones)
  const step = cellW * 12 < 80 ? 24 : 12;

  return (
    <div className="rounded-xl border border-border-subtle bg-layer-1 p-4 sm:p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <span className="micro-label">Spread against fair value · 72 hours to the newest record · hourly mean</span>
        <div className="flex items-center gap-2 text-xs text-text-secondary">
          <span>below</span>
          <span
            aria-hidden
            className="h-2 w-28 rounded-full"
            style={{ background: `linear-gradient(90deg, ${mix(CHEAP, 1)}, ${mix(CHEAP, 0)}, ${mix(RICH, 1)})` }}
          />
          <span>above</span>
          <span className="tabular-nums text-text-tertiary">±{(scale * 100).toFixed(2)}%</span>
        </div>
      </div>

      <div ref={ref} className="relative mt-4">
        {width > 0 && (
          <svg
            width={width}
            height={UNIVERSE.length * ROW_H + 22}
            className="block"
            role="img"
            aria-label={`Hourly spread for nine rTokens over the last 72 hours, ${filled} filled hours.`}
            onPointerLeave={() => setHover(null)}
          >
            {UNIVERSE.map((u, r) => (
              <g key={u}>
                <text x={0} y={r * ROW_H + ROW_H / 2 + 4} fontSize="12" fill="#9194a1">
                  {u}
                </text>
                {Array.from({ length: HOURS }).map((_, h) => {
                  const cell = grid.get(`${u}|${h}`);
                  const k = cell ? Math.min(1, Math.abs(cell.v) / scale) : 0;
                  return (
                    <rect
                      key={h}
                      className="heat-cell"
                      style={{ "--d": `${(h + r * 4) * 6}ms` } as React.CSSProperties}
                      x={LABEL_W + h * cellW + GAP / 2}
                      y={r * ROW_H + GAP / 2}
                      width={Math.max(1, cellW - GAP)}
                      height={ROW_H - GAP}
                      rx={2}
                      fill={cell ? mix(cell.v >= 0 ? RICH : CHEAP, 0.18 + 0.82 * k) : "#101114"}
                      stroke={hover && hover.u === u && hover.h === h ? "#fff0cc" : "none"}
                      onPointerEnter={() => cell && setHover({ u, h, v: cell.v, n: cell.n })}
                    />
                  );
                })}
              </g>
            ))}
            {Array.from({ length: HOURS / step + 1 }).map((_, i) => {
              const t = start + i * step * HOUR;
              return (
                <text
                  key={i}
                  x={Math.min(LABEL_W + i * step * cellW, width - 4)}
                  y={UNIVERSE.length * ROW_H + 16}
                  fontSize="11"
                  fill="#777a88"
                  textAnchor={i === 0 ? "start" : i === HOURS / step ? "end" : "middle"}
                >
                  {new Date(t).toLocaleString(undefined, step === 24 ? { weekday: "short" } : { weekday: "short", hour: "2-digit" })}
                </text>
              );
            })}
          </svg>
        )}
        {hover && (
          <div
            className="pointer-events-none absolute z-10 rounded-xl border border-border bg-layer-2 px-3 py-2 text-xs shadow-lg"
            style={{
              left: Math.min(LABEL_W + hover.h * cellW + 10, Math.max(width - 200, 0)),
              top: UNIVERSE.indexOf(hover.u as (typeof UNIVERSE)[number]) * ROW_H - 52,
            }}
          >
            <div className="text-heading">
              {hover.u} · {new Date(start + hover.h * HOUR).toLocaleString(undefined, { weekday: "short", hour: "2-digit", minute: "2-digit" })}
            </div>
            <div className="mt-1 tabular-nums text-text-secondary">
              {fmtSignedPct(hover.v, 3)} mean spread, {hover.n} snapshot{hover.n === 1 ? "" : "s"}
            </div>
          </div>
        )}
      </div>
      <p className="mt-3 text-xs text-text-tertiary">
        Dark cells are hours with no snapshot: NYSE was open and the agent stood aside. Hover any cell for its value.
      </p>
    </div>
  );
}
