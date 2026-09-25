import { NextResponse } from "next/server";
import OpenAI from "openai";
import { readDecisionLog, readLedger, computeEquityUsd, latestSnapshotPrices } from "@/lib/data";

const SYSTEM_PROMPT = `You are the research assistant behind the Gloaming Desk, a dashboard for a
trading agent that manages Bitget rTokens (tokenized US stocks) overnight, while the real
NYSE/Nasdaq is closed. You answer a human trader's questions about what happened overnight
and why, using ONLY the portfolio and decision-log data given to you in this message - never
invent numbers. You never place trades or recommend the Desk auto-execute anything; you
explain and let the human decide. Keep answers concise and reference actual figures from the
data you were given.

How to read the data: the agent's signal is anchored to where each real share last closed
(16:00 ET). For a decision whose snapshot has signal_spec "since_last_close_v2", "spread" is
the rToken's return since that close minus the blended return since that close of the live
proxies (index futures, crypto, FX), and it is normally only a few tenths of a percent, so
most decisions are holds; a hold record carries Qwen's reasoning in hold_rationale. Decision
records from before Sept 25 have no signal_spec: they compared the rToken's rolling 24h
return with mismatched proxy windows, which mostly measured the regular session's own move,
so do not present their spreads as overnight mispricings.`;

export async function POST(request: Request) {
  const apiKey = process.env.QWEN_API_KEY;
  if (!apiKey) {
    // Locally this comes from the repo-root .env (see next.config.ts); on Vercel
    // it has to be set as a project environment variable instead, since only this
    // subdirectory gets deployed - one message covers both without guessing which
    // environment is asking.
    return NextResponse.json(
      { error: "QWEN_API_KEY is not configured for this environment yet." },
      { status: 503 }
    );
  }

  const { message } = (await request.json()) as { message: string };
  if (!message || typeof message !== "string") {
    return NextResponse.json({ error: "message is required" }, { status: 400 });
  }

  const ledger = await readLedger();
  const records = await readDecisionLog(3);
  const markPrices = latestSnapshotPrices(records);
  const equityUsd = ledger ? computeEquityUsd(ledger, markPrices) : null;

  const recentEvents = records
    .filter((r) => r.underlying !== null && (r.decision || r.error || r.hold_rationale))
    .sort((a, b) => b.timestamp.localeCompare(a.timestamp))
    .slice(0, 15);

  const contextText = JSON.stringify(
    {
      portfolio: ledger
        ? { cashUsd: ledger.cash_usd, equityUsd, positions: ledger.positions, fills: ledger.fills.slice(-10) }
        : null,
      recentDecisions: recentEvents,
    },
    null,
    2
  );

  const client = new OpenAI({
    baseURL: process.env.QWEN_BASE_URL || "https://hackathon.bitgetops.com/v1",
    apiKey,
  });

  try {
    const completion = await client.chat.completions.create({
      model: process.env.QWEN_MODEL || "qwen3.8-max",
      messages: [
        { role: "system", content: SYSTEM_PROMPT },
        { role: "user", content: `Current data:\n${contextText}\n\nQuestion: ${message}` },
      ],
      temperature: 0.3,
    });

    const answer = completion.choices[0]?.message?.content ?? "No response generated.";
    return NextResponse.json({ answer });
  } catch (err) {
    return NextResponse.json({ error: `Qwen call failed: ${String(err)}` }, { status: 502 });
  }
}
