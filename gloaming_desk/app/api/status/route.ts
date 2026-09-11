import { NextResponse } from "next/server";
import { isNyseClosed } from "@/lib/marketHours";

export async function GET() {
  const closed = isNyseClosed();
  return NextResponse.json({
    nyseClosed: closed,
    agentActive: closed, // the Agent only trades while NYSE is closed - same condition
    serverTimeUtc: new Date().toISOString(),
  });
}
