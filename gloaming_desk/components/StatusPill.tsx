"use client";

import { useEffect, useState } from "react";

type Status = { nyseClosed: boolean; agentActive: boolean; serverTimeUtc: string };

// Mint is a live signal, so this is the one place the pill is coloured: only while the
// agent is actually working (NYSE closed). Idle is a quiet neutral, never a warning.
export default function StatusPill() {
  const [status, setStatus] = useState<Status | null>(null);

  useEffect(() => {
    function load() {
      fetch("/api/status")
        .then((r) => r.json())
        .then(setStatus)
        .catch(() => {});
    }
    load();
    const interval = setInterval(load, 60_000); // real market-hours boundary, worth rechecking periodically
    return () => clearInterval(interval);
  }, []);

  if (!status) return null;

  return (
    <span
      className={
        status.agentActive
          ? "inline-flex items-center gap-2 whitespace-nowrap rounded-full border border-mint/40 bg-mint-soft px-3 py-1.5 text-xs font-medium text-mint"
          : "inline-flex items-center gap-2 whitespace-nowrap rounded-full border border-border-subtle px-3 py-1.5 text-xs font-medium text-text-secondary"
      }
    >
      <span
        className={
          status.agentActive ? "h-1.5 w-1.5 animate-pulse rounded-full bg-mint" : "h-1.5 w-1.5 rounded-full bg-text-tertiary"
        }
      />
      {status.agentActive ? "Agent live: NYSE closed" : "Agent idle: NYSE open"}
    </span>
  );
}
