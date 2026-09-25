"use client";

import Link from "next/link";
import { useDeskData } from "@/lib/useDeskData";
import { fmtSignedUsd, fmtUsd } from "@/lib/format";
import { UNIVERSE } from "@/lib/universe";
import { Band, PageHeader } from "@/components/Container";
import SectionHeader from "@/components/SectionHeader";
import StatTile from "@/components/StatTile";
import RiskMeters from "@/components/RiskMeters";
import PositionsTable from "@/components/PositionsTable";
import FairValueChart from "@/components/FairValueChart";
import SignalContextCard from "@/components/SignalContextCard";
import OvernightTimeline from "@/components/OvernightTimeline";
import ChatPanel from "@/components/ChatPanel";
import DecisionStressTest from "@/components/DecisionStressTest";
import DataNotice from "@/components/DataNotice";

export default function DeskView() {
  const { portfolio, events, loading, error, lastUpdated, reload } = useDeskData();
  const equity = portfolio?.equityUsd ?? 0;
  const dailyPnl = portfolio?.dailyPnlUsd ?? 0;
  const hoursSinceClose = events.find((e) => e.snapshot?.hours_since_close !== undefined)?.snapshot?.hours_since_close;

  return (
    <>
      <PageHeader
        eyebrow="AI Trading Desk"
        title="The overnight desk."
        description="The book, the spread against each real close, and a plain-English account of what happened while the market was shut. Read-only: the desk recommends and explains, it never trades."
      >
        <p className="text-xs tabular-nums text-text-tertiary" aria-live="polite">
          {lastUpdated ? `Updated ${lastUpdated.toLocaleTimeString()}` : "Loading live data"}
        </p>
      </PageHeader>

      {error && (
        <div className="mx-auto max-w-[1216px] px-4 pb-6 sm:px-6 lg:px-10">
          <DataNotice message={error} onRetry={reload} />
        </div>
      )}

      <Band label="The book" first>
        <SectionHeader
          eyebrow="The book"
          title="What it holds, and how near it is to its limits."
          description="A paper book on real prices. The meters show, live, how close it sits to each cap the risk layer enforces."
        />
        {!portfolio?.configured && !loading ? (
          <p className="mt-10 text-sm text-warning">{portfolio?.message ?? "Portfolio data not available yet."}</p>
        ) : (
          <div className="mt-10 space-y-4">
            <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
              {loading ? (
                Array.from({ length: 4 }).map((_, i) => (
                  <div key={i} aria-hidden className="h-[112px] animate-pulse rounded-xl border border-border-subtle bg-layer-1" />
                ))
              ) : (
                <>
                  <StatTile label="Equity" value={fmtUsd(equity)} live />
                  <StatTile label="Cash" value={fmtUsd(portfolio?.cashUsd ?? 0)} />
                  <StatTile label="Today's P&L" value={fmtSignedUsd(dailyPnl)} tone={dailyPnl >= 0 ? "positive" : "negative"} />
                  <StatTile label="Total fills" value={String(portfolio?.totalFills ?? 0)} sub="paper fills, real prices" />
                </>
              )}
            </div>
            {!loading && <RiskMeters equityUsd={equity} dailyPnlUsd={dailyPnl} positions={portfolio?.positions ?? []} />}
            {!loading && portfolio && (
              <div className="pt-6">
                <h3 className="micro-label mb-4">Open positions</h3>
                <PositionsTable portfolio={portfolio} />
              </div>
            )}
          </div>
        )}
      </Band>

      <Band label="Signal">
        <SectionHeader
          eyebrow="Signal"
          title="Where each rToken sits against its real close."
          description="The spread is the rToken's move since the real share's last close, minus what the live proxies (index futures, crypto, FX) justify. It is normally a few tenths of a percent, so most nights are quiet."
        />
        <div className="mt-10 grid gap-4 lg:grid-cols-[minmax(0,8fr)_minmax(0,4fr)]">
          <div className="rounded-xl border border-border-subtle bg-layer-1 p-5 sm:p-6">
            <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
              <p className="eyebrow">Spread by symbol, latest cycle</p>
              {hoursSinceClose !== undefined && (
                <p className="text-xs tabular-nums text-text-tertiary">
                  real close was {hoursSinceClose.toFixed(1)}h before the latest cycle
                </p>
              )}
            </div>
            <div className="mt-5">
              <FairValueChart events={events} />
            </div>
            <div className="mt-4 flex flex-wrap gap-x-6 gap-y-2 text-xs text-text-tertiary">
              <span className="flex items-center gap-2">
                <span aria-hidden className="h-2 w-2 rounded-full bg-mint" /> rToken cheap vs fair value (buy side)
              </span>
              <span className="flex items-center gap-2">
                <span aria-hidden className="h-2 w-2 rounded-full bg-negative" /> rToken rich vs fair value (sell side)
              </span>
            </div>
            <nav aria-label="Symbol pages" className="mt-5 flex flex-wrap gap-2 border-t border-border-subtle pt-5">
              {UNIVERSE.map((u) => (
                <Link
                  key={u}
                  href={`/desk/${u}`}
                  className="inline-flex min-h-11 items-center rounded-full border border-border px-4 text-sm text-text-secondary transition-colors hover:border-border-strong hover:text-heading"
                >
                  {u}
                </Link>
              ))}
            </nav>
          </div>
          <SignalContextCard context={events.find((e) => e.snapshot)?.snapshot?.bitget_signal_context} />
        </div>
      </Band>

      <Band label="Overnight timeline and chat">
        <SectionHeader
          eyebrow="Overnight"
          title="What happened, and why."
          description="Trades, and each symbol's latest hold with the reason Qwen gave. Ask the desk anything about the real data below."
        />
        <div className="mt-10 grid gap-8 lg:grid-cols-[minmax(0,7fr)_minmax(0,5fr)] lg:gap-10">
          <div>
            <h3 className="micro-label mb-4">Overnight timeline</h3>
            <OvernightTimeline events={events} />
            <Link
              href="/agent#feed"
              className="mt-4 inline-flex min-h-11 items-center text-sm font-medium text-heading underline-offset-4 hover:underline"
            >
              See every decision on the Agent page →
            </Link>
          </div>
          <div className="flex flex-col">
            <h3 className="micro-label mb-4">Ask the desk</h3>
            <div className="min-h-[420px] flex-1 rounded-xl border border-border-subtle bg-layer-1 p-5 sm:p-6">
              <ChatPanel />
            </div>
          </div>
        </div>
      </Band>

      <Band label="Stress test">
        <SectionHeader
          eyebrow="Stress test"
          title="What if tonight goes wrong?"
          description="Replays each held symbol's worst night from real history against today's book. A hypothetical, never a forecast."
        />
        <div className="mt-10 rounded-xl border border-border-subtle bg-layer-1 p-5 sm:p-8">
          <DecisionStressTest />
        </div>
      </Band>
    </>
  );
}
