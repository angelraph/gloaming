import type { Metadata } from "next";
import { Container } from "@/components/Container";
import Roadmap from "@/components/Roadmap";

export const metadata: Metadata = {
  title: "Roadmap",
  description: "What has shipped, what is in progress and what is planned. Planned items are intentions, not promises.",
};

export default function Page() {
  return (
    <Container className="py-14 sm:py-16 lg:py-20">
      <Roadmap />
    </Container>
  );
}
