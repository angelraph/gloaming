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
          ? "inline-flex items-center gap-1.5 rounded-full bg-emerald-950/60 px-2.5 py-1 text-xs font-medium text-emerald-300"
          : "inline-flex items-center gap-1.5 rounded-full bg-neutral-800 px-2.5 py-1 text-xs font-medium text-neutral-400"
      }
    >
      <span
        className={
          status.agentActive ? "h-1.5 w-1.5 rounded-full bg-emerald-400" : "h-1.5 w-1.5 rounded-full bg-neutral-500"
        }
      />
      {status.agentActive ? "Agent active - NYSE closed" : "Agent idle - NYSE open"}
    </span>
  );
}
