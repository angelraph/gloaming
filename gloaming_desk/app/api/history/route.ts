import { NextResponse } from "next/server";

// The last three days of the agent's snapshots, read straight from the decision log the
// agent commits to the public repository after every cycle (the live mirror only holds the
// newest ~500 records, about half a day). Only the fields the console charts need are kept:
// time, symbol, rToken price, fair value and spread. Rebuilt at most every 15 minutes.
export const revalidate = 900;

const RAW = "https://raw.githubusercontent.com/angelraph/gloaming/master/gloaming_agent/decision_log";
const DAYS = 4; // today plus three full days back, so a 72-hour window is always covered

export type HistoryPoint = { t: string; u: string; p: number; f: number | null; s: number };

export async function GET() {
  const now = Date.now();
  const dates = Array.from({ length: DAYS }, (_, i) => new Date(now - i * 86_400_000).toISOString().slice(0, 10));
  const points: HistoryPoint[] = [];

  await Promise.all(
    dates.map(async (d) => {
      try {
        const r = await fetch(`${RAW}/${d}.jsonl`, { cache: "no-store" });
        if (!r.ok) return;
        for (const line of (await r.text()).split("\n")) {
          if (!line) continue;
          try {
            const rec = JSON.parse(line);
            const s = rec.snapshot;
            if (!rec.underlying || !s || s.signal_spec !== "since_last_close_v2") continue;
            points.push({ t: rec.timestamp, u: rec.underlying, p: s.rtoken_last_price, f: s.fair_value_price ?? null, s: s.spread });
          } catch {
            // one malformed line never sinks the rest
          }
        }
      } catch {
        // a missing day (or a GitHub hiccup) just leaves a gap
      }
    }),
  );

  points.sort((a, b) => a.t.localeCompare(b.t));
  // cached at Vercel's edge, so GitHub is read at most once every 15 minutes
  return NextResponse.json(
    { source: "gloaming_agent/decision_log on GitHub", count: points.length, points },
    { headers: { "Cache-Control": "public, s-maxage=900, stale-while-revalidate=3600" } },
  );
}
