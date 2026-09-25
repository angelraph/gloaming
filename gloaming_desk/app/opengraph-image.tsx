import { ImageResponse } from "next/og";

export const alt = "Gloaming: trades the hours the market can't";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

// The share card for the X post and link previews: the wordmark and tagline on the Desk's
// own near-black canvas, with the gilded sphere.
export default function OpengraphImage() {
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
        <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
          <div
            style={{
              width: 56,
              height: 56,
              borderRadius: 56,
              background: "radial-gradient(circle at 35% 30%, #fff0cc, #ae9357 45%, #2e3038 100%)",
            }}
          />
          <div style={{ fontSize: 40, fontFamily: "serif" }}>Gloaming</div>
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
