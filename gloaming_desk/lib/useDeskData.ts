"use client";

import { useCallback, useEffect, useState } from "react";
import type { DecisionRecord } from "@/lib/data";

export type Portfolio = {
  configured: boolean;
  message?: string;
  cashUsd?: number;
  equityUsd?: number;
  dailyPnlUsd?: number;
  positions?: Array<{
    symbol: string;
    qty: number;
    markPrice: number | null;
    notionalUsd: number | null;
    lastFillPrice: number | null;
  }>;
  totalFills?: number;
};

// One shared polling hook, so every page gets the same loading, error and refresh behavior
// (real data changes as the agent trades; 30s matches how often a cycle can land).
export function useDeskData(pollMs = 30_000) {
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [events, setEvents] = useState<DecisionRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const load = useCallback(async () => {
    try {
      const [p, t] = await Promise.all([
        fetch("/api/portfolio").then((r) => {
          if (!r.ok) throw new Error(`portfolio ${r.status}`);
          return r.json();
        }),
        fetch("/api/timeline?days=3").then((r) => {
          if (!r.ok) throw new Error(`timeline ${r.status}`);
          return r.json();
        }),
      ]);
      setPortfolio(p);
      setEvents(t.events ?? []);
      setError(null);
      setLastUpdated(new Date());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load data");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const interval = setInterval(load, pollMs);
    return () => clearInterval(interval);
  }, [load, pollMs]);

  return { portfolio, events, loading, error, lastUpdated, reload: load };
}
