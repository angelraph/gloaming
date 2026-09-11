"use client";

import { useEffect, useState } from "react";
import StatTile from "@/components/StatTile";
import FairValueChart from "@/components/FairValueChart";
import OvernightTimeline from "@/components/OvernightTimeline";
import ChatPanel from "@/components/ChatPanel";
import DecisionStressTest from "@/components/DecisionStressTest";
import StatusPill from "@/components/StatusPill";

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
    <main className="mx-auto flex min-h-screen max-w-6xl flex-col gap-8 p-6 sm:p-10">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Gloaming Desk</h1>
          <p className="mt-1 text-sm text-neutral-400">
            Overnight research desk for Bitget rTokens, while the real NYSE/Nasdaq is
            closed. Read-only - this page never places a trade.
          </p>
        </div>
        <div className="flex flex-col items-end gap-1.5">
          <StatusPill />
          {lastUpdated && (
            <span className="text-xs text-neutral-600">
              Updated {lastUpdated.toLocaleTimeString()}
            </span>
          )}
        </div>
      </header>

      {loading ? (
        <p className="text-sm text-neutral-500">Loading real portfolio and decision data...</p>
      ) : !portfolio?.configured ? (
        <div className="rounded-lg border border-amber-900/50 bg-amber-950/30 p-4 text-sm text-amber-300">
          {portfolio?.message ?? "Portfolio data not available yet."}
        </div>
      ) : (
        <section className="grid grid-cols-2 gap-4 sm:grid-cols-4">
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

      <section>
        <h2 className="mb-3 text-sm font-medium text-neutral-300">
          Fair-value spread by symbol (latest cycle)
        </h2>
        <div className="rounded-lg border border-neutral-800 bg-neutral-900/30 p-4">
          <FairValueChart events={timeline?.events ?? []} />
        </div>
      </section>

      <div className="grid grid-cols-1 gap-8 lg:grid-cols-2">
        <section>
          <h2 className="mb-3 text-sm font-medium text-neutral-300">Overnight timeline</h2>
          <OvernightTimeline events={timeline?.events ?? []} />
        </section>

        <section className="flex flex-col">
          <h2 className="mb-3 text-sm font-medium text-neutral-300">Ask the desk</h2>
          <div className="min-h-[400px] flex-1 rounded-lg border border-neutral-800 bg-neutral-900/30 p-4">
            <ChatPanel />
          </div>
        </section>
      </div>

      <section>
        <h2 className="mb-3 text-sm font-medium text-neutral-300">Decision stress test</h2>
        <div className="rounded-lg border border-neutral-800 bg-neutral-900/30 p-4">
          <DecisionStressTest />
        </div>
      </section>
    </main>
  );
}
