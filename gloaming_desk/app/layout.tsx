import type { Metadata } from "next";
import { Inter, Playfair_Display } from "next/font/google";
import "./globals.css";

// Two-tier type system. Playfair Display (a free stand-in for the high-contrast didone
// serif the "midnight vault" reference calls for) carries every heading from 28px up and
// the large numerals; Inter carries everything functional below that. The serif speaks
// to the editorial moments, the sans to the informational ones, and the two never cross.
const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
  weight: ["300", "400", "500", "600"],
});

const playfair = Playfair_Display({
  variable: "--font-display",
  subsets: ["latin"],
  weight: ["400", "500"],
});

export const metadata: Metadata = {
  title: "Gloaming Desk",
  description:
    "Gloaming trades the hours the market can't: an autonomous, risk-gated overnight desk for Bitget rTokens while NYSE is closed.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${inter.variable} ${playfair.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
