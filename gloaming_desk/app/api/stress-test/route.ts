import { NextResponse } from "next/server";
import {
  computeEquityUsd,
  findMarketWideWorstDate,
  latestSnapshotPrices,
  readDecisionLog,
  readHistoricalScenarios,
  readLedger,
} from "@/lib/data";

type PositionImpact = {
  underlying: string;
  symbol: string;
  qty: number;
  markPrice: number;
  currentNotional: number;
  scenarioReturn: number;
  hypotheticalPnlUsd: number;
};

type Scenario = {
  id: string;
  label: string;
  description: string;
  positions: PositionImpact[];
  totalHypotheticalPnlUsd: number;
  hypotheticalEquityUsd: number;
};

export async function GET() {
  const ledger = readLedger();
  const scenarios = readHistoricalScenarios();

  if (!ledger) {
    return NextResponse.json({ available: false, message: "No paper ledger yet - the Agent hasn't run a cycle." });
  }
  if (!scenarios) {
    return NextResponse.json({
      available: false,
      message: "No historical scenario data yet - run `python -m backtest.run_backtest` from engine/.",
    });
  }

  const records = readDecisionLog(3);
  const markPrices = latestSnapshotPrices(records);
  const currentEquity = computeEquityUsd(ledger, markPrices);

  // underlying (AAPL) -> rtoken symbol (RAAPLUSDT) lookup, since the ledger keys
  // positions by rtoken symbol but historical_scenarios.json keys by underlying.
  const underlyingBySymbol = new Map<string, string>();
  for (const [underlying, data] of Object.entries(scenarios)) {
    underlyingBySymbol.set(data.rtoken_symbol, underlying);
  }

  function buildScenario(id: string, label: string, description: string, pickReturn: (underlying: string) => number | null): Scenario {
    const positions: PositionImpact[] = [];
    let total = 0;

    for (const [symbol, qty] of Object.entries(ledger!.positions)) {
      const underlying = underlyingBySymbol.get(symbol);
      if (!underlying) continue;
      const scenarioReturn = pickReturn(underlying);
      if (scenarioReturn === null) continue;

      const markPrice = markPrices[symbol] ?? ledger!.fills.slice().reverse().find((f) => f.symbol === symbol)?.price ?? 0;
      const currentNotional = qty * markPrice;
      const hypotheticalPnlUsd = currentNotional * scenarioReturn;
      total += hypotheticalPnlUsd;

      positions.push({ underlying, symbol, qty, markPrice, currentNotional, scenarioReturn, hypotheticalPnlUsd });
    }

    return {
      id,
      label,
      description,
      positions,
      totalHypotheticalPnlUsd: total,
      hypotheticalEquityUsd: currentEquity + total,
    };
  }

  const worstPerSymbolScenario = buildScenario(
    "worst-per-symbol",
    "Each position's own worst historical night",
    "Replays each held symbol's single worst overnight return from real ~90-day history against today's position in that symbol.",
    (underlying) => {
      const history = scenarios[underlying]?.history ?? [];
      if (history.length === 0) return null;
      return Math.min(...history.map((d) => d.rtoken_return));
    }
  );

  const marketWideDate = findMarketWideWorstDate(scenarios);
  const marketWideScenario = marketWideDate
    ? buildScenario(
        "market-wide-worst-night",
        `Market-wide worst night (${marketWideDate})`,
        `Replays the actual overnight move each held symbol had on ${marketWideDate} - the single date with the worst average return across the universe, i.e. a real correlated overnight event, not a cherry-picked single-symbol move.`,
        (underlying) => {
          const day = scenarios[underlying]?.history.find((d) => d.date === marketWideDate);
          return day ? day.rtoken_return : null;
        }
      )
    : null;

  return NextResponse.json({
    available: true,
    currentEquityUsd: currentEquity,
    scenarios: [worstPerSymbolScenario, ...(marketWideScenario ? [marketWideScenario] : [])],
  });
}
