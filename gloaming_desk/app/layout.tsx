import type { Metadata } from "next";
import { Space_Grotesk, JetBrains_Mono } from "next/font/google";
import "./globals.css";

// Deliberately not the Next.js default Geist/Geist_Mono pairing every unstyled
// scaffold ships with. Space Grotesk carries real character for headings and UI
// text; JetBrains Mono (tabular figures) is used specifically for prices and
// percentages, the classic trading-terminal signal that this is a real product,
// not a template.
const spaceGrotesk = Space_Grotesk({
  variable: "--font-sans",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

const jetbrainsMono = JetBrains_Mono({
  variable: "--font-mono",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
});

export const metadata: Metadata = {
  title: "Gloaming Desk",
  description: "Overnight research desk for Bitget rTokens while NYSE is closed.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${spaceGrotesk.variable} ${jetbrainsMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
