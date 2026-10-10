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
      {/* The numeral scales with the tile's own width (container query units), so a long
          locale-formatted amount such as "US$98,049.06" fits on one line at every width instead
          of being cut off with an ellipsis. */}
      <div className="mt-3" style={{ containerType: "inline-size" }}>
        <div
          className={`font-display whitespace-nowrap leading-none tabular-nums ${valueColor}`}
          style={{ fontSize: "clamp(15px, 12cqi, 34px)" }}
        >
          {value}
        </div>
      </div>
      {sub && <div className="mt-2 text-xs text-text-tertiary">{sub}</div>}
    </div>
  );
}
