"use client";

import { useMemo, useState } from "react";
import { Area, AreaChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { PerformanceSummary } from "@/lib/performance";
import { fmtDate, fmtPct, fmtSignedUsd, fmtUsd } from "@/lib/format";

const RANGES = [
  { key: "7d", label: "7D", days: 7 },
  { key: "14d", label: "14D", days: 14 },
  { key: "all", label: "All", days: Infinity },
] as const;

function Spark({ values, tone }: { values: number[]; tone: string }) {
  if (values.length < 2) return null;
  const w = 96;
  const h = 28;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const pts = values.map((v, i) => `${((i / (values.length - 1)) * w).toFixed(1)},${(h - ((v - min) / span) * (h - 4) - 2).toFixed(1)}`);
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="h-7 w-24" aria-hidden>
      <polyline points={pts.join(" ")} fill="none" stroke={tone} strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round" />
      <circle cx={w} cy={pts[pts.length - 1].split(",")[1]} r="2.5" fill={tone} />
    </svg>
  );
}

function Tile({ label, value, sub, tone, spark }: { label: string; value: string; sub: string; tone?: string; spark?: React.ReactNode }) {
  return (
    <div className="spotlight rounded-xl border border-border-subtle bg-layer-1 p-4">
      <div className="flex items-start justify-between gap-2">
        <span className="micro-label">{label}</span>
        {spark}
      </div>
      <div className={`mt-2 text-[24px] font-medium leading-none ${tone ?? "text-heading"}`}>{value}</div>
      <div className="mt-2 text-xs text-text-tertiary">{sub}</div>
    </div>
  );
}

// The book at a glance: four headline tiles with their own small trend, and the paper equity
// curve (one point per fill, plus a live point) with a range filter above it.
export default function BookPanel({
  perf,
  dailyPnl,
  verified,
}: {
  perf: PerformanceSummary | null;
  dailyPnl: number;
  verified: { matched: number; checked: number } | null;
}) {
  const [range, setRange] = useState<(typeof RANGES)[number]["key"]>("all");
  const data = useMemo(() => {
    if (!perf) return [];
    const days = RANGES.find((r) => r.key === range)!.days;
    const cutoff = Number.isFinite(days) ? Date.parse(perf.curve[perf.curve.length - 1].t) - days * 86_400_000 : -Infinity;
    return perf.curve.map((p) => ({ t: Date.parse(p.t), equity: p.equity })).filter((p) => p.t >= cutoff);
  }, [perf, range]);

  if (!perf) return <div aria-hidden className="h-[420px] animate-pulse rounded-xl bg-layer-1" />;
  const recent = perf.curve.slice(-60).map((p) => p.equity);
  const realizedNet = perf.realizedPnlUsd - perf.costs.recordedUsd;

  return (
    <div>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Tile
          label="Paper equity"
          value={fmtUsd(perf.currentEquityUsd)}
          sub={`${perf.totalReturn >= 0 ? "+" : ""}${fmtPct(perf.totalReturn)} since Sept 11`}
          tone={perf.totalReturn >= 0 ? "text-positive" : "text-heading"}
          spark={<Spark values={recent} tone="#cc9166" />}
        />
        <Tile label="Today" value={fmtSignedUsd(dailyPnl)} sub="against today's opening equity" tone={dailyPnl >= 0 ? "text-positive" : "text-negative"} />
        <Tile
          label="Realized, net of costs"
          value={fmtSignedUsd(realizedNet)}
          sub={`${perf.closingFills} closing fills, max drawdown ${fmtPct(perf.maxDrawdown)}`}
          tone={realizedNet >= 0 ? "text-positive" : "text-negative"}
        />
        <Tile
          label="Matched on Bitget"
          value={verified ? `${verified.matched} / ${verified.checked}` : "checking"}
          sub="fills inside a real Bitget minute's range"
          tone="text-mint"
        />
      </div>

      <div className="mt-4 rounded-xl border border-border-subtle bg-layer-1 p-4 sm:p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <span className="micro-label">Paper equity, re-marked at every fill</span>
          <div className="flex rounded-full border border-border-subtle p-0.5" role="group" aria-label="Time range">
            {RANGES.map((r) => (
              <button
                key={r.key}
                type="button"
                aria-pressed={range === r.key}
                onClick={() => setRange(r.key)}
                className={`min-h-8 rounded-full px-3 text-xs font-medium transition-colors ${
                  range === r.key ? "bg-layer-2 text-heading" : "text-text-tertiary hover:text-text-primary"
                }`}
              >
                {r.label}
              </button>
            ))}
          </div>
        </div>
        <div
          className="mt-3"
          role="img"
          aria-label={`Paper equity from ${fmtUsd(data[0]?.equity ?? 0)} to ${fmtUsd(data[data.length - 1]?.equity ?? 0)}; the dashed line is the $100,000 start.`}
        >
          <ResponsiveContainer width="100%" height={260}>
            <AreaChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="consoleEquityFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#cc9166" stopOpacity={0.32} />
                  <stop offset="100%" stopColor="#cc9166" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid vertical={false} stroke="#1c1d22" />
              <XAxis
                dataKey="t"
                type="number"
                scale="time"
                domain={["dataMin", "dataMax"]}
                stroke="#777a88"
                fontSize={11}
                tickLine={false}
                axisLine={false}
                minTickGap={48}
                tickFormatter={(v: number) => fmtDate(new Date(v).toISOString())}
              />
              <YAxis
                stroke="#777a88"
                fontSize={11}
                tickLine={false}
                axisLine={false}
                width={56}
                domain={["auto", "auto"]}
                tickFormatter={(v: number) => `$${(v / 1000).toFixed(1)}k`}
              />
              <Tooltip
                cursor={{ stroke: "#464853" }}
                contentStyle={{ background: "#14151a", border: "1px solid #2e3038", borderRadius: 12, fontSize: 12 }}
                labelStyle={{ color: "#ffffff" }}
                labelFormatter={(v) => new Date(Number(v)).toLocaleString()}
                formatter={(v) => [fmtUsd(Number(v)), "equity"]}
              />
              <ReferenceLine y={perf.startingEquityUsd} stroke="#464853" strokeDasharray="4 4" />
              <Area type="stepAfter" dataKey="equity" stroke="#e8c9a0" strokeWidth={2} fill="url(#consoleEquityFill)" isAnimationActive animationDuration={900} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
