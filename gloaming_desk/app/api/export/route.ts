import { NextResponse } from "next/server";
import { readDecisionLog, readLedger } from "@/lib/data";
import { computePerformance } from "@/lib/performance";

export const dynamic = "force-dynamic";

// Downloadable records: ?dataset=fills|decisions&format=csv|json.
// fills = the full paper ledger; decisions = what the live mirror holds (the most recent ~500
// records). The complete decision history is committed to the public repository every cycle.

// Spreadsheet apps execute a cell that starts with = + - @, and the rationale text is model
// output, so neutralize those with a leading apostrophe.
function csvCell(v: unknown): string {
  let s = v === null || v === undefined ? "" : String(v);
  if (/^[=+\-@\t\r]/.test(s)) s = `'${s}`;
  return `"${s.replace(/"/g, '""')}"`;
}

function toCsv(rows: Array<Record<string, unknown>>): string {
  if (rows.length === 0) return "";
  const cols = Object.keys(rows[0]);
  return [cols.join(","), ...rows.map((r) => cols.map((c) => csvCell(r[c])).join(","))].join("\n");
}

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const dataset = searchParams.get("dataset") === "decisions" ? "decisions" : "fills";
  const format = searchParams.get("format") === "json" ? "json" : "csv";

  let rows: Array<Record<string, unknown>>;
  if (dataset === "fills") {
    const ledger = await readLedger();
    // Running balance after each fill: cash exactly as the ledger keeps it (costs included), and
    // equity re-marked at each symbol's latest fill price (the same basis as the Performance page).
    const curve = ledger ? computePerformance(ledger, {}).curve : [];
    let cash = 100_000;
    rows = (ledger?.fills ?? []).map((f, i) => {
      cash += (f.side === "buy" ? -f.notional_usd : f.notional_usd) - (f.cost_usd ?? 0);
      return {
        timestamp: f.timestamp,
        symbol: f.symbol,
        side: f.side,
        qty: f.qty,
        price: f.price,
        notional_usd: f.notional_usd,
        cost_usd: f.cost_usd ?? 0,
        cash_balance_usd: Math.round(cash * 100) / 100,
        equity_marked_at_fills_usd: Math.round((curve[i]?.equity ?? 0) * 100) / 100,
        rationale: f.rationale,
      };
    });
  } else {
    const records = await readDecisionLog(3);
    rows = records
      .filter((r) => r.underlying)
      .map((r) => ({
        timestamp: r.timestamp,
        underlying: r.underlying,
        decision_source: r.decision_source ?? "",
        action: r.error ? "error" : r.decision ? r.decision.side : "hold",
        notional_usd: r.decision?.notional_usd ?? "",
        risk_approved: r.risk_result ? r.risk_result.approved : "",
        spread: r.snapshot?.spread ?? "",
        signal_spec: r.snapshot?.signal_spec ?? "",
        rationale: r.decision?.rationale ?? r.hold_rationale ?? r.error ?? "",
      }));
  }

  const stamp = new Date().toISOString().slice(0, 10);
  const filename = `gloaming-${dataset}-${stamp}.${format}`;
  const body = format === "json" ? JSON.stringify(rows, null, 2) : toCsv(rows);
  return new NextResponse(body, {
    headers: {
      "Content-Type": format === "json" ? "application/json" : "text/csv; charset=utf-8",
      "Content-Disposition": `attachment; filename="${filename}"`,
    },
  });
}
