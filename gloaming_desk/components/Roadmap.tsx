import SectionHeader from "@/components/SectionHeader";

type Entry = { when?: string; title: string; detail: string };

// Shipped entries are dated from the repository history and the decision log. Planned
// entries are intentions, labeled as such: nothing here is promised, and nothing planned
// is presented as done.
const SHIPPED: Entry[] = [
  {
    when: "Sep 25",
    title: "A multi-page Desk with a decision inspector",
    detail:
      "Separate pages for the desk, the agent and its performance, a page per symbol, an inspector on every decision showing the market inputs and the book Qwen was shown, downloadable records, and keyboard and screen-reader support.",
  },
  {
    when: "Sep 26",
    title: "Dry runs can no longer touch the live Desk",
    detail:
      "A local test run once overwrote the public ledger mirror with stale data. Dry runs now write nothing to Redis, and each live cycle re-asserts the ledger mirror so any missed push heals itself within 15 minutes.",
  },
  {
    when: "Sep 25",
    title: "Signal anchored to the real close",
    detail:
      "The spread is now measured from each real share's last regular-session close, with every input over the same window. Replaces a signal that mostly measured the session's own move. Disclosed in the docs.",
  },
  {
    when: "Sep 24",
    title: "Qwen sees its own book",
    detail:
      "Each decision prompt includes the agent's position, net and gross exposure against the caps, what the risk layer would approve, and its recent fills. Model thinking mode off, so calls take 5 to 8 seconds instead of 30 or more.",
  },
  {
    when: "Sep 22 to 24",
    title: "A risk layer that can de-risk",
    detail:
      "Found through live operation: the caps blocked risk-reducing trades as hard as risk-adding ones and left the book stuck for eight days. Now net-exposure aware, with a 25% net cap and a labeled backstop.",
  },
  {
    when: "Sep 22",
    title: "Bitget signal wired in",
    detail:
      "Sentiment, BTC positioning, news and yield curve from Bitget's public MCP server, degrading honestly when its sources are empty.",
  },
  {
    when: "Sep 12 to 13",
    title: "Unattended, every 15 minutes",
    detail: "Runs on GitHub Actions, not a laptop, and only while NYSE is closed.",
  },
  {
    when: "Sep 11",
    title: "Qwen decides, on a paper ledger",
    detail:
      "Qwen3.8-max becomes the primary decision-maker. Fills post to a ledger marked to live rToken prices, mirrored to Redis for this Desk.",
  },
  {
    when: "Sep 10",
    title: "The loop, end to end",
    detail: "Live snapshot, decision, risk gate, paper fill, decision log.",
  },
];

const IN_PROGRESS: Entry[] = [
  {
    title: "Watching how quiet the anchored signal is over a full night and a weekend",
    detail:
      "The first production cycles ran clean: every record carried the new signal, every decision came from Qwen with a written reason, and spreads stayed under half a percent. The open question is how sparse trading becomes over a weekend.",
  },
];

const PLANNED: Entry[] = [
  {
    title: "Calibrate the blend on since-close returns",
    detail: "The 0.5 / 0.3 / 0.2 weights are a heuristic prior. Fit them against the anchored window once there is enough history.",
  },
  {
    title: "Re-run the backtest on the same specification",
    detail: "The Alpha Factory backtest uses daily close-to-close returns, a different signal from the live one.",
  },
  {
    title: "Model early closes and holidays",
    detail: "The close is treated as 16:00 ET every trading day today.",
  },
  {
    title: "Company-specific inputs",
    detail: "The proxies are broad-market signals with no view on one company. News and earnings context, when the Bitget signal sources return data.",
  },
  {
    title: "Fees and slippage in the paper ledger",
    detail: "Fills are at the last price today.",
  },
];

function Card({ entry, planned = false }: { entry: Entry; planned?: boolean }) {
  return (
    <li
      className={`rounded-xl p-5 ${
        planned ? "border border-dashed border-border bg-transparent" : "border border-border-subtle bg-layer-1"
      }`}
    >
      {entry.when && <p className="micro-label text-copper">{entry.when}</p>}
      <h3 className={`text-[17px] font-medium leading-snug text-heading ${entry.when ? "mt-3" : ""}`}>{entry.title}</h3>
      <p className="mt-2 text-sm leading-relaxed text-text-secondary">{entry.detail}</p>
    </li>
  );
}

function ColumnHeader({ label, count, live = false }: { label: string; count: number; live?: boolean }) {
  return (
    <div className="mb-4 flex items-center gap-3">
      {live && <span aria-hidden className="h-1.5 w-1.5 animate-pulse rounded-full bg-mint" />}
      <h3 className="micro-label text-text-secondary">{label}</h3>
      <span className="text-xs text-text-tertiary">{count}</span>
      <span aria-hidden className="h-px flex-1 bg-border-subtle" />
    </div>
  );
}

export default function Roadmap() {
  return (
    <div>
      <SectionHeader
        eyebrow="Roadmap"
        title="What shipped, what is being proven, what is next."
        description="Shipped items are dated from the repository history. Planned items are intentions, not commitments."
      />

      <div className="mt-12">
        <ColumnHeader label="In progress" count={IN_PROGRESS.length} live />
        <ul className="grid gap-4 sm:grid-cols-2">
          {IN_PROGRESS.map((e) => (
            <Card key={e.title} entry={e} />
          ))}
        </ul>
      </div>

      <div className="mt-12 grid gap-12 lg:grid-cols-2 lg:gap-10">
        <div>
          <ColumnHeader label="Shipped" count={SHIPPED.length} />
          <ul className="space-y-4">
            {SHIPPED.map((e) => (
              <Card key={e.title} entry={e} />
            ))}
          </ul>
        </div>
        <div>
          <ColumnHeader label="Planned" count={PLANNED.length} />
          <ul className="space-y-4">
            {PLANNED.map((e) => (
              <Card key={e.title} entry={e} planned />
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
