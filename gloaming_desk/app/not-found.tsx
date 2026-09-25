import Link from "next/link";
import { Container } from "@/components/Container";

export default function NotFound() {
  return (
    <Container className="py-24 text-center">
      <p className="eyebrow">404</p>
      <h1 className="font-display mt-5 text-[40px] leading-tight text-heading sm:text-[56px]">Nothing here after dark.</h1>
      <p className="mx-auto mt-5 max-w-md text-text-secondary">That page does not exist. The desk is one click away.</p>
      <Link
        href="/desk"
        className="mt-8 inline-flex min-h-11 items-center rounded-full bg-heading px-6 text-sm font-medium text-background hover:bg-text-primary"
      >
        Go to the desk
      </Link>
    </Container>
  );
}
