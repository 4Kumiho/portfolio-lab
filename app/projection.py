"""Proiezione futura di un piano di accumulo (PAC).

Metodo "storico": simulazione Monte Carlo che ricampiona a blocchi di 12 mesi i
rendimenti mensili reali del portafoglio (block bootstrap), cosi' da conservare
anni buoni e anni cattivi nelle proporzioni osservate in passato.
Metodo "fisso": crescita costante a un rendimento annuo scelto.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

PERCENTILES = (10, 25, 50, 75, 90)
BLOCK = 12


@dataclass
class Plan:
    initial: float
    monthly: float
    months: int
    annual_increase: float = 0.0     # aumento annuo del versamento (es. 0.02 = +2% ogni anno)
    inflation: float = 0.0           # usata solo per esprimere i valori in "euro di oggi"


@dataclass
class Projection:
    dates: pd.DatetimeIndex
    bands: dict[int, np.ndarray]     # percentile -> valore nel tempo
    invested: np.ndarray
    final_values: np.ndarray         # valore finale di ogni scenario simulato
    growth: np.ndarray               # moltiplicatore del capitale iniziale per scenario
    contrib_growth: np.ndarray       # valore finale di 1 EUR/mese versato per scenario
    deflator: np.ndarray             # 1 / (1+inflazione)^t, per ogni mese
    plan: Plan

    def final(self, p: int) -> float:
        return float(self.bands[p][-1])

    def prob_at_least(self, target: float) -> float:
        return float((self.final_values >= target).mean())

    def prob_loss(self) -> float:
        return float((self.final_values < self.invested[-1]).mean())

    def required_monthly(self, target: float, percentile: int = 50) -> float:
        """Versamento mensile iniziale necessario per arrivare a `target` nel percentile scelto."""
        base = self.plan.initial * self.growth
        if np.percentile(base, percentile) >= target:
            return 0.0
        lo, hi = 0.0, max(target / max(self.plan.months, 1), 1.0)
        while np.percentile(base + hi * self.contrib_growth, percentile) < target:
            hi *= 2
            if hi > 1e9:
                return float("nan")
        for _ in range(60):
            mid = (lo + hi) / 2
            if np.percentile(base + mid * self.contrib_growth, percentile) < target:
                lo = mid
            else:
                hi = mid
        return hi


def _contributions(plan: Plan) -> np.ndarray:
    """Versamento di ogni mese (all'inizio del mese), con aumento annuo."""
    t = np.arange(plan.months)
    return plan.monthly * (1 + plan.annual_increase) ** (t // 12)


def _block_bootstrap(hist: np.ndarray, months: int, n_sims: int, rng: np.random.Generator) -> np.ndarray:
    n_blocks = int(np.ceil(months / BLOCK))
    starts = rng.integers(0, len(hist), size=(n_sims, n_blocks))
    idx = (starts[:, :, None] + np.arange(BLOCK)[None, None, :]) % len(hist)   # blocchi circolari
    return hist[idx].reshape(n_sims, -1)[:, :months]


def project(plan: Plan, start: pd.Timestamp, hist_returns: np.ndarray | None = None,
            fixed_return: float | None = None, n_sims: int = 5000, seed: int = 7,
            real: bool = False) -> Projection:
    if plan.months < 1:
        raise ValueError("L'anno obiettivo deve essere nel futuro.")
    if fixed_return is not None:
        r = (1 + fixed_return) ** (1 / 12) - 1
        R = np.full((1, plan.months), r)
    else:
        if hist_returns is None or len(hist_returns) < 24:
            raise ValueError("Servono almeno 2 anni di storico del portafoglio per la simulazione.")
        R = _block_bootstrap(np.asarray(hist_returns, dtype=float), plan.months, n_sims,
                             np.random.default_rng(seed))

    contrib = _contributions(plan)
    growth_f = 1 + R
    S = R.shape[0]
    values = np.empty((S, plan.months + 1))
    values[:, 0] = plan.initial
    v = np.full(S, plan.initial, dtype=float)
    for t in range(plan.months):
        v = (v + contrib[t]) * growth_f[:, t]
        values[:, t + 1] = v

    # scomposizione lineare: valore finale = iniziale * G + versamento * H
    suffix = np.cumprod(growth_f[:, ::-1], axis=1)[:, ::-1]      # prod_{j>=t} (1+r_j)
    G = suffix[:, 0]
    rel = contrib / plan.monthly if plan.monthly > 0 else (1 + plan.annual_increase) ** (np.arange(plan.months) // 12)
    H = (suffix * rel[None, :]).sum(axis=1)

    invested = plan.initial + np.concatenate([[0.0], np.cumsum(contrib)])
    deflator = (1 + plan.inflation) ** (-np.arange(plan.months + 1) / 12)
    if real:
        values = values * deflator[None, :]
        invested = invested * deflator
        G = G * deflator[-1]
        H = H * deflator[-1]

    bands = {p: np.percentile(values, p, axis=0) for p in PERCENTILES}
    dates = pd.date_range(start, periods=plan.months + 1, freq="ME")
    return Projection(dates=dates, bands=bands, invested=invested, final_values=values[:, -1],
                      growth=G, contrib_growth=H, deflator=deflator, plan=plan)
