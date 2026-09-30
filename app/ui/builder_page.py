"""Pagina 'Portafoglio': scegli gli asset, i pesi e guarda la simulazione."""
from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd
from PySide6.QtCore import QSortFilterProxyModel, Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (QAbstractItemView, QButtonGroup, QComboBox, QDoubleSpinBox,
                               QFileDialog, QFrame, QGridLayout, QHBoxLayout, QHeaderView,
                               QLineEdit, QMessageBox, QPushButton, QScrollArea,
                               QTableView, QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout,
                               QWidget)

from .. import backtest
from ..universe import ASSETS, BY_TICKER, CATEGORIES, CATEGORY_COLORS
from . import theme
from .charts import AnnualBarChart, TimeSeriesChart
from .state import BENCHMARKS, PRESETS, AppState
from .widgets import (DonutChart, KpiCard, card, fmt_money, fmt_money_short, fmt_num, fmt_pct,
                      label, tone)

SORT_ROLE = Qt.UserRole + 1
SAVE_DIR = Path(__file__).resolve().parents[2] / "portafogli"


def dot_icon(color: str, size: int = 10) -> QIcon:
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setBrush(QColor(color))
    p.setPen(Qt.NoPen)
    p.drawEllipse(0, 0, size, size)
    p.end()
    return QIcon(pm)


class CatalogFilter(QSortFilterProxyModel):
    def __init__(self):
        super().__init__()
        self.category: str | None = None
        self.text = ""
        self.setSortRole(SORT_ROLE)

    def set_filter(self, category: str | None = None, text: str | None = None):
        if category is not None:
            self.category = None if category == "Tutti" else category
        if text is not None:
            self.text = text.lower().strip()
        self.invalidateFilter()

    def filterAcceptsRow(self, row, parent):
        m = self.sourceModel()
        ticker = m.index(row, 0, parent).data(Qt.UserRole)
        a = BY_TICKER[ticker]
        if self.category and a.category != self.category:
            return False
        if self.text and self.text not in a.ticker.lower() and self.text not in a.name.lower():
            return False
        return True


