"use client";

import Link from "next/link";
import { Fragment, useEffect, useState } from "react";
import { useDeskData } from "@/lib/useDeskData";
import { fmtSignedPct, fmtSignedUsd, fmtUsd } from "@/lib/format";
import { Band, Container } from "@/components/Container";
import SectionHeader from "@/components/SectionHeader";
import LatestCycleGrid from "@/components/LatestCycleGrid";
import VerifyPanel from "@/components/VerifyPanel";
import DataNotice from "@/components/DataNotice";
import Reveal from "@/components/motion/Reveal";
import CountUp from "@/components/motion/CountUp";
import DuskDial from "@/components/home/DuskDial";
import TradeTape from "@/components/home/TradeTape";
import LoopFlow from "@/components/home/LoopFlow";

// Mirrors gloaming_agent/paper_ledger.py STARTING_EQUITY_USD.
const STARTING_EQUITY_USD = 100_000;
// The paper record's first fill (gloaming_agent/paper_ledger.json).
const RECORD_START = Date.UTC(2026, 8, 11);

const HEADLINE = "Gloaming trades the hours the market can't.";

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

function Pending() {
  return <span aria-hidden className="inline-block h-[34px] w-24 animate-pulse rounded-md bg-layer-2 align-bottom" />;
}

type VerificationSummary = { checked: number; matched: number; total_fills: number; pending: number; stale?: number };

function useVerificationSummary() {
  const [s, setS] = useState<VerificationSummary | null>(null);
  useEffect(() => {
    fetch("/api/fill-verification")
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => setS(d?.configured ? d.summary : null))
      .catch(() => setS(null));
  }, []);
  return s;
}

