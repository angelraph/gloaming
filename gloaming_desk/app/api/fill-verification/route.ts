import { NextResponse } from "next/server";
import { readFillVerification } from "@/lib/data";

export const dynamic = "force-dynamic";

// The fill-by-fill check against Bitget's public candles. Returns the summary plus every
// fill that did not match or matched only a stale price, so the exceptions are shown,
// not just the count.
export async function GET() {
  const v = await readFillVerification();
  if (!v) return NextResponse.json({ configured: false });
  const staleAfter = v.summary.stale_after_minutes ?? 15;
  return NextResponse.json({
    configured: true,
    summary: v.summary,
    exceptions: v.fills.filter((f) => f.status !== "matched" || (f.lag_minutes ?? 0) > staleAfter),
    sample: v.fills.filter((f) => f.status === "matched" && (f.lag_minutes ?? 0) <= staleAfter).slice(-5).reverse(),
  });
}
