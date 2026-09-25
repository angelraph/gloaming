"use client";

import { useEffect, useState } from "react";
import SiteNav, { NAV_SECTIONS } from "@/components/SiteNav";
import SectionHeader from "@/components/SectionHeader";
import StatTile from "@/components/StatTile";
import RiskMeters from "@/components/RiskMeters";
import FairValueChart from "@/components/FairValueChart";
import SignalContextCard from "@/components/SignalContextCard";
import OvernightTimeline from "@/components/OvernightTimeline";
import ChatPanel from "@/components/ChatPanel";
import DecisionStressTest from "@/components/DecisionStressTest";
import Faq from "@/components/Faq";
import Roadmap from "@/components/Roadmap";

// Mirrors gloaming_agent/paper_ledger.py STARTING_EQUITY_USD.
const STARTING_EQUITY_USD = 100_000;

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
      signal_spec?: string;
      real_close_price?: number;
      hours_since_close?: number;
      rtoken_return_since_close?: number;
      fair_value_return_since_close?: number;
      fair_value_return_24h?: number;
      rtoken_pcnt_24h?: number;
      bitget_signal_context?: {
        fear_greed?: Record<string, unknown>;
        long_short?: Record<string, unknown>;
        news?: Array<{ feed?: string; error?: string; items?: unknown[] }>;
        macro?: { yield_curve?: Record<string, unknown> } & Record<string, unknown>;
      } | null;
    };
    decision?: { side: string; notional_usd: number; rationale: string } | null;
    hold_rationale?: string;
    error?: string;
  }>;
  count: number;
};

function fmtUsd(n: number) {
  return n.toLocaleString(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 2 });
}

function fmtSignedUsd(n: number) {
  return `${n >= 0 ? "+" : "-"}${fmtUsd(Math.abs(n))}`;
}

function fmtSignedPct(n: number) {
  return `${n >= 0 ? "+" : "-"}${(Math.abs(n) * 100).toFixed(2)}%`;
}

// One rhythm for every content band: a hairline, generous vertical space, the same gutter.
function Section({ id, children }: { id: string; children: React.ReactNode }) {
  return (
    <section id={id} className="border-t border-border-subtle">
      <div className="mx-auto w-full max-w-[1216px] px-4 py-16 sm:px-6 sm:py-20 lg:px-10 lg:py-24">{children}</div>
    </section>
  );
}

