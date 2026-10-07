"use client";

import Link from "next/link";
import type { DecisionRecord } from "@/lib/data";
import { fmtSignedPct, fmtTime, fmtUsd } from "@/lib/format";

// One real decision, followed through the five steps of a cycle. A point of light travels
// the path and each step brightens as it passes; the words under each step come from the
// newest record in the decision log, not from a script.

function clip(s: string, n: number) {
  const t = s.replace(/^\[[^\]]+\]\s*/, "").trim();
  return t.length > n ? `${t.slice(0, n).replace(/\s+\S*$/, "").replace(/[\s;:,.(-]+$/, "")}…` : t;
}

function steps(r: DecisionRecord) {
  const s = r.snapshot!;
  const sym = r.underlying ?? s.rtoken_symbol;
  const traded = !!r.decision;
  const source = r.decision_source?.startsWith("qwen") ? "Qwen3.8-max" : "The rule-based fallback";
  const reason = traded ? r.decision!.rationale : r.hold_rationale ?? "";
  return [
    {
      title: "Observe",
      body:
        s.fair_value_price !== undefined
          ? `${sym} rToken at ${fmtUsd(s.rtoken_last_price)} against a fair value of ${fmtUsd(s.fair_value_price)}: a ${fmtSignedPct(s.spread)} spread.`
          : `${sym} rToken at ${fmtUsd(s.rtoken_last_price)}, a ${fmtSignedPct(s.spread)} spread against fair value.`,
    },
    {
      title: "Decide",
      body: `${source} chose ${traded ? `to ${r.decision!.side} ${fmtUsd(r.decision!.notional_usd)}` : "to hold"}. “${clip(reason, 120)}”`,
    },
    {
      title: "Gate",
      body: !traded
        ? "Nothing to gate: a hold places no order, so the risk layer had no trade to check."
        : r.risk_result?.approved
          ? `Approved by the risk layer at ${fmtUsd(r.risk_result.adjusted_notional_usd)}.`
          : `Rejected by the risk layer${r.risk_result?.reasons?.[0] ? `: ${clip(r.risk_result.reasons[0], 90)}` : "."}`,
    },
    {
      title: "Execute",
      body: traded && r.risk_result?.approved ? "Filled on the paper ledger at the live rToken price." : "No fill. The book stays as it was.",
    },
    {
      title: "Record",
      body: `Written to the decision log at ${fmtTime(r.timestamp)} and committed to the public repository.`,
    },
  ];
}

export default function LoopFlow({ events }: { events: DecisionRecord[] }) {
  const record = events.find((e) => e.snapshot && !e.error);
  if (!record) return <div aria-hidden className="h-48 animate-pulse rounded-xl border border-border-subtle bg-layer-1" />;
  const list = steps(record);

  return (
    <div>
      <div className="relative">
        {/* the path and the light that travels it (wide screens) */}
        <div aria-hidden className="absolute left-[10%] right-[10%] top-[27px] hidden h-px overflow-hidden bg-border lg:block">
          <div className="loop-light h-px w-1/4" />
        </div>
        <ol className="relative grid gap-3 lg:grid-cols-5">
          {list.map((s, i) => (
            <li key={s.title} className="flex flex-col">
              <span
                className="loop-node mx-auto hidden h-[54px] w-[54px] items-center justify-center rounded-full border font-display text-[22px] text-copper lg:flex"
                style={{ "--node-delay": `${0.2 + i * 1.34}s` } as React.CSSProperties}
                aria-hidden
              >
                {i + 1}
              </span>
              <div
                className="loop-node spotlight mt-0 flex-1 rounded-xl border p-5 lg:mt-5"
                style={{ "--node-delay": `${0.35 + i * 1.34}s` } as React.CSSProperties}
              >
                <h3 className="text-sm font-medium text-heading">
                  <span className="mr-2 font-display text-copper lg:hidden">{i + 1}</span>
                  {s.title}
                </h3>
                <p className="mt-2 text-sm leading-relaxed text-text-secondary">{s.body}</p>
              </div>
            </li>
          ))}
        </ol>
      </div>
      <p className="mt-6 text-sm text-text-tertiary">
        The newest record in the log, {record.underlying} at {fmtTime(record.timestamp)}.{" "}
        <Link href="/agent#feed" className="text-copper underline-offset-4 hover:underline">
          Open the full feed
        </Link>
      </p>
    </div>
  );
}
