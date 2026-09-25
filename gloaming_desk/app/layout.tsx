import type { Metadata, Viewport } from "next";
import { Inter, Playfair_Display } from "next/font/google";
import SiteNav from "@/components/SiteNav";
import SiteFooter from "@/components/SiteFooter";
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

const DESCRIPTION =
  "Gloaming trades the hours the market can't: an autonomous, risk-gated overnight desk for Bitget rTokens while NYSE is closed.";

export const metadata: Metadata = {
  metadataBase: new URL("https://gloamingdesk.vercel.app"),
  title: { default: "Gloaming Desk", template: "%s · Gloaming" },
  description: DESCRIPTION,
  openGraph: { title: "Gloaming Desk", description: DESCRIPTION, siteName: "Gloaming", type: "website" },
  twitter: { card: "summary_large_image", title: "Gloaming Desk", description: DESCRIPTION },
};

export const viewport: Viewport = { themeColor: "#08080a", colorScheme: "dark" };

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${inter.variable} ${playfair.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col">
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-full focus:bg-heading focus:px-5 focus:py-3 focus:text-sm focus:font-medium focus:text-background"
        >
          Skip to content
        </a>
        <SiteNav />
        <main id="main" tabIndex={-1} className="flex-1 outline-none">
          {children}
        </main>
        <SiteFooter />
      </body>
    </html>
  );
}
