import type { Metadata } from "next";
import DeskView from "@/components/views/DeskView";

export const metadata: Metadata = {
  title: "Desk",
  description: "The overnight book, spreads against each real close, a timeline, chat and a stress test. Read-only.",
};

export default function Page() {
  return <DeskView />;
}
