"use client";

import { Bar, BarChart, CartesianGrid, Cell, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

type SnapshotEvent = {
  timestamp: string;
  underlying: string | null;
  snapshot?: {
    rtoken_symbol: string;
    spread: number;
  };
};

// Latest spread per symbol, from whichever event is most recent - this IS the
// "actual vs fair value" gap the whole project is built on, in chart form. Since Sept 25
// it is the rToken's return since the real close minus the proxies' return since the close.
function latestSpreadBySymbol(events: SnapshotEvent[]) {
  const bySymbol = new Map<string, { symbol: string; spread: number; timestamp: string }>();
  for (const e of events) {
    if (!e.snapshot || !e.underlying) continue;
    const existing = bySymbol.get(e.underlying);
    if (!existing || e.timestamp > existing.timestamp) {
      bySymbol.set(e.underlying, {
        symbol: e.underlying,
        spread: e.snapshot.spread * 100,
        timestamp: e.timestamp,
      });
    }
  }
  return Array.from(bySymbol.values()).sort((a, b) => b.spread - a.spread);
}

// Recharts renders to SVG and doesn't reliably resolve CSS custom properties in
// every context, so these mirror app/globals.css literally - keep in sync if the
// palette changes there.
const COLORS = {
  grid: "#1c1d22",
  axis: "#777a88",
  tooltipBg: "#14151a",
  tooltipBorder: "#2e3038",
  tooltipLabel: "#ffffff",
  rich: "#e5786d", // positive spread -> overpriced vs. fair value -> the sell side
  cheap: "#3fe280", // negative spread -> underpriced vs. fair value -> the buy side
};

export default function FairValueChart({ events }: { events: SnapshotEvent[] }) {
  const data = latestSpreadBySymbol(events);

  if (data.length === 0) {
    return <div className="text-sm text-text-tertiary">No snapshot data yet.</div>;
  }

  return (
    <ResponsiveContainer width="100%" height={280}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 4 }}>
        <defs>
          {/* the gilded gradient, reserved for data-visualization lines: here, the zero baseline */}
          <linearGradient id="gilded" gradientUnits="userSpaceOnUse" x1="0%" y1="0" x2="100%" y2="0">
            <stop offset="0%" stopColor="#ae9357" />
            <stop offset="40%" stopColor="#fff0cc" />
            <stop offset="70%" stopColor="#ae9357" />
            <stop offset="100%" stopColor="#bd9d4f" stopOpacity={0.1} />
          </linearGradient>
        </defs>
        <CartesianGrid vertical={false} stroke={COLORS.grid} />
        <XAxis dataKey="symbol" stroke={COLORS.axis} fontSize={12} tickLine={false} axisLine={false} />
        <YAxis
          stroke={COLORS.axis}
          fontSize={12}
          tickLine={false}
          axisLine={false}
          width={52}
          tickFormatter={(v: number) => `${v.toFixed(2)}%`}
        />
        <Tooltip
          cursor={{ fill: "rgba(255,255,255,0.03)" }}
          contentStyle={{
            background: COLORS.tooltipBg,
            border: `1px solid ${COLORS.tooltipBorder}`,
            borderRadius: 12,
            fontSize: 12,
          }}
          labelStyle={{ color: COLORS.tooltipLabel }}
          formatter={(value) => [`${Number(value).toFixed(3)}%`, "spread"]}
        />
        <ReferenceLine y={0} stroke="url(#gilded)" strokeWidth={1.5} />
        <Bar dataKey="spread" radius={[4, 4, 4, 4]} maxBarSize={44}>
          {data.map((d) => (
            <Cell key={d.symbol} fill={d.spread > 0 ? COLORS.rich : COLORS.cheap} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
