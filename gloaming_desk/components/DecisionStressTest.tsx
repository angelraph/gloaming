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
        No open positions to stress-test right now - the Agent&apos;s current book is
        flat. Scenarios will populate once it holds a position.
      </div>
    );
  }

  const scenario = data.scenarios[selected];

  return (
    <div>
      <div className="mb-3 flex flex-wrap gap-2">
        {data.scenarios.map((s, i) => (
          <button
            key={s.id}
            onClick={() => setSelected(i)}
            className={
              i === selected
                ? "rounded-md bg-brand px-3 py-1.5 text-xs font-medium text-white"
                : "rounded-md border border-border px-3 py-1.5 text-xs text-text-secondary hover:border-text-tertiary"
            }
          >
            {s.label}
          </button>
        ))}
      </div>

      <p className="mb-3 text-xs text-text-tertiary">{scenario.description}</p>

      <div className="mb-3 flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span className="text-xs text-text-tertiary">If this happened tonight:</span>
        <span
          className={
            scenario.totalHypotheticalPnlUsd >= 0
              ? "font-mono text-lg font-semibold tabular-nums text-positive"
              : "font-mono text-lg font-semibold tabular-nums text-negative"
          }
        >
          {fmtUsd(scenario.totalHypotheticalPnlUsd)}
        </span>
        <span className="text-xs text-text-tertiary">
          equity would be {fmtUsd(scenario.hypotheticalEquityUsd)}
        </span>
      </div>

      {scenario.positions.length === 0 ? (
        <p className="text-sm text-text-tertiary">No held symbols have data for this scenario.</p>
      ) : (
        <div className="-mx-1 overflow-x-auto px-1">
          <table className="w-full min-w-[420px] text-left text-xs">
            <thead className="text-text-tertiary">
              <tr>
                <th className="py-1 pr-3 font-medium">Symbol</th>
                <th className="py-1 pr-3 font-medium">Position</th>
                <th className="py-1 pr-3 font-medium">Scenario move</th>
                <th className="py-1 text-right font-medium">Hypothetical P&amp;L</th>
              </tr>
            </thead>
            <tbody>
              {scenario.positions.map((p) => (
                <tr key={p.symbol} className="border-t border-border-subtle">
                  <td className="py-1.5 pr-3 font-medium">{p.underlying}</td>
                  <td className="py-1.5 pr-3 font-mono text-text-secondary tabular-nums">
                    {p.qty >= 0 ? "long" : "short"} {fmtUsd(Math.abs(p.currentNotional))}
                  </td>
                  <td className="py-1.5 pr-3 font-mono text-text-secondary tabular-nums">{fmtPct(p.scenarioReturn)}</td>
                  <td
                    className={
                      p.hypotheticalPnlUsd >= 0
                        ? "py-1.5 text-right font-mono tabular-nums text-positive"
                        : "py-1.5 text-right font-mono tabular-nums text-negative"
                    }
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
