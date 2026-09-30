"""Ricerca dei portafogli "migliori" sul periodo storico scelto."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from .universe import BY_TICKER, CATEGORIES

MAX_SHARPE = "Miglior rischio/rendimento"
MAX_RETURN = "Massimo rendimento"
MIN_RISK = "Minimo rischio"
OBJECTIVES = [MAX_SHARPE, MAX_RETURN, MIN_RISK]


@dataclass
class Constraints:
    max_weight: float = 0.20                       # peso massimo per singolo asset
    category_min: dict[str, float] = field(default_factory=lambda: {c: 0.0 for c in CATEGORIES})
    category_max: dict[str, float] = field(default_factory=lambda: {c: 1.0 for c in CATEGORIES})
    min_weight_shown: float = 0.005                # sotto questa soglia il peso viene azzerato


@dataclass
class Frontier:
    vols: np.ndarray
    rets: np.ndarray


@dataclass
class OptimizationOutput:
    solutions: dict[str, dict[str, float]]
    stats: dict[str, tuple[float, float]]   # (volatilita', rendimento medio) per soluzione
    frontier: Frontier
    asset_points: pd.DataFrame        # vol / cagr per asset (per il grafico)
    universe: list[str]
    excluded: list[str]
    start: pd.Timestamp
    end: pd.Timestamp


def eligible_universe(prices: pd.DataFrame, tickers: list[str]) -> tuple[list[str], list[str]]:
    """Asset con dati completi nell'intero periodo."""
    ok, bad = [], []
    for t in tickers:
        s = prices[t] if t in prices else None
        if s is None or s.iloc[:2].isna().any() or s.isna().mean() > 0.02:
            bad.append(t)
        else:
            ok.append(t)
    return ok, bad


def _check_feasible(tickers: list[str], c: Constraints) -> None:
    cats = [BY_TICKER[t].category for t in tickers]
    if c.max_weight * len(tickers) < 1 - 1e-9:
        raise ValueError(
            f"Con un massimo del {c.max_weight:.0%} per asset servono almeno "
            f"{int(np.ceil(1 / c.max_weight))} asset: ne sono disponibili {len(tickers)}."
        )
    if sum(c.category_min.values()) > 1 + 1e-9:
        raise ValueError("La somma dei minimi per categoria supera il 100%.")
    reachable = 0.0
    for cat in CATEGORIES:
        n = cats.count(cat)
        lo, hi = c.category_min.get(cat, 0), c.category_max.get(cat, 1)
        if lo > hi:
            raise ValueError(f"{cat}: il minimo e' maggiore del massimo.")
        cap = min(hi, n * c.max_weight)
        if lo > cap + 1e-9:
            raise ValueError(f"{cat}: impossibile raggiungere il minimo del {lo:.0%} "
                             f"con {n} asset disponibili.")
        reachable += cap
    if reachable < 1 - 1e-9:
        raise ValueError("I massimi per categoria non permettono di arrivare al 100%.")


def _constraints(tickers: list[str], c: Constraints) -> list[dict]:
    cons: list[dict] = [{"type": "eq", "fun": lambda w: w.sum() - 1, "jac": lambda w: np.ones_like(w)}]
    for cat in CATEGORIES:
        mask = np.array([BY_TICKER[t].category == cat for t in tickers], dtype=float)
        if not mask.any():
            continue
        lo, hi = c.category_min.get(cat, 0.0), c.category_max.get(cat, 1.0)
        if lo > 0:
            cons.append({"type": "ineq", "fun": lambda w, m=mask, lo=lo: m @ w - lo, "jac": lambda w, m=mask: m})
        if hi < 1:
            cons.append({"type": "ineq", "fun": lambda w, m=mask, hi=hi: hi - m @ w, "jac": lambda w, m=mask: -m})
    return cons


def _start_point(tickers: list[str], c: Constraints) -> np.ndarray:
    """Punto iniziale che rispetta (circa) i vincoli di categoria."""
    cats = np.array([BY_TICKER[t].category for t in tickers])
    w = np.zeros(len(tickers))
    present = [cat for cat in CATEGORIES if (cats == cat).any()]
    alloc = {cat: c.category_min.get(cat, 0.0) for cat in present}
    rest = 1 - sum(alloc.values())
    room = {cat: min(c.category_max.get(cat, 1.0), (cats == cat).sum() * c.max_weight) - alloc[cat]
            for cat in present}
    total_room = sum(max(r, 0) for r in room.values()) or 1
    for cat in present:
        alloc[cat] += rest * max(room[cat], 0) / total_room
        idx = np.where(cats == cat)[0]
        w[idx] = alloc[cat] / len(idx)
    return np.clip(w, 0, c.max_weight)


