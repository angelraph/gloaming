import { NextResponse } from "next/server";
import { readDecisionLog } from "@/lib/data";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const days = Number(searchParams.get("days") ?? "3");

  const records = await readDecisionLog(days);

  // Newest first, and skip the empty "market open, skipped" placeholder records
  // that run_once() writes every 15 minutes during NYSE hours - real content only.
  const events = records
    .filter((r) => r.underlying !== null)
    .sort((a, b) => b.timestamp.localeCompare(a.timestamp));

  return NextResponse.json({ events, count: events.length });
}
