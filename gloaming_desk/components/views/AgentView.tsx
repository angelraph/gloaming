"use client";

import { useDeskData } from "@/lib/useDeskData";
import { UNIVERSE } from "@/lib/universe";
import { Band, PageHeader } from "@/components/Container";
import SectionHeader from "@/components/SectionHeader";
import RiskMeters from "@/components/RiskMeters";
import LatestCycleGrid from "@/components/LatestCycleGrid";
import DecisionFeed from "@/components/DecisionFeed";
import DataNotice from "@/components/DataNotice";

const PIPELINE = [
  { n: "1", title: "Observe", body: "A live snapshot per symbol: the rToken price, the real share's last close, and what index futures, BTC/ETH and the dollar have done since." },
  { n: "2", title: "Decide", body: "Qwen3.8-max reads the snapshot, Bitget's own signal context and its own book, then chooses buy, sell or hold, a size and a stop, and explains why." },
  { n: "3", title: "Gate", body: "A deterministic risk layer, with no model in it, approves, shrinks or rejects the trade against hard caps." },
  { n: "4", title: "Execute", body: "An approved trade becomes a paper fill on the ledger at the live rToken price." },
  { n: "5", title: "Record", body: "The snapshot, reasoning, verdict and fill are written to the decision log and committed to the repository." },
];

export default function AgentView() {
  const { portfolio, events, loading, error, reload } = useDeskData();
  const equity = portfolio?.equityUsd ?? 0;

  return (
    <>
      <PageHeader
        eyebrow="Agentic Trading"
        title="An agent you can audit."
        description="Qwen makes the calls, a non-LLM risk layer bounds them, and every decision is recorded with its reasoning. Open any row to see exactly what the record holds."
      />

      {error && (
        <div className="mx-auto max-w-[1216px] px-4 pb-6 sm:px-6 lg:px-10">
          <DataNotice message={error} onRetry={reload} />
        </div>
      )}

      <Band label="The loop" first>
        <SectionHeader
          eyebrow="The loop"
          title="Observe, decide, gate, execute, record."
          description="One cycle every 15 minutes while NYSE is closed, run unattended on GitHub Actions."
        />
        <ol className="mt-10 grid gap-3 md:grid-cols-5">
          {PIPELINE.map((s) => (
            <li key={s.n} className="rounded-xl border border-border-subtle bg-layer-1 p-5">
              <span className="font-display text-[28px] leading-none text-copper" aria-hidden>
                {s.n}
              </span>
              <h3 className="mt-3 text-sm font-medium text-heading">{s.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-text-secondary">{s.body}</p>
            </li>
          ))}
        </ol>
      </Band>

      <Band label="Latest cycle">
        <SectionHeader
          eyebrow="Latest cycle"
          title="Where it stands right now."
          description={`${UNIVERSE.length} symbols, each with its most recent verdict and spread. Select one for its full page.`}
        />
        <div className="mt-10">
          <LatestCycleGrid events={events} />
        </div>
        <div className="mt-6 rounded-xl border border-border-subtle bg-layer-1 p-5">
          <h3 className="text-sm font-medium text-heading">Why it can go days without a trade</h3>
          <p className="mt-2 text-sm leading-relaxed text-text-secondary">
            Holding is a decision, not an outage. Every fill is charged an assumed 0.15%, so a round trip costs about
            0.30%, and Qwen is told so. On most nights the spread against fair value sits well under 0.1%: too small to
            pay for itself. When that happens, Qwen holds and writes down why, and the agent keeps running every 15
            minutes. Open any hold in the feed below to read its reason. An agent that trades only when the trade can
            pay for its costs will sit still for long stretches, and that is the intended behavior.
          </p>
        </div>
      </Band>

      <Band label="Risk limits">
        <SectionHeader
          eyebrow="Risk layer"
          title="The limits no model can talk its way past."
          description="Enforced in code before any paper fill. The meters show the live book against each one."
        />
        <div className="mt-10">
          {loading ? (
            <div aria-hidden className="h-40 animate-pulse rounded-xl border border-border-subtle bg-layer-1" />
          ) : (
            <RiskMeters equityUsd={equity} dailyPnlUsd={portfolio?.dailyPnlUsd ?? 0} positions={portfolio?.positions ?? []} />
          )}
        </div>
      </Band>

      <Band id="feed" label="Decision feed">
        <SectionHeader
          eyebrow="Decision feed"
          title="Every record, newest first."
          description={`The live mirror holds the most recent ${events.length || "~500"} records. The complete history is committed to the public repository.`}
        />
        <div className="mt-10">
          {loading ? (
            <div aria-hidden className="h-64 animate-pulse rounded-xl border border-border-subtle bg-layer-1" />
          ) : (
            <DecisionFeed events={events} symbols={[...UNIVERSE]} />
          )}
        </div>
      </Band>
    </>
  );
}
