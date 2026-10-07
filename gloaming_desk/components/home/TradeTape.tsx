"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { fmtUsd } from "@/lib/format";
import { underlyingFromRtoken } from "@/lib/universe";

type Fill = {
  timestamp: string;
  symbol: string;
  side: string;
  qty: number;
  price: number;
  notional_usd: number;
  check: "matched" | "stale" | "mismatch" | "no_data" | "pending";
};

const CHECK_LABEL: Record<Fill["check"], { text: string; tone: string }> = {
  matched: { text: "matched on Bitget", tone: "text-mint" },
  stale: { text: "stale Bitget price", tone: "text-warning" },
  mismatch: { text: "no Bitget match", tone: "text-negative" },
  no_data: { text: "no Bitget candles", tone: "text-negative" },
  pending: { text: "check pending", tone: "text-text-tertiary" },
};

function when(iso: string) {
  return new Date(iso).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

function Item({ f }: { f: Fill }) {
  const u = underlyingFromRtoken(f.symbol);
  const label = CHECK_LABEL[f.check] ?? CHECK_LABEL.pending;
  return (
    <li className="flex shrink-0 items-center">
      <Link
        href={`/desk/${u}`}
        className="flex min-h-11 items-center gap-3 rounded-full border border-border-subtle bg-layer-1 px-4 py-2 transition-colors hover:border-border-strong hover:bg-layer-2"
      >
        <span className={`text-[11px] font-semibold tracking-wide ${f.side === "buy" ? "text-mint" : "text-negative"}`}>
          {f.side.toUpperCase()}
        </span>
        <span className="text-sm font-medium text-heading">{u}</span>
        <span className="text-sm tabular-nums text-text-secondary">
          {fmtUsd(f.notional_usd)} at {f.price}
        </span>
        <span className="text-xs tabular-nums text-text-tertiary">{when(f.timestamp)}</span>
        <span className={`text-xs ${label.tone}`}>{label.text}</span>
      </Link>
      <span aria-hidden className="mx-3 h-1 w-1 rounded-full bg-border-strong" />
    </li>
  );
}

// Real fills from the paper ledger, newest first, moving slowly across the page. Each one
// carries its check against Bitget's own 1-minute candles. Hover or focus pauses it; with
// reduced motion it becomes a plain horizontal scroller.
export default function TradeTape({ limit = 24 }: { limit?: number }) {
  const [fills, setFills] = useState<Fill[] | null>(null);
  const [total, setTotal] = useState(0);

  useEffect(() => {
    fetch(`/api/fills?limit=${limit}&verified=1`)
      .then((r) => (r.ok ? r.json() : { fills: [], total: 0 }))
      .then((d) => {
        setFills(d.fills ?? []);
        setTotal(d.total ?? 0);
      })
      .catch(() => setFills([]));
  }, [limit]);

  if (fills === null) return <div aria-hidden className="h-[60px] animate-pulse rounded-full bg-layer-1" />;
  if (fills.length === 0) return null;

  return (
    <div className="tape">
      <p className="sr-only">
        The {fills.length} most recent of {total} paper fills, each checked against Bitget&apos;s public candles.
      </p>
      <div className="tape-scroller tape-fade overflow-hidden">
        <div className="tape-track flex w-max" style={{ "--tape-duration": `${fills.length * 5}s` } as React.CSSProperties}>
          <ul className="flex">
            {fills.map((f) => (
              <Item key={`a-${f.timestamp}-${f.symbol}`} f={f} />
            ))}
          </ul>
          {/* the second copy makes the loop seamless; it is hidden from assistive tech and the tab order */}
          <ul className="flex" aria-hidden inert>
            {fills.map((f) => (
              <Item key={`b-${f.timestamp}-${f.symbol}`} f={f} />
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
