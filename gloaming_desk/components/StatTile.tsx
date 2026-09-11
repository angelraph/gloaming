export default function StatTile({
  label,
  value,
  sub,
  tone = "neutral",
}: {
  label: string;
  value: string;
  sub?: string;
  tone?: "neutral" | "positive" | "negative";
}) {
  const valueColor =
    tone === "positive" ? "text-positive" : tone === "negative" ? "text-negative" : "text-text-primary";

  return (
    <div className="rounded-lg border border-border-subtle bg-layer-1 p-3.5 sm:p-4">
      <div className="text-[11px] uppercase tracking-wide text-text-tertiary">{label}</div>
      <div className={`mt-1 truncate font-mono text-xl font-medium tabular-nums sm:text-2xl ${valueColor}`}>
        {value}
      </div>
      {sub && <div className="mt-1 text-xs text-text-tertiary">{sub}</div>}
    </div>
  );
}
