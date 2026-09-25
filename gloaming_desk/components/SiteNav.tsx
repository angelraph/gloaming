"use client";

import { useEffect, useState } from "react";
import StatusPill from "@/components/StatusPill";

export const NAV_SECTIONS = [
  { id: "desk", label: "Desk" },
  { id: "signal", label: "Signal" },
  { id: "activity", label: "Activity" },
  { id: "stress", label: "Stress test" },
  { id: "faq", label: "FAQ" },
  { id: "roadmap", label: "Roadmap" },
] as const;

// A flat top bar: wordmark left, section links, live status right. The active section gets
// a 2px mint underline (mint is a live signal, so the nav says "you are here, and it is
// live"); everything else stays achromatic.
export default function SiteNav() {
  const [active, setActive] = useState<string>("desk");

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        // the section whose top has passed the upper part of the viewport wins
        const visible = entries.filter((e) => e.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        if (visible[0]) setActive(visible[0].target.id);
      },
      { rootMargin: "-30% 0px -60% 0px", threshold: 0 }
    );
    NAV_SECTIONS.forEach(({ id }) => {
      const el = document.getElementById(id);
      if (el) observer.observe(el);
    });
    return () => observer.disconnect();
  }, []);

  return (
    <div className="sticky top-0 z-40 border-b border-border-subtle bg-background">
      <div className="mx-auto flex max-w-[1216px] flex-wrap items-center justify-between gap-x-4 gap-y-1 px-4 sm:px-6 md:flex-nowrap lg:gap-x-6 lg:px-10">
        <a href="#desk" className="flex items-center gap-3 py-3.5">
          <span
            aria-hidden
            className="h-7 w-7 shrink-0 rounded-full"
            style={{
              background: "radial-gradient(circle at 35% 30%, #fff0cc, #ae9357 45%, #2e3038 100%)",
              boxShadow: "0 0 0 1px rgba(255,255,255,0.18)",
            }}
          />
          <span className="font-display text-[22px] leading-none text-heading">Gloaming</span>
        </a>

        <nav
          aria-label="Sections"
          className="order-3 -mx-1 flex w-full items-center gap-1 overflow-x-auto md:order-2 md:mx-0 md:w-auto md:min-w-0 md:flex-1 md:justify-center"
        >
          {NAV_SECTIONS.map(({ id, label }) => (
            <a
              key={id}
              href={`#${id}`}
              aria-current={active === id ? "true" : undefined}
              className={`relative whitespace-nowrap px-3 py-3.5 text-sm transition-colors ${
                active === id ? "text-heading" : "text-text-secondary hover:text-heading"
              }`}
            >
              {label}
              <span
                aria-hidden
                className={`absolute inset-x-3 bottom-0 h-0.5 rounded-full bg-mint transition-opacity ${
                  active === id ? "opacity-100" : "opacity-0"
                }`}
              />
            </a>
          ))}
        </nav>

        <div className="order-2 shrink-0 md:order-3">
          <StatusPill />
        </div>
      </div>
    </div>
  );
}
