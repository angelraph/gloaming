import type { NextConfig } from "next";
import { config as loadEnv } from "dotenv";
import path from "path";

// Load the repo-root .env (QWEN_API_KEY etc.) rather than requiring a second,
// duplicated .env.local here - the Desk and the Agent read the same credentials
// file, same as engine/ does in Python via python-dotenv.
loadEnv({ path: path.resolve(__dirname, "..", ".env") });

const nextConfig: NextConfig = {
  // Silences a spurious workspace-root warning: the repo has a second
  // package-lock.json at gloaming/ (from installing the Bitget Agent Hub CLI
  // packages), which Turbopack otherwise misidentifies as this app's root.
  turbopack: {
    root: __dirname,
  },
};

export default nextConfig;
