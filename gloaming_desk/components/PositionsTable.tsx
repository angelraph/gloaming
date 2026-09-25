"use client";

import Link from "next/link";
import type { Portfolio } from "@/lib/useDeskData";
import { fmtPct, fmtUsd } from "@/lib/format";
import { underlyingFromRtoken } from "@/lib/universe";

// Every open position, long or short, sized against equity (the per-symbol cap is 15%).
export default function PositionsTable({ portfolio }: { portfolio: Portfolio }) {
  const equity = portfolio.equityUsd ?? 0;
  const rows = [...(portfolio.positions ?? [])]
    .filter((p) => Math.abs(p.qty) > 1e-9)
    .sort((a, b) => Math.abs(b.notionalUsd ?? 0) - Math.abs(a.notionalUsd ?? 0));

  if (rows.length === 0) {
    return <p className="text-sm text-text-tertiary">No open positions.</p>;
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-border-subtle bg-layer-1">
      <table className="w-full min-w-[520px] text-left text-sm">
        <caption className="sr-only">Open paper positions, sized against equity</caption>
        <thead>
          <tr className="border-b border-border-subtle text-text-tertiary">
            <th scope="col" className="micro-label px-4 py-3 font-normal">Symbol</th>
            <th scope="col" className="micro-label px-4 py-3 font-normal">Side</th>
            <th scope="col" className="micro-label px-4 py-3 text-right font-normal">Quantity</th>
            <th scope="col" className="micro-label px-4 py-3 text-right font-normal">Notional</th>
            <th scope="col" className="micro-label px-4 py-3 text-right font-normal">% of equity</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((p) => {
            const u = underlyingFromRtoken(p.symbol);
            const long = p.qty > 0;
            return (
              <tr key={p.symbol} className="border-b border-border-subtle last:border-0">
                <th scope="row" className="px-4 py-3 font-medium">
                  <Link href={`/desk/${u}`} className="inline-flex min-h-8 items-center text-heading underline-offset-4 hover:underline">
                    {u}
                  </Link>
                </th>
                <td className={`px-4 py-3 ${long ? "text-mint" : "text-negative"}`}>{long ? "Long" : "Short"}</td>
                <td className="px-4 py-3 text-right tabular-nums text-text-secondary">{Math.abs(p.qty).toFixed(4)}</td>
                <td className="px-4 py-3 text-right tabular-nums text-heading">
                  {p.notionalUsd === null ? "n/a" : fmtUsd(Math.abs(p.notionalUsd))}
                </td>
                <td className="px-4 py-3 text-right tabular-nums text-text-secondary">
                  {p.notionalUsd === null || equity === 0 ? "n/a" : fmtPct(Math.abs(p.notionalUsd) / equity, 1)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
