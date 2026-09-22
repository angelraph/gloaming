"use client";

import { useEffect, useState } from "react";
import StatTile from "@/components/StatTile";
import FairValueChart from "@/components/FairValueChart";
import OvernightTimeline from "@/components/OvernightTimeline";
import ChatPanel from "@/components/ChatPanel";
import DecisionStressTest from "@/components/DecisionStressTest";
import StatusPill from "@/components/StatusPill";
import SignalContextCard from "@/components/SignalContextCard";

type Portfolio = {
  configured: boolean;
  message?: string;
  cashUsd?: number;
  equityUsd?: number;
  dailyPnlUsd?: number;
  positions?: Array<{ symbol: string; qty: number; notionalUsd: number | null }>;
  totalFills?: number;
};

type TimelineResponse = {
  events: Array<{
    timestamp: string;
    underlying: string | null;
    decision_source?: string;
    snapshot?: {
      rtoken_symbol: string;
      rtoken_last_price: number;
      spread: number;
      fair_value_return_24h: number;
      rtoken_pcnt_24h: number;
      bitget_signal_context?: {
        fear_greed?: Record<string, unknown>;
        long_short?: Record<string, unknown>;
      } | null;
    };
    decision?: { side: string; notional_usd: number; rationale: string } | null;
    error?: string;
  }>;
  count: number;
};

function fmtUsd(n: number) {
  return n.toLocaleString(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 2 });
}

export default function Home() {
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [timeline, setTimeline] = useState<TimelineResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  useEffect(() => {
    async function load() {
      const [p, t] = await Promise.all([
        fetch("/api/portfolio").then((r) => r.json()),
        fetch("/api/timeline?days=3").then((r) => r.json()),
      ]);
      setPortfolio(p);
      setTimeline(t);
      setLoading(false);
      setLastUpdated(new Date());
    }
    load();
    const interval = setInterval(load, 30_000); // real data refreshes as the Agent trades
    return () => clearInterval(interval);
  }, []);

  return (
    <main className="mx-auto flex min-h-screen w-full min-w-0 max-w-6xl flex-col gap-8 px-4 py-6 sm:px-6 sm:py-10 lg:px-10">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-3">
          <div
            aria-hidden
            className="mt-0.5 h-8 w-8 shrink-0 rounded-full"
            style={{
              background: "radial-gradient(circle at 35% 30%, var(--brand), transparent 70%), " +
                "linear-gradient(135deg, var(--layer-2), var(--background))",
              boxShadow: "0 0 24px -6px var(--brand)",
            }}
          />
          <div className="min-w-0">
            <h1 className="text-2xl font-semibold tracking-tight">Gloaming Desk</h1>
            <p className="mt-1 max-w-md text-sm text-text-secondary">
              Overnight research desk for Bitget rTokens, while the real NYSE/Nasdaq is
              closed. Read-only - this page never places a trade.
            </p>
          </div>
        </div>
        <div className="flex flex-col items-end gap-1.5">
          <StatusPill />
          {lastUpdated && (
            <span className="text-xs tabular-nums text-text-tertiary">
              Updated {lastUpdated.toLocaleTimeString()}
            </span>
          )}
        </div>
      </header>

      {loading ? (
        <section className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-[74px] animate-pulse rounded-lg border border-border-subtle bg-layer-1" />
          ))}
        </section>
      ) : !portfolio?.configured ? (
        <div className="rounded-lg border border-warning/30 bg-warning-soft p-4 text-sm text-warning">
          {portfolio?.message ?? "Portfolio data not available yet."}
        </div>
      ) : (
        <section className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
          <StatTile label="Equity" value={fmtUsd(portfolio.equityUsd ?? 0)} />
          <StatTile label="Cash" value={fmtUsd(portfolio.cashUsd ?? 0)} />
          <StatTile
            label="Today's P&L"
            value={fmtUsd(portfolio.dailyPnlUsd ?? 0)}
            tone={(portfolio.dailyPnlUsd ?? 0) >= 0 ? "positive" : "negative"}
          />
          <StatTile label="Total fills" value={String(portfolio.totalFills ?? 0)} />
        </section>
      )}

      <SignalContextCard
        context={timeline?.events.find((e) => e.snapshot)?.snapshot?.bitget_signal_context}
      />

      <section>
        <h2 className="mb-3 text-sm font-medium text-text-secondary">
          Fair-value spread by symbol (latest cycle)
        </h2>
        <div className="rounded-lg border border-border-subtle bg-layer-1 p-3 sm:p-4">
          <FairValueChart events={timeline?.events ?? []} />
        </div>
      </section>

      <div className="grid grid-cols-1 gap-6 sm:gap-8 lg:grid-cols-2">
        <section>
          <h2 className="mb-3 text-sm font-medium text-text-secondary">Overnight timeline</h2>
          <OvernightTimeline events={timeline?.events ?? []} />
        </section>

        <section className="flex flex-col">
          <h2 className="mb-3 text-sm font-medium text-text-secondary">Ask the desk</h2>
          <div className="min-h-[360px] flex-1 rounded-lg border border-border-subtle bg-layer-1 p-3 sm:p-4">
            <ChatPanel />
          </div>
        </section>
      </div>

      <section>
        <h2 className="mb-3 text-sm font-medium text-text-secondary">Decision stress test</h2>
        <div className="rounded-lg border border-border-subtle bg-layer-1 p-3 sm:p-4">
          <DecisionStressTest />
        </div>
      </section>

      <footer className="mt-4 border-t border-border-subtle pt-4 text-xs text-text-tertiary">
        Gloaming trades the hours the market can&apos;t. Built for Bitget&apos;s AI &amp; Crypto Hackathon, Genesis Season 2.
      </footer>
    </main>
  );
}