def _solve(fun, jac, x0, bounds, cons) -> np.ndarray:
    res = minimize(fun, x0, jac=jac, bounds=bounds, constraints=cons, method="SLSQP",
                   options={"maxiter": 1000, "ftol": 1e-10})
    w = np.clip(res.x, 0, None)
    return w / w.sum()


def optimize(prices: pd.DataFrame, tickers: list[str], c: Constraints,
             risk_free: float = 0.02, frontier_points: int = 30) -> OptimizationOutput:
    universe, excluded = eligible_universe(prices, tickers)
    if len(universe) < 2:
        raise ValueError("Servono almeno 2 asset con storico completo nel periodo scelto.")
    _check_feasible(universe, c)

    sub = prices[universe].ffill()
    R = sub.pct_change().iloc[1:].fillna(0.0).to_numpy()
    mu = R.mean(axis=0) * 12
    cov = np.cov(R, rowvar=False) * 12
    cov = cov + np.eye(len(universe)) * 1e-10

    bounds = [(0.0, c.max_weight)] * len(universe)
    cons = _constraints(universe, c)
    x0 = _start_point(universe, c)

    def neg_sharpe(w):
        s = np.sqrt(w @ cov @ w)
        return -(w @ mu - risk_free) / s

    def neg_sharpe_jac(w):
        s = np.sqrt(w @ cov @ w)
        ex = w @ mu - risk_free
        return -(mu * s - ex * (cov @ w) / s) / s ** 2

    # massimo rendimento composto (CAGR) di un portafoglio ribilanciato mensilmente
    def neg_growth(w):
        g = 1 + R @ w
        return -np.mean(np.log(np.clip(g, 1e-9, None))) * 12

    def neg_growth_jac(w):
        g = np.clip(1 + R @ w, 1e-9, None)
        return -(R / g[:, None]).mean(axis=0) * 12

    def var(w):
        return w @ cov @ w

    def var_jac(w):
        return 2 * cov @ w

    w_sharpe = _solve(neg_sharpe, neg_sharpe_jac, x0, bounds, cons)
    w_ret = _solve(neg_growth, neg_growth_jac, x0, bounds, cons)
    w_min = _solve(var, var_jac, x0, bounds, cons)

    # frontiera efficiente: minima varianza per rendimenti target crescenti
    r_lo, r_hi = w_min @ mu, max(w_ret @ mu, w_sharpe @ mu)
    f_vols, f_rets = [], []
    prev = w_min
    for target in np.linspace(r_lo, r_hi, frontier_points):
        tc = cons + [{"type": "ineq", "fun": lambda w, t=target: w @ mu - t, "jac": lambda w: mu}]
        w = _solve(var, var_jac, prev, bounds, tc)
        prev = w
        f_vols.append(np.sqrt(w @ cov @ w))
        f_rets.append(w @ mu)

    def clean(w: np.ndarray) -> dict[str, float]:
        w = np.where(w < c.min_weight_shown, 0, w)
        w = w / w.sum()
        return {t: float(x) for t, x in sorted(zip(universe, w), key=lambda p: -p[1]) if x > 0}

    years = len(R) / 12
    growth = sub.iloc[-1] / sub.iloc[0]
    points = pd.DataFrame({
        "vol": R.std(axis=0, ddof=1) * np.sqrt(12),
        "ret": mu,
        "cagr": growth.to_numpy() ** (1 / years) - 1,
    }, index=universe)

    solutions = {MAX_SHARPE: clean(w_sharpe), MAX_RETURN: clean(w_ret), MIN_RISK: clean(w_min)}
    stats = {}
    for name, sol in solutions.items():
        w = np.array([sol.get(t, 0.0) for t in universe])
        stats[name] = (float(np.sqrt(w @ cov @ w)), float(w @ mu))

    return OptimizationOutput(
        solutions=solutions,
        stats=stats,
        frontier=Frontier(np.array(f_vols), np.array(f_rets)),
        asset_points=points,
        universe=universe,
        excluded=excluded,
        start=sub.index[0],
        end=sub.index[-1],
    )