const TRUST = [
  {
    title: "Paper trading, live prices",
    sub: "Real rToken prices, simulated fills",
    icon: <path d="M3 17l5-5 4 4 8-9M15 7h5v5" />,
  },
  {
    title: "Qwen3.8-max decides",
    sub: "It sees its own book every cycle",
    icon: <path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9L12 3z" />,
  },
  {
    title: "A non-LLM risk layer",
    sub: "Caps, breakers, no leverage",
    icon: <path d="M12 3l8 3v6c0 4.5-3.2 8-8 9-4.8-1-8-4.5-8-9V6l8-3zM9 12l2 2 4-4" />,
  },
  {
    title: "Unattended, every 15 minutes",
    sub: "Only while NYSE is closed",
    icon: <path d="M12 7v5l3 2M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />,
  },
];

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

  const events = timeline?.events ?? [];
  const equity = portfolio?.equityUsd ?? 0;
  const sinceStart = (equity - STARTING_EQUITY_USD) / STARTING_EQUITY_USD;
  const dailyPnl = portfolio?.dailyPnlUsd ?? 0;
  const openPositions = (portfolio?.positions ?? []).length;
  const hoursSinceClose = events.find((e) => e.snapshot?.hours_since_close !== undefined)?.snapshot?.hours_since_close;

  return (
    <>
      <SiteNav />

      <main className="flex-1">
        {/* HERO: a serif statement on the left, the live book on the right */}
        <section id="desk">
          <div className="mx-auto w-full max-w-[1216px] px-4 pb-16 pt-14 sm:px-6 sm:pt-20 lg:px-10 lg:pb-20 lg:pt-24">
            <div className="grid items-center gap-12 lg:grid-cols-[minmax(0,6fr)_minmax(0,5fr)] lg:gap-16">
              <div>
                <p className="eyebrow">Overnight desk · Bitget rTokens</p>
                <h1 className="font-display mt-6 text-[44px] leading-[1.02] text-heading sm:text-[64px] lg:text-[72px]">
                  Gloaming trades the hours the market can&apos;t.
                </h1>
                <p className="mt-6 max-w-xl text-[17px] leading-relaxed text-text-secondary">
                  An autonomous agent for Bitget&apos;s tokenized US stocks while NYSE is closed. Every
                  decision is explained, every trade is risk-gated, and this desk is read-only.
                </p>
                <div className="mt-9 flex flex-wrap gap-3">
                  <a
                    href="#activity"
                    className="rounded-full bg-heading px-6 py-3 text-sm font-medium tracking-wide text-background transition-colors hover:bg-text-primary"
                  >
                    See tonight&apos;s decisions
                  </a>
                  <a
                    href="#faq"
                    className="rounded-full border border-heading/70 px-6 py-3 text-sm font-medium tracking-wide text-heading transition-colors hover:bg-layer-2"
                  >
                    How it works
                  </a>
                </div>
              </div>

              {/* the one card allowed a mint hairline: live, money-bearing numbers */}
              <div className="rounded-xl border border-mint/70 bg-layer-1 p-6 sm:p-8">
                <div className="flex items-center justify-between gap-3">
                  <span className="micro-label">Live book</span>
                  {lastUpdated && (
                    <span className="text-xs tabular-nums text-text-tertiary">Updated {lastUpdated.toLocaleTimeString()}</span>
                  )}
                </div>
                {loading ? (
                  <div className="mt-6 h-[104px] animate-pulse rounded-lg bg-layer-2" />
                ) : !portfolio?.configured ? (
                  <p className="mt-6 text-sm text-warning">{portfolio?.message ?? "Portfolio data not available yet."}</p>
                ) : (
                  <>
                    <div className="mt-6 font-display text-[52px] leading-none tabular-nums text-heading sm:text-[64px]">
                      {fmtUsd(equity)}
                    </div>
                    <p className="mt-3 text-sm text-text-secondary">
                      paper equity ·{" "}
                      <span className={`tabular-nums ${sinceStart >= 0 ? "text-positive" : "text-negative"}`}>
                        {fmtSignedPct(sinceStart)}
                      </span>{" "}
                      since start
                    </p>
                    <div className="mt-7 grid grid-cols-2 gap-4 border-t border-border-subtle pt-6">
                      <div>
                        <div className="micro-label">Today</div>
                        <div className={`mt-2 text-lg tabular-nums ${dailyPnl >= 0 ? "text-positive" : "text-negative"}`}>
                          {fmtSignedUsd(dailyPnl)}
                        </div>
                      </div>
                      <div>
                        <div className="micro-label">Open positions</div>
                        <div className="mt-2 text-lg tabular-nums text-heading">{openPositions}</div>
                      </div>
                    </div>
                  </>
                )}
              </div>
            </div>

            {/* trust by what is actually true, not by borrowed logos */}
            <ul className="mt-16 grid gap-x-8 gap-y-6 border-t border-border-subtle pt-8 sm:grid-cols-2 lg:mt-20 lg:grid-cols-4">
              {TRUST.map((t) => (
                <li key={t.title} className="flex items-start gap-3.5">
                  <svg
                    aria-hidden
                    viewBox="0 0 24 24"
                    className="mt-0.5 h-5 w-5 shrink-0 text-text-secondary"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    {t.icon}
                  </svg>
                  <div>
                    <p className="text-sm font-medium text-heading">{t.title}</p>
                    <p className="mt-1 text-xs text-text-tertiary">{t.sub}</p>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </section>

        {/* THE BOOK: numbers, then the caps they live under */}
        <Section id="book">
          <SectionHeader
            eyebrow="The book"
            title="What it holds, and how close it is to its limits."
            description="A paper book on real prices. The meters show, live, how near it sits to each cap the risk layer enforces."
          />
          {!portfolio?.configured && !loading ? null : (
            <div className="mt-10 space-y-4">
              <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
                {loading ? (
                  Array.from({ length: 4 }).map((_, i) => (
                    <div key={i} className="h-[112px] animate-pulse rounded-xl border border-border-subtle bg-layer-1" />
                  ))
                ) : (
                  <>
                    <StatTile label="Equity" value={fmtUsd(equity)} live />
                    <StatTile label="Cash" value={fmtUsd(portfolio?.cashUsd ?? 0)} />
                    <StatTile
                      label="Today's P&L"
                      value={fmtSignedUsd(dailyPnl)}
                      tone={dailyPnl >= 0 ? "positive" : "negative"}
                    />
                    <StatTile label="Total fills" value={String(portfolio?.totalFills ?? 0)} sub="paper fills, real prices" />
                  </>
                )}
              </div>
              {!loading && (
                <RiskMeters equityUsd={equity} dailyPnlUsd={dailyPnl} positions={portfolio?.positions ?? []} />
              )}
            </div>
          )}
        </Section>

        {/* THE SIGNAL */}
        <Section id="signal">
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
            </div>
            <SignalContextCard context={events.find((e) => e.snapshot)?.snapshot?.bitget_signal_context} />
          </div>
        </Section>

        {/* ACTIVITY */}
        <Section id="activity">
          <SectionHeader
            eyebrow="Activity"
            title="Every decision, with its reasoning."
            description="Trades, and each symbol's latest hold with the reason Qwen gave. A quiet night is still explained."
          />
          <div className="mt-10 grid gap-8 lg:grid-cols-[minmax(0,7fr)_minmax(0,5fr)] lg:gap-10">
            <div>
              <p className="micro-label mb-4">Overnight timeline</p>
              <OvernightTimeline events={events} />
            </div>
            <div className="flex flex-col">
              <p className="micro-label mb-4">Ask the desk</p>
              <div className="min-h-[420px] flex-1 rounded-xl border border-border-subtle bg-layer-1 p-5 sm:p-6">
                <ChatPanel />
              </div>
            </div>
          </div>
        </Section>

        {/* STRESS TEST */}
        <Section id="stress">
          <SectionHeader
            eyebrow="Stress test"
            title="What if tonight goes wrong?"
            description="Replays each held symbol's worst night from real history against today's book. A hypothetical, never a forecast."
          />
          <div className="mt-10 rounded-xl border border-border-subtle bg-layer-1 p-5 sm:p-8">
            <DecisionStressTest />
          </div>
        </Section>

        <Section id="faq">
          <Faq />
        </Section>

        <Section id="roadmap">
          <Roadmap />
        </Section>
      </main>

      <footer className="border-t border-border-subtle">
        <div className="mx-auto grid w-full max-w-[1216px] gap-10 px-4 py-14 sm:px-6 lg:grid-cols-[minmax(0,5fr)_minmax(0,3fr)_minmax(0,4fr)] lg:px-10">
          <div>
            <p className="font-display text-[26px] leading-none text-heading">Gloaming</p>
            <p className="mt-4 max-w-sm text-sm leading-relaxed text-text-secondary">
              Gloaming trades the hours the market can&apos;t. An autonomous, risk-gated overnight desk for
              Bitget rTokens.
            </p>
          </div>
          <nav aria-label="Footer sections">
            <p className="micro-label">Sections</p>
            <ul className="mt-4 space-y-2.5 text-sm">
              {NAV_SECTIONS.map(({ id, label }) => (
                <li key={id}>
                  <a href={`#${id}`} className="text-text-secondary transition-colors hover:text-heading">
                    {label}
                  </a>
                </li>
              ))}
            </ul>
          </nav>
          <div>
            <p className="micro-label">Good to know</p>
            <ul className="mt-4 space-y-2.5 text-sm text-text-secondary">
              <li>Paper trading only. Nothing here is financial advice.</li>
              <li>This desk is read-only and never places a trade.</li>
              <li>Built for Bitget&apos;s AI &amp; Crypto Hackathon, Genesis Season 2.</li>
            </ul>
          </div>
        </div>
      </footer>
    </>
  );
}
