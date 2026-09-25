import type { Metadata } from "next";
import { Container } from "@/components/Container";
import Faq from "@/components/Faq";

export const metadata: Metadata = {
  title: "FAQ",
  description: "Plain answers about Gloaming, including what it cannot do.",
};

export default function Page() {
  return (
    <Container className="py-14 sm:py-16 lg:py-20">
      <Faq />
    </Container>
  );
}
