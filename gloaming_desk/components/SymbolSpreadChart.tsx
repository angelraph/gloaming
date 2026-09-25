"use client";

import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { DecisionRecord } from "@/lib/data";

const COLORS = { grid: "#1c1d22", axis: "#777a88", tooltipBg: "#14151a", tooltipBorder: "#2e3038" };

// One symbol's spread through time, from the anchored-signal (v2) snapshots only: the earlier
// rolling-24h records measured a different quantity and would make a misleading line.
export default function SymbolSpreadChart({ events, symbol }: { events: DecisionRecord[]; symbol: string }) {
  const data = events
    .filter((e) => e.underlying === symbol && e.snapshot?.signal_spec === "since_last_close_v2")
    .map((e) => ({ t: new Date(e.timestamp).getTime(), spread: (e.snapshot?.spread ?? 0) * 100 }))
    .sort((a, b) => a.t - b.t);

  if (data.length < 2) {
    return <p className="text-sm text-text-tertiary">Not enough anchored-signal records yet to draw a line for {symbol}.</p>;
  }

  const min = Math.min(...data.map((d) => d.spread));
  const max = Math.max(...data.map((d) => d.spread));
  const summary = `Spread for ${symbol} over ${data.length} cycles, from ${min.toFixed(3)}% to ${max.toFixed(3)}%.`;

  return (
    <div>
      <div role="img" aria-label={summary}>
        <ResponsiveContainer width="100%" height={260}>
          <LineChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 4 }}>
            <defs>
              <linearGradient id="spreadLine" gradientUnits="userSpaceOnUse" x1="0%" y1="0" x2="100%" y2="0">
                <stop offset="0%" stopColor="#ae9357" />
                <stop offset="50%" stopColor="#fff0cc" />
                <stop offset="100%" stopColor="#ae9357" />
              </linearGradient>
            </defs>
            <CartesianGrid vertical={false} stroke={COLORS.grid} />
            <XAxis
              dataKey="t"
              type="number"
              scale="time"
              domain={["dataMin", "dataMax"]}
              stroke={COLORS.axis}
              fontSize={12}
              tickLine={false}
              axisLine={false}
              minTickGap={48}
              tickFormatter={(v: number) => new Date(v).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
            />
            <YAxis
              stroke={COLORS.axis}
              fontSize={12}
              tickLine={false}
              axisLine={false}
              width={52}
              tickFormatter={(v: number) => `${v.toFixed(2)}%`}
            />
            <Tooltip
              contentStyle={{ background: COLORS.tooltipBg, border: `1px solid ${COLORS.tooltipBorder}`, borderRadius: 12, fontSize: 12 }}
              labelFormatter={(v) => new Date(Number(v)).toLocaleString()}
              formatter={(v) => [`${Number(v).toFixed(3)}%`, "spread"]}
            />
            <ReferenceLine y={0} stroke="#464853" />
            <Line type="monotone" dataKey="spread" stroke="url(#spreadLine)" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <details className="mt-3 text-sm text-text-secondary">
        <summary className="inline-flex min-h-11 cursor-pointer items-center text-text-secondary hover:text-heading">
          View chart data as a table
        </summary>
        <div className="mt-2 max-h-64 overflow-auto rounded-lg border border-border-subtle">
          <table className="w-full text-left text-xs">
            <caption className="sr-only">Spread for {symbol} by cycle</caption>
            <thead>
              <tr className="border-b border-border-subtle text-text-tertiary">
                <th scope="col" className="px-3 py-2 font-normal">Time</th>
                <th scope="col" className="px-3 py-2 text-right font-normal">Spread</th>
              </tr>
            </thead>
            <tbody>
              {[...data].reverse().map((d) => (
                <tr key={d.t} className="border-b border-border-subtle last:border-0">
                  <td className="px-3 py-1.5 tabular-nums">{new Date(d.t).toLocaleString()}</td>
                  <td className="px-3 py-1.5 text-right tabular-nums">{d.spread.toFixed(3)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  );
}
