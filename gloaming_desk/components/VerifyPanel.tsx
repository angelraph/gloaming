import { REPO_URL } from "@/lib/nav";

const LINKS = [
  {
    label: "Every cycle's decision log",
    detail: "Committed to the repository after each 15-minute cycle, one JSON record per symbol.",
    href: `${REPO_URL}/tree/master/gloaming_agent/decision_log`,
  },
  {
    label: "The paper ledger",
    detail: "Every fill, cash and position, as the agent's own file.",
    href: `${REPO_URL}/blob/master/gloaming_agent/paper_ledger.json`,
  },
  {
    label: "The unattended runs",
    detail: "GitHub Actions history: each cycle's log, on GitHub's runners, not a laptop.",
    href: `${REPO_URL}/actions`,
  },
  {
    label: "The risk layer's code",
    detail: "The deterministic, non-LLM caps and breakers, readable end to end.",
    href: `${REPO_URL}/blob/master/gloaming_agent/risk_controls.py`,
  },
];

// Nothing on this Desk asks to be taken on trust: each claim has a public source.
export default function VerifyPanel() {
  return (
    <ul className="grid gap-4 sm:grid-cols-2">
      {LINKS.map((l) => (
        <li key={l.href}>
          <a
            href={l.href}
            target="_blank"
            rel="noreferrer noopener"
            className="block h-full rounded-xl border border-border-subtle bg-layer-1 p-5 transition-colors hover:border-border-strong hover:bg-layer-2"
          >
            <span className="text-sm font-medium text-heading">
              {l.label}
              <span aria-hidden> ↗</span>
              <span className="sr-only"> (opens in a new tab)</span>
            </span>
            <span className="mt-2 block text-sm leading-relaxed text-text-secondary">{l.detail}</span>
          </a>
        </li>
      ))}
    </ul>
  );
}
