"""Pagina 'Proiezione': se verso X al mese, quanto avro' nell'anno Y?"""
from __future__ import annotations

from datetime import date

import pandas as pd
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QAbstractItemView, QButtonGroup, QCheckBox, QDoubleSpinBox,
                               QGridLayout, QHBoxLayout, QHeaderView, QRadioButton, QScrollArea,
                               QSpinBox, QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout,
                               QWidget)

from .. import backtest
from ..projection import Plan, Projection, project
from . import theme
from .charts import TimeSeriesChart
from .state import AppState
from .widgets import KpiCard, card, fmt_money, fmt_money_short, fmt_num, fmt_pct, label


def _money_spin(value: float, step: float, maximum: float = 100_000_000) -> QDoubleSpinBox:
    s = QDoubleSpinBox()
    s.setRange(0, maximum)
    s.setDecimals(0)
    s.setSingleStep(step)
    s.setGroupSeparatorShown(True)
    s.setValue(value)
    s.setAlignment(Qt.AlignRight)
    s.setFixedWidth(140)
    return s


def _pct_spin(value: float, maximum: float = 30, decimals: int = 1) -> QDoubleSpinBox:
    s = QDoubleSpinBox()
    s.setRange(-10, maximum)
    s.setDecimals(decimals)
    s.setSingleStep(0.5)
    s.setSuffix(" %")
    s.setValue(value)
    s.setAlignment(Qt.AlignRight)
    s.setFixedWidth(100)
    return s


