"""
The overnight anchor for Gloaming's fair-value signal.

The thesis is a gap that can open while NYSE is closed: the rToken keeps trading, the
real share does not. So the question the signal has to answer is "where should the
rToken be now, given where the real share closed and what has moved since?" - not
"how does its rolling 24h return compare with some proxies?".

Measured Sept 25 against the previous version (which compared the rToken's rolling
24h return, which includes the whole regular session, with proxy returns over
mismatched windows: a ~5-day futures return, a true 24h crypto return, and a 1-hour
FX return): every rToken sat within about +/-0.25% of its real share's last close
(most within 0.1%), while the reported spreads were as large as -4.6% (META) and
+2.8% (MSFT). Those spreads were the session's own idiosyncratic move, which the
rToken had already priced correctly and the proxy blend has no term for, not a
mispricing that could close. The real overnight dislocation was about 0.1%.

Here every input is measured over the SAME window - from the last regular-session
close (16:00 ET) to now:

    fair value      = real close x (1 + blended proxy return since that close)
    spread          = rToken return since that close - blended proxy return since it

Everything in this module is a pure function over price series except the thin
fetch_* wrappers, so the window arithmetic is unit-tested without a network.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

NYSE_TZ = ZoneInfo("America/New_York")
SESSION_CLOSE_ET = time(16, 0)
REFERENCE_TICKER = "SPY"  # its last completed session defines the anchor for the whole universe
MAX_BASE_STALENESS = timedelta(hours=3)  # the bar we price the close from must sit this near it
VOL_LOOKBACK_DAYS = 10
MIN_VOL_OBSERVATIONS = 5


class AnchorUnavailable(RuntimeError):
    """The real-share close could not be established, so no signal can be computed
    this cycle. Callers must skip trading rather than fall back to stale numbers."""


def session_close_utc(session_date: date) -> datetime:
    """16:00 ET on `session_date`, in UTC. (Early-close days and holidays are not
    modeled, the same simplification is_nyse_closed() already documents.)"""
    return datetime.combine(session_date, SESSION_CLOSE_ET, tzinfo=NYSE_TZ).astimezone(timezone.utc)


def last_completed_session(session_dates, now_utc: datetime) -> date | None:
    """The most recent trading date whose 16:00 ET close has already happened. A daily
    bar for a session still in progress is never used as an anchor."""
    for d in sorted((pd.Timestamp(x).date() for x in session_dates), reverse=True):
        if session_close_utc(d) <= now_utc:
            return d
    return None


def _to_utc_index(series: pd.Series) -> pd.Series:
    s = series.dropna().copy()
    idx = pd.DatetimeIndex(s.index)
    s.index = idx.tz_localize("UTC") if idx.tz is None else idx.tz_convert("UTC")
    return s.sort_index()


def return_since(prices: pd.Series, since_utc: datetime, bar: timedelta = timedelta(hours=1)) -> float | None:
    """Return from the price at `since_utc` to the latest price, for a series of bars
    indexed by bar START. A bar that started at t closes at t + bar, so the price AT
    `since_utc` is the close of the last bar that has ended by then. None (never a
    guess) when the series has no bar near that moment - callers record the proxy as
    missing instead of inventing a number.

    A closed market simply has no newer bars: over a weekend the futures return since
    Friday's close correctly ends at Friday's last bar."""
    p = _to_utc_index(prices)
    if p.empty:
        return None
    ended = p[(p.index + bar) <= pd.Timestamp(since_utc)]
    if ended.empty:
        return None
    if pd.Timestamp(since_utc) - (ended.index[-1] + bar) > MAX_BASE_STALENESS:
        return None
    base = float(ended.iloc[-1])
    if base == 0:
        return None
    return float(p.iloc[-1]) / base - 1.0


def daily_volatility(closes: pd.Series, through: date) -> float | None:
    """Realized volatility of the real share: standard deviation of its last
    VOL_LOOKBACK_DAYS daily returns up to the anchor session. Feeds the risk layer's
    volatility-scaled sizing (control #4) with a real volatility, since the spread is
    now a small dislocation and can no longer stand in for one."""
    c = closes.dropna()
    c = c[[pd.Timestamp(i).date() <= through for i in c.index]]
    rets = c.pct_change().dropna().tail(VOL_LOOKBACK_DAYS)
    if len(rets) < MIN_VOL_OBSERVATIONS:
        return None
    return float(rets.std())


@dataclass
class OvernightAnchor:
    session_date: date
    session_close_utc: datetime
    fetched_at_utc: datetime
    close_prices: dict = field(default_factory=dict)       # underlying -> official close on session_date
    daily_volatility: dict = field(default_factory=dict)   # underlying -> realized daily vol (may be absent)
    futures_return: dict = field(default_factory=dict)     # futures ticker -> return since close (None if unavailable)
    crypto_return: float | None = None                     # blended BTC/ETH return since close
    fx_return: float | None = None                         # inverted DXY return since close (+ == risk-on)
    missing: list = field(default_factory=list)            # proxies unavailable this cycle, recorded on every snapshot

    @property
    def hours_since_close(self) -> float:
        return (self.fetched_at_utc - self.session_close_utc).total_seconds() / 3600.0


def _flatten(df: pd.DataFrame, ticker: str, column: str = "Close") -> pd.Series:
    """yfinance returns different column layouts for one ticker versus many."""
    if isinstance(df.columns, pd.MultiIndex):
        if ticker in df.columns.get_level_values(0):
            return df[ticker][column]
        return df[column][ticker]
    return df[column]


def fetch_equity_closes(underlyings: list[str], now_utc: datetime) -> tuple[date, dict, dict]:
    """Official daily closes for every underlying on the last completed session, plus
    each one's realized daily volatility. Raises AnchorUnavailable if the reference
    session cannot be established at all."""
    import yfinance as yf

    tickers = sorted(set(underlyings) | {REFERENCE_TICKER})
    data = yf.download(tickers, period="20d", interval="1d", group_by="ticker",
                       auto_adjust=True, progress=False)
    if data is None or data.empty:
        raise AnchorUnavailable("no daily price data returned")
    reference = _flatten(data, REFERENCE_TICKER).dropna()
    session = last_completed_session(reference.index, now_utc)
    if session is None:
        raise AnchorUnavailable(f"no completed session found for {REFERENCE_TICKER}")

    closes, vols = {}, {}
    for t in underlyings:
        try:
            series = _flatten(data, t).dropna()
        except KeyError:
            continue
        on_date = series[[pd.Timestamp(i).date() == session for i in series.index]]
        if on_date.empty:
            continue  # this symbol has no close on the anchor session: it gets no signal this cycle
        closes[t] = float(on_date.iloc[-1])
        vol = daily_volatility(series, session)
        if vol is not None:
            vols[t] = vol
    return session, closes, vols


def fetch_futures_returns(tickers: list[str], since_utc: datetime) -> dict:
    import yfinance as yf

    data = yf.download(tickers, period="7d", interval="1h", group_by="ticker",
                       auto_adjust=True, progress=False)
    out = {}
    for t in tickers:
        try:
            out[t] = return_since(_flatten(data, t), since_utc)
        except Exception:  # noqa: BLE001 - one bad ticker must not cost the others
            out[t] = None
    return out


def fetch_fx_return(since_utc: datetime) -> float | None:
    """Inverted DXY return since the close, so positive means risk-on, the same sign
    convention crypto uses."""
    from data.fx import fetch_dxy_history

    try:
        df = fetch_dxy_history(period="7d", interval="1h")
        r = return_since(df["dxy_close"], since_utc)
        return None if r is None else -r
    except Exception:  # noqa: BLE001
        return None


def fetch_crypto_return(since_utc: datetime, symbols: list[str] | None = None) -> float | None:
    """Equal-weighted BTC/ETH return since the close, from Bitget's own hourly klines
    (the same source as the previous rolling-24h crypto term)."""
    from data.crypto_beta import CRYPTO_BETA_SYMBOLS
    from data.rtoken_client import get_candles_history

    symbols = symbols or CRYPTO_BETA_SYMBOLS
    start_ms = int((since_utc - timedelta(hours=3)).timestamp() * 1000)
    end_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    returns = []
    try:
        for symbol in symbols:
            df = get_candles_history(symbol, interval="1H", limit="100", start_time_ms=start_ms, end_time_ms=end_ms)
            r = return_since(df["close"], since_utc)
            if r is None:
                return None  # half a blend would be a different signal, so report it missing
            returns.append(r)
    except Exception:  # noqa: BLE001
        return None
    return sum(returns) / len(returns) if returns else None


def fetch_overnight_anchor(underlyings: list[str], futures_tickers: list[str],
                           now_utc: datetime | None = None) -> OvernightAnchor:
    """Everything the signal needs for one cycle, fetched once and shared across all
    symbols. A proxy that cannot be fetched is recorded in `missing` and contributes
    nothing (the same "no new information" convention as before) rather than being
    replaced by a stale or invented value; a missing real close is different, it
    raises, because without it there is no anchor at all."""
    now_utc = now_utc or datetime.now(timezone.utc)
    session, closes, vols = fetch_equity_closes(underlyings, now_utc)
    close_utc = session_close_utc(session)

    futures = fetch_futures_returns(futures_tickers, close_utc)
    crypto = fetch_crypto_return(close_utc)
    fx = fetch_fx_return(close_utc)

    missing = [f"futures:{t}" for t, r in futures.items() if r is None]
    if crypto is None:
        missing.append("crypto_beta")
    if fx is None:
        missing.append("fx_risk_sentiment")
    return OvernightAnchor(
        session_date=session, session_close_utc=close_utc, fetched_at_utc=now_utc,
        close_prices=closes, daily_volatility=vols, futures_return=futures,
        crypto_return=crypto, fx_return=fx, missing=missing,
    )


if __name__ == "__main__":
    if "--smoke-test" in sys.argv:
        from fairvalue.config import RTOKEN_UNIVERSE

        tickers = sorted({cfg["futures_proxy"] for cfg in RTOKEN_UNIVERSE.values()})
        a = fetch_overnight_anchor(list(RTOKEN_UNIVERSE), tickers)
        print(f"anchor session {a.session_date} closed {a.session_close_utc:%Y-%m-%d %H:%M}Z, {a.hours_since_close:.1f}h ago")
        print("closes:", {k: round(v, 2) for k, v in a.close_prices.items()})
        print("daily vol:", {k: f"{v:.2%}" for k, v in a.daily_volatility.items()})
        print("futures since close:", a.futures_return)
        print("crypto since close:", a.crypto_return, "| fx since close:", a.fx_return)
        print("missing:", a.missing or "none")
    else:
        print("Usage: python overnight_anchor.py --smoke-test")
