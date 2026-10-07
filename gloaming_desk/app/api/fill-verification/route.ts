import { NextResponse } from "next/server";
import { readFillVerification } from "@/lib/data";

export const dynamic = "force-dynamic";

// The fill-by-fill check against Bitget's public candles. Returns the summary plus every
// fill that did not match, so the exceptions are shown, not just the count.
export async function GET() {
  const v = await readFillVerification();
  if (!v) return NextResponse.json({ configured: false });
  return NextResponse.json({
    configured: true,
    summary: v.summary,
    exceptions: v.fills.filter((f) => f.status !== "matched"),
    sample: v.fills.filter((f) => f.status === "matched").slice(-5).reverse(),
  });
}
