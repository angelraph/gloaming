"use client";

import { useCallback, useEffect, useState } from "react";
import type { PerformanceSummary } from "@/lib/performance";
import { fmtDate, fmtPct, fmtSignedPct, fmtSignedUsd, fmtUsd } from "@/lib/format";
import { underlyingFromRtoken } from "@/lib/universe";
import { Band, PageHeader } from "@/components/Container";
import SectionHeader from "@/components/SectionHeader";
import StatTile from "@/components/StatTile";
import EquityCurve from "@/components/EquityCurve";
import ExportButtons from "@/components/ExportButtons";
import VerifyPanel from "@/components/VerifyPanel";
import DataNotice from "@/components/DataNotice";

type Resp = ({ configured: true } & PerformanceSummary) | { configured: false };

export default function PerformanceView() {
  const [data, setData] = useState<Resp | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const r = await fetch("/api/performance");
      if (!r.ok) throw new Error(`performance ${r.status}`);
      setData(await r.json());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load");
    }
  }, []);

  useEffect(() => {
    load();
    const i = setInterval(load, 60_000);
    return () => clearInterval(i);
  }, [load]);

  const p = data && data.configured ? data : null;

  return (
    <>
      <PageHeader
        eyebrow="Validation"
        title="The paper-trading record."
        description="Derived only from the ledger's real fills. The method and its limits are stated next to the numbers, because a short window and simple marking deserve plain labels."
      />
      {error && (
        <div className="mx-auto max-w-[1216px] px-4 pb-6 sm:px-6 lg:px-10">
          <DataNotice message={error} onRetry={load} />
        </div>
      )}

      <Band label="Headline numbers" first>
        {!p ? (
          <div aria-hidden className="grid grid-cols-2 gap-3 lg:grid-cols-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="h-[112px] animate-pulse rounded-xl border border-border-subtle bg-layer-1" />
            ))}
          </div>
        ) : (
          <>
            <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-3">
              <StatTile
                label="Total return"
                value={fmtSignedPct(p.totalReturn)}
                tone={p.totalReturn >= 0 ? "positive" : "negative"}
                sub={`${fmtUsd(p.startingEquityUsd)} to ${fmtUsd(p.currentEquityUsd)}`}
                live
              />
              <StatTile
                label="Realized P&L"
                value={fmtSignedUsd(p.realizedPnlUsd)}
                tone={p.realizedPnlUsd >= 0 ? "positive" : "negative"}
                sub="from position-reducing fills"
              />
              <StatTile label="Max drawdown" value={fmtPct(p.maxDrawdown)} sub="on the marked curve, see notes" />
              <StatTile
                label="Win rate"
                value={p.winRate === null ? "n/a" : fmtPct(p.winRate, 1)}
                sub={`${p.winningFills} of ${p.closingFills} closing fills gained`}
              />
              <StatTile
                label="Sharpe (annualized)"
                value={p.sharpe === null ? "n/a" : p.sharpe.toFixed(2)}
                sub={`daily returns, n = ${p.dailyReturnsCount}, indicative only`}
              />
              <StatTile
                label="Observed"
                value={`${p.observedDays} days`}
                sub={`${p.totalFills} fills, ${p.firstFillAt ? fmtDate(p.firstFillAt) : ""} to ${p.lastFillAt ? fmtDate(p.lastFillAt) : ""}`}
              />
            </div>
          </>
        )}
      </Band>

      <Band label="Equity curve">
        <SectionHeader
          eyebrow="Equity"
          title="Paper equity through time."
          description="Re-marked at every fill, with a final point at live prices. The dashed line is the $100,000 start."
        />
        <div className="mt-10 rounded-xl border border-border-subtle bg-layer-1 p-5 sm:p-6">
          {p ? <EquityCurve curve={p.curve} startingEquityUsd={p.startingEquityUsd} /> : <div aria-hidden className="h-[300px] animate-pulse rounded-lg bg-layer-2" />}
        </div>
      </Band>

      {p && (
        <Band label="By symbol">
          <SectionHeader eyebrow="By symbol" title="Where the realized P&L came from." />
          <div className="mt-10 overflow-x-auto rounded-xl border border-border-subtle bg-layer-1">
            <table className="w-full min-w-[420px] text-left text-sm">
              <caption className="sr-only">Fills and realized P&amp;L by symbol</caption>
              <thead>
                <tr className="border-b border-border-subtle">
                  <th scope="col" className="micro-label px-4 py-3 font-normal">Symbol</th>
                  <th scope="col" className="micro-label px-4 py-3 text-right font-normal">Fills</th>
                  <th scope="col" className="micro-label px-4 py-3 text-right font-normal">Realized P&amp;L</th>
                </tr>
              </thead>
              <tbody>
                {p.bySymbol.map((s) => (
                  <tr key={s.symbol} className="border-b border-border-subtle last:border-0">
                    <th scope="row" className="px-4 py-3 font-medium text-heading">{underlyingFromRtoken(s.symbol)}</th>
                    <td className="px-4 py-3 text-right tabular-nums text-text-secondary">{s.fills}</td>
                    <td className={`px-4 py-3 text-right tabular-nums ${s.realizedPnlUsd >= 0 ? "text-positive" : "text-negative"}`}>
                      {fmtSignedUsd(s.realizedPnlUsd)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Band>
      )}

      <Band label="Method and limits">
        <SectionHeader
          eyebrow="Read this first"
          title="How these numbers are made, and where they are soft."
        />
        <ul className="mt-10 max-w-3xl list-disc space-y-3 pl-5 text-[15px] leading-relaxed text-text-secondary">
          <li>Everything is paper trading on a virtual ledger. Bitget&apos;s demo environment does not list rToken symbols, so fills are simulated at live rToken prices.</li>
          <li>Equity is re-marked at each fill using each symbol&apos;s last fill price. Between fills it does not move, so drawdown is understated; the final point uses live prices.</li>
          <li>Win rate counts closing fills that realized a gain (average-cost basis, shorts included), not complete round trips.</li>
          <li>Sharpe uses one equity value per UTC day and √365, because the agent works nights and weekends. With only a couple of weeks of days it is an indication, not a statistic.</li>
          <li>Fills carry no fees or slippage yet. Real execution would cost more than this record shows.</li>
          <li>The window includes the earlier rolling-24h signal, which a later check found was mostly measuring the session&apos;s own move. That is disclosed in the docs; the record is not edited to hide it.</li>
        </ul>
      </Band>

      <Band label="Download the data">
        <SectionHeader
          eyebrow="Download"
          title="Take the record and check it."
          description="Fills is the whole ledger. Decisions is what the live mirror holds, the most recent ~500 records; the complete history is in the repository."
        />
        <div className="mt-8">
          <ExportButtons />
        </div>
      </Band>

      <Band label="Verify it yourself">
        <SectionHeader eyebrow="Verify it yourself" title="The sources behind every number." />
        <div className="mt-10">
          <VerifyPanel />
        </div>
      </Band>
    </>
  );
}