class ProjectionPage(QWidget):
    def __init__(self, state: AppState, parent=None):
        super().__init__(parent)
        self.state = state
        self.portfolio: backtest.Result | None = None
        self.proj: Projection | None = None

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

        root.addWidget(label("Proiezione futura", "PageTitle"))
        root.addWidget(label("Quanto potresti avere in futuro versando una cifra ogni mese? L'app simula migliaia "
                             "di futuri possibili ricombinando gli anni buoni e cattivi del tuo portafoglio.",
                             "PageSub", wrap=True))

        row = QHBoxLayout()
        row.setSpacing(18)
        row.addWidget(self._build_config(), 0, Qt.AlignTop)
        right = QVBoxLayout()
        right.setSpacing(14)
        right.addWidget(self._build_headline())
        right.addWidget(self._build_kpis())
        right.addWidget(self._build_charts(), 1)
        row.addLayout(right, 1)
        root.addLayout(row)
        root.addStretch(1)

        self._timer = QTimer(self, singleShot=True, interval=150)
        self._timer.timeout.connect(self.recompute)
        state.portfolio_simulated.connect(self._on_portfolio)
        state.settings_changed.connect(self._schedule)

    # ------------------------------------------------------------ input
    def _build_config(self):
        frame, lay = card("Il tuo piano")
        frame.setFixedWidth(370)
        this_year = date.today().year

        def row(text: str, w: QWidget, tip: str = "") -> None:
            h = QHBoxLayout()
            lbl = label(text)
            if tip:
                lbl.setToolTip(tip)
                w.setToolTip(tip)
            h.addWidget(lbl)
            h.addStretch(1)
            h.addWidget(w)
            lay.addLayout(h)

        lay.addWidget(label("QUANTO INVESTI", "FieldLabel"))
        self.initial = _money_spin(0, 1000)
        self.monthly = _money_spin(200, 50, 1_000_000)
        self.increase = _pct_spin(0, 20)
        row("Capitale iniziale", self.initial, "Soldi che investi subito, una volta sola.")
        row("Versamento mensile", self.monthly, "Quanto versi all'inizio di ogni mese.")
        row("Aumento annuo del versamento", self.increase,
            "Se prevedi di aumentare il versamento ogni anno (es. perché cresce lo stipendio).")

        lay.addSpacing(6)
        lay.addWidget(label("FINO A QUANDO", "FieldLabel"))
        self.year = QSpinBox()
        self.year.setRange(this_year + 1, this_year + 60)
        self.year.setValue(this_year + 20)
        self.year.setFixedWidth(100)
        self.year.setAlignment(Qt.AlignRight)
        row("Anno", self.year)
        self.duration = label("", "Faint")
        lay.addWidget(self.duration)

        lay.addSpacing(6)
        lay.addWidget(label("COME CRESCONO I SOLDI", "FieldLabel"))
        self.mode = QButtonGroup(self)
        self.mode_hist = QRadioButton("Come il mio portafoglio (dati storici)")
        self.mode_fixed = QRadioButton("Rendimento fisso annuo")
        self.mode_hist.setChecked(True)
        self.mode.addButton(self.mode_hist)
        self.mode.addButton(self.mode_fixed)
        lay.addWidget(self.mode_hist)
        self.hist_info = label("", "Faint", wrap=True)
        self.hist_info.setContentsMargins(24, 0, 0, 0)
        lay.addWidget(self.hist_info)
        fixed_row = QHBoxLayout()
        fixed_row.addWidget(self.mode_fixed)
        fixed_row.addStretch(1)
        self.fixed = _pct_spin(6, 30)
        self.fixed.setToolTip("Riferimenti indicativi: conto deposito 2–3%, obbligazioni 3–4%, "
                              "bilanciato 5–6%, azionario mondo 7–8% (lungo periodo, prima delle tasse).")
        fixed_row.addWidget(self.fixed)
        lay.addLayout(fixed_row)

        lay.addSpacing(6)
        lay.addWidget(label("INFLAZIONE", "FieldLabel"))
        self.inflation = _pct_spin(2, 15)
        row("Inflazione annua stimata", self.inflation)
        self.real = QCheckBox("Mostra i valori in euro di oggi")
        self.real.setToolTip("Toglie l'effetto dell'inflazione: ti dice quanto varranno quei soldi in termini "
                             "di potere d'acquisto attuale.")
        lay.addWidget(self.real)

        lay.addSpacing(6)
        lay.addWidget(label("OBIETTIVO (FACOLTATIVO)", "FieldLabel"))
        self.target = _money_spin(0, 5000)
        row("Voglio arrivare a", self.target, "Lascia 0 se non hai un obiettivo preciso.")

        self.error = label("", wrap=True)
        self.error.setStyleSheet(f"color:{theme.NEGATIVE};")
        self.error.hide()
        lay.addWidget(self.error)

        for w in (self.initial, self.monthly, self.increase, self.year, self.fixed, self.inflation, self.target):
            w.valueChanged.connect(self._schedule)
        for w in (self.mode_hist, self.mode_fixed, self.real):
            w.toggled.connect(self._schedule)
        return frame

    def _build_headline(self):
        frame, lay = card(None)
        self.headline = label("", wrap=True)
        self.headline.setTextFormat(Qt.RichText)
        self.headline.setStyleSheet("font-size: 15pt;")
        self.subline = label("", "Muted", wrap=True)
        self.subline.setTextFormat(Qt.RichText)
        lay.addWidget(self.headline)
        lay.addWidget(self.subline)
        return frame

    def _build_kpis(self):
        w = QWidget()
        grid = QGridLayout(w)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(12)
        self.kpi = {}
        items = [("p10", "Scenario pessimistico"), ("p50", "Scenario probabile"), ("p90", "Scenario ottimistico"),
                 ("invested", "Totale versato"), ("gain", "Guadagno probabile"), ("loss", "Rischio di perdere")]
        tips = {
            "p10": "Solo 1 futuro simulato su 10 è andato peggio di così.",
            "p50": "Il valore mediano: metà dei futuri simulati è andata meglio, metà peggio.",
            "p90": "Solo 1 futuro simulato su 10 è andato meglio di così.",
            "loss": "Percentuale di futuri simulati in cui alla fine hai meno di quanto versato.",
        }
        for i, (key, title) in enumerate(items):
            k = KpiCard(title)
            if key in tips:
                k.setToolTip(tips[key])
            self.kpi[key] = k
            grid.addWidget(k, i // 3, i % 3)
        self.goal_row = QWidget()
        g = QGridLayout(self.goal_row)
        g.setContentsMargins(0, 0, 0, 0)
        g.setSpacing(12)
        for i, (key, title) in enumerate([("goal_prob", "Probabilità di raggiungere l'obiettivo"),
                                          ("goal_need", "Versamento necessario (probabile)"),
                                          ("goal_safe", "Versamento necessario (prudente)")]):
            k = KpiCard(title)
            self.kpi[key] = k
            g.addWidget(k, 0, i)
        self.kpi["goal_need"].setToolTip("Quanto versare al mese per arrivarci nello scenario probabile (mediano).")
        self.kpi["goal_safe"].setToolTip("Quanto versare al mese per arrivarci anche nello scenario pessimistico.")
        grid.addWidget(self.goal_row, 2, 0, 1, 3)
        self.goal_row.hide()
        return w

    def _build_charts(self):
        frame, lay = card(None)
        self.tabs = QTabWidget()
        cur = lambda: self.state.settings.currency
        self.chart = TimeSeriesChart(lambda v: fmt_money_short(v, cur()))
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Anno", "Versato", "Pessimistico", "Probabile", "Ottimistico"])
        self.table.verticalHeader().hide()
        self.table.setShowGrid(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.tabs.addTab(self.chart, "Grafico")
        self.tabs.addTab(self.table, "Anno per anno")
        self.tabs.setMinimumHeight(430)
        lay.addWidget(self.tabs)
        self.note = label("", "Faint", wrap=True)
        lay.addWidget(self.note)
        return frame

    # ------------------------------------------------------------ calcolo
    def _on_portfolio(self, res):
        self.portfolio = res
        self._schedule()

    def _schedule(self, *_):
        self._timer.start()

    def _hist_description(self) -> str:
        res = self.portfolio
        if res is None:
            return "Nessun portafoglio: costruiscine uno nella pagina «Portafoglio»."
        m = res.metrics
        idx = res.returns.index
        return (f"{len(res.weights)} asset · {fmt_pct(m['cagr'], 1)}/anno · volatilità "
                f"{fmt_pct(m['volatility'], 1)}<br>storico {idx[0]:%m/%Y}–{idx[-1]:%m/%Y} "
                f"(cambia periodo dalla barra in alto)")

    def recompute(self):
        cur = self.state.settings.currency
        sym = "€ " if cur == "EUR" else "$ "
        for w in (self.initial, self.monthly, self.target):
            w.setPrefix(sym)
        self.hist_info.setText(self._hist_description())
        today = pd.Timestamp.today().normalize()
        start = today + pd.offsets.MonthEnd(0)
        months = (self.year.value() - start.year) * 12 + (12 - start.month)
        yrs, mm = divmod(months, 12)
        self.duration.setText(f"{yrs} anni" + (f" e {mm} mesi" if mm else "") + " di investimento, "
                              f"fino a dicembre {self.year.value()}")

        plan = Plan(initial=self.initial.value(), monthly=self.monthly.value(), months=months,
                    annual_increase=self.increase.value() / 100, inflation=self.inflation.value() / 100)
        fixed = self.mode_fixed.isChecked()
        if not fixed and self.portfolio is None:
            self._show_error("Per usare i dati storici crea prima un portafoglio nella pagina «Portafoglio», "
                             "oppure scegli «Rendimento fisso annuo».")
            return
        if plan.initial <= 0 and plan.monthly <= 0:
            self._show_error("Inserisci un capitale iniziale o un versamento mensile.")
            return
        try:
            self.proj = project(plan, start,
                                hist_returns=None if fixed else self.portfolio.returns.to_numpy(),
                                fixed_return=self.fixed.value() / 100 if fixed else None,
                                real=self.real.isChecked())
        except ValueError as e:
            self._show_error(str(e))
            return
        self.error.hide()
        self._render(self.proj, fixed, cur)

    def _show_error(self, msg: str):
        self.error.setText(msg)
        self.error.show()
        self.headline.setText("")
        self.subline.setText("")
        for k in self.kpi.values():
            k.set("–")
        self.chart.set_series([])
        self.table.setRowCount(0)

    def _render(self, pr: Projection, fixed: bool, cur: str):
        money = lambda v: fmt_money(v, cur)
        p10, p50, p90 = pr.final(10), pr.final(50), pr.final(90)
        invested = pr.invested[-1]
        real = self.real.isChecked()
        plan = pr.plan
        year = self.year.value()

        what = []
        if plan.initial > 0:
            what.append(f"{money(plan.initial)} subito")
        if plan.monthly > 0:
            what.append(f"{money(plan.monthly)} al mese")
        acc = theme.ACCENT
        self.headline.setText(
            f"Investendo {' e '.join(what)} fino al {year} avresti "
            f"{'' if fixed else 'probabilmente '}circa <b style='color:{acc}'>{money(round(p50, -2))}</b>"
            + (" <span style='color:#8B93A7; font-size:11pt'>(in euro di oggi)</span>" if real else ""))
        if fixed:
            sub = (f"Con un rendimento costante del {fmt_num(self.fixed.value(), 1)}% l'anno. "
                   f"Di questi, {money(invested)} sono soldi versati da te e "
                   f"{money(p50 - invested)} sono guadagno.")
        else:
            sub = (f"In 8 futuri simulati su 10 finiresti tra <b>{money(round(p10, -2))}</b> e "
                   f"<b>{money(round(p90, -2))}</b>. Di tasca tua avresti versato {money(invested)}.")
        self.subline.setText(sub)

        k = self.kpi
        if fixed:
            k["p10"].set("–", "solo con dati storici")
            k["p90"].set("–", "solo con dati storici")
            k["loss"].set("–", "solo con dati storici")
        else:
            k["p10"].set(fmt_money(p10, cur), "1 caso su 10 va peggio", theme.WARNING)
            k["p90"].set(fmt_money(p90, cur), "1 caso su 10 va meglio", theme.POSITIVE)
            loss = pr.prob_loss()
            k["loss"].set(fmt_pct(loss, 1), "finire sotto il versato",
                          theme.POSITIVE if loss < 0.05 else (theme.WARNING if loss < 0.2 else theme.NEGATIVE))
        k["p50"].set(fmt_money(p50, cur), "valore mediano", theme.ACCENT)
        k["invested"].set(fmt_money(invested, cur), f"{len(pr.dates) - 1} versamenti mensili")
        gain = p50 - invested
        k["gain"].set(fmt_money(gain, cur), fmt_pct(gain / invested if invested else float('nan'), 0, sign=True),
                      theme.POSITIVE if gain >= 0 else theme.NEGATIVE)

        target = self.target.value()
        self.goal_row.setVisible(target > 0)
        if target > 0:
            if fixed:
                reached = p50 >= target
                k["goal_prob"].set("Sì" if reached else "No", "con rendimento fisso",
                                   theme.POSITIVE if reached else theme.NEGATIVE)
            else:
                prob = pr.prob_at_least(target)
                k["goal_prob"].set(fmt_pct(prob, 0), f"di arrivare a {fmt_money_short(target, cur)}",
                                   theme.POSITIVE if prob >= 0.7 else (theme.WARNING if prob >= 0.4 else theme.NEGATIVE))
            need = pr.required_monthly(target, 50)
            k["goal_need"].set(fmt_money(need, cur) + "/mese", "scenario probabile")
            if fixed:
                k["goal_safe"].set("–", "solo con dati storici")
            else:
                safe = pr.required_monthly(target, 10)
                k["goal_safe"].set(fmt_money(safe, cur) + "/mese", "arrivi anche nel caso pessimistico")

        # grafico
        idx = pr.dates
        s = lambda a: pd.Series(a, index=idx)
        series = [("Probabile", s(pr.bands[50]), theme.ACCENT)]
        if not fixed:
            series += [("Ottimistico", s(pr.bands[90]), theme.POSITIVE),
                       ("Pessimistico", s(pr.bands[10]), theme.WARNING)]
        series.append(("Versato", s(pr.invested), theme.MUTED))
        if target > 0:
            series.append(("Obiettivo", s([target] * len(idx)), theme.NEGATIVE))
        self.chart.set_series(series, dashed={"Versato", "Obiettivo", "Ottimistico", "Pessimistico"})
        if not fixed:
            self.chart.add_band(s(pr.bands[10]), s(pr.bands[90]), theme.ACCENT, 28)
            self.chart.add_band(s(pr.bands[25]), s(pr.bands[75]), theme.ACCENT, 45)

        # tabella anno per anno (dicembre di ogni anno)
        self.table.setRowCount(0)
        dec = [i for i, d in enumerate(idx) if d.month == 12]
        for i in dec:
            r = self.table.rowCount()
            self.table.insertRow(r)
            cells = [str(idx[i].year), money(pr.invested[i]),
                     "–" if fixed else money(pr.bands[10][i]), money(pr.bands[50][i]),
                     "–" if fixed else money(pr.bands[90][i])]
            for c, txt in enumerate(cells):
                it = QTableWidgetItem(txt)
                it.setTextAlignment((Qt.AlignLeft if c == 0 else Qt.AlignRight) | Qt.AlignVCenter)
                if c == 3:
                    it.setForeground(QColor(theme.ACCENT))
                if target > 0 and c == 3 and pr.bands[50][i] >= target:
                    it.setForeground(QColor(theme.POSITIVE))
                self.table.setItem(r, c, it)

        if fixed:
            self.note.setText("Rendimento costante: nella realtà ci saranno anni positivi e negativi. "
                              "Valori prima di tasse e costi.")
        else:
            self.note.setText("Metodo: 5.000 simulazioni che ricompongono a blocchi di 12 mesi i rendimenti "
                              "storici del portafoglio. Area scura = metà centrale dei casi, area chiara = 8 casi "
                              "su 10. Valori prima di tasse (26%) e costi. Il futuro può essere diverso dal passato.")
