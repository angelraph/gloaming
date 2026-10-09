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

    // One glowing dot, rendered once and stamped for every mote: far cheaper than shadowBlur
    // per mote per frame, which made the hero heavy on slow machines.
    const sprite = (core: string) => {
      const c = document.createElement("canvas");
      c.width = c.height = 48;
      const g = c.getContext("2d")!;
      const grd = g.createRadialGradient(24, 24, 0, 24, 24, 24);
      grd.addColorStop(0, core);
      grd.addColorStop(0.16, core);
      grd.addColorStop(0.32, "rgba(204, 145, 102, 0.35)");
      grd.addColorStop(1, "rgba(204, 145, 102, 0)");
      g.fillStyle = grd;
      g.fillRect(0, 0, 48, 48);
      return c;
    };
    const warmSprite = sprite("rgba(230, 180, 130, 1)");
    const paleSprite = sprite("rgba(255, 240, 204, 1)");

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
        const s = m.r * 6; // the sprite carries the glow, so it is drawn larger than the core
        ctx.globalAlpha = m.a * fade;
        ctx.drawImage(m.warm ? warmSprite : paleSprite, x - s / 2, y - s / 2, s, s);
      }
      ctx.globalAlpha = 1;
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
