"use client";

// Shown when a fetch fails. role="alert" so assistive tech announces it; a retry button so a
// dropped connection is recoverable without a page reload.
export default function DataNotice({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div
      role="alert"
      className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-warning/40 bg-warning-soft px-4 py-3 text-sm text-warning"
    >
      <span>Could not load live data ({message}). Showing what was last received.</span>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="min-h-11 rounded-full border border-warning/50 px-5 text-sm font-medium text-warning transition-colors hover:bg-layer-2"
        >
          Try again
        </button>
      )}
    </div>
  );
}
