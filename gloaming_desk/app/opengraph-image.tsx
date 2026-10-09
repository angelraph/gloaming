import { readFileSync } from "fs";
import { join } from "path";
import { ImageResponse } from "next/og";

export const alt = "Gloaming: trades the hours the market can't";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

// The share card for the X post and link previews: the Gloaming lockup and the line on the
// Desk's own near-black canvas.
export default function OpengraphImage() {
  const lockup = `data:image/png;base64,${readFileSync(join(process.cwd(), "public/brand/lockup.png")).toString("base64")}`;
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          background: "#08080a",
          padding: 72,
          color: "#ffffff",
        }}
      >
        <div style={{ display: "flex" }}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={lockup} width={469} height={118} alt="" />
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
          <div style={{ fontSize: 84, lineHeight: 1.05, fontFamily: "serif", maxWidth: 980 }}>
            Gloaming trades the hours the market can&apos;t.
          </div>
          <div style={{ fontSize: 30, color: "#9194a1", maxWidth: 900 }}>
            An autonomous, risk-gated overnight agent for Bitget rTokens. Every decision explained.
          </div>
        </div>
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 24, color: "#cc9166" }}>
          <div>BITGET AI &amp; CRYPTO HACKATHON · GENESIS SEASON 2</div>
          <div style={{ color: "#3fe280" }}>LIVE · PAPER TRADING</div>
        </div>
      </div>
    ),
    size
  );
}
