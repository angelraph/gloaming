import { Redis } from "@upstash/redis";

// Explicit client, not Redis.fromEnv() - that helper looks for
// UPSTASH_REDIS_REST_URL/TOKEN by convention, but Vercel's KV integration names
// these KV_REST_API_URL/KV_REST_API_TOKEN (confirmed Sept 11, see .env.example) -
// fromEnv() would silently find nothing and this whole sync would look
// "configured" while never actually connecting. Null when not configured, so
// callers can cleanly fall back to local files (see lib/data.ts).
export const redis =
  process.env.KV_REST_API_URL && process.env.KV_REST_API_TOKEN
    ? new Redis({ url: process.env.KV_REST_API_URL, token: process.env.KV_REST_API_TOKEN })
    : null;

export const KEYS = {
  decisionLog: "gloaming:decision_log",
  ledger: "gloaming:paper_ledger",
  historicalScenarios: "gloaming:historical_scenarios",
} as const;
