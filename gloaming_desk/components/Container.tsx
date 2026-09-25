// One rhythm for every content band on every page: the same gutter, and hairline-separated
// bands with generous vertical space.
export function Container({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return <div className={`mx-auto w-full max-w-[1216px] px-4 sm:px-6 lg:px-10 ${className}`}>{children}</div>;
}

export function Band({
  children,
  id,
  label,
  first = false,
}: {
  children: React.ReactNode;
  id?: string;
  label?: string;
  first?: boolean;
}) {
  return (
    <section id={id} aria-label={label} className={first ? "" : "border-t border-border-subtle"}>
      <Container className="py-14 sm:py-16 lg:py-20">{children}</Container>
    </section>
  );
}

// The opening of every page: eyebrow, serif h1, one supporting line. The page's only h1.
export function PageHeader({
  eyebrow,
  title,
  description,
  children,
}: {
  eyebrow: string;
  title: string;
  description?: string;
  children?: React.ReactNode;
}) {
  return (
    <section>
      <Container className="pb-10 pt-12 sm:pb-12 sm:pt-16 lg:pt-20">
        <p className="eyebrow">{eyebrow}</p>
        <h1 className="font-display mt-5 max-w-3xl text-[38px] leading-[1.06] text-heading sm:text-[52px] lg:text-[60px]">
          {title}
        </h1>
        {description && (
          <p className="mt-5 max-w-2xl text-base leading-relaxed text-text-secondary sm:text-[17px]">{description}</p>
        )}
        {children && <div className="mt-8">{children}</div>}
      </Container>
    </section>
  );
}
