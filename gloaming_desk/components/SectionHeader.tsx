// Every content section opens the same way: a small copper eyebrow, a serif headline, and a
// quiet supporting line. The serif/sans handoff (28px and up is serif, below is Inter) is
// the whole typographic signature, so this is the one place it is set.
export default function SectionHeader({
  eyebrow,
  title,
  description,
  className = "",
}: {
  eyebrow: string;
  title: string;
  description?: string;
  className?: string;
}) {
  return (
    <header className={`max-w-2xl ${className}`}>
      <p className="eyebrow">{eyebrow}</p>
      <h2 className="font-display mt-4 text-[32px] leading-[1.12] text-heading sm:text-[40px] lg:text-[44px]">{title}</h2>
      {description && <p className="mt-4 text-[15px] leading-relaxed text-text-secondary sm:text-base">{description}</p>}
    </header>
  );
}
