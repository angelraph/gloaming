"use client";

import { Area, AreaChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { EquityPoint } from "@/lib/performance";
import { fmtDate, fmtUsd } from "@/lib/format";

const COLORS = { grid: "#1c1d22", axis: "#777a88", tooltipBg: "#14151a", tooltipBorder: "#2e3038" };

// One point per fill (equity re-marked at each), plus a final live point. The gilded gradient
// is the data line; the dashed line is the $100,000 starting equity.
export default function EquityCurve({ curve, startingEquityUsd }: { curve: EquityPoint[]; startingEquityUsd: number }) {
  const data = curve.map((p) => ({ t: new Date(p.t).getTime(), equity: p.equity }));
  const first = curve[0];
  const last = curve[curve.length - 1];
  const summary = `Paper equity curve from ${fmtDate(first.t)} to ${fmtDate(last.t)}, starting at ${fmtUsd(
    startingEquityUsd
  )} and ending at ${fmtUsd(last.equity)}.`;

  return (
    <div role="img" aria-label={summary}>
      <ResponsiveContainer width="100%" height={300}>
        <AreaChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 4 }}>
          <defs>
            <linearGradient id="equityFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#cc9166" stopOpacity={0.28} />
              <stop offset="100%" stopColor="#cc9166" stopOpacity={0} />
            </linearGradient>
            <linearGradient id="equityLine" gradientUnits="userSpaceOnUse" x1="0%" y1="0" x2="100%" y2="0">
              <stop offset="0%" stopColor="#ae9357" />
              <stop offset="45%" stopColor="#fff0cc" />
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
            tickFormatter={(v: number) => fmtDate(new Date(v).toISOString())}
            minTickGap={40}
          />
          <YAxis
            stroke={COLORS.axis}
            fontSize={12}
            tickLine={false}
            axisLine={false}
            width={64}
            domain={["auto", "auto"]}
            tickFormatter={(v: number) => `$${(v / 1000).toFixed(1)}k`}
          />
          <Tooltip
            contentStyle={{ background: COLORS.tooltipBg, border: `1px solid ${COLORS.tooltipBorder}`, borderRadius: 12, fontSize: 12 }}
            labelStyle={{ color: "#ffffff" }}
            labelFormatter={(v) => new Date(Number(v)).toLocaleString()}
            formatter={(v) => [fmtUsd(Number(v)), "equity"]}
          />
          <ReferenceLine y={startingEquityUsd} stroke="#464853" strokeDasharray="4 4" />
          <Area type="monotone" dataKey="equity" stroke="url(#equityLine)" strokeWidth={2} fill="url(#equityFill)" />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
