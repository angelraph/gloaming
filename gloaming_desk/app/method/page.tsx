import type { Metadata } from "next";
import Link from "next/link";
import { Band, PageHeader } from "@/components/Container";
import SectionHeader from "@/components/SectionHeader";
import VerifyPanel from "@/components/VerifyPanel";

export const metadata: Metadata = {
  title: "Method",
  description: "The overnight signal, the risk layer, and exactly what the model and the code each decide.",
};

// Mirrors gloaming_agent/risk_controls.py; the docs in the repository are the long form.
const LIMITS = [
  ["Per-symbol cap", "15% of equity", "No single rToken can grow past this."],
  ["Gross exposure cap", "60% of equity", "Longs plus shorts, together."],
  ["Net exposure cap", "25% of equity", "Directional lean either way. Trades that reduce an over-cap book are still allowed."],
  ["Daily loss breaker", "-5% of equity", "Halts new risk for the day. De-risking stays allowed."],
  ["Per-trade loss", "2% of equity", "Rejects any trade whose stop-implied loss would be larger."],
  ["Volatility scaling", "Up to -75% size", "Cuts a trade's size for symbols more volatile than typical, using the real share's recent daily volatility."],
  ["LLM ceiling", "$1,000 per decision", "The most a model call can ask for."],
  ["Leverage", "None", "Cash-settled paper positions only."],
  ["Net-cap backstop", "2% of equity per cycle", "If the book stays over its net cap after 8 active cycles, a labeled, rule-based trim brings it back. It is marked as rule-based in the log, never as Qwen's."],
];

const SPLIT = [
  { who: "Qwen3.8-max decides", what: "Direction, size (inside the ceiling) and stop for each symbol, every cycle, with a written reason. It is shown its own book." },
  { who: "The risk layer decides", what: "Whether that trade is allowed, and at what size. Plain code, no model, no way to argue with it." },
  { who: "The desk only explains", what: "The chat and stress test read real data and narrate it. They never place, size or approve a trade." },
];

export default function Page() {
  return (
    <>
      <PageHeader
        eyebrow="Method"
        title="How Gloaming decides."
        description="One signal, one loop, one set of limits. Written so a skeptical reader can check each claim against the code."
      />

      <Band label="The mechanic" first>
        <SectionHeader
          eyebrow="The mechanic"
          title="Tokenized shares never close. Their reference does."
          description="Bitget rTokens trade around the clock. The real shares trade about 6.5 hours on weekdays. When NYSE is shut nothing pins an rToken to its share, so the agent watches the gap between where an rToken trades and where its share last closed, adjusted for what live proxies have done since."
        />
      </Band>

      <Band label="The signal">
        <SectionHeader eyebrow="The signal" title="Since the last close, on the same clock." />
        <div className="mt-10 grid gap-4 md:grid-cols-3">
          {[
            ["Fair value", "The real share's last regular-session close, moved by the blended proxy return since that close."],
            ["The blend", "0.5 index futures, 0.3 crypto (BTC and ETH), 0.2 the dollar index, inverted. A heuristic prior that the roadmap plans to calibrate."],
            ["The spread", "The rToken's own return since the close, minus the blended proxy return since the close. Positive means rich, negative means cheap."],
          ].map(([t, b]) => (
            <div key={t} className="rounded-xl border border-border-subtle bg-layer-1 p-6">
              <h3 className="text-sm font-medium text-heading">{t}</h3>
              <p className="mt-3 text-sm leading-relaxed text-text-secondary">{b}</p>
            </div>
          ))}
        </div>
        <div className="mt-6 max-w-3xl rounded-xl border border-copper/40 bg-copper-soft p-6">
          <h3 className="text-sm font-medium text-copper">A correction we made in the open</h3>
          <p className="mt-3 text-sm leading-relaxed text-text-primary">
            The first signal (through Sep 24) compared an rToken&apos;s rolling 24-hour move with proxies measured over different
            windows. Checking it against the real closes showed it mostly measured the session&apos;s own move, so spreads of several
            percent (up to about 4.6) were mostly not gaps. The rTokens actually sit within about a quarter of a percent of the real close. The signal was
            rebuilt on Sep 25 and the earlier records are left in place, labeled by their signal specification. The full account is in{" "}
            <Link href="/faq" className="underline underline-offset-4">the FAQ</Link> and the repository docs.
          </p>
        </div>
      </Band>

      <Band label="Who decides what">
        <SectionHeader eyebrow="Who decides what" title="A model with judgment, bounded by code without any." />
        <ul className="mt-10 grid gap-4 md:grid-cols-3">
          {SPLIT.map((s) => (
            <li key={s.who} className="rounded-xl border border-border-subtle bg-layer-1 p-6">
              <h3 className="font-display text-[22px] leading-tight text-heading">{s.who}</h3>
              <p className="mt-3 text-sm leading-relaxed text-text-secondary">{s.what}</p>
            </li>
          ))}
        </ul>
      </Band>

      <Band label="Risk limits">
        <SectionHeader eyebrow="Risk layer" title="The hard limits, in one table." />
        <div className="mt-10 overflow-x-auto rounded-xl border border-border-subtle bg-layer-1">
          <table className="w-full min-w-[560px] text-left text-sm">
            <caption className="sr-only">Risk limits enforced before any paper fill</caption>
            <thead>
              <tr className="border-b border-border-subtle">
                <th scope="col" className="micro-label px-4 py-3 font-normal">Control</th>
                <th scope="col" className="micro-label px-4 py-3 font-normal">Limit</th>
                <th scope="col" className="micro-label px-4 py-3 font-normal">What it does</th>
              </tr>
            </thead>
            <tbody>
              {LIMITS.map(([c, l, d]) => (
                <tr key={c} className="border-b border-border-subtle align-top last:border-0">
                  <th scope="row" className="px-4 py-3 font-medium text-heading">{c}</th>
                  <td className="px-4 py-3 tabular-nums text-text-primary">{l}</td>
                  <td className="px-4 py-3 text-text-secondary">{d}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Band>

      <Band label="Read the source">
        <SectionHeader eyebrow="Read the source" title="Every claim on this page has a file behind it." />
        <div className="mt-10">
          <VerifyPanel />
        </div>
      </Band>
    </>
  );
}
