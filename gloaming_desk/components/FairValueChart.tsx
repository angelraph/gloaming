"use client";

import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

type SnapshotEvent = {
  timestamp: string;
  underlying: string | null;
  snapshot?: {
    rtoken_symbol: string;
    spread: number;
  };
};

// Latest spread per symbol, from whichever event is most recent - this IS the
// "actual vs fair value" gap the whole project is built on, in chart form.
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
// every context, so these mirror app/globals.css's --negative/--positive/etc.
// literally - keep in sync if the palette changes there.
const COLORS = {
  grid: "#26262e",
  axis: "#6b6b74",
  tooltipBg: "#1c1c23",
  tooltipBorder: "#26262e",
  tooltipLabel: "#f4f5f7",
  rich: "#f1493f", // positive spread -> overpriced vs. fair value -> the sell side
  cheap: "#01bc8d", // negative spread -> underpriced vs. fair value -> the buy side
};

export default function FairValueChart({ events }: { events: SnapshotEvent[] }) {
  const data = latestSpreadBySymbol(events);

  if (data.length === 0) {
    return <div className="text-sm text-text-tertiary">No snapshot data yet.</div>;
  }

  return (
    <ResponsiveContainer width="100%" height={260}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: 8, bottom: 8 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={COLORS.grid} />
        <XAxis dataKey="symbol" stroke={COLORS.axis} fontSize={12} />
        <YAxis
          stroke={COLORS.axis}
          fontSize={12}
          tickFormatter={(v: number) => `${v.toFixed(1)}%`}
          label={{ value: "Spread (actual vs. fair value)", angle: -90, position: "insideLeft", fill: COLORS.axis, fontSize: 11 }}
        />
        <Tooltip
          contentStyle={{ background: COLORS.tooltipBg, border: `1px solid ${COLORS.tooltipBorder}`, borderRadius: 8 }}
          labelStyle={{ color: COLORS.tooltipLabel }}
          formatter={(value) => [`${Number(value).toFixed(2)}%`, "spread"]}
        />
        <Bar dataKey="spread" radius={[4, 4, 0, 0]}>
          {data.map((d) => (
            <Cell key={d.symbol} fill={d.spread > 0 ? COLORS.rich : COLORS.cheap} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
