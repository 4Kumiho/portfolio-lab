"""Stato condiviso dell'applicazione + barra impostazioni della simulazione."""
from __future__ import annotations

from datetime import date

import pandas as pd
from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QComboBox, QDoubleSpinBox, QFrame, QHBoxLayout, QSpinBox

from ..backtest import REBALANCE_OPTIONS, Settings
from ..data import PriceData, asset_stats, slice_period
from .widgets import field

PRESETS: dict[str, dict[str, float]] = {
    "Classico 60/40": {"SPY": 60, "AGG": 40},
    "All Weather (Ray Dalio)": {"VTI": 30, "TLT": 40, "IEF": 15, "GLD": 7.5, "DBC": 7.5},
    "Permanent Portfolio (Harry Browne)": {"VTI": 25, "TLT": 25, "SHY": 25, "GLD": 25},
    "Golden Butterfly": {"VTI": 20, "IJR": 20, "TLT": 20, "SHY": 20, "GLD": 20},
    "Three-Fund (Bogleheads)": {"VTI": 50, "EFA": 30, "AGG": 20},
    "Azionario mondo 100%": {"SPY": 60, "EFA": 30, "EEM": 10},
    "Diversificato 4 categorie": {"SPY": 30, "EFA": 10, "AAPL": 5, "MSFT": 5, "JNJ": 5,
                                  "AGG": 20, "TIP": 10, "GLD": 15},
}

BENCHMARKS: dict[str, dict[str, float] | None] = {
    "Nessun confronto": None,
    "S&P 500 (SPY)": {"SPY": 1},
    "Mondo (ACWI)": {"ACWI": 1},
    "Classico 60/40": {"SPY": 0.6, "AGG": 0.4},
    "Obbligazioni USA (AGG)": {"AGG": 1},
    "Oro (GLD)": {"GLD": 1},
}


class AppState(QObject):
    data_changed = Signal()
    settings_changed = Signal()
    open_portfolio = Signal(dict)       # richiesta di aprire un portafoglio nel costruttore
    portfolio_simulated = Signal(object)  # ultimo backtest.Result del costruttore (o None)

    def __init__(self):
        super().__init__()
        self.data: PriceData | None = None
        this_year = date.today().year
        self.settings = Settings(start_year=this_year - 20, end_year=this_year)
        self._monthly: dict[str, pd.DataFrame] = {}
        self._stats: dict[tuple, pd.DataFrame] = {}

    def set_data(self, data: PriceData) -> None:
        self.data = data
        self._monthly.clear()
        self._stats.clear()
        self.data_changed.emit()

    def set_settings(self, s: Settings) -> None:
        self.settings = s
        self.settings_changed.emit()

    def monthly(self) -> pd.DataFrame | None:
        if self.data is None:
            return None
        cur = self.settings.currency
        if cur not in self._monthly:
            self._monthly[cur] = self.data.monthly(cur)
        return self._monthly[cur]

    def period_prices(self) -> pd.DataFrame | None:
        m = self.monthly()
        if m is None:
            return None
        return slice_period(m, self.settings.start_year, self.settings.end_year)

    def period_stats(self) -> pd.DataFrame | None:
        s = self.settings
        key = (s.currency, s.start_year, s.end_year)
        if key not in self._stats:
            p = self.period_prices()
            if p is None:
                return None
            self._stats[key] = asset_stats(p)
        return self._stats[key]


class SettingsBar(QFrame):
    """Periodo, capitale, PAC, ribilanciamento, valuta, tasso risk-free."""

    def __init__(self, state: AppState, parent=None):
        super().__init__(parent)
        self.state = state
        self.setObjectName("SettingsBar")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(24, 12, 24, 12)
        lay.setSpacing(14)
        s = state.settings
        this_year = date.today().year

        self.start = QSpinBox(); self.start.setRange(2004, this_year); self.start.setValue(s.start_year)
        self.end = QSpinBox(); self.end.setRange(2004, this_year); self.end.setValue(s.end_year)
        self.initial = QDoubleSpinBox(); self.initial.setRange(0, 100_000_000); self.initial.setDecimals(0)
        self.initial.setSingleStep(1000); self.initial.setValue(s.initial); self.initial.setGroupSeparatorShown(True)
        self.monthly = QDoubleSpinBox(); self.monthly.setRange(0, 1_000_000); self.monthly.setDecimals(0)
        self.monthly.setSingleStep(50); self.monthly.setValue(s.monthly); self.monthly.setGroupSeparatorShown(True)
        self.rebal = QComboBox(); self.rebal.addItems(list(REBALANCE_OPTIONS)); self.rebal.setCurrentText(s.rebalance)
        self.currency = QComboBox(); self.currency.addItems(["EUR", "USD"]); self.currency.setCurrentText(s.currency)
        self.rf = QDoubleSpinBox(); self.rf.setRange(0, 15); self.rf.setDecimals(1); self.rf.setSingleStep(0.5)
        self.rf.setSuffix(" %"); self.rf.setValue(s.risk_free * 100)

        for w in (self.start, self.end):
            w.setFixedWidth(80)
        self.initial.setFixedWidth(130); self.monthly.setFixedWidth(110)
        self.rebal.setFixedWidth(130); self.currency.setFixedWidth(80); self.rf.setFixedWidth(80)
        self._update_prefix()

        lay.addWidget(field("Dal", self.start))
        lay.addWidget(field("Al", self.end))
        lay.addSpacing(8)
        lay.addWidget(field("Capitale iniziale", self.initial))
        lay.addWidget(field("Versamento mensile (PAC)", self.monthly))
        lay.addSpacing(8)
        lay.addWidget(field("Ribilanciamento", self.rebal))
        lay.addWidget(field("Valuta", self.currency))
        lay.addWidget(field("Tasso senza rischio", self.rf))
        lay.addStretch(1)

        self.rf.setToolTip("Rendimento di un investimento 'sicuro' (es. BOT), usato per lo Sharpe ratio.")
        self.rebal.setToolTip("Ogni quanto riportare i pesi alle percentuali scelte vendendo ciò che è salito "
                              "e comprando ciò che è sceso.")

        self._timer = QTimer(self, singleShot=True, interval=350)
        self._timer.timeout.connect(self._emit)
        for w in (self.start, self.end, self.initial, self.monthly, self.rf):
            w.valueChanged.connect(self._timer.start)
        for w in (self.rebal, self.currency):
            w.currentTextChanged.connect(self._timer.start)
        self.currency.currentTextChanged.connect(self._update_prefix)

    def _update_prefix(self):
        sym = "€ " if self.currency.currentText() == "EUR" else "$ "
        self.initial.setPrefix(sym)
        self.monthly.setPrefix(sym)

    def _emit(self):
        start, end = self.start.value(), self.end.value()
        if end < start:
            end = start
            self.end.blockSignals(True); self.end.setValue(end); self.end.blockSignals(False)
        self.state.set_settings(Settings(
            start_year=start, end_year=end, initial=self.initial.value(), monthly=self.monthly.value(),
            rebalance=self.rebal.currentText(), currency=self.currency.currentText(),
            risk_free=self.rf.value() / 100,
        ))
