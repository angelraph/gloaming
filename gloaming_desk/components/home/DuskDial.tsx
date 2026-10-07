"use client";

import { useEffect, useRef, useState } from "react";
import { isNyseClosed } from "@/lib/marketHours";

// A 24-hour dial in New York time: noon at the top, midnight at the bottom. The thin grey
// arc is the regular NYSE session (09:30 to 16:00 on weekdays); the copper arc is the
// gloaming, every hour the real market is shut and the agent is allowed to act. The hand is
// now. The center holds whatever the page passes in (the live book).

const SIZE = 480; // room outside the ring for the labels and the outer orbit
const C = SIZE / 2;
const R = 190;
const SESSION_OPEN = 9 * 60 + 30;
const SESSION_CLOSE = 16 * 60;
const CYCLE_MINUTES = 15;

function polar(minutes: number, r: number) {
  const a = (minutes / 1440) * 2 * Math.PI + Math.PI; // midnight at the bottom
  // rounded, so the server's and the browser's trig agree and hydration matches
  return { x: Math.round((C + r * Math.sin(a)) * 100) / 100, y: Math.round((C - r * Math.cos(a)) * 100) / 100 };
}

function arc(fromMin: number, toMin: number, r: number) {
  const a = polar(fromMin, r);
  const b = polar(toMin, r);
  const span = (((toMin - fromMin) % 1440) + 1440) % 1440;
  return `M ${a.x} ${a.y} A ${r} ${r} 0 ${span > 720 ? 1 : 0} 1 ${b.x} ${b.y}`;
}

function arcLength(fromMin: number, toMin: number, r: number) {
  const span = (((toMin - fromMin) % 1440) + 1440) % 1440;
  return (span / 1440) * 2 * Math.PI * r;
}

function nyNow(now: Date) {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/New_York",
    weekday: "short",
    hour: "numeric",
    minute: "numeric",
    second: "numeric",
    hourCycle: "h23",
  }).formatToParts(now);
  const get = (t: string) => parts.find((p) => p.type === t)?.value ?? "0";
  const weekday = get("weekday");
  return {
    minutes: (Number(get("hour")) % 24) * 60 + Number(get("minute")) + Number(get("second")) / 60,
    weekend: weekday === "Sat" || weekday === "Sun",
    label: `${String(Number(get("hour")) % 24).padStart(2, "0")}:${get("minute").padStart(2, "0")}`,
  };
}

// Cycles are dispatched on the quarter hour (UTC), so this is the next scheduled start.
function nextCycle(now: Date) {
  const ms = CYCLE_MINUTES * 60_000;
  const left = ms - (now.getTime() % ms);
  const m = Math.floor(left / 60_000);
  const s = Math.floor((left % 60_000) / 1000);
  return `${m}:${String(s).padStart(2, "0")}`;
}