export default function HomeView() {
  const { portfolio, events, loading, error, reload } = useDeskData();
  const verification = useVerificationSummary();
  const equity = portfolio?.equityUsd ?? 0;
  const sinceStart = (equity - STARTING_EQUITY_USD) / STARTING_EQUITY_USD;
  const dailyPnl = portfolio?.dailyPnlUsd ?? 0;
  const openPositions = (portfolio?.positions ?? []).filter((p) => Math.abs(p.qty) > 1e-9).length;
  const newest = events[0]?.timestamp;
  const [days, setDays] = useState<number | null>(null);
  useEffect(() => {
    const t = setTimeout(() => setDays(Math.floor((Date.now() - RECORD_START) / 86_400_000)), 0);
    return () => clearTimeout(t);
  }, []);

  const words = HEADLINE.split(" ");

  return (
    <>
      <section className="relative overflow-hidden">
        {/* dusk: a low copper light on the horizon, breathing slowly */}
        <div aria-hidden className="dusk-sky pointer-events-none absolute inset-x-0 bottom-0 h-[85%]" />
        <div aria-hidden className="dusk-horizon pointer-events-none absolute inset-x-0 bottom-0 h-px" />

        <Container className="relative pb-14 pt-12 sm:pt-16 lg:pb-16 lg:pt-20">
          {error && (
            <div className="mb-8">
              <DataNotice message={error} onRetry={reload} />
            </div>
          )}
          <div className="grid items-center gap-12 lg:grid-cols-[minmax(0,6fr)_minmax(0,5fr)] lg:gap-14">
            <div>
              <p className="eyebrow fade-in">Overnight desk · Bitget rTokens</p>
              <h1
                aria-label={HEADLINE}
                className="font-display mt-6 text-[44px] leading-[1.04] text-heading sm:text-[64px] lg:text-[72px]"
              >
                {words.map((w, i) => (
                  <Fragment key={i}>
                    <span aria-hidden className="word-mask">
                      <span className="word-rise" style={{ "--word-delay": `${150 + i * 90}ms` } as React.CSSProperties}>
                        {w}
                      </span>
                    </span>
                    {i < words.length - 1 ? " " : ""}
                  </Fragment>
                ))}
              </h1>
              <p className="fade-in mt-6 max-w-xl text-[17px] leading-relaxed text-text-secondary" style={{ "--fade-delay": "800ms" } as React.CSSProperties}>
                An autonomous agent for Bitget&apos;s tokenized US stocks, working only while NYSE is closed. Every
                decision is explained, every trade is risk-gated, and every fill is checked against Bitget&apos;s own
                prices.
              </p>
              <div className="fade-in mt-9 flex flex-wrap gap-3" style={{ "--fade-delay": "1000ms" } as React.CSSProperties}>
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

            <div className="fade-in" style={{ "--fade-delay": "200ms" } as React.CSSProperties}>
              <DuskDial>
                <span className="micro-label">Live book</span>
                {loading ? (
                  <span aria-hidden className="mt-4 block h-12 w-40 animate-pulse rounded-lg bg-layer-2" />
                ) : !portfolio?.configured ? (
                  <span className="mt-4 text-sm text-warning">{portfolio?.message ?? "Portfolio data not available yet."}</span>
                ) : (
                  <>
                    <CountUp
                      value={equity}
                      format={(n) => fmtUsd(n)}
                      className="font-display mt-3 block text-[30px] leading-none tabular-nums text-heading sm:text-[40px]"
                    />
                    <span className="mt-2 text-xs text-text-secondary sm:text-sm">
                      paper equity ·{" "}
                      <span className={`tabular-nums ${sinceStart >= 0 ? "text-positive" : "text-negative"}`}>{fmtSignedPct(sinceStart)}</span>
                    </span>
                    <span className="mt-4 flex gap-5 border-t border-border-subtle pt-3 text-xs">
                      <span>
                        <span className="micro-label block">Today</span>
                        <span className={`mt-1.5 block tabular-nums ${dailyPnl >= 0 ? "text-positive" : "text-negative"}`}>{fmtSignedUsd(dailyPnl)}</span>
                      </span>
                      <span>
                        <span className="micro-label block">Open</span>
                        <span className="mt-1.5 block tabular-nums text-heading">{openPositions} positions</span>
                      </span>
                    </span>
                  </>
                )}
              </DuskDial>
            </div>
          </div>

          <ul className="mt-14 grid gap-x-8 gap-y-6 border-t border-border-subtle pt-8 sm:grid-cols-2 lg:mt-16 lg:grid-cols-4">
            {TRUST.map((t, i) => (
              <Reveal as="li" key={t.title} delay={i * 110} className="flex items-start gap-3.5">
                <svg
                  aria-hidden
                  viewBox="0 0 24 24"
                  className="mt-0.5 h-5 w-5 shrink-0 text-copper"
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
              </Reveal>
            ))}
          </ul>
        </Container>
      </section>

      <section aria-label="Recent trades" className="border-t border-border-subtle py-10 sm:py-12">
        <Container>
          <Reveal className="mb-6 flex flex-wrap items-baseline justify-between gap-3">
            <div>
              <p className="eyebrow">The tape</p>
              <h2 className="font-display mt-3 text-[28px] leading-tight text-heading sm:text-[32px]">Real fills, checked against Bitget.</h2>
            </div>
            <Link href="/performance" className="text-sm text-copper underline-offset-4 hover:underline">
              The full record →
            </Link>
          </Reveal>
        </Container>
        <Reveal delay={150}>
          <TradeTape />
        </Reveal>
        <Container>
          <Reveal delay={250} className="mt-10 grid grid-cols-2 gap-6 border-t border-border-subtle pt-8 lg:grid-cols-4">
            <div>
              <div className="micro-label">Fills on the ledger</div>
              <div className="font-display mt-3 text-[34px] leading-none tabular-nums text-heading">
                {loading ? <Pending /> : portfolio?.totalFills !== undefined ? <CountUp value={portfolio.totalFills} format={(n) => Math.round(n).toLocaleString()} /> : "n/a"}
              </div>
            </div>
            <div>
              <div className="micro-label">Matched Bitget&apos;s prices</div>
              <div className="font-display mt-3 text-[34px] leading-none tabular-nums text-mint">
                {verification ? <CountUp value={verification.matched} format={(n) => Math.round(n).toLocaleString()} /> : <Pending />}
              </div>
              {verification && (
                <div className="mt-2 text-xs text-text-tertiary">
                  of {verification.checked.toLocaleString()} checked
                  {verification.pending > 0 ? `, ${verification.pending} still to check` : ""}
                  {verification.stale ? `, ${verification.stale} at a stale price` : ""}
                </div>
              )}
            </div>
            <div>
              <div className="micro-label">Days unattended</div>
              <div className="font-display mt-3 text-[34px] leading-none tabular-nums text-heading">
                {days !== null ? <CountUp value={days} format={(n) => String(Math.round(n))} /> : <Pending />}
              </div>
              <div className="mt-2 text-xs text-text-tertiary">since the first fill on Sept 11; on GitHub Actions since Sept 13</div>
            </div>
            <div>
              <div className="micro-label">Total return</div>
              <div className={`font-display mt-3 text-[34px] leading-none tabular-nums ${sinceStart >= 0 ? "text-positive" : "text-negative"}`}>
                {loading ? <Pending /> : portfolio?.configured ? fmtSignedPct(sinceStart) : "n/a"}
              </div>
              <div className="mt-2 text-xs text-text-tertiary">paper, shown as it is</div>
            </div>
          </Reveal>
        </Container>
      </section>

      <Band label="One decision">
        <Reveal>
          <SectionHeader
            eyebrow="One decision, end to end"
            title="Observe, decide, gate, execute, record."
            description="Every fifteen minutes, for each of nine symbols. This is the newest real record, followed through the loop."
          />
        </Reveal>
        <Reveal delay={150} className="mt-10">
          <LoopFlow events={events} />
        </Reveal>
      </Band>

      <Band label="Two tracks">
        <Reveal>
          <SectionHeader
            eyebrow="One engine, two submissions"
            title="An agent that trades, and a desk that explains."
            description="Both are built on the same overnight signal. The agent acts inside hard limits; the desk only recommends and explains, and never places a trade."
          />
        </Reveal>
        <ul className="mt-10 grid gap-4 md:grid-cols-2">
          {TRACKS.map((t, i) => (
            <Reveal as="li" key={t.href} delay={i * 140}>
              <Link
                href={t.href}
                className="lift group block h-full rounded-xl border border-border-subtle bg-layer-1 p-6 hover:border-copper/50 hover:bg-layer-2 sm:p-8"
              >
                <span className="eyebrow">{t.eyebrow}</span>
                <span className="font-display mt-4 block text-[30px] leading-tight text-heading">{t.title}</span>
                <span className="mt-3 block text-[15px] leading-relaxed text-text-secondary">{t.body}</span>
                <span className="mt-6 inline-flex min-h-11 items-center gap-1.5 text-sm font-medium text-heading">
                  {t.cta}
                  <span aria-hidden className="transition-transform duration-300 group-hover:translate-x-1">→</span>
                </span>
              </Link>
            </Reveal>
          ))}
        </ul>
      </Band>

      <Band label="Latest cycle">
        <Reveal>
          <SectionHeader
            eyebrow="Latest cycle"
            title="Nine symbols, checked every fifteen minutes."
            description={
              newest
                ? `Most recent record: ${new Date(newest).toLocaleString()}. Most nights are quiet holds, and each one is explained.`
                : "Waiting for the first record."
            }
          />
        </Reveal>
        <Reveal delay={150} className="mt-10">
          <LatestCycleGrid events={events} />
        </Reveal>
      </Band>

      <Band label="Verify it yourself">
        <Reveal>
          <SectionHeader
            eyebrow="Verify it yourself"
            title="Nothing here is asked to be taken on trust."
            description="Every number on this desk comes from files anyone can open: the decision log, the ledger, the runs that produced them, and the check of every fill against Bitget."
          />
        </Reveal>
        <Reveal delay={150} className="mt-10">
          <VerifyPanel />
        </Reveal>
      </Band>
    </>
  );
}
