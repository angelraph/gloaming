"""
Universe map and fair-value model weights for Gloaming.

RTOKEN_UNIVERSE maps each underlying ticker to:
  - rtoken_symbol: the live Bitget SPOT symbol (confirmed Day 1 via `bgc market
    --action instruments --category SPOT` - rTokens are regular SPOT pairs with
    symbolType == "stock", baseCoin prefixed "r", isReality == "yes"; naming
    convention is R<TICKER>USDT, e.g. AAPL -> RAAPLUSDT).
  - futures_proxy: nearest CME index-futures proxy (Yahoo ticker) for overnight signal
  - sector_beta_hint: rough crypto/risk-sentiment sensitivity, used only as an
    initial prior before OLS calibration (Day 3) replaces it.

Day 1 finding: the live universe is far larger than the ~36-name announcement -
`instruments_spot.json` (fetched Sept 10) shows **1,175** rToken symbols online.
The full list is cached at engine/data/cache/rtoken_universe.json (symbol, baseCoin,
status, launchTime) for later expansion; RTOKEN_UNIVERSE below starts with a
deliberately small, liquid, well-known core to keep the fair-value model and
backtest tractable for the hackathon build, not the full 1,175.
"""

FUTURES_PROXY = {
    "large_cap_tech": "NQ=F",   # Nasdaq-100 futures proxy
    "broad_market": "ES=F",     # S&P 500 futures proxy
}

# underlying ticker -> config. Confirmed live against Bitget SPOT instruments Day 1.
RTOKEN_UNIVERSE = {
    "AAPL": {"rtoken_symbol": "RAAPLUSDT", "futures_proxy": FUTURES_PROXY["large_cap_tech"], "sector_beta_hint": 0.8},
    "AMZN": {"rtoken_symbol": "RAMZNUSDT", "futures_proxy": FUTURES_PROXY["large_cap_tech"], "sector_beta_hint": 0.9},
    "META": {"rtoken_symbol": "RMETAUSDT", "futures_proxy": FUTURES_PROXY["large_cap_tech"], "sector_beta_hint": 1.0},
    "TSLA": {"rtoken_symbol": "RTSLAUSDT", "futures_proxy": FUTURES_PROXY["large_cap_tech"], "sector_beta_hint": 1.3},
    "GOOGL": {"rtoken_symbol": "RGOOGLUSDT", "futures_proxy": FUTURES_PROXY["large_cap_tech"], "sector_beta_hint": 0.85},
    "NVDA": {"rtoken_symbol": "RNVDAUSDT", "futures_proxy": FUTURES_PROXY["large_cap_tech"], "sector_beta_hint": 1.2},
    "MSFT": {"rtoken_symbol": "RMSFTUSDT", "futures_proxy": FUTURES_PROXY["large_cap_tech"], "sector_beta_hint": 0.8},
    "QQQ": {"rtoken_symbol": "RQQQUSDT", "futures_proxy": FUTURES_PROXY["large_cap_tech"], "sector_beta_hint": 1.0},
    "SPY": {"rtoken_symbol": "RSPYUSDT", "futures_proxy": FUTURES_PROXY["broad_market"], "sector_beta_hint": 1.0},
}

# Fair-value blend weights (v1 heuristic prior; Day 3 replaces with OLS-calibrated
# weights per symbol where enough overlapping history exists).
FAIRVALUE_WEIGHTS = {
    "futures_proxy_return": 0.5,
    "crypto_beta_return": 0.3,   # BTC/ETH blended return as risk-sentiment proxy
    "fx_risk_sentiment_return": 0.2,    # DXY inverse as risk-on/off proxy
}