export default function DuskDial({ children }: { children?: React.ReactNode }) {
  const [now, setNow] = useState<Date | null>(null);
  const [still, setStill] = useState(true); // no comet until we know motion is welcome
  const tiltRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    // first tick right after mount, so server and client render the same empty dial
    const t = setTimeout(() => {
      setNow(new Date());
      setStill(window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false);
    }, 0);
    const i = setInterval(() => setNow(new Date()), 1000);
    return () => {
      clearTimeout(t);
      clearInterval(i);
    };
  }, []);

  const ny = now ? nyNow(now) : null;
  const closed = now ? isNyseClosed(now) : true;
  const hand = ny ? polar(ny.minutes, R) : null;
  const handInner = ny ? polar(ny.minutes, R - 26) : null;
  const sessionLen = arcLength(SESSION_OPEN, SESSION_CLOSE, R);
  const gloamingLen = arcLength(SESSION_CLOSE, SESSION_OPEN, R);
  const open = polar(SESSION_OPEN, R + 22);
  const close = polar(SESSION_CLOSE, R + 22);

  const gloamPath = !ny ? "" : ny.weekend ? `M ${C} ${C + R} a ${R} ${R} 0 1 1 0.01 0` : arc(SESSION_CLOSE, SESSION_OPEN, R);

  // the dial leans a few degrees toward the pointer
  const onMove = (e: React.PointerEvent) => {
    if (still || !tiltRef.current) return;
    const r = tiltRef.current.getBoundingClientRect();
    const x = (e.clientX - r.left) / r.width - 0.5;
    const y = (e.clientY - r.top) / r.height - 0.5;
    tiltRef.current.style.transform = `perspective(900px) rotateX(${(-y * 10).toFixed(2)}deg) rotateY(${(x * 10).toFixed(2)}deg)`;
  };
  const onLeave = () => {
    if (tiltRef.current) tiltRef.current.style.transform = "";
  };

  const status = !ny
    ? ""
    : ny.weekend
      ? "Weekend. The real market is shut all day"
      : closed
        ? "NYSE closed. The agent is active"
        : "NYSE open. The agent waits for the close";

  return (
    <figure className="relative mx-auto w-full max-w-[460px]" onPointerMove={onMove} onPointerLeave={onLeave}>
      <div ref={tiltRef} className="dial-tilt relative">
      <svg viewBox={`0 0 ${SIZE} ${SIZE}`} className="w-full" role="img" aria-label={`24-hour New York clock. ${status}.`}>
        <defs>
          <linearGradient id="gloam" x1="0" y1="1" x2="1" y2="0">
            <stop offset="0%" stopColor="#ae9357" />
            <stop offset="45%" stopColor="#fff0cc" />
            <stop offset="100%" stopColor="#cc9166" />
          </linearGradient>
          <filter id="glow" x="-200%" y="-200%" width="500%" height="500%">
            <feGaussianBlur stdDeviation="3" result="b" />
            <feMerge>
              <feMergeNode in="b" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <filter id="soft" x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="7" />
          </filter>
        </defs>

        {/* outer orbit: a slow decorative ring with three bright points */}
        <g className="fade-in" style={{ "--fade-delay": "900ms" } as React.CSSProperties}>
        <g className="dial-orbit">
          <circle cx={C} cy={C} r={R + 38} fill="none" stroke="#3a3c45" strokeWidth="1" strokeDasharray="1.5 6" />
          {[0, 120, 240].map((deg) => {
            const a = (deg * Math.PI) / 180;
            return (
              <circle
                key={deg}
                cx={Math.round((C + (R + 38) * Math.cos(a)) * 100) / 100}
                cy={Math.round((C + (R + 38) * Math.sin(a)) * 100) / 100}
                r={deg === 0 ? 3.2 : 2.2}
                fill={deg === 0 ? "#fff0cc" : "#cc9166"}
                opacity={deg === 0 ? 1 : 0.75}
                filter={deg === 0 ? "url(#glow)" : undefined}
              />
            );
          })}
        </g>
        </g>

        {/* hour ticks */}
        {Array.from({ length: 96 }).map((_, i) => {
          const m = i * 15;
          const major = i % 4 === 0;
          const a = polar(m, R - 14);
          const b = polar(m, R - (major ? 24 : 18));
          return (
            <line
              key={i}
              x1={a.x}
              y1={a.y}
              x2={b.x}
              y2={b.y}
              stroke={major ? "#464853" : "#1c1d22"}
              strokeWidth={major ? 1.2 : 1}
              className="fade-in"
              style={{ "--fade-delay": `${300 + i * 6}ms` } as React.CSSProperties}
            />
          );
        })}

        {/* base ring */}
        <circle cx={C} cy={C} r={R} fill="none" stroke="#14151a" strokeWidth="10" />

        {/* the regular session: thin and grey, or absent at the weekend */}
        {ny && !ny.weekend && (
          <path
            d={arc(SESSION_OPEN, SESSION_CLOSE, R)}
            fill="none"
            stroke="#2e3038"
            strokeWidth="3"
            strokeLinecap="round"
            className="dial-draw"
            style={{ "--len": sessionLen, "--draw-delay": "200ms" } as React.CSSProperties}
          />
        )}

        {/* the gloaming: soft glow under a gilded stroke */}
        {ny && (
          <>
            <path
              d={gloamPath}
              fill="none"
              stroke="#cc9166"
              strokeWidth="12"
              filter="url(#soft)"
              className="dial-glow"
            />
            <path
              d={gloamPath}
              fill="none"
              stroke="url(#gloam)"
              strokeWidth="5"
              strokeLinecap="round"
              className="dial-draw"
              style={{ "--len": ny.weekend ? 2 * Math.PI * R : gloamingLen, "--draw-delay": "500ms" } as React.CSSProperties}
            />
          </>
        )}

        {/* a comet that keeps travelling the closed hours */}
        {ny && !still && (
          <g className="fade-in" style={{ "--fade-delay": "2200ms" } as React.CSSProperties}>
            {/* the tail: twelve fading points trailing the head along the same path */}
            {Array.from({ length: 12 }).map((_, i) => (
              <circle key={i} r={Math.max(1, 5 - i * 0.35)} fill={i < 2 ? "#fff8e6" : "#cc9166"} opacity={Math.max(0.06, 1 - i * 0.085)}>
                <animateMotion dur="9s" repeatCount="indefinite" path={gloamPath} begin={`${(i * 0.045).toFixed(3)}s`} />
              </circle>
            ))}
            <circle r="14" fill="#fff0cc" opacity="0.4" filter="url(#soft)">
              <animateMotion dur="9s" repeatCount="indefinite" path={gloamPath} />
            </circle>
          </g>
        )}

        {/* session labels */}
        {ny && !ny.weekend && (
          <g className="fade-in" style={{ "--fade-delay": "1400ms" } as React.CSSProperties} fill="#777a88" fontSize="12" textAnchor="middle">
            <text x={open.x} y={open.y + 4}>09:30</text>
            <text x={close.x} y={close.y + 4}>16:00</text>
          </g>
        )}

        {/* the hand: now */}
        {hand && handInner && (
          <g className="fade-in" style={{ "--fade-delay": "1600ms" } as React.CSSProperties}>
            <line x1={handInner.x} y1={handInner.y} x2={hand.x} y2={hand.y} stroke={closed ? "#3fe280" : "#9194a1"} strokeWidth="1.5" />
            {closed && <circle cx={hand.x} cy={hand.y} r="6" fill="#3fe280" className="pulse-ring" />}
            <circle cx={hand.x} cy={hand.y} r="6" fill={closed ? "#3fe280" : "#9194a1"} stroke="#08080a" strokeWidth="3" />
          </g>
        )}
      </svg>

      {/* center content */}
      <div className="absolute inset-0 flex flex-col items-center justify-center px-[22%] text-center">{children}</div>
      </div>

      <figcaption className="mt-4 flex flex-wrap items-center justify-center gap-x-4 gap-y-1 text-xs text-text-tertiary">
        {ny ? (
          <>
            <span className={closed ? "text-mint" : "text-text-secondary"}>{status}</span>
            <span className="tabular-nums">New York {ny.label}</span>
            <span className="tabular-nums">Next cycle in {now ? nextCycle(now) : ""}</span>
          </>
        ) : (
          <span>&nbsp;</span>
        )}
      </figcaption>
    </figure>
  );
}
