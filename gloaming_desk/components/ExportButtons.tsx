const ITEMS = [
  { dataset: "fills", format: "csv", label: "Fills (CSV)", hint: "the whole paper ledger" },
  { dataset: "fills", format: "json", label: "Fills (JSON)", hint: "the whole paper ledger" },
  { dataset: "decisions", format: "csv", label: "Decisions (CSV)", hint: "the most recent ~500 records" },
  { dataset: "decisions", format: "json", label: "Decisions (JSON)", hint: "the most recent ~500 records" },
];

export default function ExportButtons() {
  return (
    <ul className="flex flex-wrap gap-3">
      {ITEMS.map((i) => (
        <li key={`${i.dataset}-${i.format}`}>
          <a
            href={`/api/export?dataset=${i.dataset}&format=${i.format}`}
            download
            className="inline-flex min-h-11 items-center rounded-full border border-border px-5 text-sm text-heading transition-colors hover:bg-layer-2"
          >
            {i.label}
            <span className="sr-only">, {i.hint}</span>
          </a>
        </li>
      ))}
    </ul>
  );
}
