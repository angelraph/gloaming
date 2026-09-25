import type { Metadata } from "next";
import PerformanceView from "@/components/views/PerformanceView";

export const metadata: Metadata = {
  title: "Performance",
  description: "The paper-trading record: return, drawdown, win rate and Sharpe, with the method and its limits stated.",
};

export default function Page() {
  return <PerformanceView />;
}
