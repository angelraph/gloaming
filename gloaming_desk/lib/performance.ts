import type { LedgerState } from "@/lib/data";

// Paper-trading performance, derived ONLY from the ledger's real fills. No invented series.
//
// Method (also shown on the Performance page):
//   - Equity is re-marked at every fill, using each symbol's most recent FILL price as its
//     mark. The Desk holds no continuous price history, so between fills equity does not move
//     and intraday drawdown is understated. The final point uses live marks.
//   - Realized P&L uses average cost per symbol, with signed quantities (the book can be
//     short). A "closing fill" is any fill that reduces an open position.
//   - Win rate is the share of closing fills that realized a gain, not of round trips.
//   - Sharpe uses one equity value per UTC day (the last one that day, carried flat through
//     days with no fills), annualized with sqrt(365) because the agent trades nights and
//     weekends. With a short window it is indicative only, and the page says so beside it.

export type EquityPoint = { t: string; equity: number };

export type PerformanceSummary = {
  startingEquityUsd: number;
  currentEquityUsd: number;
  totalReturn: number;
  realizedPnlUsd: number;
  closingFills: number;
  winningFills: number;
  winRate: number | null;
  maxDrawdown: number;
  sharpe: number | null;
  observedDays: number;
  dailyReturnsCount: number;
  totalFills: number;
  firstFillAt: string | null;
  lastFillAt: string | null;
  bySymbol: Array<{ symbol: string; fills: number; realizedPnlUsd: number }>;
  curve: EquityPoint[];
};

export function computePerformance(
  ledger: LedgerState,
  liveMarks: Record<string, number>,
  startingEquityUsd = 100_000
): PerformanceSummary {
  let cash = startingEquityUsd;
  const pos: Record<string, number> = {};
  const avg: Record<string, number> = {};
  const marks: Record<string, number> = {};
  const per: Record<string, { fills: number; realizedPnlUsd: number }> = {};
  let realized = 0;
  let closing = 0;
  let winning = 0;
  const curve: EquityPoint[] = [];

  const equityNow = (m: Record<string, number>) =>
    cash + Object.entries(pos).reduce((s, [sym, q]) => s + (m[sym] !== undefined ? q * m[sym] : 0), 0);

  for (const f of ledger.fills) {
    const dq = f.side === "buy" ? f.qty : -f.qty;
    cash += f.side === "buy" ? -f.notional_usd : f.notional_usd;
    const p = pos[f.symbol] ?? 0;
    const a = avg[f.symbol] ?? 0;
    per[f.symbol] ??= { fills: 0, realizedPnlUsd: 0 };
    per[f.symbol].fills += 1;

    if (p === 0 || Math.sign(p) === Math.sign(dq)) {
      avg[f.symbol] = (Math.abs(p) * a + Math.abs(dq) * f.price) / (Math.abs(p) + Math.abs(dq));
      pos[f.symbol] = p + dq;
    } else {
      const closed = Math.min(Math.abs(p), Math.abs(dq));
      const pnl = closed * (f.price - a) * Math.sign(p);
      realized += pnl;
      per[f.symbol].realizedPnlUsd += pnl;
      closing += 1;
      if (pnl > 0) winning += 1;
      pos[f.symbol] = p + dq;
      if (Math.abs(dq) > Math.abs(p)) avg[f.symbol] = f.price; // flipped through zero: new cost basis
    }
    marks[f.symbol] = f.price;
    curve.push({ t: f.timestamp, equity: equityNow(marks) });
  }

  const currentEquity = equityNow({ ...marks, ...liveMarks });
  curve.push({ t: new Date().toISOString(), equity: currentEquity });

  // max drawdown on the marked curve
  let peak = startingEquityUsd;
  let maxDd = 0;
  for (const pt of curve) {
    peak = Math.max(peak, pt.equity);
    maxDd = Math.max(maxDd, (peak - pt.equity) / peak);
  }

  // one equity value per UTC day -> daily returns -> Sharpe
  const dayEnd = new Map<string, number>();
  for (const pt of curve) dayEnd.set(pt.t.slice(0, 10), pt.equity);
  // every calendar day from the first fill to today, carrying the last value through days
  // with no fills (equity is only re-marked at fills, so those days are flat by construction)
  const sortedDays = [...dayEnd.keys()].sort();
  const returns: number[] = [];
  let prev = startingEquityUsd;
  if (sortedDays.length > 0) {
    const end = new Date(`${sortedDays[sortedDays.length - 1]}T00:00:00Z`).getTime();
    for (let t = new Date(`${sortedDays[0]}T00:00:00Z`).getTime(); t <= end; t += 86_400_000) {
      const v = dayEnd.get(new Date(t).toISOString().slice(0, 10)) ?? prev;
      returns.push(v / prev - 1);
      prev = v;
    }
  }
  let sharpe: number | null = null;
  if (returns.length >= 5) {
    const mean = returns.reduce((s, r) => s + r, 0) / returns.length;
    const variance = returns.reduce((s, r) => s + (r - mean) ** 2, 0) / (returns.length - 1);
    const sd = Math.sqrt(variance);
    if (sd > 0) sharpe = (mean / sd) * Math.sqrt(365);
  }

  const first = ledger.fills[0]?.timestamp ?? null;
  const last = ledger.fills[ledger.fills.length - 1]?.timestamp ?? null;
  const observedDays = first ? Math.max(1, Math.ceil((Date.now() - new Date(first).getTime()) / 86_400_000)) : 0;

  return {
    startingEquityUsd,
    currentEquityUsd: currentEquity,
    totalReturn: currentEquity / startingEquityUsd - 1,
    realizedPnlUsd: realized,
    closingFills: closing,
    winningFills: winning,
    winRate: closing > 0 ? winning / closing : null,
    maxDrawdown: maxDd,
    sharpe,
    observedDays,
    dailyReturnsCount: returns.length,
    totalFills: ledger.fills.length,
    firstFillAt: first,
    lastFillAt: last,
    bySymbol: Object.entries(per)
      .map(([symbol, v]) => ({ symbol, ...v }))
      .sort((a, b) => b.realizedPnlUsd - a.realizedPnlUsd),
    curve,
  };
}
