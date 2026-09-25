"use client";

// Mirrors gloaming_agent/risk_controls.py RiskConfig: the caps the deterministic, non-LLM
// risk layer enforces. Keep in sync if those change there.
const CAPS = { net: 0.25, gross: 0.6, symbol: 0.15, dailyLoss: 0.05 };

type Position = { symbol: string; notionalUsd: number | null };

function fmtPct(n: number, digits = 1) {
  return `${(n * 100).toFixed(digits)}%`;
}

// Healthy is mint (a live, in-limits signal), close to the cap turns copper, over turns coral.
function tone(ratio: number) {
  if (ratio > 1) return { bar: "bg-negative", text: "text-negative" };
  if (ratio >= 0.9) return { bar: "bg-copper", text: "text-copper" };
  return { bar: "bg-mint", text: "text-mint" };
}

function Meter({ label, value, cap, ratio, note }: { label: string; value: string; cap: string; ratio: number; note?: string }) {
  const t = tone(ratio);
  return (
    <div>
      <div className="flex items-baseline justify-between gap-3">
        <span className="micro-label">{label}</span>
        <span className="text-xs text-text-tertiary">cap {cap}</span>
      </div>
      <div className={`font-display mt-2 text-[26px] leading-none tabular-nums ${t.text}`}>{value}</div>
      <div
        className="mt-3 h-1 w-full overflow-hidden rounded-full bg-border-subtle"
        role="meter"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(Math.min(ratio, 1) * 100)}
      >
        <div className={`h-full rounded-full ${t.bar}`} style={{ width: `${Math.min(Math.max(ratio, 0), 1) * 100}%` }} />
      </div>
      {note && <p className="mt-2 text-xs text-text-tertiary">{note}</p>}
    </div>
  );
}

export default function RiskMeters({
  equityUsd,
  dailyPnlUsd,
  positions,
}: {
  equityUsd: number;
  dailyPnlUsd: number;
  positions: Position[];
}) {
  const priced = positions.filter((p): p is { symbol: string; notionalUsd: number } => p.notionalUsd !== null);
  const net = priced.reduce((s, p) => s + p.notionalUsd, 0);
  const gross = priced.reduce((s, p) => s + Math.abs(p.notionalUsd), 0);
  const largest = priced.reduce<{ symbol: string; notionalUsd: number } | null>(
    (best, p) => (best === null || Math.abs(p.notionalUsd) > Math.abs(best.notionalUsd) ? p : best),
    null
  );

  const netPct = equityUsd > 0 ? net / equityUsd : 0;
  const grossPct = equityUsd > 0 ? gross / equityUsd : 0;
  const largestPct = equityUsd > 0 && largest ? Math.abs(largest.notionalUsd) / equityUsd : 0;
  const dailyPct = equityUsd > 0 ? dailyPnlUsd / equityUsd : 0;
  const dailyLossRatio = Math.max(0, -dailyPct) / CAPS.dailyLoss;

  const direction = Math.abs(netPct) < 0.0005 ? "Flat" : netPct > 0 ? "Net long" : "Net short";

  return (
    <div className="rounded-xl border border-border-subtle bg-layer-1 p-5 sm:p-6">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <p className="eyebrow">Risk layer, live</p>
        <p className="text-xs text-text-tertiary">Caps are enforced by a deterministic, non-LLM layer that can reject or resize any decision.</p>
      </div>
      <div className="mt-6 grid grid-cols-2 gap-x-6 gap-y-7 lg:grid-cols-4">
        <Meter
          label="Net exposure"
          value={`${direction} ${fmtPct(Math.abs(netPct))}`}
          cap={fmtPct(CAPS.net, 0)}
          ratio={Math.abs(netPct) / CAPS.net}
          note="Long minus short, as a share of equity"
        />
        <Meter
          label="Gross exposure"
          value={fmtPct(grossPct)}
          cap={fmtPct(CAPS.gross, 0)}
          ratio={grossPct / CAPS.gross}
          note="All positions, either direction"
        />
        <Meter
          label="Largest position"
          value={fmtPct(largestPct)}
          cap={fmtPct(CAPS.symbol, 0)}
          ratio={largestPct / CAPS.symbol}
          note={largest ? `${largest.symbol.replace(/^R|USDT$/g, "")}, ${largest.notionalUsd >= 0 ? "long" : "short"}` : "No open positions"}
        />
        <Meter
          label="Daily loss"
          value={`${dailyPct >= 0 ? "+" : "-"}${fmtPct(Math.abs(dailyPct), 2)}`}
          cap={`-${fmtPct(CAPS.dailyLoss, 0)}`}
          ratio={dailyLossRatio}
          note="New risk halts at the breaker; de-risking still allowed"
        />
      </div>
    </div>
  );
}
