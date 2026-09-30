"""Pagina 'Ottimizzatore': trova le combinazioni migliori sul periodo storico."""
from __future__ import annotations

from PySide6.QtCore import QThreadPool, Qt
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QDoubleSpinBox, QFrame, QGridLayout,
                               QHBoxLayout, QProgressBar, QPushButton, QRadioButton, QScrollArea,
                               QTabWidget, QVBoxLayout, QWidget)

from .. import backtest, optimizer
from ..universe import ASSETS, BY_TICKER, CATEGORIES, CATEGORY_COLORS
from . import theme
from .charts import FrontierChart, TimeSeriesChart
from .state import AppState
from .widgets import (Task, WeightBars, card, fmt_money, fmt_money_short, fmt_num, fmt_pct, label,
                      tone)

SOLUTION_COLORS = {
    optimizer.MAX_SHARPE: "#B78CFF",
    optimizer.MAX_RETURN: "#4FD1E8",
    optimizer.MIN_RISK: "#C6F36B",
}
SOLUTION_DESC = {
    optimizer.MAX_SHARPE: "Il miglior compromesso: più rendimento per ogni unità di rischio (max Sharpe).",
    optimizer.MAX_RETURN: "Il portafoglio che è cresciuto di più, accettando oscillazioni forti.",
    optimizer.MIN_RISK: "Il portafoglio più stabile: oscillazioni minime, rendimento più basso.",
}


def _pct_spin(value: float, maximum: float = 100) -> QDoubleSpinBox:
    s = QDoubleSpinBox()
    s.setRange(0, maximum)
    s.setDecimals(0)
    s.setSingleStep(5)
    s.setSuffix(" %")
    s.setValue(value)
    s.setFixedWidth(80)
    s.setAlignment(Qt.AlignRight)
    return s


