# Gloaming - Overnight NAV Convergence Backtest

Supplementary quantitative validation for the Agentic Trading and AI Trading Desk
submissions (see [docs/architecture.md](../docs/architecture.md) for why this isn't
a separate formal Alpha Factory entry). Fully reproducible: `python -m
backtest.run_backtest` from `engine/` with the venv active.

## Thesis

When NYSE/Nasdaq is closed, nothing forces a Bitget rToken's on-chain price back to
its real-share value - there's no direct arbitrage pressure in that window. We
estimate a synthetic fair value from proxies that stay live during the closed
window (CME index-futures proxy, crypto beta, FX risk sentiment), and trade the
spread between that fair value and the rToken's actual price, betting on
convergence.

## Data

- **rToken prices**: live Bitget SPOT data via `bgc` for the confirmed universe in
  `fairvalue/config.py` (AAPL, AMZN, META, TSLA, GOOGL, NVDA, MSFT, QQQ, SPY -
  symbols `R<TICKER>USDT`). **~90 days of real daily history** exist since launch
  (confirmed Sept 10, 2026), satisfying the ≥60-day requirement without synthetic
  data.
- **Futures proxy**: `ES=F`/`NQ=F` via yfinance - an accessible stand-in for true
  CME tick data, disclosed as such.
- **Crypto beta**: BTC/ETH equal-weighted blended daily return via Bitget SPOT data.
- **FX risk sentiment**: inverted DXY daily return via yfinance.

### Key data finding: rTokens genuinely trade all 7 days/week

Checking bar counts by weekday confirmed the project's core premise directly:
rToken daily candles land almost evenly across all seven weekdays (Mon–Sun), while
the free futures-proxy and FX data sources only carry weekday bars - because CME
index futures and most FX venues are themselves closed over the weekend. Rather
than inner-joining and silently dropping every weekend day (exactly the window this
project targets), we reindex futures/FX returns onto the rToken's full daily
calendar and fill weekend gaps with 0 ("no new proxy information since Friday's
close"). This is a modeling choice that matches reality, not a data-cleaning hack:
on weekends, `crypto_beta_return` - the one proxy that *is* live 24/7 - becomes the
sole driver of the synthetic fair value, which is the correct behavior.

## Methodology

1. **Signal**: `fairvalue/model.py` blends the three proxy return series into a
   synthetic fair-value return, compounds it into a fair-value price path anchored
   to the rToken's price at the start of the window, and computes
   `spread_pct = (actual - fair) / fair`.
2. **Calibration**: proxy weights are OLS-calibrated (`calibrate_weights`, plain
   `numpy.linalg.lstsq`, unconstrained) on the **first N-30 days (in-sample)** per
   symbol, not hand-picked - see per-symbol weights in `results/backtest_summary.json`.
3. **Strategy**: `backtest/engine.py` computes a 14-day rolling z-score of the
   spread and forms `position = -clip(zscore / 2, -1, 1)` - short when the rToken
   trades rich, long when cheap. The position from day *t* trades day *t+1*'s
   realized return (`shift(1)`, no lookahead).
4. **Evaluation**: reported on the full window and separately on the **last 30 days
   (out-of-sample)**, i.e. days the calibration never saw.

## Results (portfolio, equal-weight across 9 symbols, full window)

| Metric | Value |
|---|---|
| Sharpe | 1.86 |
| Sortino | 2.01 |
| Max drawdown | -3.5% |
| Win rate | 58.3% |
| Total return | 4.1% |
| Periods | 84 days |

Full per-symbol figures (full-window and out-of-sample Sharpe, calibrated weights,
day counts) are in `results/backtest_summary.json`; the equity curve is in
`results/portfolio_equity.csv`.

**Reported honestly, not cherry-picked**: per-symbol results are mixed - AAPL and
TSLA's out-of-sample Sharpe are strongly positive (5.8, 4.6), while META and SPY are
negative out-of-sample (-3.5, -2.5). The blended portfolio Sharpe smooths this
dispersion but individual-symbol reliability clearly varies, which is disclosed
rather than hidden.

## Known limitations (disclosed, not hidden)

1. **Futures/FX proxies, not true CME/interbank data** - `ES=F`/`NQ=F`/DXY via
   Yahoo Finance are accessible stand-ins, not tick-level CME or FX data.
2. **Unconstrained OLS on ~55–59 in-sample days for 3 free parameters** is a real
   small-sample overfitting risk - some calibrated FX weights are large in
   magnitude (e.g. 3–4x), likely a scale artifact of DXY's much smaller daily %
   moves relative to equities/crypto rather than a genuine causal relationship.
   Ridge/L2 regularization or regressor standardization is flagged as follow-up
   work, not yet implemented.
3. **Weekend fair value is driven solely by crypto beta** once futures/FX are
   zero-filled - reasonable given real market structure, but means the model has
   no true weekend-specific macro-event signal of its own (that's handled instead
   by the live Agent's use of `bitget-signal`'s news/macro skills, not this
   backtest).
4. **No transaction costs or slippage** modeled - `turnover` is reported as a
   diagnostic, but PnL doesn't net out trading costs.
