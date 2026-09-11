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
    return <div className="text-sm text-neutral-500">Loading stress test data...</div>;
  }

  if (!data.available || !data.scenarios || data.scenarios.length === 0) {
    return <div className="text-sm text-neutral-500">{data.message ?? "No stress-test data available."}</div>;
  }

  if (data.scenarios.every((s) => s.positions.length === 0)) {
    return (
      <div className="text-sm text-neutral-500">
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
                ? "rounded-md bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white"
                : "rounded-md border border-neutral-700 px-3 py-1.5 text-xs text-neutral-300 hover:border-neutral-500"
            }
          >
            {s.label}
          </button>
        ))}
      </div>

      <p className="mb-3 text-xs text-neutral-500">{scenario.description}</p>

      <div className="mb-3 flex items-baseline gap-3">
        <span className="text-xs text-neutral-500">If this happened tonight:</span>
        <span
          className={
            scenario.totalHypotheticalPnlUsd >= 0
              ? "text-lg font-semibold text-emerald-400"
              : "text-lg font-semibold text-rose-400"
          }
        >
          {fmtUsd(scenario.totalHypotheticalPnlUsd)}
        </span>
        <span className="text-xs text-neutral-500">
          equity would be {fmtUsd(scenario.hypotheticalEquityUsd)}
        </span>
      </div>

      {scenario.positions.length === 0 ? (
        <p className="text-sm text-neutral-500">No held symbols have data for this scenario.</p>
      ) : (
        <table className="w-full text-left text-xs">
          <thead className="text-neutral-500">
            <tr>
              <th className="py-1 pr-3">Symbol</th>
              <th className="py-1 pr-3">Position</th>
              <th className="py-1 pr-3">Scenario move</th>
              <th className="py-1 text-right">Hypothetical P&L</th>
            </tr>
          </thead>
          <tbody>
            {scenario.positions.map((p) => (
              <tr key={p.symbol} className="border-t border-neutral-800">
                <td className="py-1.5 pr-3 font-medium">{p.underlying}</td>
                <td className="py-1.5 pr-3 text-neutral-400">
                  {p.qty >= 0 ? "long" : "short"} {fmtUsd(Math.abs(p.currentNotional))}
                </td>
                <td className="py-1.5 pr-3 text-neutral-400">{fmtPct(p.scenarioReturn)}</td>
                <td
                  className={
                    p.hypotheticalPnlUsd >= 0
                      ? "py-1.5 text-right text-emerald-400"
                      : "py-1.5 text-right text-rose-400"
                  }
                >
                  {fmtUsd(p.hypotheticalPnlUsd)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
