import fs from "fs";
import path from "path";

// Reads directly from the same files gloaming_agent/agent_loop.py writes -
// decision_log/*.jsonl (the event -> decision -> execution trail) and
// paper_ledger.json (current portfolio state). No separate FastAPI/SQLite layer:
// the data already exists in real, verified form on disk, so re-serving it
// through another service would just be an extra moving part with nothing to
// show for it. See docs/architecture.md for the full reasoning.

const REPO_ROOT = path.resolve(process.cwd(), "..");
const DECISION_LOG_DIR = path.join(REPO_ROOT, "gloaming_agent", "decision_log");
const LEDGER_PATH = path.join(REPO_ROOT, "gloaming_agent", "paper_ledger.json");
const HISTORICAL_SCENARIOS_PATH = path.join(
  REPO_ROOT, "alpha_factory", "results", "historical_scenarios.json"
);

export type DecisionRecord = {
  timestamp: string;
  underlying: string | null;
  decision_source?: string;
  snapshot?: {
    rtoken_symbol: string;
    rtoken_last_price: number;
    rtoken_pcnt_24h: number;
    futures_proxy_pcnt_24h: number;
    crypto_beta_pcnt_24h: number;
    fx_risk_sentiment_pcnt_24h: number;
    fair_value_return_24h: number;
    spread: number;
  };
  decision?: {
    symbol: string;
    side: string;
    notional_usd: number;
    rationale: string;
    stop_loss_pct: number;
    confidence: number;
  } | null;
  risk_result?: {
    approved: boolean;
    adjusted_notional_usd: number;
    reasons: string[];
  } | null;
  execution?: unknown;
  error?: string;
};

export type LedgerState = {
  cash_usd: number;
  positions: Record<string, number>;
  fills: Array<{
    timestamp: string;
    symbol: string;
    side: string;
    qty: number;
    price: number;
    notional_usd: number;
    rationale: string;
  }>;
  equity_at_day_start_usd: number;
  day_start_date: string;
};

export function readLedger(): LedgerState | null {
  try {
    const raw = fs.readFileSync(LEDGER_PATH, "utf-8");
    return JSON.parse(raw) as LedgerState;
  } catch {
    return null; // ledger doesn't exist yet - agent hasn't run, not an error state
  }
}

export function readDecisionLog(days: number = 3): DecisionRecord[] {
  if (!fs.existsSync(DECISION_LOG_DIR)) return [];

  const files = fs
    .readdirSync(DECISION_LOG_DIR)
    .filter((f) => f.endsWith(".jsonl"))
    .sort()
    .slice(-days);

  const records: DecisionRecord[] = [];
  for (const file of files) {
    const content = fs.readFileSync(path.join(DECISION_LOG_DIR, file), "utf-8");
    for (const line of content.trim().split("\n")) {
      if (!line) continue;
      try {
        records.push(JSON.parse(line) as DecisionRecord);
      } catch {
        // one malformed line shouldn't break the whole timeline
      }
    }
  }
  return records;
}

// Most recent live price per symbol from the decision log's snapshots - fresher
// than a fill price when the Agent checked a symbol but did not trade it this
// cycle (every cycle logs a snapshot for every symbol, decision or not).
export function latestSnapshotPrices(records: DecisionRecord[]): Record<string, number> {
  const prices: Record<string, number> = {};
  const sorted = [...records].sort((a, b) => a.timestamp.localeCompare(b.timestamp));
  for (const r of sorted) {
    if (r.snapshot) prices[r.snapshot.rtoken_symbol] = r.snapshot.rtoken_last_price;
  }
  return prices;
}

// Last real fill price per symbol - used as the mark when no fresher live price
// is available to the Desk (it doesn't shell out to bgc itself; the Agent's own
// live snapshots, visible via the decision log, are the fresher source when
// present). Same fallback convention as paper_ledger.py's Python side.
export function lastFillPrices(ledger: LedgerState): Record<string, number> {
  const prices: Record<string, number> = {};
  for (const fill of ledger.fills) {
    prices[fill.symbol] = fill.price; // later fills overwrite earlier ones
  }
  return prices;
}

export function computeEquityUsd(ledger: LedgerState, markPrices: Record<string, number>): number {
  const marks = { ...lastFillPrices(ledger), ...markPrices }; // live marks win when supplied
  let positionsValue = 0;
  for (const [symbol, qty] of Object.entries(ledger.positions)) {
    const price = marks[symbol];
    if (price !== undefined) positionsValue += qty * price;
  }
  return ledger.cash_usd + positionsValue;
}

// Real per-day (return, spread) history per underlying, exported by
// engine/backtest/run_backtest.py from the SAME ~90-day live rToken history the
// Alpha Factory backtest uses - not invented or synthetic scenarios. Regenerate
// with `python -m backtest.run_backtest` from engine/.
export type HistoricalDay = { date: string; rtoken_return: number; spread_pct: number };
export type HistoricalScenarios = Record<string, { rtoken_symbol: string; history: HistoricalDay[] }>;

export function readHistoricalScenarios(): HistoricalScenarios | null {
  try {
    const raw = fs.readFileSync(HISTORICAL_SCENARIOS_PATH, "utf-8");
    return JSON.parse(raw) as HistoricalScenarios;
  } catch {
    return null; // hasn't been generated yet - not an error state, just not run
  }
}

// The single historical date with the worst AVERAGE return across the whole
// universe - found from the data itself, not hardcoded, so it stays correct as
// the backtest is regenerated with fresh history. This is a genuine correlated
// overnight event (several symbols independently show it as their own worst day),
// not a cherry-picked one-symbol move.
export function findMarketWideWorstDate(scenarios: HistoricalScenarios): string | null {
  const returnsByDate = new Map<string, number[]>();
  for (const { history } of Object.values(scenarios)) {
    for (const day of history) {
      const arr = returnsByDate.get(day.date) ?? [];
      arr.push(day.rtoken_return);
      returnsByDate.set(day.date, arr);
    }
  }
  let worstDate: string | null = null;
  let worstAvg = Infinity;
  for (const [date, returns] of returnsByDate) {
    if (returns.length < 2) continue; // need at least 2 symbols for "market-wide"
    const avg = returns.reduce((a, b) => a + b, 0) / returns.length;
    if (avg < worstAvg) {
      worstAvg = avg;
      worstDate = date;
    }
  }
  return worstDate;
}
