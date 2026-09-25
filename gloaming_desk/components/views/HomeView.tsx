"use client";

import Link from "next/link";
import { useDeskData } from "@/lib/useDeskData";
import { fmtSignedPct, fmtSignedUsd, fmtUsd } from "@/lib/format";
import { Band, Container } from "@/components/Container";
import SectionHeader from "@/components/SectionHeader";
import LatestCycleGrid from "@/components/LatestCycleGrid";
import VerifyPanel from "@/components/VerifyPanel";
import DataNotice from "@/components/DataNotice";

// Mirrors gloaming_agent/paper_ledger.py STARTING_EQUITY_USD.
const STARTING_EQUITY_USD = 100_000;

const TRUST = [
  { title: "Paper trading, live prices", sub: "Real rToken prices, simulated fills", icon: <path d="M3 17l5-5 4 4 8-9M15 7h5v5" /> },
  { title: "Qwen3.8-max decides", sub: "It sees its own book every cycle", icon: <path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9L12 3z" /> },
  { title: "A non-LLM risk layer", sub: "Caps, breakers, no leverage", icon: <path d="M12 3l8 3v6c0 4.5-3.2 8-8 9-4.8-1-8-4.5-8-9V6l8-3zM9 12l2 2 4-4" /> },
  { title: "Unattended, every 15 minutes", sub: "Only while NYSE is closed", icon: <path d="M12 7v5l3 2M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /> },
];

const TRACKS = [
  {
    href: "/agent",
    eyebrow: "Agentic Trading",
    title: "Gloaming Agent",
    body: "The autonomous side: Qwen decides, a deterministic risk layer gates every trade, and each decision has a reasoning trail you can open and inspect.",
    cta: "Watch the agent",
  },
  {
    href: "/desk",
    eyebrow: "AI Trading Desk",
    title: "Gloaming Desk",
    body: "The human side: the book, the spread against fair value, an overnight timeline, a chat over the real data, and a stress test. Read-only by design.",
    cta: "Open the desk",
  },
];

export default function HomeView() {
  const { portfolio, events, loading, error, lastUpdated, reload } = useDeskData();
  const equity = portfolio?.equityUsd ?? 0;
  const sinceStart = (equity - STARTING_EQUITY_USD) / STARTING_EQUITY_USD;
  const dailyPnl = portfolio?.dailyPnlUsd ?? 0;
  const openPositions = (portfolio?.positions ?? []).filter((p) => Math.abs(p.qty) > 1e-9).length;
  const newest = events[0]?.timestamp;

  return (
    <>
      <section>
        <Container className="pb-14 pt-14 sm:pt-20 lg:pb-16 lg:pt-24">
          {error && (
            <div className="mb-8">
              <DataNotice message={error} onRetry={reload} />
            </div>
          )}
          <div className="grid items-center gap-12 lg:grid-cols-[minmax(0,6fr)_minmax(0,5fr)] lg:gap-16">
            <div>
              <p className="eyebrow">Overnight desk · Bitget rTokens</p>
              <h1 className="font-display mt-6 text-[44px] leading-[1.02] text-heading sm:text-[64px] lg:text-[72px]">
                Gloaming trades the hours the market can&apos;t.
              </h1>
              <p className="mt-6 max-w-xl text-[17px] leading-relaxed text-text-secondary">
                An autonomous agent for Bitget&apos;s tokenized US stocks while NYSE is closed. Every decision is
                explained, every trade is risk-gated, and this desk is read-only.
              </p>
              <div className="mt-9 flex flex-wrap gap-3">
                <Link
                  href="/desk"
                  className="inline-flex min-h-11 items-center rounded-full bg-heading px-6 text-sm font-medium tracking-wide text-background transition-colors hover:bg-text-primary"
                >
                  Open the desk
                </Link>
                <Link
                  href="/method"
                  className="inline-flex min-h-11 items-center rounded-full border border-heading/70 px-6 text-sm font-medium tracking-wide text-heading transition-colors hover:bg-layer-2"
                >
                  How it works
                </Link>
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
                <div className="mt-6 h-[104px] animate-pulse rounded-lg bg-layer-2" aria-hidden />
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
        </Container>
      </section>

      <Band label="Two tracks">
        <SectionHeader
          eyebrow="One engine, two submissions"
          title="An agent that trades, and a desk that explains."
          description="Both are built on the same overnight signal. The agent acts inside hard limits; the desk only recommends and explains, and never places a trade."
        />
        <ul className="mt-10 grid gap-4 md:grid-cols-2">
          {TRACKS.map((t) => (
            <li key={t.href}>
              <Link
                href={t.href}
                className="block h-full rounded-xl border border-border-subtle bg-layer-1 p-6 transition-colors hover:border-border-strong hover:bg-layer-2 sm:p-8"
              >
                <span className="eyebrow">{t.eyebrow}</span>
                <span className="font-display mt-4 block text-[30px] leading-tight text-heading">{t.title}</span>
                <span className="mt-3 block text-[15px] leading-relaxed text-text-secondary">{t.body}</span>
                <span className="mt-6 inline-flex min-h-11 items-center text-sm font-medium text-heading">{t.cta} →</span>
              </Link>
            </li>
          ))}
        </ul>
      </Band>

      <Band label="Latest cycle">
        <SectionHeader
          eyebrow="Latest cycle"
          title="Nine symbols, checked every fifteen minutes."
          description={
            newest
              ? `Most recent record: ${new Date(newest).toLocaleString()}. Most nights are quiet holds, and each one is explained.`
              : "Waiting for the first record."
          }
        />
        <div className="mt-10">
          <LatestCycleGrid events={events} />
        </div>
      </Band>

      <Band label="Verify it yourself">
        <SectionHeader
          eyebrow="Verify it yourself"
          title="Nothing here is asked to be taken on trust."
          description="Every number on this desk comes from files anyone can open: the decision log, the ledger and the runs that produced them."
        />
        <div className="mt-10">
          <VerifyPanel />
        </div>
      </Band>
    </>
  );
}
