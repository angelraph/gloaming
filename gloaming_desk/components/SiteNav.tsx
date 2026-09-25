"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import StatusPill from "@/components/StatusPill";

import { NAV_LINKS } from "@/lib/nav";

function isActive(pathname: string, href: string) {
  return href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`);
}

// A flat top bar: wordmark left, page links, live status right. The current page carries a
// 2px mint underline and aria-current="page" (mint is a live signal, so the nav says "you are
// here, and it is live"); everything else stays achromatic. Every link is at least 44px tall.
export default function SiteNav() {
  const pathname = usePathname();

  return (
    <header className="sticky top-0 z-40 border-b border-border-subtle bg-background">
      <div className="mx-auto flex max-w-[1216px] flex-wrap items-center justify-between gap-x-4 gap-y-0 px-4 sm:px-6 md:flex-nowrap lg:gap-x-6 lg:px-10">
        <Link href="/" className="flex min-h-11 items-center gap-3 py-2" aria-label="Gloaming home">
          <span
            aria-hidden
            className="h-7 w-7 shrink-0 rounded-full"
            style={{
              background: "radial-gradient(circle at 35% 30%, #fff0cc, #ae9357 45%, #2e3038 100%)",
              boxShadow: "0 0 0 1px rgba(255,255,255,0.18)",
            }}
          />
          <span className="font-display text-[22px] leading-none text-heading">Gloaming</span>
        </Link>

        <nav
          aria-label="Main"
          className="order-3 -mx-1 flex w-full items-center gap-1 overflow-x-auto md:order-2 md:mx-0 md:w-auto md:min-w-0 md:flex-1 md:justify-center"
        >
          {NAV_LINKS.map(({ href, label }) => {
            const active = isActive(pathname, href);
            return (
              <Link
                key={href}
                href={href}
                aria-current={active ? "page" : undefined}
                className={`relative flex min-h-11 items-center whitespace-nowrap px-3 text-sm transition-colors ${
                  active ? "text-heading" : "text-text-secondary hover:text-heading"
                }`}
              >
                {label}
                <span
                  aria-hidden
                  className={`absolute inset-x-3 bottom-0 h-0.5 rounded-full bg-mint transition-opacity ${
                    active ? "opacity-100" : "opacity-0"
                  }`}
                />
              </Link>
            );
          })}
        </nav>

        <div className="order-2 shrink-0 md:order-3">
          <StatusPill />
        </div>
      </div>
    </header>
  );
}