class SolutionCard(QFrame):
    def __init__(self, name: str, on_open, parent=None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.name = name
        self.weights: dict[str, float] = {}
        color = SOLUTION_COLORS[name]
        self.setStyleSheet(f"QFrame#Card {{ border-top: 3px solid {color}; }}")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 14, 18, 16)
        lay.setSpacing(8)
        title = label(f"★  {name}", "CardTitle")
        title.setStyleSheet(f"color:{color};")
        lay.addWidget(title)
        lay.addWidget(label(SOLUTION_DESC[name], "Muted", wrap=True))

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(2)
        self.vals = {}
        for i, (key, t) in enumerate([("cagr", "Rend./anno"), ("vol", "Volatilità"), ("dd", "Max DD"),
                                      ("sharpe", "Sharpe"), ("final", "Valore finale"), ("n", "Asset")]):
            grid.addWidget(label(t.upper(), "KpiTitle"), (i // 3) * 2, i % 3)
            v = label("–")
            v.setStyleSheet("font-size: 12.5pt; font-weight: 700;")
            grid.addWidget(v, (i // 3) * 2 + 1, i % 3)
            self.vals[key] = v
        lay.addLayout(grid)
        lay.addSpacing(4)
        self.bars = WeightBars()
        lay.addWidget(self.bars)
        lay.addStretch(1)
        self.open_btn = QPushButton("Apri nel costruttore  →")
        self.open_btn.setCursor(Qt.PointingHandCursor)
        self.open_btn.setEnabled(False)
        self.open_btn.clicked.connect(lambda: on_open(self.weights))
        lay.addWidget(self.open_btn)

    def set_result(self, weights: dict[str, float], res: backtest.Result, currency: str):
        self.weights = weights
        m = res.metrics
        self.vals["cagr"].setText(fmt_pct(m["cagr"], 2))
        self.vals["cagr"].setStyleSheet(f"font-size: 12.5pt; font-weight: 700; color:{tone(m['cagr'])};")
        self.vals["vol"].setText(fmt_pct(m["volatility"], 1))
        self.vals["dd"].setText(fmt_pct(m["max_drawdown"], 1))
        self.vals["sharpe"].setText(fmt_num(m["sharpe"], 2))
        self.vals["final"].setText(fmt_money_short(m["final_value"], currency))
        self.vals["final"].setToolTip(fmt_money(m["final_value"], currency))
        self.vals["n"].setText(str(len(weights)))
        self.bars.set_rows([(t, BY_TICKER[t].name, w, CATEGORY_COLORS[BY_TICKER[t].category])
                            for t, w in weights.items()])
        self.open_btn.setEnabled(True)


class OptimizerPage(QWidget):
    def __init__(self, state: AppState, get_portfolio, parent=None):
        super().__init__(parent)
        self.state = state
        self.get_portfolio = get_portfolio
        self.pool = QThreadPool.globalInstance()
        self.output: optimizer.OptimizationOutput | None = None

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

        root.addWidget(label("Trova la combinazione migliore", "PageTitle"))
        root.addWidget(label("L'ottimizzatore prova tutte le combinazioni possibili degli asset scelti e ti "
                             "mostra le tre migliori secondo criteri diversi, rispettando i vincoli che imposti.",
                             "PageSub", wrap=True))

        banner = QFrame()
        banner.setObjectName("Banner")
        bl = QHBoxLayout(banner)
        bl.setContentsMargins(14, 10, 14, 10)
        warn = label("⚠  Attenzione: questi portafogli sono ottimizzati «col senno di poi» sui dati passati. "
                     "Chi ha vinto negli ultimi 20 anni non vincerà per forza nei prossimi 20. Usa i risultati "
                     "come spunto e preferisci soluzioni diversificate (limita il peso massimo per asset).",
                     wrap=True)
        warn.setStyleSheet(f"color:{theme.WARNING};")
        bl.addWidget(warn)
        root.addWidget(banner)

        top = QHBoxLayout()
        top.setSpacing(18)
        top.addWidget(self._build_config(), 0)
        sol = QHBoxLayout()
        sol.setSpacing(14)
        self.cards = {n: SolutionCard(n, self._open) for n in optimizer.OBJECTIVES}
        for c in self.cards.values():
            sol.addWidget(c, 1)
        top.addLayout(sol, 1)
        root.addLayout(top)

        charts, lay = card(None)
        self.tabs = QTabWidget()
        self.frontier = FrontierChart()
        cur = lambda: self.state.settings.currency
        self.curves = TimeSeriesChart(lambda v: fmt_money_short(v, cur()))
        self.dd = TimeSeriesChart(lambda v: f"{v * 100:.0f}%")
        self.tabs.addTab(self.frontier, "Frontiera efficiente")
        self.tabs.addTab(self.curves, "Andamento a confronto")
        self.tabs.addTab(self.dd, "Drawdown a confronto")
        self.tabs.setMinimumHeight(460)
        lay.addWidget(self.tabs)
        self.frontier_hint = label(
            "Ogni puntino è un asset (colore = categoria). La linea bianca è la frontiera efficiente: "
            "i portafogli che danno il massimo rendimento per ogni livello di rischio. Le stelle sono le "
            "tre soluzioni trovate: stanno sotto la frontiera «libera» perché rispettano i tuoi vincoli.", "Faint", wrap=True)
        lay.addWidget(self.frontier_hint)
        root.addWidget(charts)
        root.addStretch(1)

        state.data_changed.connect(self._update_universe_count)
        state.settings_changed.connect(self._update_universe_count)

    # ------------------------------------------------------------ configurazione
    def _build_config(self) -> QFrame:
        frame, lay = card("Impostazioni")
        frame.setFixedWidth(360)

        lay.addWidget(label("TRA QUALI ASSET CERCARE", "FieldLabel"))
        self.src_group = QButtonGroup(self)
        self.src_all = QRadioButton("Tutto il catalogo (categorie spuntate)")
        self.src_mine = QRadioButton("Solo gli asset del mio portafoglio")
        self.src_all.setChecked(True)
        for b in (self.src_all, self.src_mine):
            self.src_group.addButton(b)
            lay.addWidget(b)
            b.toggled.connect(self._update_universe_count)

        lay.addSpacing(6)
        lay.addWidget(label("VINCOLI PER CATEGORIA", "FieldLabel"))
        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(6)
        grid.addWidget(label("min", "Faint"), 0, 1, Qt.AlignCenter)
        grid.addWidget(label("max", "Faint"), 0, 2, Qt.AlignCenter)
        self.cat_check, self.cat_min, self.cat_max = {}, {}, {}
        for i, cat in enumerate(CATEGORIES, start=1):
            cb = QCheckBox(cat)
            cb.setChecked(True)
            cb.setStyleSheet(f"QCheckBox {{ color: {CATEGORY_COLORS[cat]}; font-weight: 600; }}")
            cb.toggled.connect(self._update_universe_count)
            mn, mx = _pct_spin(0), _pct_spin(100)
            grid.addWidget(cb, i, 0)
            grid.addWidget(mn, i, 1)
            grid.addWidget(mx, i, 2)
            self.cat_check[cat], self.cat_min[cat], self.cat_max[cat] = cb, mn, mx
        lay.addLayout(grid)

        lay.addSpacing(6)
        row = QHBoxLayout()
        row.addWidget(label("PESO MASSIMO PER SINGOLO ASSET", "FieldLabel"))
        row.addStretch(1)
        self.max_w = _pct_spin(20)
        self.max_w.setRange(1, 100)
        self.max_w.setToolTip("Evita di mettere tutto su pochi titoli. 10–25% è una scelta prudente.")
        row.addWidget(self.max_w)
        lay.addLayout(row)

        lay.addSpacing(6)
        self.universe_lbl = label("", "Muted", wrap=True)
        lay.addWidget(self.universe_lbl)
        lay.addStretch(1)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(6)
        self.progress.hide()
        lay.addWidget(self.progress)
        self.error = label("", wrap=True)
        self.error.setStyleSheet(f"color:{theme.NEGATIVE};")
        self.error.hide()
        lay.addWidget(self.error)
        self.run_btn = QPushButton("Trova i portafogli migliori")
        self.run_btn.setObjectName("Primary")
        self.run_btn.setCursor(Qt.PointingHandCursor)
        self.run_btn.clicked.connect(self.run)
        lay.addWidget(self.run_btn)
        return frame

    def _candidates(self) -> list[str]:
        if self.src_mine.isChecked():
            return [t for t, w in self.get_portfolio().items() if w > 0]
        cats = {c for c, cb in self.cat_check.items() if cb.isChecked()}
        return [a.ticker for a in ASSETS if a.category in cats]

    def _update_universe_count(self, *_):
        prices = self.state.period_prices()
        cands = self._candidates()
        if prices is None:
            self.universe_lbl.setText("In attesa dei dati…")
            return
        ok, bad = optimizer.eligible_universe(prices, [t for t in cands if t in prices])
        missing = len(cands) - len(ok)
        s = self.state.settings
        txt = f"<b>{len(ok)}</b> asset con storico completo dal {s.start_year} al {s.end_year}."
        if missing:
            txt += f" {missing} esclusi perché nati dopo (riduci il periodo per includerli)."
        self.universe_lbl.setText(txt)

    def _constraints(self) -> optimizer.Constraints:
        c = optimizer.Constraints(max_weight=self.max_w.value() / 100)
        for cat in CATEGORIES:
            on = self.cat_check[cat].isChecked() or self.src_mine.isChecked()
            c.category_min[cat] = self.cat_min[cat].value() / 100 if on else 0.0
            c.category_max[cat] = self.cat_max[cat].value() / 100 if on else 0.0
        return c

    # ------------------------------------------------------------ esecuzione
    def run(self):
        prices = self.state.period_prices()
        if prices is None:
            return
        cands = [t for t in self._candidates() if t in prices]
        c = self._constraints()
        self.error.hide()
        self.run_btn.setEnabled(False)
        self.run_btn.setText("Calcolo in corso…")
        self.progress.show()
        task = Task(self._compute, prices, cands, c, self.state.settings)
        task.signals.finished.connect(self._on_done)
        task.signals.error.connect(self._on_error)
        self.pool.start(task)

    @staticmethod
    def _compute(prices, cands, c, settings):
        out = optimizer.optimize(prices, cands, c, settings.risk_free)
        window = prices.loc[out.start:out.end]
        results = {n: backtest.run(window, w, settings) for n, w in out.solutions.items()}
        return out, results, settings

    def _reset_button(self):
        self.run_btn.setEnabled(True)
        self.run_btn.setText("Trova i portafogli migliori")
        self.progress.hide()

    def _on_error(self, msg: str):
        self._reset_button()
        self.error.setText(msg)
        self.error.show()

    def _on_done(self, payload):
        self._reset_button()
        out, results, settings = payload
        self.output = out
        for n, card_ in self.cards.items():
            card_.set_result(out.solutions[n], results[n], settings.currency)

        colors = {t: CATEGORY_COLORS[BY_TICKER[t].category] for t in out.asset_points.index}
        names = {t: BY_TICKER[t].name for t in out.asset_points.index}
        # rischio/rendimento delle soluzioni nello stesso spazio della frontiera
        pts = [(n, out.stats[n][0], out.stats[n][1], SOLUTION_COLORS[n]) for n in optimizer.OBJECTIVES]
        self.frontier.set_data(out.asset_points, colors, names,
                               (out.frontier.vols, out.frontier.rets), pts)
        self.curves.set_series([(n, results[n].value, SOLUTION_COLORS[n]) for n in optimizer.OBJECTIVES]
                               + [("Versato", results[optimizer.MAX_SHARPE].invested, theme.MUTED)],
                               dashed={"Versato"})
        self.dd.set_series([(n, results[n].drawdown, SOLUTION_COLORS[n]) for n in optimizer.OBJECTIVES])
        self.frontier_hint.setText(
            self.frontier_hint.text().split(" Periodo")[0]
            + f" Periodo analizzato: {out.start:%m/%Y} – {out.end:%m/%Y}, {len(out.universe)} asset.")

    def _open(self, weights: dict[str, float]):
        if weights:
            self.state.open_portfolio.emit({t: w * 100 for t, w in weights.items()})
