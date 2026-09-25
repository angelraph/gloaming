import { NextResponse } from "next/server";
import { readLedger } from "@/lib/data";

export const dynamic = "force-dynamic";

// Real paper fills from the ledger, newest first. ?symbol=RAAPLUSDT filters, ?limit= caps (max 500).
export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const symbol = searchParams.get("symbol");
  const limit = Math.min(Math.max(Number(searchParams.get("limit") ?? "50") || 50, 1), 500);

  const ledger = await readLedger();
  if (!ledger) return NextResponse.json({ fills: [], total: 0 });

  const all = symbol ? ledger.fills.filter((f) => f.symbol === symbol) : ledger.fills;
  return NextResponse.json({ fills: all.slice(-limit).reverse(), total: all.length });
}
