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

export default function FairValueChart({ events }: { events: SnapshotEvent[] }) {
  const data = latestSpreadBySymbol(events);

  if (data.length === 0) {
    return <div className="text-sm text-neutral-500">No snapshot data yet.</div>;
  }

  return (
    <ResponsiveContainer width="100%" height={260}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: 8, bottom: 8 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
        <XAxis dataKey="symbol" stroke="#a1a1aa" fontSize={12} />
        <YAxis
          stroke="#a1a1aa"
          fontSize={12}
          tickFormatter={(v: number) => `${v.toFixed(1)}%`}
          label={{ value: "Spread (actual vs. fair value)", angle: -90, position: "insideLeft", fill: "#a1a1aa", fontSize: 11 }}
        />
        <Tooltip
          contentStyle={{ background: "#18181b", border: "1px solid #3f3f46", borderRadius: 8 }}
          labelStyle={{ color: "#e4e4e7" }}
          formatter={(value) => [`${Number(value).toFixed(2)}%`, "spread"]}
        />
        <Bar dataKey="spread" radius={[4, 4, 0, 0]}>
          {data.map((d) => (
            <Cell key={d.symbol} fill={d.spread > 0 ? "#f43f5e" : "#10b981"} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
