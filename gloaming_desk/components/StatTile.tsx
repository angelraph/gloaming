// A numeric proof point: micro-label above, serif numeral below. `live` puts a mint hairline
// around the tile, reserved for cards that carry live, money-bearing numbers.
export default function StatTile({
  label,
  value,
  sub,
  tone = "neutral",
  live = false,
}: {
  label: string;
  value: string;
  sub?: string;
  tone?: "neutral" | "positive" | "negative";
  live?: boolean;
}) {
  const valueColor =
    tone === "positive" ? "text-positive" : tone === "negative" ? "text-negative" : "text-heading";

  return (
    <div
      className={`rounded-xl border bg-layer-1 p-4 sm:p-5 ${live ? "border-mint/70" : "border-border-subtle"}`}
    >
      <div className="micro-label">{label}</div>
      <div className={`font-display mt-3 truncate text-[28px] leading-none tabular-nums sm:text-[34px] ${valueColor}`}>
        {value}
      </div>
      {sub && <div className="mt-2 text-xs text-text-tertiary">{sub}</div>}
    </div>
  );
}
