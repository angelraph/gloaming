"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { fmtTime, fmtUsd } from "@/lib/format";
import { underlyingFromRtoken } from "@/lib/universe";

type Fill = { timestamp: string; symbol: string; side: string; price: number; notional_usd: number; rationale: string; check?: string };

const HOLD_MS = 7000;

function quote(r: string) {
  const t = r.replace(/^\[[^\]]+\]\s*/, "").trim();
  return t.length > 300 ? `${t.slice(0, 300).replace(/\s+\S*$/, "").replace(/[\s;:,.(-]+$/, "")}…` : t;
}

// Qwen's own written reasons for its most recent real trades, one at a time, each fading
// out as the next fades in. Hover or focus holds the current one. Only fills whose
// rationale came from Qwen are shown; nothing here is paraphrased beyond a length cut.
export default function ReasonRotator() {
  const [fills, setFills] = useState<Fill[]>([]);
  const [i, setI] = useState(0);
  const [paused, setPaused] = useState(false);

  useEffect(() => {
    fetch("/api/fills?limit=60&verified=1")
      .then((r) => (r.ok ? r.json() : { fills: [] }))
      .then((d) => setFills((d.fills ?? []).filter((f: Fill) => f.rationale?.startsWith("[Qwen")).slice(0, 8)))
      .catch(() => setFills([]));
  }, []);

  useEffect(() => {
    if (paused || fills.length < 2) return;
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return;
    const t = setInterval(() => setI((n) => (n + 1) % fills.length), HOLD_MS);
    return () => clearInterval(t);
  }, [paused, fills.length]);

  if (fills.length === 0) return <div aria-hidden className="h-[260px] animate-pulse rounded-2xl border border-border-subtle bg-layer-1" />;

  return (
    <div
      className="spotlight relative overflow-hidden rounded-2xl border border-border-subtle bg-layer-1 p-6 sm:p-10"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onFocus={() => setPaused(true)}
      onBlur={() => setPaused(false)}
    >
      <span aria-hidden className="font-display pointer-events-none absolute -top-6 left-4 select-none text-[160px] leading-none text-copper/15">
        “
      </span>
      <div className="relative grid min-h-[230px] sm:min-h-[200px]">
        {fills.map((f, n) => {
          const active = n === i;
          const u = underlyingFromRtoken(f.symbol);
          return (
            <figure
              key={f.timestamp + f.symbol}
              aria-hidden={!active}
              className={`reason-slide col-start-1 row-start-1 ${active ? "is-active" : ""}`}
            >
              <blockquote className="font-display text-[20px] leading-[1.45] text-heading sm:text-[24px]">{quote(f.rationale)}</blockquote>
              <figcaption className="mt-6 flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
                <span className={`text-[11px] font-semibold tracking-wide ${f.side === "buy" ? "text-mint" : "text-negative"}`}>
                  {f.side.toUpperCase()}
                </span>
                <Link href={`/desk/${u}`} tabIndex={active ? 0 : -1} className="font-medium text-heading underline-offset-4 hover:underline">
                  {u}
                </Link>
                <span className="tabular-nums text-text-secondary">
                  {fmtUsd(f.notional_usd)} at {f.price}
                </span>
                <span className="tabular-nums text-text-tertiary">{fmtTime(f.timestamp)}</span>
                {f.check === "matched" && <span className="text-xs text-mint">matched on Bitget</span>}
                <span className="text-xs text-text-tertiary">Qwen3.8-max</span>
              </figcaption>
            </figure>
          );
        })}
      </div>
      <div className="mt-8 flex items-center gap-2" role="tablist" aria-label="Choose a trade">
        {fills.map((f, n) => (
          <button
            key={n}
            type="button"
            role="tab"
            aria-selected={n === i}
            aria-label={`Trade ${n + 1} of ${fills.length}`}
            onClick={() => setI(n)}
            className="group flex h-11 items-center"
          >
            <span className={`block h-[3px] rounded-full transition-all duration-500 ${n === i ? "w-10 bg-copper" : "w-4 bg-border-strong group-hover:bg-text-tertiary"}`}>
              {n === i && !paused && <span key={i} className="reason-progress block h-full rounded-full bg-[#fff0cc]" />}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
