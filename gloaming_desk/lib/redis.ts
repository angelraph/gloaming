import { Redis } from "@upstash/redis";

// The Redis mirror is OFF by default since 2026-10-21. Its writes started failing with 403
// Forbidden that day, and a mirror that is stale but readable would show old numbers without
// any error, which is worse than no mirror. The Desk now reads the committed files from the
// public repository instead (see lib/data.ts), which are written every cycle and are the
// source of truth anyway. Set GLOAMING_USE_REDIS=1 together with the KV variables to switch the
// mirror back on.
//
// Explicit client, not Redis.fromEnv() - that helper looks for
// UPSTASH_REDIS_REST_URL/TOKEN by convention, but Vercel's KV integration names
// these KV_REST_API_URL/KV_REST_API_TOKEN (confirmed Sept 11, see .env.example).
// Null when not enabled, so callers fall back to the repository files.
export const redis =
  process.env.GLOAMING_USE_REDIS === "1" && process.env.KV_REST_API_URL && process.env.KV_REST_API_TOKEN
    ? new Redis({ url: process.env.KV_REST_API_URL, token: process.env.KV_REST_API_TOKEN })
    : null;

export const KEYS = {
  decisionLog: "gloaming:decision_log",
  ledger: "gloaming:paper_ledger",
  historicalScenarios: "gloaming:historical_scenarios",
  fillVerification: "gloaming:fill_verification",
} as const;
