"use client";

import { useEffect, useRef } from "react";

// Fine gold motes drifting up through the hero, like the last light of the day. Purely
// decorative: a canvas behind the content, paused when it is off screen or the tab is
// hidden, and not drawn at all with reduced motion.
export default function DuskDust({ count = 110 }: { count?: number }) {
  const ref = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return;
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let w = 0;
    let h = 0;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const resize = () => {
      w = canvas.clientWidth;
      h = canvas.clientHeight;
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();

    const motes = Array.from({ length: count }, () => ({
      // positions are fractions of the canvas, so a resize (or a first measure of 0) never bunches them up
      fx: Math.random(),
      fy: Math.random(),
      r: 0.8 + Math.random() * 2.2,
      vy: 0.08 + Math.random() * 0.32,
      sway: Math.random() * Math.PI * 2,
      a: 0.3 + Math.random() * 0.6,
      warm: Math.random() < 0.7,
    }));

    let visible = true;
    const io = new IntersectionObserver((e) => (visible = e[0]?.isIntersecting ?? true));
    io.observe(canvas);
    window.addEventListener("resize", resize);

    let frame = 0;
    let t = 0;
    const draw = () => {
      frame = requestAnimationFrame(draw);
      if (!visible || document.hidden) return;
      t += 0.01;
      ctx.clearRect(0, 0, w, h);
      if (!w || !h) resize();
      for (const m of motes) {
        m.fy -= m.vy / Math.max(h, 1);
        if (m.fy < -0.01) {
          m.fy = 1.01;
          m.fx = Math.random();
        }
        const x = m.fx * w + Math.sin(t + m.sway) * 14;
        const y = m.fy * h;
        // brighter near the horizon, fading as they rise
        const fade = Math.min(1, Math.max(0, m.fy / 0.9));
        ctx.beginPath();
        ctx.arc(x, y, m.r, 0, Math.PI * 2);
        ctx.fillStyle = m.warm ? `rgba(230, 180, 130, ${m.a * fade})` : `rgba(255, 240, 204, ${m.a * fade})`;
        ctx.shadowColor = "rgba(204, 145, 102, 0.8)";
        ctx.shadowBlur = m.r * 4;
        ctx.fill();
      }
    };
    frame = requestAnimationFrame(draw);

    return () => {
      cancelAnimationFrame(frame);
      io.disconnect();
      window.removeEventListener("resize", resize);
    };
  }, [count]);

  return <canvas ref={ref} aria-hidden className="pointer-events-none absolute inset-0 h-full w-full" />;
}
