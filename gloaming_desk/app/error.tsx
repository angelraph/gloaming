"use client";

import { Container } from "@/components/Container";

export default function ErrorPage({ reset }: { error: Error; reset: () => void }) {
  return (
    <Container className="py-24 text-center">
      <p className="eyebrow">Something broke</p>
      <h1 className="font-display mt-5 text-[40px] leading-tight text-heading sm:text-[56px]">This page failed to load.</h1>
      <p className="mx-auto mt-5 max-w-md text-text-secondary">
        The agent is unaffected; this is only the viewer. Try again in a moment.
      </p>
      <button
        type="button"
        onClick={reset}
        className="mt-8 inline-flex min-h-11 items-center rounded-full bg-heading px-6 text-sm font-medium text-background hover:bg-text-primary"
      >
        Try again
      </button>
    </Container>
  );
}
