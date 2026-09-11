"use client";

import { useEffect, useState } from "react";

type Status = { nyseClosed: boolean; agentActive: boolean; serverTimeUtc: string };

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
          ? "inline-flex items-center gap-1.5 rounded-full bg-positive-soft px-2.5 py-1 text-xs font-medium text-positive"
          : "inline-flex items-center gap-1.5 rounded-full bg-layer-2 px-2.5 py-1 text-xs font-medium text-text-tertiary"
      }
    >
      <span
        className={
          status.agentActive ? "h-1.5 w-1.5 animate-pulse rounded-full bg-positive" : "h-1.5 w-1.5 rounded-full bg-text-tertiary"
        }
      />
      {status.agentActive ? "Agent active - NYSE closed" : "Agent idle - NYSE open"}
    </span>
  );
}
