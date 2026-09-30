"""Finestra principale: sidebar di navigazione, barra impostazioni, pagine."""
from __future__ import annotations

from PySide6.QtCore import Qt, QThreadPool
from PySide6.QtWidgets import (QButtonGroup, QFrame, QHBoxLayout, QMainWindow, QMessageBox,
                               QProgressBar, QPushButton, QScrollArea, QStackedWidget, QVBoxLayout,
                               QWidget)

from .. import data as data_mod
from . import theme
from .builder_page import BuilderPage
from .optimizer_page import OptimizerPage
from .projection_page import ProjectionPage
from .state import AppState, SettingsBar
from .widgets import Task, card, label

GUIDE = [
    ("Rendimento annuo (CAGR)",
     "Di quanto è cresciuto in media ogni anno il portafoglio, con l'interesse composto. Un CAGR del 7% "
     "raddoppia il capitale in circa 10 anni."),
    ("IRR sui tuoi versamenti",
     "Con il PAC ogni versamento resta investito per un tempo diverso. L'IRR è il rendimento annuo "
     "effettivo che hanno ottenuto i TUOI soldi, tenendo conto di quando li hai versati."),
    ("Volatilità",
     "Quanto «balla» il valore del portafoglio in un anno. Con una volatilità del 15% non è raro vedere "
     "anni tra −15% e +15% rispetto alla media."),
    ("Max drawdown",
     "La perdita peggiore dal punto più alto al punto più basso successivo. È la domanda chiave: "
     "riusciresti a non vendere se il tuo portafoglio perdesse questa percentuale?"),
    ("Sharpe ratio",
     "Rendimento in eccesso rispetto a un investimento senza rischio, diviso per la volatilità. Misura "
     "quanto vieni pagato per ogni unità di rischio. Sopra 0,5 discreto, sopra 1 ottimo."),
    ("Ribilanciamento",
     "Col tempo i pesi si spostano (ciò che sale pesa di più). Ribilanciare vuol dire riportarli alle "
     "percentuali scelte: vendi un po' di ciò che è salito e compri ciò che è sceso."),
    ("PAC (Piano di accumulo)",
     "Investire una cifra fissa ogni mese. Riduce il rischio di entrare tutto nel momento sbagliato."),
    ("Proiezione futura",
     "Stima quanto potresti avere in un anno futuro. Con i «dati storici» l'app crea 5.000 futuri possibili "
     "rimescolando gli anni del tuo portafoglio: lo scenario probabile è quello a metà, il pessimistico e "
     "l'ottimistico sono i casi peggiori e migliori escludendo gli estremi (1 su 10)."),
    ("Frontiera efficiente",
     "L'insieme dei portafogli che, per ogni livello di rischio, danno il rendimento più alto possibile. "
     "Stare sotto la frontiera vuol dire prendersi rischio non pagato."),
    ("Valuta",
     "Quasi tutti gli strumenti sono quotati in dollari: in modalità EUR i rendimenti includono l'effetto "
     "del cambio EUR/USD, come succederebbe a un investitore italiano."),
    ("Dati e limiti",
     "Prezzi da Yahoo Finance, con dividendi reinvestiti. Non sono incluse tasse (26% in Italia, 12,5% "
     "sui titoli di Stato), commissioni e costi di cambio. I rendimenti passati non garantiscono quelli "
     "futuri."),
]


class GuidePage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)
        body = QWidget()
        body.setObjectName("Root")
        scroll.setWidget(body)
        lay = QVBoxLayout(body)
        lay.setContentsMargins(24, 20, 24, 24)
        lay.setSpacing(14)
        lay.addWidget(label("Guida rapida", "PageTitle"))
        lay.addWidget(label("I concetti che trovi nell'app, spiegati in breve.", "PageSub"))
        grid = QHBoxLayout()
        cols = [QVBoxLayout(), QVBoxLayout()]
        for i, (t, d) in enumerate(GUIDE):
            f, fl = card(t)
            fl.addWidget(label(d, "Muted", wrap=True))
            cols[i % 2].addWidget(f)
        for c in cols:
            c.addStretch(1)
            c.setSpacing(14)
            grid.addLayout(c, 1)
        grid.setSpacing(14)
        lay.addLayout(grid)
        lay.addStretch(1)


class LoadingPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.addStretch(1)
        f, fl = card("Preparo i dati storici", "Primo avvio: scarico 20+ anni di prezzi per 200 strumenti "
                                               "da Yahoo Finance. Ci vuole circa un minuto, poi restano "
                                               "salvati sul tuo PC.")
        f.setFixedWidth(460)
        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(8)
        self.msg = label("", "Faint")
        fl.addSpacing(8)
        fl.addWidget(self.bar)
        fl.addWidget(self.msg)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(f)
        row.addStretch(1)
        lay.addLayout(row)
        lay.addStretch(2)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Portfolio Lab — simulatore di portafogli")
        self.resize(1560, 980)
        self.state = AppState()
        self.pool = QThreadPool.globalInstance()

        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)
        h = QHBoxLayout(root)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)
        h.addWidget(self._build_sidebar())

        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(0)
        self.settings_bar = SettingsBar(self.state)
        right.addWidget(self.settings_bar)
        self.stack = QStackedWidget()
        self.builder = BuilderPage(self.state)
        self.optimizer = OptimizerPage(self.state, lambda: dict(self.builder.weights))
        self.projection = ProjectionPage(self.state)
        self.guide = GuidePage()
        self.loading = LoadingPage()
        for w in (self.builder, self.optimizer, self.projection, self.guide, self.loading):
            self.stack.addWidget(w)
        right.addWidget(self.stack, 1)
        h.addLayout(right, 1)

        self.state.open_portfolio.connect(lambda _: self._go(0))
        self._init_data()

    # ------------------------------------------------------------ sidebar
    def _build_sidebar(self) -> QFrame:
        side = QFrame()
        side.setObjectName("Sidebar")
        side.setFixedWidth(230)
        lay = QVBoxLayout(side)
        lay.setContentsMargins(16, 22, 16, 18)
        lay.setSpacing(4)
        logo = label("◆ Portfolio Lab", "Logo")
        logo.setStyleSheet(f"color:{theme.TEXT};")
        lay.addWidget(logo)
        lay.addWidget(label("Simulatore storico di portafogli", "LogoSub"))
        lay.addSpacing(24)

        self.nav = QButtonGroup(self)
        self.nav_buttons = []
        for i, text in enumerate(["◉   Portafoglio", "✦   Ottimizzatore", "➚   Proiezione futura", "ⓘ   Guida"]):
            b = QPushButton(text)
            b.setObjectName("NavButton")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.clicked.connect(lambda _=False, i=i: self._go(i))
            self.nav.addButton(b, i)
            self.nav_buttons.append(b)
            lay.addWidget(b)
        self.nav_buttons[0].setChecked(True)
        lay.addStretch(1)

        box = QFrame()
        box.setStyleSheet(f"background:{theme.SURFACE_2}; border-radius:12px;")
        bl = QVBoxLayout(box)
        bl.setContentsMargins(12, 12, 12, 12)
        bl.setSpacing(6)
        bl.addWidget(label("DATI", "FieldLabel"))
        self.data_lbl = label("—", wrap=True)
        self.data_lbl.setStyleSheet("font-size: 9pt;")
        bl.addWidget(self.data_lbl)
        self.data_bar = QProgressBar()
        self.data_bar.setRange(0, 100)
        self.data_bar.setTextVisible(False)
        self.data_bar.setFixedHeight(5)
        self.data_bar.hide()
        bl.addWidget(self.data_bar)
        self.refresh_btn = QPushButton("Aggiorna dati")
        self.refresh_btn.setCursor(Qt.PointingHandCursor)
        self.refresh_btn.clicked.connect(self.refresh_data)
        bl.addWidget(self.refresh_btn)
        lay.addWidget(box)
        lay.addSpacing(8)
        lay.addWidget(label("Non è consulenza finanziaria.\nI rendimenti passati non garantiscono "
                            "quelli futuri.", "Faint", wrap=True))
        return side

    def _go(self, i: int):
        if self.state.data is None:
            return
        self.stack.setCurrentIndex(i)
        self.nav_buttons[i].setChecked(True)

    # ------------------------------------------------------------ dati
    def _init_data(self):
        cached = data_mod.load_cache()
        if cached is not None:
            self._set_data(cached)
            if data_mod.cache_is_stale(cached):
                self.refresh_data()
        else:
            self.stack.setCurrentWidget(self.loading)
            self.settings_bar.setEnabled(False)
            self.refresh_data()

    def refresh_data(self):
        self.refresh_btn.setEnabled(False)
        self.refresh_btn.setText("Aggiornamento…")
        self.data_bar.show()
        task = Task(data_mod.download_all, with_progress=True)
        task.signals.progress.connect(self._on_progress)
        task.signals.finished.connect(self._on_downloaded)
        task.signals.error.connect(self._on_download_error)
        self.pool.start(task)

    def _on_progress(self, p: int, msg: str):
        self.data_bar.setValue(p)
        self.loading.bar.setValue(p)
        self.loading.msg.setText(msg)

    def _on_downloaded(self, data):
        self._reset_refresh()
        self._set_data(data)

    def _on_download_error(self, msg: str):
        self._reset_refresh()
        QMessageBox.warning(self, "Download non riuscito",
                            f"Non sono riuscito a scaricare i dati.\n\n{msg}")

    def _reset_refresh(self):
        self.refresh_btn.setEnabled(True)
        self.refresh_btn.setText("Aggiorna dati")
        self.data_bar.hide()

    def _set_data(self, data):
        first_load = self.state.data is None
        self.state.set_data(data)
        n = len(data.tickers)
        last = data.daily.index[-1]
        self.data_lbl.setText(f"{n} strumenti · Yahoo Finance\nprezzi fino al {last:%d/%m/%Y}\n"
                              f"aggiornati il {data.updated:%d/%m/%Y %H:%M}")
        if first_load:
            self.settings_bar.setEnabled(True)
            self.stack.setCurrentIndex(0)
            if not self.builder.weights:
                from .state import PRESETS
                self.builder.load_weights(PRESETS["Diversificato 4 categorie"])
