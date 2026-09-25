"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useDeskData } from "@/lib/useDeskData";
import { fmtDate, fmtPct, fmtSignedPct, fmtTime, fmtUsd } from "@/lib/format";
import { UNIVERSE, rtokenSymbol } from "@/lib/universe";
import { Band, Container } from "@/components/Container";
import SectionHeader from "@/components/SectionHeader";
import StatTile from "@/components/StatTile";
import SymbolSpreadChart from "@/components/SymbolSpreadChart";
import DecisionFeed from "@/components/DecisionFeed";
import DataNotice from "@/components/DataNotice";

type Fill = { timestamp: string; symbol: string; side: string; qty: number; price: number; notional_usd: number; rationale: string };

export default function SymbolView({ symbol }: { symbol: string }) {
  const { portfolio, events, loading, error, reload } = useDeskData();
  const [fills, setFills] = useState<{ fills: Fill[]; total: number } | null>(null);
  const r = rtokenSymbol(symbol);

  useEffect(() => {
    let live = true;
    fetch(`/api/fills?symbol=${r}&limit=25`)
      .then((x) => x.json())
      .then((d) => live && setFills(d))
      .catch(() => live && setFills({ fills: [], total: 0 }));
    return () => {
      live = false;
    };
  }, [r]);

  const mine = events.filter((e) => e.underlying === symbol);
  const latest = mine.find((e) => e.snapshot);
  const s = latest?.snapshot;
  const pos = portfolio?.positions?.find((p) => p.symbol === r);
  const equity = portfolio?.equityUsd ?? 0;
  const idx = UNIVERSE.indexOf(symbol as (typeof UNIVERSE)[number]);
  const prev = UNIVERSE[(idx + UNIVERSE.length - 1) % UNIVERSE.length];
  const next = UNIVERSE[(idx + 1) % UNIVERSE.length];

  return (
    <>
      <section>
        <Container className="pb-10 pt-12 sm:pt-16">
          <nav aria-label="Breadcrumb" className="text-sm text-text-tertiary">
            <Link href="/desk" className="inline-flex min-h-8 items-center hover:text-heading">Desk</Link>
            <span aria-hidden> / </span>
            <span aria-current="page" className="text-text-secondary">{symbol}</span>
          </nav>
          <div className="mt-6 flex flex-wrap items-end justify-between gap-6">
            <div>
              <p className="eyebrow">{r} · overnight worked example</p>
              <h1 className="font-display mt-4 text-[48px] leading-none text-heading sm:text-[64px]">{symbol}</h1>
              <p className="mt-4 max-w-xl text-[15px] leading-relaxed text-text-secondary">
                Where this rToken sits against the real share&apos;s last close, what the agent did about it, and every fill.
              </p>
            </div>
            <div className="flex gap-2">
              <Link href={`/desk/${prev}`} className="inline-flex min-h-11 items-center rounded-full border border-border px-5 text-sm text-heading hover:bg-layer-2">
                ← {prev}
              </Link>
              <Link href={`/desk/${next}`} className="inline-flex min-h-11 items-center rounded-full border border-border px-5 text-sm text-heading hover:bg-layer-2">
                {next} →
              </Link>
            </div>
          </div>
          {error && (
            <div className="mt-6">
              <DataNotice message={error} onRetry={reload} />
            </div>
          )}
        </Container>
      </section>

      <Band label="Where it stands" first>
        {loading ? (
          <div aria-hidden className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="h-[112px] animate-pulse rounded-xl border border-border-subtle bg-layer-1" />
            ))}
          </div>
        ) : !s ? (
          <p className="text-sm text-text-tertiary">No recent snapshot for {symbol} in the live window.</p>
        ) : (
          <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
            <StatTile label={`${r} price`} value={fmtUsd(s.rtoken_last_price)} live />
            <StatTile label="Real close" value={s.real_close_price ? fmtUsd(s.real_close_price) : "n/a"} sub={s.hours_since_close !== undefined ? `${s.hours_since_close.toFixed(1)}h ago` : undefined} />
            <StatTile
              label="Spread"
              value={fmtSignedPct(s.spread, 3)}
              tone={s.spread > 0 ? "negative" : "positive"}
              sub={s.spread > 0 ? "rich vs fair value" : "cheap vs fair value"}
            />
            <StatTile
              label="Position"
              value={pos && Math.abs(pos.qty) > 1e-9 && pos.notionalUsd !== null ? fmtUsd(Math.abs(pos.notionalUsd)) : "Flat"}
              sub={
                pos?.notionalUsd && equity
                  ? `${pos.qty > 0 ? "Long" : "Short"}, ${fmtPct(Math.abs(pos.notionalUsd) / equity, 1)} of equity (cap 15%)`
                  : undefined
              }
            />
          </div>
        )}
      </Band>

      <Band label="Spread over time">
        <SectionHeader
          eyebrow="Spread"
          title={`${symbol} against its fair value, cycle by cycle.`}
          description="Only anchored-signal records are drawn. Above zero the rToken is rich (the sell side); below, cheap (the buy side)."
        />
        <div className="mt-10 rounded-xl border border-border-subtle bg-layer-1 p-5 sm:p-6">
          <SymbolSpreadChart events={events} symbol={symbol} />
        </div>
      </Band>

      <Band label="Decisions">
        <SectionHeader eyebrow="Decisions" title={`Every recent ${symbol} decision, with its reasoning.`} />
        <div className="mt-10">
          <DecisionFeed events={mine} />
        </div>
      </Band>

      <Band label="Fills">
        <SectionHeader
          eyebrow="Fills"
          title={`${symbol} paper fills.`}
          description={fills ? `${fills.total} fills in total; the latest ${fills.fills.length} shown.` : "Loading fills."}
        />
        <div className="mt-10 overflow-x-auto rounded-xl border border-border-subtle bg-layer-1">
          <table className="w-full min-w-[560px] text-left text-sm">
            <caption className="sr-only">Recent paper fills for {symbol}</caption>
            <thead>
              <tr className="border-b border-border-subtle">
                <th scope="col" className="micro-label px-4 py-3 font-normal">Time</th>
                <th scope="col" className="micro-label px-4 py-3 font-normal">Side</th>
                <th scope="col" className="micro-label px-4 py-3 text-right font-normal">Quantity</th>
                <th scope="col" className="micro-label px-4 py-3 text-right font-normal">Price</th>
                <th scope="col" className="micro-label px-4 py-3 text-right font-normal">Notional</th>
              </tr>
            </thead>
            <tbody>
              {(fills?.fills ?? []).map((f) => (
                <tr key={f.timestamp} className="border-b border-border-subtle last:border-0">
                  <td className="px-4 py-3 tabular-nums text-text-secondary">{fmtTime(f.timestamp)}</td>
                  <td className={`px-4 py-3 ${f.side === "buy" ? "text-mint" : "text-negative"}`}>{f.side}</td>
                  <td className="px-4 py-3 text-right tabular-nums text-text-secondary">{f.qty.toFixed(4)}</td>
                  <td className="px-4 py-3 text-right tabular-nums text-heading">{fmtUsd(f.price)}</td>
                  <td className="px-4 py-3 text-right tabular-nums text-text-secondary">{fmtUsd(f.notional_usd)}</td>
                </tr>
              ))}
              {fills && fills.fills.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-6 text-text-tertiary">No fills for {symbol} yet.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        {fills && fills.fills.length > 0 && (
          <p className="mt-3 text-xs text-text-tertiary">Earliest shown: {fmtDate(fills.fills[fills.fills.length - 1].timestamp)}</p>
        )}
      </Band>
    </>
  );
}
