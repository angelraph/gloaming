import { NextResponse } from "next/server";
import { latestSnapshotPrices, readDecisionLog, readLedger } from "@/lib/data";
import { computePerformance } from "@/lib/performance";

export const dynamic = "force-dynamic";

export async function GET() {
  const ledger = await readLedger();
  if (!ledger) return NextResponse.json({ configured: false });
  const records = await readDecisionLog(3);
  return NextResponse.json({
    configured: true,
    ...computePerformance(ledger, latestSnapshotPrices(records)),
  });
}
