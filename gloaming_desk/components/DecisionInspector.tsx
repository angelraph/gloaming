"use client";

import { useEffect, useRef } from "react";
import type { DecisionRecord } from "@/lib/data";
import { fmtPct, fmtSignedPct, fmtTime, fmtUsd } from "@/lib/format";

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-border-subtle py-2.5 last:border-0">
      <dt className="text-sm text-text-secondary">{label}</dt>
      <dd className="text-right text-sm tabular-nums text-heading">{value}</dd>
    </div>
  );
}

function opt(n: number | null | undefined, f: (x: number) => string) {
  return n === null || n === undefined ? <span className="text-text-tertiary">not available</span> : f(n);
}

// A modal built on the native <dialog>: showModal() gives focus trapping, Escape to close and
// an inert background for free, so keyboard and screen-reader users are not stranded.
// It shows what the record actually holds: the market inputs, the model's stated reasoning, the
// risk layer's verdict and what execution did. The book context Qwen also sees each cycle
// (its own position and exposure) is not stored per record, and this panel says so.
export default function DecisionInspector({ record, onClose }: { record: DecisionRecord | null; onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (record && !d.open) d.showModal();
    if (!record && d.open) d.close();
  }, [record]);

  const s = record?.snapshot;
  const d = record?.decision;
  const isHold = record && !d && !record.error;
  const reasoning = d?.rationale ?? record?.hold_rationale;
  const execution = record?.execution;

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      onClick={(e) => {
        if (e.target === ref.current) onClose(); // click on the backdrop
      }}
      aria-labelledby="inspector-title"
      className="m-auto w-[min(720px,calc(100vw-24px))] max-h-[88vh] overflow-y-auto rounded-xl border border-border bg-layer-1 p-0 text-text-primary backdrop:bg-black/70"
    >
      {record && (
        <div className="p-5 sm:p-8">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="eyebrow">Decision inspector</p>
              <h2 id="inspector-title" className="font-display mt-3 text-[30px] leading-tight text-heading">
                {record.underlying}{" "}
                <span className={isHold ? "text-text-secondary" : d?.side === "buy" ? "text-mint" : "text-negative"}>
                  {record.error ? "error" : d ? `${d.side} ${fmtUsd(d.notional_usd)}` : "hold"}
                </span>
              </h2>
              <p className="mt-2 text-sm tabular-nums text-text-tertiary">
                {fmtTime(record.timestamp)} · decided by {record.decision_source ?? "unknown"}
              </p>
            </div>
            <button
              type="button"
              onClick={onClose}
              className="min-h-11 shrink-0 rounded-full border border-border px-5 text-sm text-heading transition-colors hover:bg-layer-2"
            >
              Close
            </button>
          </div>

          {record.error ? (
            <p className="mt-6 text-sm text-warning">This cycle recorded an error: {record.error}</p>
          ) : (
            <>
              <section className="mt-7">
                <h3 className="micro-label">The model&apos;s reasoning</h3>
                <p className="mt-3 text-[15px] leading-relaxed text-text-primary">
                  {reasoning ?? "No reasoning was recorded for this decision."}
                </p>
                {d && (
                  <p className="mt-2 text-xs text-text-tertiary">
                    stop-loss {fmtPct(d.stop_loss_pct, 1)} · confidence {fmtPct(d.confidence, 0)}
                  </p>
                )}
              </section>

              {s && (
                <section className="mt-7">
                  <h3 className="micro-label">Market inputs recorded</h3>
                  <dl className="mt-3">
                    <Row label={`${s.rtoken_symbol} last price`} value={fmtUsd(s.rtoken_last_price)} />
                    <Row label="Real share's last close" value={opt(s.real_close_price, fmtUsd)} />
                    <Row label="Hours since that close" value={opt(s.hours_since_close, (n) => n.toFixed(1))} />
                    <Row label="rToken return since close" value={opt(s.rtoken_return_since_close, fmtSignedPct)} />
                    <Row label="Futures proxy return" value={opt(s.futures_proxy_return_since_close, fmtSignedPct)} />
                    <Row label="Crypto proxy return" value={opt(s.crypto_beta_return_since_close, fmtSignedPct)} />
                    <Row label="FX proxy return" value={opt(s.fx_risk_sentiment_return_since_close, fmtSignedPct)} />
                    <Row label="Fair-value return (blend)" value={opt(s.fair_value_return_since_close, fmtSignedPct)} />
                    <Row label="Fair-value price" value={opt(s.fair_value_price, fmtUsd)} />
                    <Row label="Spread" value={<span className="text-heading">{fmtSignedPct(s.spread, 3)}</span>} />
                    <Row label="Recent daily volatility" value={opt(s.recent_daily_volatility, (n) => fmtPct(n))} />
                    <Row label="Signal specification" value={s.signal_spec ?? "earlier rolling-24h signal"} />
                  </dl>
                  {s.missing_proxies && s.missing_proxies.length > 0 && (
                    <p className="mt-2 text-xs text-warning">Missing proxies this cycle: {s.missing_proxies.join(", ")}</p>
                  )}
                  {s.bitget_signal_context && (
                    <p className="mt-3 text-xs text-text-tertiary">
                      Bitget signal context (sentiment, positioning, news, macro) was attached to this cycle.
                    </p>
                  )}
                </section>
              )}

              <section className="mt-7">
                <h3 className="micro-label">Risk layer verdict</h3>
                {record.risk_result ? (
                  <div className="mt-3">
                    <p className={`text-sm font-medium ${record.risk_result.approved ? "text-mint" : "text-negative"}`}>
                      {record.risk_result.approved
                        ? `Approved at ${fmtUsd(record.risk_result.adjusted_notional_usd)}`
                        : "Rejected by the risk layer"}
                    </p>
                    {record.risk_result.reasons.length > 0 && (
                      <ul className="mt-2 list-disc space-y-1.5 pl-5 text-sm text-text-secondary">
                        {record.risk_result.reasons.map((r, i) => (
                          <li key={i}>{r}</li>
                        ))}
                      </ul>
                    )}
                  </div>
                ) : (
                  <p className="mt-3 text-sm text-text-secondary">
                    No trade was proposed, so the risk layer had nothing to approve or reject.
                  </p>
                )}
              </section>

              {execution !== undefined && execution !== null && (
                <section className="mt-7">
                  <h3 className="micro-label">Execution</h3>
                  <p className="mt-3 break-words text-sm text-text-secondary">
                    {typeof execution === "string"
                      ? execution
                      : `Paper fill recorded: ${(execution as { qty?: number; price?: number }).qty ?? "?"} @ ${
                          (execution as { price?: number }).price ?? "?"
                        }`}
                  </p>
                </section>
              )}

              <p className="mt-7 border-t border-border-subtle pt-4 text-xs leading-relaxed text-text-tertiary">
                Qwen is also shown its own book each cycle (its position, exposure against the caps and recent
                fills). That context is not stored per record yet, so it is not shown here.
              </p>
            </>
          )}
        </div>
      )}
    </dialog>
  );
}
