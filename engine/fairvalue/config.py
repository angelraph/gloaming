"""
Universe map and fair-value model weights for Gloaming.

RTOKEN_UNIVERSE maps each Bitget rToken symbol to:
  - underlying: the real equity/ETF ticker it tracks
  - futures_proxy: nearest CME index-futures proxy (Yahoo ticker) for overnight signal
  - sector_beta_hint: rough crypto/risk-sentiment sensitivity, used only as an
    initial prior before OLS calibration (Day 3) replaces it.

TODO (Day 1 spike): confirm exact rToken symbols exposed by the Bitget Agent SDK
market-data ops and reconcile against this list — this is a first-draft mapping
from the "first batch, ~36 large-cap names" announced with Stocks 2.0.
"""

FUTURES_PROXY = {
    "large_cap_tech": "NQ=F",   # Nasdaq-100 futures proxy
    "broad_market": "ES=F",     # S&P 500 futures proxy
}

# underlying ticker -> config. rToken symbol prefix/suffix convention TBD Day 1.
RTOKEN_UNIVERSE = {
    "AAPL": {"futures_proxy": FUTURES_PROXY["large_cap_tech"], "sector_beta_hint": 0.8},
    "AMZN": {"futures_proxy": FUTURES_PROXY["large_cap_tech"], "sector_beta_hint": 0.9},
    "META": {"futures_proxy": FUTURES_PROXY["large_cap_tech"], "sector_beta_hint": 1.0},
    "TSLA": {"futures_proxy": FUTURES_PROXY["large_cap_tech"], "sector_beta_hint": 1.3},
    "GOOGL": {"futures_proxy": FUTURES_PROXY["large_cap_tech"], "sector_beta_hint": 0.85},
    "NVDA": {"futures_proxy": FUTURES_PROXY["large_cap_tech"], "sector_beta_hint": 1.2},
    "MSFT": {"futures_proxy": FUTURES_PROXY["large_cap_tech"], "sector_beta_hint": 0.8},
    "QQQ": {"futures_proxy": FUTURES_PROXY["large_cap_tech"], "sector_beta_hint": 1.0},
    # remainder of the ~36-name batch to be filled in once the live symbol list
    # is confirmed against the Bitget Agent SDK on Day 1.
}

# Fair-value blend weights (v1 heuristic prior; Day 3 replaces with OLS-calibrated
# weights per symbol where enough overlapping history exists).
FAIRVALUE_WEIGHTS = {
    "futures_proxy_return": 0.5,
    "crypto_beta_return": 0.3,   # BTC/ETH blended return as risk-sentiment proxy
    "fx_risk_sentiment": 0.2,    # DXY inverse as risk-on/off proxy
}
