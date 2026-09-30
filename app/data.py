"""Download, cache e preparazione dei prezzi storici (Yahoo Finance)."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

from .universe import ASSETS, BY_TICKER, FX_TICKER

CACHE_DIR = Path(__file__).resolve().parent.parent / "cache"
CACHE_PRICES = CACHE_DIR / "prices.csv"
CACHE_META = CACHE_DIR / "meta.json"
HISTORY_START = "2003-01-01"
CHUNK = 25
CACHE_MAX_AGE_DAYS = 3

ProgressCb = Callable[[int, str], None]


@dataclass
class PriceData:
    daily: pd.DataFrame                  # prezzi adjusted giornalieri, valuta nativa
    fx: pd.Series                        # EURUSD giornaliero (USD per 1 EUR)
    updated: datetime
    failed: list[str] = field(default_factory=list)

    @property
    def tickers(self) -> list[str]:
        return list(self.daily.columns)

    def monthly(self, currency: str = "EUR") -> pd.DataFrame:
        """Prezzi di fine mese convertiti nella valuta richiesta."""
        m = self.daily.resample("ME").last()
        fx = self.fx.resample("ME").last().reindex(m.index)
        out = m.copy()
        for t in out.columns:
            native = BY_TICKER[t].currency if t in BY_TICKER else "USD"
            if currency == "EUR" and native == "USD":
                out[t] = out[t] / fx
            elif currency == "USD" and native == "EUR":
                out[t] = out[t] * fx
        # valori non positivi o buchi isolati: niente rendimenti infiniti
        out = out.where(out > 0)
        return out


def _clean(close: pd.DataFrame) -> pd.DataFrame:
    close = close.sort_index()
    close.index = pd.to_datetime(close.index).tz_localize(None)
    close = close.where(close > 0)
    # riempie solo buchi brevi (festivita', giorni senza scambi)
    return close.ffill(limit=10)


def _download_chunk(tickers: list[str]) -> pd.DataFrame:
    import yfinance as yf

    raw = yf.download(
        tickers,
        start=HISTORY_START,
        auto_adjust=True,
        progress=False,
        threads=True,
        group_by="column",
    )
    if raw is None or raw.empty:
        return pd.DataFrame()
    if isinstance(raw.columns, pd.MultiIndex):
        close = raw["Close"]
    else:
        close = raw[["Close"]].rename(columns={"Close": tickers[0]})
    return close.reindex(columns=tickers)


def download_all(progress: ProgressCb | None = None) -> PriceData:
    tickers = [a.ticker for a in ASSETS] + [FX_TICKER]
    parts: list[pd.DataFrame] = []
    chunks = [tickers[i:i + CHUNK] for i in range(0, len(tickers), CHUNK)]
    for i, chunk in enumerate(chunks):
        if progress:
            progress(int(100 * i / len(chunks)), f"Scarico {chunk[0]} ... {chunk[-1]}")
        df = pd.DataFrame()
        for attempt in range(3):
            try:
                df = _download_chunk(chunk)
                break
            except Exception:  # rete instabile / rate limit
                time.sleep(2 * (attempt + 1))
        parts.append(df)

    close = _clean(pd.concat(parts, axis=1))
    close = close.loc[:, ~close.columns.duplicated()]
    fx = close.pop(FX_TICKER) if FX_TICKER in close else pd.Series(dtype=float)
    if fx.dropna().empty:
        raise RuntimeError("Impossibile scaricare il cambio EUR/USD: controlla la connessione.")

    failed = [t for t in close.columns if close[t].dropna().shape[0] < 30]
    close = close.drop(columns=failed)
    data = PriceData(daily=close, fx=fx.ffill(), updated=datetime.now(), failed=failed)
    if progress:
        progress(100, "Salvataggio cache")
    save_cache(data)
    return data


def save_cache(data: PriceData) -> None:
    CACHE_DIR.mkdir(exist_ok=True)
    pd.concat([data.daily, data.fx.rename(FX_TICKER)], axis=1).to_csv(CACHE_PRICES)
    meta = {"updated": data.updated.isoformat(), "failed": data.failed}
    CACHE_META.write_text(json.dumps(meta), encoding="utf-8")


def load_cache() -> PriceData | None:
    if not (CACHE_PRICES.exists() and CACHE_META.exists()):
        return None
    try:
        meta = json.loads(CACHE_META.read_text(encoding="utf-8"))
        daily = pd.read_csv(CACHE_PRICES, index_col=0, parse_dates=True)
        fx = daily.pop(FX_TICKER)
        return PriceData(daily=daily, fx=fx, updated=datetime.fromisoformat(meta["updated"]),
                         failed=meta.get("failed", []))
    except Exception:
        return None


def cache_is_stale(data: PriceData) -> bool:
    return (datetime.now() - data.updated).days >= CACHE_MAX_AGE_DAYS


def slice_period(prices: pd.DataFrame, start_year: int, end_year: int) -> pd.DataFrame:
    """Prezzi mensili nel periodo, includendo il mese precedente come base."""
    start = pd.Timestamp(year=start_year, month=1, day=1) - pd.offsets.MonthEnd(1)
    end = pd.Timestamp(year=end_year, month=12, day=31)
    return prices.loc[(prices.index >= start) & (prices.index <= end)]


def asset_stats(prices: pd.DataFrame) -> pd.DataFrame:
    """CAGR, volatilita' e primo anno disponibile per ogni colonna."""
    rows = {}
    for t in prices.columns:
        s = prices[t].dropna()
        if len(s) < 13:
            rows[t] = (np.nan, np.nan, np.nan, s.index[0].year if len(s) else np.nan)
            continue
        years = (s.index[-1] - s.index[0]).days / 365.25
        cagr = (s.iloc[-1] / s.iloc[0]) ** (1 / years) - 1
        r = s.pct_change().dropna()
        vol = r.std() * np.sqrt(12)
        dd = (s / s.cummax() - 1).min()
        rows[t] = (cagr, vol, dd, s.index[0].year)
    return pd.DataFrame.from_dict(rows, orient="index", columns=["cagr", "vol", "maxdd", "since"])