class BuilderPage(QWidget):
    def __init__(self, state: AppState, parent=None):
        super().__init__(parent)
        self.state = state
        self.weights: dict[str, float] = {}
        self.result: backtest.Result | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)
        body = QWidget()
        body.setObjectName("Root")
        scroll.setWidget(body)
        root = QVBoxLayout(body)
        root.setContentsMargins(24, 20, 24, 24)
        root.setSpacing(18)

        root.addWidget(label("Costruisci il tuo portafoglio", "PageTitle"))
        root.addWidget(label("Scegli gli strumenti dal catalogo, assegna le percentuali e guarda come sarebbe "
                             "andato il portafoglio nel periodo selezionato. I risultati si aggiornano da soli.",
                             "PageSub", wrap=True))

        top = QHBoxLayout()
        top.setSpacing(18)
        top.addWidget(self._build_catalog(), 1)
        top.addWidget(self._build_portfolio(), 1)
        root.addLayout(top)

        self.banner = QFrame()
        self.banner.setObjectName("Banner")
        bl = QHBoxLayout(self.banner)
        bl.setContentsMargins(14, 10, 14, 10)
        self.banner_text = label("", wrap=True)
        self.banner_text.setStyleSheet(f"color:{theme.WARNING};")
        bl.addWidget(self.banner_text)
        self.banner.hide()
        root.addWidget(self.banner)

        root.addWidget(self._build_kpis())
        root.addWidget(self._build_charts())
        root.addStretch(1)

        self._sim_timer = QTimer(self, singleShot=True, interval=200)
        self._sim_timer.timeout.connect(self.simulate)
        state.data_changed.connect(self._on_data)
        state.settings_changed.connect(self._on_settings)
        state.open_portfolio.connect(self.load_weights)

    # ------------------------------------------------------------ catalogo
    def _build_catalog(self) -> QFrame:
        frame, lay = card("Catalogo", "Doppio clic per aggiungere. Clicca sulle colonne per ordinare.")
        self.search = QLineEdit()
        self.search.setPlaceholderText("Cerca per nome o ticker (es. Apple, SPY, oro)…")
        self.search.setClearButtonEnabled(True)
        lay.addWidget(self.search)

        chips = QHBoxLayout()
        chips.setSpacing(6)
        self.chip_group = QButtonGroup(self)
        for i, name in enumerate(["Tutti"] + CATEGORIES):
            b = QPushButton(name)
            b.setObjectName("Chip")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            if name != "Tutti":
                b.setIcon(dot_icon(CATEGORY_COLORS[name], 8))
            if i == 0:
                b.setChecked(True)
            self.chip_group.addButton(b)
            chips.addWidget(b)
        chips.addStretch(1)
        lay.addLayout(chips)

        self.cat_model = QStandardItemModel(0, 6)
        self.cat_model.setHorizontalHeaderLabels(["Ticker", "Nome", "Dal", "Rend./anno", "Volatilità", "Max DD"])
        for a in ASSETS:
            t = QStandardItem(a.ticker)
            t.setData(a.ticker, Qt.UserRole)
            t.setData(a.ticker, SORT_ROLE)
            t.setIcon(dot_icon(CATEGORY_COLORS[a.category]))
            t.setToolTip(a.category)
            n = QStandardItem(a.name)
            n.setData(a.name, SORT_ROLE)
            n.setToolTip(a.name)
            row = [t, n] + [QStandardItem("–") for _ in range(4)]
            for it in row:
                it.setEditable(False)
            for it in row[2:]:
                it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.cat_model.appendRow(row)

        self.proxy = CatalogFilter()
        self.proxy.setSourceModel(self.cat_model)
        self.catalog = QTableView()
        self.catalog.setModel(self.proxy)
        self.catalog.setSortingEnabled(True)
        self.catalog.sortByColumn(0, Qt.AscendingOrder)
        self.catalog.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.catalog.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.catalog.verticalHeader().hide()
        self.catalog.verticalHeader().setDefaultSectionSize(32)
        self.catalog.setShowGrid(False)
        self.catalog.setWordWrap(False)
        self.catalog.setMinimumHeight(420)
        h = self.catalog.horizontalHeader()
        h.setSectionResizeMode(QHeaderView.Fixed)
        h.setSectionResizeMode(1, QHeaderView.Stretch)
        for col, width in ((0, 92), (2, 50), (3, 84), (4, 76), (5, 64)):
            self.catalog.setColumnWidth(col, width)
        h.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        lay.addWidget(self.catalog, 1)

        row = QHBoxLayout()
        self.catalog_count = label("", "Faint")
        row.addWidget(self.catalog_count)
        row.addStretch(1)
        add = QPushButton("Aggiungi selezionati  →")
        add.setCursor(Qt.PointingHandCursor)
        add.clicked.connect(self._add_selected)
        row.addWidget(add)
        lay.addLayout(row)

        self.search.textChanged.connect(lambda t: (self.proxy.set_filter(text=t), self._update_count()))
        self.chip_group.buttonClicked.connect(lambda b: (self.proxy.set_filter(category=b.text()),
                                                         self._update_count()))
        self.catalog.doubleClicked.connect(lambda idx: self.add_asset(idx.siblingAtColumn(0).data(Qt.UserRole)))
        self._update_count()
        return frame

    def _update_count(self):
        self.catalog_count.setText(f"{self.proxy.rowCount()} strumenti")

    def _refresh_catalog_stats(self):
        stats = self.state.period_stats()
        if stats is None:
            return
        for r in range(self.cat_model.rowCount()):
            t = self.cat_model.item(r, 0).data(Qt.UserRole)
            if t not in stats.index:
                vals = (math.nan,) * 4
            else:
                s = stats.loc[t]
                vals = (s.since, s.cagr, s.vol, s.maxdd)
            since, cagr, vol, dd = vals
            cells = [
                ("–" if pd.isna(since) else str(int(since)), since if not pd.isna(since) else 9999, None),
                (fmt_pct(cagr), cagr if not pd.isna(cagr) else -9, tone(cagr)),
                (fmt_pct(vol), vol if not pd.isna(vol) else 9, None),
                (fmt_pct(dd, 0), dd if not pd.isna(dd) else -9, None),
            ]
            for c, (txt, key, color) in enumerate(cells, start=2):
                it = self.cat_model.item(r, c)
                it.setText(txt)
                it.setData(float(key), SORT_ROLE)
                if color:
                    it.setForeground(QColor(color))

    # ------------------------------------------------------------ portafoglio
    def _build_portfolio(self) -> QFrame:
        frame, lay = card("Il tuo portafoglio")

        tools = QHBoxLayout()
        tools.setSpacing(8)
        self.preset = QComboBox()
        self.preset.addItem("Carica un modello…")
        self.preset.addItems(list(PRESETS))
        self.preset.setMinimumWidth(220)
        self.preset.activated.connect(self._on_preset)
        tools.addWidget(self.preset)
        tools.addStretch(1)
        for text, slot, tip in (
            ("Pesi uguali", self._equal_weights, "Stessa percentuale a tutti gli asset"),
            ("Normalizza", self._normalize, "Riporta il totale al 100% mantenendo le proporzioni"),
            ("Salva", self._save, "Salva il portafoglio su file"),
            ("Apri", self._load, "Apri un portafoglio salvato"),
            ("Svuota", self._clear, "Rimuovi tutti gli asset"),
        ):
            b = QPushButton(text)
            b.setToolTip(tip)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(slot)
            tools.addWidget(b)
        lay.addLayout(tools)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Asset", "Categoria", "Peso", ""])
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(40)
        self.table.setShowGrid(False)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.setFocusPolicy(Qt.NoFocus)
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.Stretch)
        h.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.Fixed)
        h.setSectionResizeMode(3, QHeaderView.Fixed)
        h.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.table.setColumnWidth(2, 110)
        self.table.setColumnWidth(3, 36)
        self.table.setMinimumHeight(230)

        self.empty_hint = label("Il portafoglio è vuoto.\nAggiungi asset dal catalogo oppure carica un modello "
                                "dal menu qui sopra.", "Muted", wrap=True)
        self.empty_hint.setAlignment(Qt.AlignCenter)
        self.empty_hint.setMinimumHeight(230)
        lay.addWidget(self.table, 1)
        lay.addWidget(self.empty_hint, 1)

        bottom = QHBoxLayout()
        self.donut = DonutChart()
        bottom.addWidget(self.donut, 1)
        side = QVBoxLayout()
        side.addStretch(1)
        self.total_pill = label("")
        self.total_pill.setAlignment(Qt.AlignCenter)
        side.addWidget(self.total_pill)
        self.total_hint = label("", "Faint", wrap=True)
        self.total_hint.setAlignment(Qt.AlignCenter)
        self.total_hint.setMaximumWidth(210)
        side.addWidget(self.total_hint)
        side.addStretch(1)
        bottom.addLayout(side)
        lay.addLayout(bottom)
        self._refresh_table()
        return frame

    def add_asset(self, ticker: str, weight: float | None = None):
        if ticker in self.weights:
            return
        if weight is None:
            remaining = max(0.0, 100 - sum(self.weights.values()))
            weight = remaining if remaining > 0 else 10.0
        self.weights[ticker] = float(weight)
        self._refresh_table()
        self._schedule()

    def _add_selected(self):
        rows = {i.row() for i in self.catalog.selectionModel().selectedRows()}
        tickers = [self.proxy.index(r, 0).data(Qt.UserRole) for r in sorted(rows)]
        new = [t for t in tickers if t not in self.weights]
        if not new:
            return
        remaining = max(0.0, 100 - sum(self.weights.values()))
        each = remaining / len(new) if remaining > 0 else 10.0
        for t in new:
            self.weights[t] = round(each, 2)
        self._refresh_table()
        self._schedule()

    def remove_asset(self, ticker: str):
        self.weights.pop(ticker, None)
        self._refresh_table()
        self._schedule()

    def load_weights(self, weights: dict):
        tot = sum(weights.values()) or 1
        scale = 100 / tot
        self.weights = {t: round(w * scale, 2) for t, w in weights.items() if t in BY_TICKER}
        self._refresh_table()
        self._schedule()

    def _on_preset(self, idx: int):
        if idx <= 0:
            return
        self.load_weights(PRESETS[self.preset.itemText(idx)])
        self.preset.setCurrentIndex(0)

    def _equal_weights(self):
        if self.weights:
            w = round(100 / len(self.weights), 2)
            self.weights = {t: w for t in self.weights}
            self._refresh_table(); self._schedule()

    def _normalize(self):
        tot = sum(self.weights.values())
        if tot > 0:
            self.weights = {t: round(w * 100 / tot, 2) for t, w in self.weights.items()}
            self._refresh_table(); self._schedule()

    def _clear(self):
        self.weights.clear()
        self._refresh_table(); self._schedule()

    def _save(self):
        if not self.weights:
            return
        SAVE_DIR.mkdir(exist_ok=True)
        path, _ = QFileDialog.getSaveFileName(self, "Salva portafoglio", str(SAVE_DIR / "portafoglio.json"),
                                              "Portafoglio (*.json)")
        if path:
            Path(path).write_text(json.dumps(self.weights, indent=2), encoding="utf-8")

    def _load(self):
        SAVE_DIR.mkdir(exist_ok=True)
        path, _ = QFileDialog.getOpenFileName(self, "Apri portafoglio", str(SAVE_DIR), "Portafoglio (*.json)")
        if not path:
            return
        try:
            w = json.loads(Path(path).read_text(encoding="utf-8"))
            self.load_weights({str(k): float(v) for k, v in w.items()})
        except Exception as e:
            QMessageBox.warning(self, "Errore", f"File non valido:\n{e}")

    def _refresh_table(self):
        self.table.setRowCount(0)
        for t, w in self.weights.items():
            a = BY_TICKER[t]
            r = self.table.rowCount()
            self.table.insertRow(r)
            it = QTableWidgetItem(f"{t}   ·   {a.name}")
            it.setIcon(dot_icon(CATEGORY_COLORS[a.category]))
            it.setToolTip(a.name)
            self.table.setItem(r, 0, it)
            c = QTableWidgetItem(a.category)
            c.setForeground(QColor(theme.MUTED))
            self.table.setItem(r, 1, c)
            spin = QDoubleSpinBox()
            spin.setRange(0, 100)
            spin.setDecimals(1)
            spin.setSingleStep(1)
            spin.setSuffix(" %")
            spin.setValue(w)
            spin.setAlignment(Qt.AlignRight)
            spin.valueChanged.connect(lambda v, t=t: self._on_weight(t, v))
            self.table.setCellWidget(r, 2, spin)
            rm = QPushButton("✕")
            rm.setObjectName("Remove")
            rm.setCursor(Qt.PointingHandCursor)
            rm.setToolTip("Rimuovi")
            rm.clicked.connect(lambda _=False, t=t: self.remove_asset(t))
            self.table.setCellWidget(r, 3, rm)
        empty = not self.weights
        self.table.setVisible(not empty)
        self.empty_hint.setVisible(empty)
        self._refresh_totals()

    def _on_weight(self, ticker: str, v: float):
        self.weights[ticker] = v
        self._refresh_totals()
        self._schedule()

    def _refresh_totals(self):
        tot = sum(self.weights.values())
        by_cat = {c: 0.0 for c in CATEGORIES}
        for t, w in self.weights.items():
            by_cat[BY_TICKER[t].category] += w
        self.donut.set_data([(c, v, CATEGORY_COLORS[c]) for c, v in by_cat.items()],
                            "ASSET", str(len(self.weights)))
        ok = abs(tot - 100) < 0.05
        color = theme.POSITIVE if ok else theme.WARNING
        self.total_pill.setText(f"Totale  {fmt_num(tot, 1)}%")
        self.total_pill.setStyleSheet(
            f"color:{color}; font-weight:700; font-size:12pt; padding:8px 16px; border-radius:14px;"
            f"background: {'rgba(46,211,160,0.12)' if ok else 'rgba(255,181,71,0.12)'};")
        if not self.weights:
            self.total_hint.setText("")
        elif ok:
            self.total_hint.setText("Perfetto, i pesi sommano al 100%.")
        else:
            self.total_hint.setText("La simulazione usa i pesi in proporzione. Premi «Normalizza» per "
                                    "portarli al 100%.")

    # ------------------------------------------------------------ risultati
    def _build_kpis(self) -> QWidget:
        w = QWidget()
        grid = QGridLayout(w)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(12)
        self.kpi = {}
        names = [
            ("final", "Valore finale"), ("invested", "Totale versato"), ("gain", "Guadagno"),
            ("cagr", "Rendimento annuo"), ("period", "Periodo"),
            ("vol", "Volatilità"), ("dd", "Max drawdown"), ("sharpe", "Sharpe ratio"),
            ("best", "Anno migliore"), ("worst", "Anno peggiore"),
        ]
        tips = {
            "cagr": "Rendimento medio composto annuo (CAGR) del portafoglio, indipendente dai versamenti.",
            "vol": "Quanto oscilla il portafoglio in un anno tipico (deviazione standard). Più alto = più rischio.",
            "dd": "La perdita massima dal picco al minimo successivo. Ti dice quanto male sarebbe potuta andare.",
            "sharpe": "Rendimento extra rispetto al tasso senza rischio diviso per la volatilità. "
                      "Sopra 0,5 è discreto, sopra 1 è ottimo.",
            "gain": "Valore finale meno il totale versato.",
        }
        for i, (key, title) in enumerate(names):
            k = KpiCard(title)
            if key in tips:
                k.setToolTip(tips[key])
            self.kpi[key] = k
            grid.addWidget(k, i // 5, i % 5)
        return w

    def _build_charts(self) -> QFrame:
        frame, lay = card(None)
        head = QHBoxLayout()
        head.addWidget(label("Andamento storico", "CardTitle"))
        head.addStretch(1)
        head.addWidget(label("Confronta con", "Muted"))
        self.bench = QComboBox()
        self.bench.addItems(list(BENCHMARKS))
        self.bench.setCurrentText("S&P 500 (SPY)")
        self.bench.setMinimumWidth(190)
        self.bench.currentTextChanged.connect(self._schedule)
        head.addWidget(self.bench)
        lay.addLayout(head)

        self.tabs = QTabWidget()
        cur = lambda: self.state.settings.currency
        self.value_chart = TimeSeriesChart(lambda v: fmt_money_short(v, cur()))
        self.growth_chart = TimeSeriesChart(lambda v: f"{v:,.0f}".replace(",", "."))
        self.dd_chart = TimeSeriesChart(lambda v: f"{v * 100:.0f}%")
        self.year_chart = AnnualBarChart()
        self.detail = QTableWidget(0, 7)
        self.detail.setHorizontalHeaderLabels(["Asset", "Peso iniziale", "Peso finale", "Rend./anno",
                                               "Volatilità", "Max DD", "Valore finale"])
        self.detail.verticalHeader().hide()
        self.detail.setShowGrid(False)
        self.detail.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.detail.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.detail.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tabs.addTab(self.value_chart, "Valore in denaro")
        self.tabs.addTab(self.growth_chart, "Crescita di 100")
        self.tabs.addTab(self.dd_chart, "Drawdown")
        self.tabs.addTab(self.year_chart, "Rendimenti annui")
        self.tabs.addTab(self.detail, "Dettaglio asset")
        self.tabs.setMinimumHeight(420)
        lay.addWidget(self.tabs)
        return frame

    # ------------------------------------------------------------ simulazione
    def _on_data(self):
        self._refresh_catalog_stats()
        self._schedule()

    def _on_settings(self):
        self._refresh_catalog_stats()
        self._schedule()

    def _schedule(self, *_):
        self._sim_timer.start()

    def _clear_results(self, message: str = ""):
        for k in self.kpi.values():
            k.set("–")
        self.value_chart.set_series([])
        self.growth_chart.set_series([])
        self.dd_chart.set_series([])
        self.year_chart.set_data(pd.Series(dtype=float))
        self.detail.setRowCount(0)
        self.banner_text.setText(message)
        self.banner.setVisible(bool(message))
        self.result = None
        self.state.portfolio_simulated.emit(None)

    def simulate(self):
        prices = self.state.period_prices()
        weights = {t: w for t, w in self.weights.items() if w > 0}
        if prices is None or not weights:
            self._clear_results()
            return
        s = self.state.settings
        try:
            res = backtest.run(prices, weights, s)
        except ValueError as e:
            self._clear_results(str(e))
            return
        self.result = res
        self.state.portfolio_simulated.emit(res)

        bench_res = None
        bench_name = self.bench.currentText()
        bw = BENCHMARKS.get(bench_name)
        if bw:
            try:
                bp = prices.loc[res.value.index[0]:]
                bench_res = backtest.run(bp, bw, s)
            except ValueError:
                bench_res = None

        self._show_kpis(res)
        self._show_charts(res, bench_res, bench_name)
        self._show_detail(res, prices)

        start = res.value.index[0]
        if res.limited_by:
            a = BY_TICKER[res.limited_by]
            self.banner_text.setText(
                f"⚠  Il periodo parte da {start:%m/%Y} invece che da gennaio {s.start_year}: "
                f"{a.ticker} ({a.name}) non ha dati prima di quella data.")
            self.banner.show()
        else:
            self.banner.hide()

    def _show_kpis(self, res: backtest.Result):
        m = res.metrics
        cur = self.state.settings.currency
        k = self.kpi
        k["final"].set(fmt_money(m["final_value"], cur), color=theme.TEXT)
        pac = self.state.settings.monthly > 0
        k["invested"].set(fmt_money(m["invested"], cur),
                          "iniziale + PAC" if pac else "capitale iniziale")
        gain_pct = m["gain"] / m["invested"] if m["invested"] else float("nan")
        k["gain"].set(fmt_money(m["gain"], cur), fmt_pct(gain_pct, 1, sign=True), tone(m["gain"]))
        k["cagr"].set(fmt_pct(m["cagr"], 2), f"IRR sui tuoi versamenti {fmt_pct(m['irr'], 2)}" if pac
                      else f"totale {fmt_pct(m['total_return'], 0, sign=True)}", tone(m["cagr"]))
        idx = res.value.index
        k["period"].set(f"{res.returns.index[0].year}–{idx[-1].year}", f"{fmt_num(m['years'], 1)} anni")
        k["vol"].set(fmt_pct(m["volatility"], 1), f"mesi positivi {fmt_pct(m['positive_months'], 0)}")
        dd = res.drawdown
        k["dd"].set(fmt_pct(m["max_drawdown"], 1), f"minimo a {dd.idxmin():%m/%Y}", theme.NEGATIVE)
        sh = m["sharpe"]
        k["sharpe"].set(fmt_num(sh, 2), f"Sortino {fmt_num(m['sortino'], 2)}",
                        theme.POSITIVE if sh >= 0.8 else (theme.WARNING if sh >= 0.4 else theme.NEGATIVE))
        ann = res.annual_returns
        k["best"].set(fmt_pct(m["best_year"], 1, sign=True), str(ann.idxmax()), theme.POSITIVE)
        k["worst"].set(fmt_pct(m["worst_year"], 1, sign=True), str(ann.idxmin()), tone(m["worst_year"]))

    def _show_charts(self, res, bench, bench_name):
        acc, grey = theme.ACCENT, theme.MUTED
        bcol = theme.WARNING
        val = [("Portafoglio", res.value, acc), ("Versato", res.invested, grey)]
        growth = [("Portafoglio", res.index, acc)]
        dd = [("Portafoglio", res.drawdown, theme.NEGATIVE)]
        if bench is not None:
            val.append((bench_name, bench.value, bcol))
            growth.append((bench_name, bench.index / bench.index.iloc[0] * 100, bcol))
            dd.append((bench_name, bench.drawdown, bcol))
        self.value_chart.set_series(val, fill_first=True, dashed={"Versato"})
        self.growth_chart.set_series(growth, fill_first=True)
        self.dd_chart.set_series(dd, fill_level=0.0)
        self.year_chart.set_data(res.annual_returns, bench.annual_returns if bench is not None else None,
                                 bench_name)

    def _show_detail(self, res: backtest.Result, prices: pd.DataFrame):
        cur = self.state.settings.currency
        sub = prices.loc[res.value.index[0]:, list(res.weights)]
        final = res.asset_values.iloc[-1]
        final_w = final / final.sum()
        self.detail.setRowCount(0)
        for t, w in sorted(res.weights.items(), key=lambda p: -p[1]):
            s = sub[t].ffill()
            years = (s.index[-1] - s.index[0]).days / 365.25
            cagr = (s.iloc[-1] / s.iloc[0]) ** (1 / years) - 1 if years > 0 else float("nan")
            vol = s.pct_change().std() * (12 ** 0.5)
            dd = (s / s.cummax() - 1).min()
            r = self.detail.rowCount()
            self.detail.insertRow(r)
            a = BY_TICKER[t]
            cells = [f"{t}  ·  {a.name}", fmt_pct(w, 1), fmt_pct(final_w[t], 1), fmt_pct(cagr, 2),
                     fmt_pct(vol, 1), fmt_pct(dd, 1), fmt_money(final[t], cur)]
            for c, txt in enumerate(cells):
                it = QTableWidgetItem(txt)
                if c == 0:
                    it.setIcon(dot_icon(CATEGORY_COLORS[a.category]))
                else:
                    it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                if c == 3:
                    it.setForeground(QColor(tone(cagr)))
                self.detail.setItem(r, c, it)
