"use client";

import { useEffect, useRef, useState } from "react";
import type { DecisionRecord } from "@/lib/data";
import type { Portfolio } from "@/lib/useDeskData";
import type { PerformanceSummary } from "@/lib/performance";
import { isNyseClosed } from "@/lib/marketHours";
import BookPanel from "./BookPanel";
import MarketPanel from "./MarketPanel";
import SpreadMap from "./SpreadMap";
import RiskPanel from "./RiskPanel";
import type { HistoryPoint } from "@/app/api/history/route";

const VIEWS = [
  { key: "book", n: "01", label: "Book", blurb: "Equity, today and what the fills earned" },
  { key: "market", n: "02", label: "Market", blurb: "Bitget's candles against the agent's fair value" },
  { key: "spread", n: "03", label: "Spread map", blurb: "Every symbol's gap, hour by hour" },
  { key: "risk", n: "04", label: "Risk", blurb: "Positions against the hard caps" },
] as const;
type ViewKey = (typeof VIEWS)[number]["key"];
const DWELL_MS = 9000;

function utcClock(d: Date) {
  return d.toISOString().slice(11, 19);
}

// The night console: four live views of the same real data, cross-fading from one to the
// next on their own like a reel until a visitor touches it; then it stays where they put it.
export default function NightConsole({
  portfolio,
  events,
  verified,
}: {
  portfolio: Portfolio | null;
  events: DecisionRecord[];
  verified: { matched: number; checked: number } | null;
}) {
  const [view, setView] = useState<ViewKey>("book");
  const [auto, setAuto] = useState(true);
  const [now, setNow] = useState<Date | null>(null);
  const [perf, setPerf] = useState<PerformanceSummary | null>(null);
  const [history, setHistory] = useState<HistoryPoint[] | null>(null);
  const [inView, setInView] = useState(false);
  const root = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    fetch("/api/performance")
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => d?.configured && setPerf(d))
      .catch(() => undefined);
    fetch("/api/history")
      .then((r) => (r.ok ? r.json() : { points: [] }))
      .then((d) => setHistory(d.points ?? []))
      .catch(() => setHistory([]));
    const t = setTimeout(() => setNow(new Date()), 0);
    const i = setInterval(() => setNow(new Date()), 1000);
    return () => {
      clearTimeout(t);
      clearInterval(i);
    };
  }, []);

  // the reel only runs while the console is on screen
  useEffect(() => {
    const el = root.current;
    if (!el) return;
    const io = new IntersectionObserver((e) => setInView(e[0]?.isIntersecting ?? false), { threshold: 0.35 });
    io.observe(el);
    return () => io.disconnect();
  }, []);

  useEffect(() => {
    if (!auto || !inView) return;
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return;
    const t = setTimeout(() => {
      const i = VIEWS.findIndex((v) => v.key === view);
      setView(VIEWS[(i + 1) % VIEWS.length].key);
    }, DWELL_MS);
    return () => clearTimeout(t);
  }, [auto, inView, view]);

  const closed = now ? isNyseClosed(now) : true;
  const last = events[0]?.timestamp;
  const current = VIEWS.find((v) => v.key === view)!;

  return (
    <div
      ref={root}
      className="console-frame relative overflow-hidden rounded-2xl border border-border bg-[#0a0b0d]"
      onPointerDown={() => setAuto(false)}
      onKeyDown={() => setAuto(false)}
    >
      {/* header strip */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border-subtle px-4 py-3 sm:px-6">
        <div className="flex items-center gap-3">
          <span className="font-display text-[18px] text-heading">Night console</span>
          <span className={`flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-medium ${closed ? "border-mint/40 text-mint" : "border-border text-text-secondary"}`}>
            <span className={`h-1.5 w-1.5 rounded-full ${closed ? "console-live bg-mint" : "bg-text-tertiary"}`} />
            {closed ? "Agent active" : "NYSE open · standing aside"}
          </span>
        </div>
        <div className="flex items-center gap-4 text-xs tabular-nums text-text-tertiary">
          {last && <span>last record {new Date(last).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })}</span>}
          <span>{now ? `${utcClock(now)} UTC` : ""}</span>
        </div>
      </div>

      <div className="grid lg:grid-cols-[200px_minmax(0,1fr)]">
        {/* view rail */}
        <div role="tablist" aria-label="Console views" className="flex gap-1 overflow-x-auto border-b border-border-subtle p-2 lg:flex-col lg:border-b-0 lg:border-r lg:p-3">
          {VIEWS.map((v) => {
            const active = v.key === view;
            return (
              <button
                key={v.key}
                role="tab"
                type="button"
                id={`console-tab-${v.key}`}
                aria-selected={active}
                aria-controls={`console-panel-${v.key}`}
                onClick={() => {
                  setAuto(false);
                  setView(v.key);
                }}
                className={`relative flex min-h-11 shrink-0 items-center gap-3 overflow-hidden rounded-lg px-3 text-left text-sm transition-colors ${
                  active ? "bg-layer-2 text-heading" : "text-text-tertiary hover:bg-layer-1 hover:text-text-primary"
                }`}
              >
                <span className={`font-display text-[13px] ${active ? "text-copper" : ""}`}>{v.n}</span>
                <span>{v.label}</span>
                {active && auto && inView && <span key={view} aria-hidden className="console-dwell absolute bottom-0 left-0 h-[2px] bg-copper" />}
              </button>
            );
          })}
          <p className="hidden px-3 pt-4 text-xs leading-relaxed text-text-tertiary lg:block">
            {auto ? "Cycling through the views. Click anywhere to take the wheel." : "Paused on your choice."}
          </p>
        </div>

        {/* panels: stacked in one cell so each fades out as the next fades in */}
        <div className="min-w-0 p-3 sm:p-5">
          <div className="mb-4 flex items-baseline justify-between gap-3">
            <p key={view} className="console-caption text-sm text-text-secondary">
              <span className="text-heading">{current.label}.</span> {current.blurb}
            </p>
          </div>
          <div className="grid">
            {VIEWS.map((v) => (
              <div
                key={v.key}
                id={`console-panel-${v.key}`}
                role="tabpanel"
                aria-labelledby={`console-tab-${v.key}`}
                aria-hidden={v.key !== view}
                inert={v.key !== view}
                className={`console-panel col-start-1 row-start-1 min-w-0 ${v.key === view ? "is-active" : ""}`}
              >
                {v.key === "book" && <BookPanel perf={perf} dailyPnl={portfolio?.dailyPnlUsd ?? 0} verified={verified} />}
                {v.key === "market" && <MarketPanel history={history} />}
                {v.key === "spread" && <SpreadMap history={history} />}
                {v.key === "risk" && <RiskPanel portfolio={portfolio} />}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
