// The nine underlyings the agent covers (gloaming_agent/agent_loop.py). An rToken's Bitget
// symbol is "R" + underlying + "USDT" (RAAPLUSDT for AAPL); the ledger keys positions by it.
export const UNIVERSE = ["AAPL", "AMZN", "GOOGL", "META", "MSFT", "NVDA", "QQQ", "SPY", "TSLA"] as const;

export function rtokenSymbol(underlying: string) {
  return `R${underlying}USDT`;
}

export function underlyingFromRtoken(symbol: string) {
  return symbol.replace(/^R/, "").replace(/USDT$/, "");
}

export function isKnownUnderlying(s: string): boolean {
  return (UNIVERSE as readonly string[]).includes(s);
}
