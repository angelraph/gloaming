// Mirrors gloaming_agent/agent_loop.py's is_nyse_closed() exactly - same
// weekday + 9:30-16:00 America/New_York window - so the Desk's "is the Agent
// active right now" indicator can never disagree with what the Agent itself
// actually does. Two independent implementations of the same real rule, kept
// deliberately simple (Intl.DateTimeFormat) rather than sharing code across the
// Python/TypeScript boundary.
export function isNyseClosed(now: Date = new Date()): boolean {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/New_York",
    weekday: "short",
    hour: "numeric",
    minute: "numeric",
    hourCycle: "h23",
  }).formatToParts(now);

  const weekday = parts.find((p) => p.type === "weekday")?.value;
  const hour = Number(parts.find((p) => p.type === "hour")?.value ?? 0) % 24;
  const minute = Number(parts.find((p) => p.type === "minute")?.value ?? 0);

  if (weekday === "Sat" || weekday === "Sun") return true;

  const minutesSinceMidnight = hour * 60 + minute;
  const marketOpen = 9 * 60 + 30;
  const marketClose = 16 * 60;
  return !(minutesSinceMidnight >= marketOpen && minutesSinceMidnight < marketClose);
}
