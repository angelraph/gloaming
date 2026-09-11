#!/usr/bin/env bash
# Day 1 setup spike for Gloaming.
# Run manually and review output at each step before proceeding - this is meant to
# be read and adapted, not blindly executed unattended.
set -euo pipefail

echo "== 1. Install Bitget Agent Hub (SDK, CLI, MCP, research skills) =="
npx @bitget-ai/bitget-agent-installer upgrade-all --target all

echo "== 2. Verify CLI is available =="
bgc --version || echo "bgc not on PATH yet - check installer output above"

echo "== 3. Reminder: configure the Agentic Account =="
echo "   - Create/confirm an isolated Agentic Account with withdrawals disabled"
echo "   - Populate BITGET_API_KEY / SECRET / PASSPHRASE in .env (never commit it)"
echo "   - Always invoke trading ops with --paper-trading (add --read-only for pure reads)"

echo "== 4. Reminder: Qwen credits + hackathon Telegram =="
echo "   - Apply: https://forms.gle/2QeJpvGB5VpipqQ68 (first 300 KYC'd teams)"
echo "   - Join: https://t.me/+o1tYqQ_lXxllYjgy for KYC approval + credit claim"
echo "   - Once approved, set QWEN_API_KEY in .env"
echo "     (QWEN_BASE_URL=https://hackathon.bitgetops.com/v1, model=qwen3.8-max)"

echo "== 5. Connectivity spikes (run after step 3/4 are configured) =="
echo "   python engine/data/futures_proxy.py --smoke-test    # confirms ES=F/NQ=F reachable"
echo "   python engine/data/rtoken_client.py --smoke-test     # confirms live rToken feed + history depth"
