import { NextResponse } from "next/server";
import { isKnownUnderlying, rtokenSymbol } from "@/lib/universe";

// Hourly candles for one rToken, straight from Bitget's public spot market-data endpoint
// (no key needed). Cached for five minutes so the landing page never hammers Bitget.
// ?u=AAPL&limit=72
export const revalidate = 300;

export type Candle = { t: number; o: number; h: number; l: number; c: number; v: number };

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const u = (searchParams.get("u") ?? "AAPL").toUpperCase();
  if (!isKnownUnderlying(u)) return NextResponse.json({ error: "unknown symbol" }, { status: 400 });
  const limit = Math.min(Math.max(Number(searchParams.get("limit") ?? "72") || 72, 12), 200);

  const url = `https://api.bitget.com/api/v2/spot/market/candles?symbol=${rtokenSymbol(u)}&granularity=1h&limit=${limit}`;
  try {
    const r = await fetch(url, { next: { revalidate: 300 } });
    const payload = await r.json();
    if (payload.code !== "00000") throw new Error(payload.msg ?? "Bitget error");
    const candles: Candle[] = (payload.data as string[][])
      .map((row) => ({ t: Number(row[0]), o: +row[1], h: +row[2], l: +row[3], c: +row[4], v: +row[6] }))
      .sort((a, b) => a.t - b.t);
    return NextResponse.json(
      { symbol: rtokenSymbol(u), source: "Bitget public spot candles, 1h", candles },
      { headers: { "Cache-Control": "public, s-maxage=300, stale-while-revalidate=900" } },
    );
  } catch (e) {
    return NextResponse.json({ error: e instanceof Error ? e.message : "candles unavailable", candles: [] }, { status: 502 });
  }
}
