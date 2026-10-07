import { NextResponse } from "next/server";
import { readFillVerification, readLedger, type FillCheck } from "@/lib/data";

export const dynamic = "force-dynamic";

// Same key gloaming_agent/verify_fills.py writes. JSON numbers print the same shortest form
// in Python and JavaScript, so the qty part matches.
function fillKey(f: { timestamp: string; symbol: string; side: string; qty: number }) {
  return `${f.timestamp}|${f.symbol}|${f.side}|${f.qty}`;
}

// Real paper fills from the ledger, newest first. ?symbol=RAAPLUSDT filters, ?limit= caps
// (max 500), ?verified=1 attaches each fill's check against Bitget's public candles.
export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const symbol = searchParams.get("symbol");
  const limit = Math.min(Math.max(Number(searchParams.get("limit") ?? "50") || 50, 1), 500);

  const ledger = await readLedger();
  if (!ledger) return NextResponse.json({ fills: [], total: 0 });

  const all = symbol ? ledger.fills.filter((f) => f.symbol === symbol) : ledger.fills;
  const page = all.slice(-limit).reverse();

  if (searchParams.get("verified") !== "1") return NextResponse.json({ fills: page, total: all.length });

  const verification = await readFillVerification();
  const checks = new Map<string, FillCheck>((verification?.fills ?? []).map((c) => [c.key, c]));
  const staleAfter = verification?.summary.stale_after_minutes ?? 15;
  return NextResponse.json({
    total: all.length,
    fills: page.map((f) => {
      const c = checks.get(fillKey(f));
      const check = !c
        ? "pending"
        : c.status !== "matched"
          ? c.status
          : (c.lag_minutes ?? 0) > staleAfter
            ? "stale"
            : "matched";
      return { ...f, check };
    }),
  });
}
