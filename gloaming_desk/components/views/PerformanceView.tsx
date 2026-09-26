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

      {p && (
        <Band label="Two signal eras">
          <SectionHeader
            eyebrow="Two eras"
            title="The record, split where the signal changed."
            description="On Sept 25 the project found that its first signal mostly measured each session's own move, and rebuilt it. The two eras are different systems, so they are shown separately rather than blended into one number."
          />
          <div className="mt-10 grid gap-4 md:grid-cols-2">
            {(
              [
                ["Earlier signal", "Sept 11 to Sept 25, 21:32 UTC", p.eras.earlier, false],
                ["Anchored signal", "From Sept 25, 22:00 UTC", p.eras.anchored, true],
              ] as const
            ).map(([name, span, e, current]) => (
              <div
                key={name}
                className={`rounded-xl border bg-layer-1 p-6 ${current ? "border-mint/50" : "border-border-subtle"}`}
              >
                <div className="flex items-baseline justify-between gap-3">
                  <h3 className="font-display text-[24px] leading-tight text-heading">{name}</h3>
                  {current && <span className="micro-label text-mint">current</span>}
                </div>
                <p className="mt-1 text-xs text-text-tertiary">{span}</p>
                <dl className="mt-5">
                  {[
                    ["Fills", String(e.fills)],
                    ["Position-reducing fills", String(e.closingFills)],
                    [
                      "Win rate",
                      e.winRate === null
                        ? "n/a yet"
                        : e.closingFills < 10
                          ? `${e.winningFills} of ${e.closingFills}, too few to judge`
                          : fmtPct(e.winRate, 1),
                    ],
                    ["Realized P&L", e.closingFills === 0 ? "n/a yet" : fmtSignedUsd(e.realizedPnlUsd)],
                  ].map(([k, v]) => (
                    <div key={k} className="flex items-baseline justify-between gap-4 border-b border-border-subtle py-2.5 last:border-0">
                      <dt className="text-sm text-text-secondary">{k}</dt>
                      <dd className="text-sm tabular-nums text-heading">{v}</dd>
                    </div>
                  ))}
                </dl>
                {current && p.eras.incident.fills > 0 && (
                  <p className="mt-4 text-xs leading-relaxed text-warning">
                    Not counted above: {p.eras.incident.fills} fills ({p.eras.incident.closingFills} position-reducing,{" "}
                    {fmtSignedUsd(p.eras.incident.realizedPnlUsd)} realized) from a data gap on Sept 26, 00:00 to 01:40
                    UTC, when the agent briefly anchored to Thursday&apos;s close. Fixed the same day. They are in the
                    ledger and in the totals at the top, and are kept out of both eras so they cannot flatter or
                    penalize either signal.
                  </p>
                )}
              </div>
            ))}
          </div>
        </Band>
      )}

      {p && (
        <Band label="Trading costs">
          <SectionHeader
            eyebrow="Costs"
            title="What trading costs, and what it would have cost."
            description="A 0.15% charge per fill (0.10% fee plus 0.05% slippage, a stated assumption) is deducted from cash from Sept 26. Earlier fills were recorded without a cost."
          />
          <div className="mt-10 grid grid-cols-2 gap-3 sm:gap-4">
            <StatTile label="Charged in the ledger" value={fmtUsd(p.costs.recordedUsd)} sub="fills from Sept 26, in the totals above" />
            <StatTile
              label="Estimated on earlier fills"
              value={fmtUsd(p.costs.estimatedOnEarlierFillsUsd)}
              sub="an estimate at the same rate, not in the ledger"
            />
          </div>
        </Band>
      )}

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
          <li>
            From Sept 26 every fill is charged a stated cost: a 0.10% fee plus 0.05% slippage. That rate is an
            assumption, not Bitget&apos;s measured rToken schedule. Earlier fills carry no cost; the estimate for them
            is shown separately below and is not in the ledger or the totals.
          </li>
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
