"use client";

import { useEffect, useMemo, useState } from "react";
import type { HistoryPoint } from "@/app/api/history/route";
import { UNIVERSE } from "@/lib/universe";
import { isNyseClosed } from "@/lib/marketHours";
import { fmtSignedPct, fmtUsd } from "@/lib/format";
import { useWidth } from "./useWidth";

type Candle = { t: number; o: number; h: number; l: number; c: number; v: number };

const H = 300;
const PAD = { top: 12, right: 64, bottom: 26, left: 8 };
const HOUR = 3_600_000;
const UP = "#3fe280";
const DOWN = "#e5786d";
const FAIR = "#fff0cc";

function hourLabel(t: number) {
  return new Date(t).toLocaleString(undefined, { weekday: "short", hour: "2-digit" });
}

// Bitget's own hourly candles for one rToken, with the agent's fair value drawn over them and
// the hours NYSE was closed shaded in copper: the gloaming, where the gap can open.
export default function MarketPanel({ history }: { history: HistoryPoint[] | null }) {
  const [u, setU] = useState<string>("NVDA");
  const [candles, setCandles] = useState<Candle[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [hover, setHover] = useState<number | null>(null);
  const { ref, width } = useWidth<HTMLDivElement>();

  useEffect(() => {
    let live = true;
    fetch(`/api/candles?u=${u}&limit=72`)
      .then((r) => r.json())
      .then((d) => {
        if (!live) return;
        setCandles(d.candles ?? []);
        setFailed(!d.candles?.length);
      })
      .catch(() => live && setFailed(true));
    return () => {
      live = false;
    };
  }, [u]);

  // the agent's fair value at each of its snapshots for this symbol (anchored signal only)
  const fair = useMemo(
    () =>
      (history ?? [])
        .filter((h) => h.u === u && h.f !== null)
        .map((h) => ({ t: Date.parse(h.t), v: h.f as number, spread: h.s })),
    [history, u],
  );

  const plotW = Math.max(0, width - PAD.left - PAD.right);
  const plotH = H - PAD.top - PAD.bottom;
  const data = candles ?? [];
  const t0 = data[0]?.t ?? 0;
  const t1 = (data[data.length - 1]?.t ?? 0) + HOUR;
  const fairIn = fair.filter((f) => f.t >= t0 && f.t <= t1);
  const lo = Math.min(...data.map((c) => c.l), ...fairIn.map((f) => f.v));
  const hi = Math.max(...data.map((c) => c.h), ...fairIn.map((f) => f.v));
  const padY = (hi - lo) * 0.08 || 1;
  const yMin = lo - padY;
  const yMax = hi + padY;
  const x = (t: number) => PAD.left + ((t - t0) / (t1 - t0 || 1)) * plotW;
  const y = (v: number) => PAD.top + (1 - (v - yMin) / (yMax - yMin || 1)) * plotH;
  const slot = data.length ? plotW / data.length : 0;
  const body = Math.max(2, slot * 0.62);

  // shaded runs of hours when NYSE was closed
  const closedRuns: Array<[number, number]> = [];
  for (const c of data) {
    if (!isNyseClosed(new Date(c.t + HOUR / 2))) continue;
    const last = closedRuns[closedRuns.length - 1];
    if (last && last[1] === c.t) last[1] = c.t + HOUR;
    else closedRuns.push([c.t, c.t + HOUR]);
  }

  const fairSegments: Array<typeof fairIn> = [];
  for (const f of fairIn) {
    const seg = fairSegments[fairSegments.length - 1];
    if (seg && f.t - seg[seg.length - 1].t < 1.5 * HOUR) seg.push(f);
    else fairSegments.push([f]);
  }

  const ticks = Array.from({ length: 5 }, (_, i) => yMin + ((yMax - yMin) * (i + 0.5)) / 5);
  const hovered = hover !== null ? data[hover] : null;
  const hoveredFair = hovered ? [...fair].reverse().find((f) => f.t <= hovered.t + HOUR) : null;
  const lastC = data[data.length - 1];
  const lastFair = fairIn[fairIn.length - 1];

  const onMove = (e: React.PointerEvent<SVGSVGElement>) => {
    const r = e.currentTarget.getBoundingClientRect();
    const px = e.clientX - r.left - PAD.left;
    const i = Math.floor(px / (slot || 1));
    setHover(i >= 0 && i < data.length ? i : null);
  };

  return (
    <div className="rounded-xl border border-border-subtle bg-layer-1 p-4 sm:p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-text-secondary">
          <span className="micro-label">R{u}USDT · 1h · Bitget</span>
          <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-sm" style={{ background: UP }} />up hour</span>
          <span className="flex items-center gap-1.5"><span className="h-2 w-2 rounded-sm" style={{ background: DOWN }} />down hour</span>
          <span className="flex items-center gap-1.5"><span className="h-0.5 w-4 rounded-full" style={{ background: FAIR }} />agent fair value</span>
          <span className="flex items-center gap-1.5"><span className="h-2.5 w-3 rounded-sm bg-copper/20" />NYSE closed</span>
        </div>
        <div className="flex flex-wrap gap-1" role="group" aria-label="Symbol">
          {UNIVERSE.map((s) => (
            <button
              key={s}
              type="button"
              aria-pressed={u === s}
              onClick={() => {
                setU(s);
                setCandles(null);
                setHover(null);
              }}
              className={`min-h-8 rounded-full px-2.5 text-xs font-medium transition-colors ${
                u === s ? "bg-copper/20 text-heading" : "text-text-tertiary hover:text-text-primary"
              }`}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      <div ref={ref} className="relative mt-3" style={{ height: H }}>
        {failed && <p className="pt-24 text-center text-sm text-text-tertiary">Bitget&apos;s candles could not be loaded just now.</p>}
        {!failed && (!candles || width === 0) && <div aria-hidden className="h-full animate-pulse rounded-lg bg-layer-2" />}
        {!failed && candles && width > 0 && data.length > 0 && (
          <svg
            width={width}
            height={H}
            className="block"
            role="img"
            aria-label={`R${u}USDT hourly candles for the last ${data.length} hours, closing at ${lastC.c}${lastFair ? `, against an agent fair value of ${lastFair.v.toFixed(2)}` : ""}.`}
            onPointerMove={onMove}
            onPointerLeave={() => setHover(null)}
          >
            {closedRuns.map(([a, b]) => (
              <rect key={a} x={x(a)} y={PAD.top} width={x(b) - x(a)} height={plotH} fill="#cc9166" opacity={0.07} />
            ))}
            {ticks.map((v) => (
              <g key={v}>
                <line x1={PAD.left} x2={PAD.left + plotW} y1={y(v)} y2={y(v)} stroke="#1c1d22" />
                <text x={PAD.left + plotW + 8} y={y(v) + 4} fontSize="11" fill="#777a88" className="tabular-nums">
                  {v.toFixed(2)}
                </text>
              </g>
            ))}
            {data.map((c, i) => {
              if (i % (slot * 12 < 80 ? 24 : 12) !== 0) return null;
              return (
                <text key={c.t} x={i === 0 ? PAD.left : x(c.t) + slot / 2} y={H - 6} fontSize="11" fill="#777a88" textAnchor={i === 0 ? "start" : "middle"}>
                  {hourLabel(c.t)}
                </text>
              );
            })}

            {data.map((c, i) => {
              const up = c.c >= c.o;
              const cx = PAD.left + i * slot + slot / 2;
              const top = y(Math.max(c.o, c.c));
              const bh = Math.max(1, Math.abs(y(c.o) - y(c.c)));
              return (
                <g key={c.t} className="candle" style={{ "--i": i } as React.CSSProperties} opacity={hover === null || hover === i ? 1 : 0.45}>
                  <line x1={cx} x2={cx} y1={y(c.h)} y2={y(c.l)} stroke={up ? UP : DOWN} strokeWidth="1" />
                  <rect x={cx - body / 2} y={top} width={body} height={bh} rx="1" fill={up ? UP : DOWN} />
                </g>
              );
            })}

            {/* one line per stretch of snapshots: it breaks wherever the agent stood aside */}
            {fairSegments.map((seg) => (
              <polyline
                key={seg[0].t}
                className="fair-line"
                points={seg.map((f) => `${x(f.t).toFixed(1)},${y(f.v).toFixed(1)}`).join(" ")}
                fill="none"
                stroke={FAIR}
                strokeWidth="2"
                strokeLinejoin="round"
                strokeLinecap="round"
              />
            ))}

            {lastC && (
              <g>
                <line x1={PAD.left} x2={PAD.left + plotW} y1={y(lastC.c)} y2={y(lastC.c)} stroke={lastC.c >= lastC.o ? UP : DOWN} strokeOpacity="0.35" />
                <rect x={PAD.left + plotW + 2} y={y(lastC.c) - 10} width={PAD.right - 4} height={20} rx="6" fill={lastC.c >= lastC.o ? UP : DOWN} />
                <text x={PAD.left + plotW + PAD.right / 2} y={y(lastC.c) + 4} fontSize="11" fontWeight="600" fill="#08080a" textAnchor="middle">
                  {lastC.c.toFixed(2)}
                </text>
              </g>
            )}

            {hovered && hover !== null && (
              <line x1={PAD.left + hover * slot + slot / 2} x2={PAD.left + hover * slot + slot / 2} y1={PAD.top} y2={PAD.top + plotH} stroke="#464853" />
            )}
          </svg>
        )}

        {hovered && hover !== null && (
          <div
            className="pointer-events-none absolute top-2 z-10 rounded-xl border border-border bg-layer-2 px-3 py-2 text-xs shadow-lg"
            style={{ left: Math.min(Math.max(PAD.left + hover * slot + 12, 0), Math.max(width - 190, 0)) }}
          >
            <div className="text-heading">{new Date(hovered.t).toLocaleString()}</div>
            <div className="mt-1 grid grid-cols-2 gap-x-3 tabular-nums text-text-secondary">
              <span>open {hovered.o}</span>
              <span>high {hovered.h}</span>
              <span>low {hovered.l}</span>
              <span>close {hovered.c}</span>
            </div>
            {hoveredFair && (
              <div className="mt-1 text-text-secondary">
                fair value {fmtUsd(hoveredFair.v)} · spread {fmtSignedPct(hoveredFair.spread)}
              </div>
            )}
            <div className="mt-1 text-text-tertiary">{isNyseClosed(new Date(hovered.t + HOUR / 2)) ? "NYSE closed" : "NYSE open"}</div>
          </div>
        )}
      </div>
    </div>
  );
}
