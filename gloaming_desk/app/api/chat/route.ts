import { NextResponse } from "next/server";
import OpenAI from "openai";
import { readDecisionLog, readLedger, computeEquityUsd, latestSnapshotPrices } from "@/lib/data";

const SYSTEM_PROMPT = `You are the research assistant behind the Gloaming Desk, a dashboard for a
trading agent that manages Bitget rTokens (tokenized US stocks) overnight, while the real
NYSE/Nasdaq is closed. You answer a human trader's questions about what happened overnight
and why, using ONLY the portfolio and decision-log data given to you in this message - never
invent numbers. You never place trades or recommend the Desk auto-execute anything; you
explain and let the human decide. Keep answers concise and reference actual figures from the
data you were given.`;

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

  const ledger = readLedger();
  const records = readDecisionLog(3);
  const markPrices = latestSnapshotPrices(records);
  const equityUsd = ledger ? computeEquityUsd(ledger, markPrices) : null;

  const recentEvents = records
    .filter((r) => r.underlying !== null && (r.decision || r.error))
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
