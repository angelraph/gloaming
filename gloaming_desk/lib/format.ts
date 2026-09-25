export function fmtUsd(n: number) {
  return n.toLocaleString(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 2 });
}

export function fmtSignedUsd(n: number) {
  return `${n >= 0 ? "+" : "-"}${fmtUsd(Math.abs(n))}`;
}

// Fractions in, percent strings out: 0.0123 -> "1.23%".
export function fmtPct(n: number, digits = 2) {
  return `${(n * 100).toFixed(digits)}%`;
}

export function fmtSignedPct(n: number, digits = 2) {
  return `${n >= 0 ? "+" : "-"}${(Math.abs(n) * 100).toFixed(digits)}%`;
}

export function fmtTime(iso: string) {
  return new Date(iso).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function fmtDate(iso: string) {
  return new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}
