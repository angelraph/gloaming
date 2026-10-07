"use client";

import { Fragment, useEffect, useRef, useState } from "react";

// A section opening (eyebrow, serif title, supporting line) whose title rises in word by
// word as it scrolls into view (and sinks back as it leaves), with a gold rule drawing out under the eyebrow.
export default function RevealTitle({
  eyebrow,
  title,
  description,
}: {
  eyebrow: string;
  title: string;
  description?: string;
}) {
  const ref = useRef<HTMLElement | null>(null);
  const [shown, setShown] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const io = new IntersectionObserver(
      (entries) => {
        // in as it enters, out again as it leaves, in either direction
        setShown(entries[entries.length - 1].isIntersecting);
      },
      { rootMargin: "0px 0px -10% 0px" },
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);

  const words = title.split(" ");
  return (
    <header ref={ref} data-shown={shown} className="title-reveal max-w-2xl">
      <p className="eyebrow flex items-center gap-3">
        <span aria-hidden className="eyebrow-rule h-px w-8" />
        {eyebrow}
      </p>
      <h2 aria-label={title} className="font-display mt-4 text-[32px] leading-[1.12] text-heading sm:text-[40px] lg:text-[44px]">
        {words.map((w, i) => (
          <Fragment key={i}>
            <span aria-hidden className="word-mask">
              <span className="title-word" style={{ "--word-delay": `${i * 70}ms` } as React.CSSProperties}>
                {w}
              </span>
            </span>
            {i < words.length - 1 ? " " : ""}
          </Fragment>
        ))}
      </h2>
      {description && (
        <p
          className="title-desc mt-4 text-[15px] leading-relaxed text-text-secondary sm:text-base"
          style={{ "--word-delay": `${words.length * 70 + 120}ms` } as React.CSSProperties}
        >
          {description}
        </p>
      )}
    </header>
  );
}
