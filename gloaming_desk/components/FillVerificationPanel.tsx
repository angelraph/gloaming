"use client";

import { useEffect, useState } from "react";
import type { FillCheck, FillVerification } from "@/lib/data";
import { fmtDate } from "@/lib/format";
import { underlyingFromRtoken } from "@/lib/universe";
import StatTile from "@/components/StatTile";

type Resp =
  | { configured: false }
  | { configured: true; summary: FillVerification["summary"]; exceptions: FillCheck[]; sample: FillCheck[] };

const SCRIPT_URL = "https://github.com/angelraph/gloaming/blob/master/gloaming_agent/verify_fills.py";
const RESULT_URL = "https://github.com/angelraph/gloaming/blob/master/gloaming_agent/fill_verification.json";

function utcMinute(iso: string): string {
  return new Date(iso).toISOString().slice(0, 16).replace("T", " ") + " UTC";
}

export default function FillVerificationPanel() {
  const [data, setData] = useState<Resp | null>(null);

  useEffect(() => {
    fetch("/api/fill-verification")
      .then((r) => (r.ok ? r.json() : { configured: false }))
      .then(setData)
      .catch(() => setData({ configured: false }));
  }, []);

  if (!data) return <div aria-hidden className="h-[112px] animate-pulse rounded-xl border border-border-subtle bg-layer-1" />;
  if (!data.configured) {
    return <p className="text-sm text-text-secondary">The check has not been published yet.</p>;
  }

  const s = data.summary;
  const staleAfter = s.stale_after_minutes ?? 15;
  const stale = s.stale ?? data.exceptions.filter((f) => f.status === "matched").length;
  const rows: Array<[string, FillCheck]> = [
    ...data.exceptions.map((f) => ["exception", f] as [string, FillCheck]),
    ...data.sample.map((f) => ["sample", f] as [string, FillCheck]),
  ];

  return (
    <>
      <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-3">
        <StatTile
          label="Matched Bitget"
          value={`${s.matched} of ${s.checked}`}
          tone={s.matched === s.checked ? "positive" : undefined}
          sub={
            s.pending > 0
              ? `fill price inside a real Bitget minute's traded range; ${s.pending} more still to be checked`
              : "fill price inside a real Bitget minute's traded range"
          }
        />
        <StatTile
          label="Did not match"
          value={String(s.mismatch + s.no_data)}
          tone={s.mismatch + s.no_data > 0 ? "negative" : undefined}
          sub={`${s.mismatch} outside every minute's range, ${s.no_data} with no candles; listed below`}
        />
        <StatTile
          label="Stale price"
          value={String(stale)}
          sub={`matched, but the last Bitget trade at that price was over ${staleAfter} min before the fill (median ${s.median_lag_minutes ?? "n/a"} min). Listed below`}
        />
      </div>

      {rows.length > 0 && (
        <div className="mt-6 overflow-x-auto rounded-xl border border-border-subtle bg-layer-1">
          <table className="w-full min-w-[640px] text-left text-sm">
            <caption className="sr-only">Fills compared with Bitget 1-minute candles</caption>
            <thead>
              <tr className="border-b border-border-subtle">
                <th scope="col" className="micro-label px-4 py-3 font-normal">Fill</th>
                <th scope="col" className="micro-label px-4 py-3 font-normal">Symbol</th>
                <th scope="col" className="micro-label px-4 py-3 text-right font-normal">Fill price</th>
                <th scope="col" className="micro-label px-4 py-3 text-right font-normal">Bitget minute low to high</th>
                <th scope="col" className="micro-label px-4 py-3 font-normal">Result</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(([kind, f]) => (
                <tr key={f.key} className="border-b border-border-subtle last:border-0">
                  <td className="px-4 py-3 tabular-nums text-text-secondary">{utcMinute(f.timestamp)}</td>
                  <th scope="row" className="px-4 py-3 font-medium text-heading">
                    {underlyingFromRtoken(f.symbol)} <span className="font-normal text-text-tertiary">{f.side}</span>
                  </th>
                  <td className="px-4 py-3 text-right tabular-nums text-heading">{f.price}</td>
                  <td className="px-4 py-3 text-right tabular-nums text-text-secondary">
                    {f.candle_low !== undefined ? `${f.candle_low} to ${f.candle_high}` : "none"}
                  </td>
                  <td className={`px-4 py-3 ${kind === "exception" ? "text-warning" : "text-positive"}`}>
                    {f.status === "matched"
                      ? kind === "exception"
                        ? `stale: last traded ${f.lag_minutes} min before, ${utcMinute(f.candle_minute!)}`
                        : `matched, ${utcMinute(f.candle_minute!)}`
                      : f.status === "mismatch"
                        ? `${f.nearest_bp} bp outside the nearest minute`
                        : "Bitget returned no candles"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <p className="mt-4 max-w-3xl text-sm leading-relaxed text-text-secondary">
        {data.exceptions.length > 0
          ? "Every fill that did not match or matched only a stale price is listed above, followed by the five most recent clean matches. Bitget leaves out minutes with no trades, so on a quiet night the last trade can be hours old. "
          : "The five most recent fills are shown above. "}
        The candles come from Bitget&apos;s public market-data endpoint, which needs no account or key, so anyone can
        rerun the{" "}
        <a href={SCRIPT_URL} target="_blank" rel="noreferrer" className="text-copper underline-offset-4 hover:underline">
          checking script
        </a>{" "}
        or read{" "}
        <a href={RESULT_URL} target="_blank" rel="noreferrer" className="text-copper underline-offset-4 hover:underline">
          the result for every fill
        </a>
        . A match shows the price really traded on Bitget at that time. It does not mean an order was placed: these
        are paper fills, and a real order of the same size could have filled at a slightly different price.
      </p>
    </>
  );
}
