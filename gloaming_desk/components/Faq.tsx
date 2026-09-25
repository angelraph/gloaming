import SectionHeader from "@/components/SectionHeader";

type Item = { q: string; a: React.ReactNode };

// Every answer states what is true today, including the limits. Nothing here is a claim
// the decision log, the ledger or the repository docs cannot back up.
const ITEMS: Item[] = [
  {
    q: "What is Gloaming?",
    a: (
      <>
        Bitget rTokens are tokenized US stocks that trade around the clock, while the real
        shares trade about 6.5 hours on weekdays. When NYSE is closed nothing pins an rToken
        to its share. Gloaming is an autonomous agent that watches the gap between where an
        rToken trades and where its real share last closed, adjusted for what live proxies
        (index futures, crypto, FX) have done since, and it works only while NYSE is closed.
      </>
    ),
  },
  {
    q: "Is real money at risk?",
    a: (
      <>
        No. Everything is paper trading on a virtual ledger. Bitget&apos;s demo environment does
        not list rToken symbols (an order for RAAPLUSDT is rejected while BTCUSDT works, checked
        on Sept 11), so fills are simulated against real, live rToken prices. Only the exchange
        accepting the order is simulated: prices, timing, decisions and risk checks are real.
        Fees and slippage are not modeled.
      </>
    ),
  },
  {
    q: "Who makes the trading decisions: an LLM or rules?",
    a: (
      <>
        Qwen3.8-max is the primary decision-maker. For every symbol, every cycle, it sees the
        market snapshot and its own book (its position, net and gross exposure against the caps,
        what the risk layer would approve, its recent fills) and answers buy, sell or hold with a
        reason. A separate, deterministic risk layer can reject or resize any decision. Two
        exceptions are disclosed and always labeled in the decision log: a rule-based fallback if
        Qwen is unavailable, and a backstop that trims exposure if the book stays over its net cap
        for about two hours without Qwen bringing it back.
      </>
    ),
  },
  {
    q: "Why are most decisions holds?",
    a: (
      <>
        The spread is the rToken&apos;s move since the real close minus what the live proxies
        justify. When the rToken is tracking its share, normally within a few tenths of a percent,
        there is nothing to trade and holding is the right answer. Each hold keeps Qwen&apos;s
        reasoning, shown in the timeline, so a quiet night is still explained.
      </>
    ),
  },
  {
    q: "What are the risk controls?",
    a: (
      <>
        <ul className="space-y-1.5">
          <li>Per-symbol cap of 15% of equity, gross exposure cap of 60%, net directional cap of 25%.</li>
          <li>A daily loss breaker at -5%: new risk halts, de-risking is still allowed.</li>
          <li>A per-trade loss cap of 2% of equity, volatility-scaled sizing, and no leverage.</li>
          <li>A $1,000 ceiling on any single decision from the LLM.</li>
        </ul>
        <p className="mt-3">The live meters above show how close the book is to each cap right now.</p>
      </>
    ),
  },
  {
    q: "Has the signal always worked this way?",
    a: (
      <>
        No, and it is disclosed. Until Sept 25 the spread compared the rToken&apos;s rolling 24h
        return with proxy returns measured over different windows (one was a 5-day futures return),
        so it mostly measured the regular session&apos;s own move, not an overnight gap. Against real
        data every rToken sat within about ±0.25% of its share&apos;s last close, while the old
        spreads reached -4.6% and +2.8%. The signal is now anchored to each share&apos;s last
        regular-session close. Records before that were produced by the old signal.
      </>
    ),
  },
  {
    q: "How has it performed?",
    a: (
      <>
        The tiles above are live, so read them there. The record through Sept 25 came from the
        earlier signal, and results since the correction are a short window. Treat it as a running
        experiment, not a proven edge. Earlier, a gap in the risk caps left the book unable to reduce
        itself for about eight days in mid-September; it was found through live operation and fixed
        (see the roadmap).
      </>
    ),
  },
  {
    q: "What is the Bitget signal card?",
    a: (
      <>
        Optional context from Bitget&apos;s public bitget-signal MCP server: crypto sentiment, BTC
        positioning, news and the yield curve. It is wired in and degrades gracefully. Its upstream
        data sources have returned nothing since Sept 22, so the card says so and never fills in a
        placeholder.
      </>
    ),
  },
  {
    q: "Does the Desk place trades?",
    a: (
      <>
        No. It is read-only. The chat answers from the real portfolio and decision data shown on
        this page and never invents numbers. The agent that trades runs separately, on a schedule.
      </>
    ),
  },
  {
    q: "What are the known limitations?",
    a: (
      <>
        Paper fills at the last price with no fees or slippage. The close is modeled as 16:00 ET on
        every trading day, so early closes and holidays are not handled. The blend weights are a
        heuristic prior, not calibrated. Closes, futures and DXY come from Yahoo Finance. The live
        window is short.
      </>
    ),
  },
];

export default function Faq() {
  return (
    <div className="grid gap-10 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] lg:gap-16">
      <div className="lg:sticky lg:top-28 lg:self-start">
        <SectionHeader
          eyebrow="FAQ"
          title="Straight answers, including the uncomfortable ones."
          description="What this is, what it is not, and where it has been wrong. Nothing here overclaims."
        />
      </div>

      <div className="divide-y divide-border-subtle border-y border-border-subtle">
        {ITEMS.map((item, i) => (
          <details key={item.q} className="group py-1" open={i === 0}>
            <summary className="flex items-center justify-between gap-6 py-5">
              <span className="text-[17px] font-medium leading-snug text-heading">{item.q}</span>
              <span
                aria-hidden
                className="faq-plus flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-border text-lg leading-none text-text-secondary transition-transform group-hover:border-border-strong group-hover:text-heading"
              >
                +
              </span>
            </summary>
            <div className="max-w-prose pb-6 text-[15px] leading-relaxed text-text-secondary">{item.a}</div>
          </details>
        ))}
      </div>
    </div>
  );
}
