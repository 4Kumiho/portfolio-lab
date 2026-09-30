"""Simulazione storica di un portafoglio su prezzi mensili."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import brentq

REBALANCE_OPTIONS = {
    "Mai": None,
    "Mensile": 1,
    "Trimestrale": 3,
    "Semestrale": 6,
    "Annuale": 12,
}


@dataclass
class Settings:
    start_year: int
    end_year: int
    initial: float = 10_000.0
    monthly: float = 0.0
    rebalance: str = "Annuale"
    currency: str = "EUR"
    risk_free: float = 0.02


@dataclass
class Result:
    weights: dict[str, float]
    value: pd.Series           # valore in denaro del portafoglio (con versamenti)
    invested: pd.Series        # somma versata cumulata
    index: pd.Series           # rendimento time-weighted, base 100
    returns: pd.Series         # rendimenti mensili time-weighted
    asset_values: pd.DataFrame # valore di ogni posizione nel tempo
    metrics: dict[str, float]
    limited_by: str | None     # asset con lo storico piu' corto (se limita il periodo)
    requested_start: pd.Timestamp

    @property
    def annual_returns(self) -> pd.Series:
        return annual_returns(self.returns)

    @property
    def drawdown(self) -> pd.Series:
        return self.index / self.index.cummax() - 1


def common_window(prices: pd.DataFrame, tickers: list[str]) -> tuple[pd.DataFrame, str | None]:
    """Taglia i prezzi al periodo in cui TUTTI gli asset scelti hanno dati."""
    sub = prices[tickers]
    firsts = {t: sub[t].first_valid_index() for t in tickers}
    missing = [t for t, d in firsts.items() if d is None]
    if missing:
        raise ValueError(f"Nessun dato nel periodo per: {', '.join(missing)}")
    latest_t = max(firsts, key=lambda t: firsts[t])
    start = firsts[latest_t]
    limited = latest_t if start > sub.index[0] else None
    sub = sub.loc[start:].ffill()
    return sub, limited


def _xirr_monthly(flows: np.ndarray) -> float:
    """IRR annualizzato di flussi mensili (negativi = versamenti, ultimo = valore finale)."""
    t = np.arange(len(flows)) / 12.0

    def npv(r: float) -> float:
        return float(np.sum(flows / (1 + r) ** t))

    try:
        return brentq(npv, -0.99, 10.0, maxiter=500)
    except (ValueError, RuntimeError):
        return float("nan")


def annual_returns(returns: pd.Series) -> pd.Series:
    """Rendimento di ogni anno solare (anni parziali inclusi)."""
    return (1 + returns).groupby(returns.index.year).prod() - 1


def compute_metrics(index: pd.Series, returns: pd.Series, risk_free: float) -> dict[str, float]:
    years = max(len(returns) / 12.0, 1e-9)
    total = index.iloc[-1] / index.iloc[0] - 1
    cagr = (1 + total) ** (1 / years) - 1
    vol = returns.std(ddof=1) * np.sqrt(12) if len(returns) > 1 else float("nan")
    ann_mean = returns.mean() * 12
    downside = returns[returns < 0]
    down_dev = np.sqrt((downside ** 2).sum() / max(len(returns), 1)) * np.sqrt(12)
    dd = index / index.cummax() - 1
    annual = annual_returns(returns)
    return {
        "total_return": total,
        "cagr": cagr,
        "volatility": vol,
        "sharpe": (ann_mean - risk_free) / vol if vol and vol > 0 else float("nan"),
        "sortino": (ann_mean - risk_free) / down_dev if down_dev > 0 else float("nan"),
        "max_drawdown": dd.min(),
        "best_year": annual.max(),
        "worst_year": annual.min(),
        "positive_months": float((returns > 0).mean()),
        "years": years,
    }


def run(prices: pd.DataFrame, weights: dict[str, float], settings: Settings) -> Result:
    """Simula il portafoglio. `prices` = prezzi mensili gia' tagliati al periodo."""
    weights = {t: w for t, w in weights.items() if w > 0}
    if not weights:
        raise ValueError("Il portafoglio e' vuoto: assegna almeno un peso.")
    tot = sum(weights.values())
    target = pd.Series({t: w / tot for t, w in weights.items()})
    tickers = list(target.index)

    sub, limited = common_window(prices, tickers)
    if len(sub) < 3:
        raise ValueError("Periodo troppo corto: servono almeno 3 mesi di dati in comune.")

    rets = sub.pct_change().iloc[1:].to_numpy()
    tw = target[tickers].to_numpy()
    step = REBALANCE_OPTIONS.get(settings.rebalance)
    initial = settings.initial
    monthly = settings.monthly
    if initial <= 0 and monthly <= 0:
        initial = 10_000.0

    n = len(sub)
    holdings = np.zeros((n, len(tickers)))
    invested = np.zeros(n)
    port_ret = np.zeros(n - 1)
    holdings[0] = initial * tw
    invested[0] = initial
    flows = [-initial]

    for i in range(1, n):
        prev = holdings[i - 1]
        prev_tot = prev.sum()
        h = prev * (1 + rets[i - 1])
        port_ret[i - 1] = h.sum() / prev_tot - 1 if prev_tot > 0 else 0.0
        if step and i % step == 0:
            h = h.sum() * tw
        if monthly > 0 and i < n - 1:
            h = h + monthly * tw
            flows.append(-monthly)
        elif i < n - 1:
            flows.append(0.0)
        invested[i] = invested[i - 1] + (monthly if (monthly > 0 and i < n - 1) else 0.0)
        holdings[i] = h

    idx = sub.index
    value = pd.Series(holdings.sum(axis=1), index=idx)
    returns = pd.Series(port_ret, index=idx[1:])
    index = pd.Series(100 * np.concatenate([[1.0], np.cumprod(1 + port_ret)]), index=idx)

    metrics = compute_metrics(index, returns, settings.risk_free)
    flows.append(value.iloc[-1])
    metrics["irr"] = _xirr_monthly(np.array(flows))
    metrics["final_value"] = value.iloc[-1]
    metrics["invested"] = invested[-1]
    metrics["gain"] = value.iloc[-1] - invested[-1]

    return Result(
        weights=dict(target),
        value=value,
        invested=pd.Series(invested, index=idx),
        index=index,
        returns=returns,
        asset_values=pd.DataFrame(holdings, index=idx, columns=tickers),
        metrics=metrics,
        limited_by=limited,
        requested_start=prices.index[0],
    )
