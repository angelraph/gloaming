import Link from "next/link";
import { NAV_LINKS, REPO_URL } from "@/lib/nav";
import { Container } from "@/components/Container";

export default function SiteFooter() {
  return (
    <footer className="border-t border-border-subtle">
      <Container className="grid gap-10 py-14 lg:grid-cols-[minmax(0,5fr)_minmax(0,3fr)_minmax(0,4fr)]">
        <div>
          <p className="font-display text-[26px] leading-none text-heading">Gloaming</p>
          <p className="mt-4 max-w-sm text-sm leading-relaxed text-text-secondary">
            Gloaming trades the hours the market can&apos;t. An autonomous, risk-gated overnight desk for Bitget
            rTokens.
          </p>
        </div>
        <nav aria-label="Footer">
          <p className="micro-label">Pages</p>
          <ul className="mt-4 space-y-1 text-sm">
            {NAV_LINKS.map(({ href, label }) => (
              <li key={href}>
                <Link
                  href={href}
                  className="inline-flex min-h-8 items-center text-text-secondary transition-colors hover:text-heading"
                >
                  {label}
                </Link>
              </li>
            ))}
            <li>
              <a
                href={REPO_URL}
                target="_blank"
                rel="noreferrer noopener"
                className="inline-flex min-h-8 items-center text-text-secondary transition-colors hover:text-heading"
              >
                Source on GitHub<span className="sr-only"> (opens in a new tab)</span>
              </a>
            </li>
          </ul>
        </nav>
        <div>
          <p className="micro-label">Good to know</p>
          <ul className="mt-4 space-y-2.5 text-sm text-text-secondary">
            <li>Paper trading only. Nothing here is financial advice.</li>
            <li>This desk is read-only and never places a trade.</li>
            <li>Built for Bitget&apos;s AI &amp; Crypto Hackathon, Genesis Season 2.</li>
          </ul>
        </div>
      </Container>
    </footer>
  );
}
