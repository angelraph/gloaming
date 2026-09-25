import type { Metadata } from "next";
import { notFound } from "next/navigation";
import SymbolView from "@/components/views/SymbolView";
import { UNIVERSE, isKnownUnderlying } from "@/lib/universe";

export function generateStaticParams() {
  return UNIVERSE.map((symbol) => ({ symbol }));
}

export async function generateMetadata({ params }: PageProps<"/desk/[symbol]">): Promise<Metadata> {
  const { symbol } = await params;
  const s = symbol.toUpperCase();
  return {
    title: `${s} overnight`,
    description: `${s}: spread against the real close, every decision with reasoning, and every paper fill.`,
  };
}

export default async function Page({ params }: PageProps<"/desk/[symbol]">) {
  const { symbol } = await params;
  const s = symbol.toUpperCase();
  if (!isKnownUnderlying(s)) notFound();
  return <SymbolView symbol={s} />;
}
