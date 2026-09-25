"use client";

import { useEffect, useState } from "react";

type PositionImpact = {
  underlying: string;
  symbol: string;
  qty: number;
  markPrice: number;
  currentNotional: number;
  scenarioReturn: number;
  hypotheticalPnlUsd: number;
};

type Scenario = {
  id: string;
  label: string;
  description: string;
  positions: PositionImpact[];
  totalHypotheticalPnlUsd: number;
  hypotheticalEquityUsd: number;
};

type StressTestResponse = {
  available: boolean;
  message?: string;
  currentEquityUsd?: number;
  scenarios?: Scenario[];
};

function fmtUsd(n: number) {
  return n.toLocaleString(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 2 });
}

function fmtPct(n: number) {
  return `${(n * 100).toFixed(2)}%`;
}

export default function DecisionStressTest() {
  const [data, setData] = useState<StressTestResponse | null>(null);
  const [selected, setSelected] = useState(0);

  useEffect(() => {
    fetch("/api/stress-test")
      .then((r) => r.json())
      .then(setData);
  }, []);

  if (!data) {
    return <div className="text-sm text-text-tertiary">Loading stress test data...</div>;
  }

  if (!data.available || !data.scenarios || data.scenarios.length === 0) {
    return <div className="text-sm text-text-tertiary">{data.message ?? "No stress-test data available."}</div>;
  }

  if (data.scenarios.every((s) => s.positions.length === 0)) {
    return (
      <div className="text-sm text-text-tertiary">
        No open positions to stress-test right now: the agent&apos;s current book is flat.
        Scenarios will populate once it holds a position.
      </div>
    );
  }

  const scenario = data.scenarios[selected];
  const up = scenario.totalHypotheticalPnlUsd >= 0;

  return (
    <div>
      <div className="flex flex-wrap gap-2" role="tablist" aria-label="Stress scenarios">
        {data.scenarios.map((s, i) => (
          <button
            key={s.id}
            role="tab"
            aria-selected={i === selected}
            onClick={() => setSelected(i)}
            className={
              i === selected
                ? "rounded-full border border-heading bg-heading px-4 py-2 text-xs font-medium tracking-wide text-background"
                : "rounded-full border border-border px-4 py-2 text-xs tracking-wide text-text-secondary transition-colors hover:border-border-strong hover:text-heading"
            }
          >
            {s.label}
          </button>
        ))}
      </div>

      <p className="mt-5 max-w-2xl text-sm leading-relaxed text-text-secondary">{scenario.description}</p>

      <div className="mt-6 flex flex-wrap items-end gap-x-6 gap-y-2">
        <div>
          <div className="micro-label">If this happened tonight</div>
          <div className={`font-display mt-3 text-[40px] leading-none tabular-nums ${up ? "text-positive" : "text-negative"}`}>
            {fmtUsd(scenario.totalHypotheticalPnlUsd)}
          </div>
        </div>
        <div className="pb-1 text-sm text-text-tertiary">equity would be {fmtUsd(scenario.hypotheticalEquityUsd)}</div>
      </div>

      {scenario.positions.length === 0 ? (
        <p className="mt-6 text-sm text-text-tertiary">No held symbols have data for this scenario.</p>
      ) : (
        <div className="-mx-1 mt-6 overflow-x-auto px-1">
          <table className="w-full min-w-[460px] text-left text-sm">
            <thead>
              <tr className="border-b border-border-subtle">
                <th className="micro-label py-3 pr-4 font-medium">Symbol</th>
                <th className="micro-label py-3 pr-4 font-medium">Position</th>
                <th className="micro-label py-3 pr-4 text-right font-medium">Scenario move</th>
                <th className="micro-label py-3 text-right font-medium">Hypothetical P&amp;L</th>
              </tr>
            </thead>
            <tbody>
              {scenario.positions.map((p) => (
                <tr key={p.symbol} className="border-b border-border-subtle last:border-b-0">
                  <td className="py-3 pr-4 font-medium text-heading">{p.underlying}</td>
                  <td className="py-3 pr-4 tabular-nums text-text-secondary">
                    {p.qty >= 0 ? "long" : "short"} {fmtUsd(Math.abs(p.currentNotional))}
                  </td>
                  <td className="py-3 pr-4 text-right tabular-nums text-text-secondary">{fmtPct(p.scenarioReturn)}</td>
                  <td
                    className={`py-3 text-right tabular-nums ${p.hypotheticalPnlUsd >= 0 ? "text-positive" : "text-negative"}`}
                  >
                    {fmtUsd(p.hypotheticalPnlUsd)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
