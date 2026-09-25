import type { Metadata } from "next";
import AgentView from "@/components/views/AgentView";

export const metadata: Metadata = {
  title: "Agent",
  description: "The autonomous loop, its risk limits and every decision with reasoning, open to inspection.",
};

export default function Page() {
  return <AgentView />;
}
