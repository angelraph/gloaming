import { NextResponse } from "next/server";
import { computeEquityUsd, latestSnapshotPrices, readDecisionLog, readLedger } from "@/lib/data";

export async function GET() {
  const ledger = await readLedger();
  if (!ledger) {
    return NextResponse.json({
      configured: false,
      message: "Paper ledger not found yet - the Agent hasn't run a cycle. See gloaming_agent/agent_loop.py.",
    });
  }

  const records = await readDecisionLog(3);
  const markPrices = latestSnapshotPrices(records);
  const equityUsd = computeEquityUsd(ledger, markPrices);

  const positions = Object.entries(ledger.positions).map(([symbol, qty]) => {
    const markPrice = markPrices[symbol] ?? null;
    const lastFill = [...ledger.fills].reverse().find((f) => f.symbol === symbol);
    return {
      symbol,
      qty,
      markPrice,
      notionalUsd: markPrice !== null ? qty * markPrice : null,
      lastFillPrice: lastFill?.price ?? null,
    };
  });

  return NextResponse.json({
    configured: true,
    cashUsd: ledger.cash_usd,
    equityUsd,
    dayStartEquityUsd: ledger.equity_at_day_start_usd,
    dayStartDate: ledger.day_start_date,
    dailyPnlUsd: equityUsd - ledger.equity_at_day_start_usd,
    positions,
    recentFills: ledger.fills.slice(-20).reverse(),
    totalFills: ledger.fills.length,
  });
}
