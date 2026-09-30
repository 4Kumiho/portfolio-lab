"""Componenti grafici riutilizzabili."""
from __future__ import annotations

import math
import traceback
from typing import Callable

from PySide6.QtCore import QObject, QRectF, QRunnable, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel,
                               QSizePolicy, QVBoxLayout, QWidget)

from . import theme


# ---------------------------------------------------------------- formattazione
def fmt_money(v: float, currency: str = "EUR", decimals: int = 0) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "–"
    sym = "€" if currency == "EUR" else "$"
    s = f"{abs(v):,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{'-' if v < 0 else ''}{sym} {s}"


def fmt_money_short(v: float, currency: str = "EUR") -> str:
    sym = "€" if currency == "EUR" else "$"
    a = abs(v)
    if a >= 1e6:
        s = f"{v / 1e6:.1f}M"
    elif a >= 1e3:
        s = f"{v / 1e3:.0f}k"
    else:
        s = f"{v:.0f}"
    return f"{sym}{s}"


def fmt_pct(v: float, decimals: int = 1, sign: bool = False) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "–"
    s = f"{v * 100:+.{decimals}f}%" if sign else f"{v * 100:.{decimals}f}%"
    return s.replace(".", ",")


def fmt_num(v: float, decimals: int = 2) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "–"
    return f"{v:.{decimals}f}".replace(".", ",")


def tone(v: float) -> str:
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return theme.TEXT
    return theme.POSITIVE if v >= 0 else theme.NEGATIVE


# ---------------------------------------------------------------- thread
class TaskSignals(QObject):
    finished = Signal(object)
    error = Signal(str)
    progress = Signal(int, str)


class Task(QRunnable):
    """Esegue una funzione in un thread del QThreadPool."""

    def __init__(self, fn: Callable, *args, with_progress: bool = False, **kwargs):
        super().__init__()
        self.fn, self.args, self.kwargs = fn, args, kwargs
        self.with_progress = with_progress
        self.signals = TaskSignals()

    def run(self) -> None:
        try:
            if self.with_progress:
                self.kwargs["progress"] = lambda p, m: self.signals.progress.emit(p, m)
            out = self.fn(*self.args, **self.kwargs)
        except Exception as e:  # mostrato all'utente
            traceback.print_exc()
            self.signals.error.emit(str(e))
        else:
            self.signals.finished.emit(out)


# ---------------------------------------------------------------- layout helpers
def card(title: str | None = None, subtitle: str | None = None, shadow: bool = True) -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName("Card")
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(18, 16, 18, 16)
    lay.setSpacing(10)
    if title:
        t = QLabel(title)
        t.setObjectName("CardTitle")
        lay.addWidget(t)
    if subtitle:
        s = QLabel(subtitle)
        s.setObjectName("Muted")
        s.setWordWrap(True)
        lay.addWidget(s)
    if shadow:
        eff = QGraphicsDropShadowEffect(frame)
        eff.setBlurRadius(28)
        eff.setOffset(0, 6)
        eff.setColor(QColor(0, 0, 0, 90))
        frame.setGraphicsEffect(eff)
    return frame, lay


def label(text: str = "", name: str | None = None, wrap: bool = False) -> QLabel:
    lbl = QLabel(text)
    if name:
        lbl.setObjectName(name)
    lbl.setWordWrap(wrap)
    return lbl


def field(title: str, widget: QWidget) -> QWidget:
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(4)
    lay.addWidget(label(title.upper(), "FieldLabel"))
    lay.addWidget(widget)
    return w


# ---------------------------------------------------------------- KPI
class KpiCard(QFrame):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setObjectName("KpiCard")
        self.setMinimumWidth(130)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(2)
        self.title = label(title.upper(), "KpiTitle")
        self.value = label("–", "KpiValue")
        self.sub = label("", "KpiSub")
        lay.addWidget(self.title)
        lay.addWidget(self.value)
        lay.addWidget(self.sub)

    def set(self, value: str, sub: str = "", color: str | None = None, tip: str | None = None) -> None:
        self.value.setText(value)
        self.value.setStyleSheet(f"color: {color};" if color else "")
        self.sub.setText(sub)
        if tip:
            self.setToolTip(tip)


# ---------------------------------------------------------------- donut
class DonutChart(QWidget):
    """Grafico a ciambella con legenda a destra."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.items: list[tuple[str, float, str]] = []
        self.center_title = ""
        self.center_value = ""
        self.setMinimumSize(300, 170)

    def set_data(self, items: list[tuple[str, float, str]], center_title: str = "", center_value: str = "") -> None:
        self.items = [(n, v, c) for n, v, c in items if v > 0]
        self.center_title, self.center_value = center_title, center_value
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        h = self.height()
        size = min(h - 10, 170)
        rect = QRectF(8, (h - size) / 2, size, size)
        thick = size * 0.16
        inner = rect.adjusted(thick / 2, thick / 2, -thick / 2, -thick / 2)
        total = sum(v for _, v, _ in self.items)

        if total <= 0:
            p.setPen(QPen(QColor(theme.SURFACE_3), thick, Qt.SolidLine, Qt.FlatCap))
            p.drawArc(inner, 0, 360 * 16)
        else:
            angle = 90 * 16
            gap = 2 * 16 if len(self.items) > 1 else 0
            for _, v, c in self.items:
                span = -int(round(v / total * 360 * 16))
                p.setPen(QPen(QColor(c), thick, Qt.SolidLine, Qt.FlatCap))
                p.drawArc(inner, angle - gap // 2, span + gap)
                angle += span

        # testo centrale
        p.setPen(QColor(theme.MUTED))
        f = QFont(theme.FONT_FAMILY, 8)
        p.setFont(f)
        p.drawText(rect.adjusted(0, -14, 0, -14), Qt.AlignCenter, self.center_title)
        p.setPen(QColor(theme.TEXT))
        f = QFont(theme.FONT_FAMILY, 13, QFont.Bold)
        p.setFont(f)
        p.drawText(rect.adjusted(0, 12, 0, 12), Qt.AlignCenter, self.center_value)

        # legenda
        x0 = rect.right() + 22
        y = h / 2 - len(self.items) * 13
        for name, v, c in self.items:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(c))
            p.drawRoundedRect(QRectF(x0, y + 5, 10, 10), 3, 3)
            p.setPen(QColor(theme.TEXT))
            p.setFont(QFont(theme.FONT_FAMILY, 9))
            p.drawText(QRectF(x0 + 18, y, self.width() - x0 - 80, 20), Qt.AlignVCenter | Qt.AlignLeft, name)
            p.setPen(QColor(theme.MUTED))
            p.setFont(QFont(theme.FONT_FAMILY, 9, QFont.Bold))
            p.drawText(QRectF(x0, y, self.width() - x0 - 6, 20), Qt.AlignVCenter | Qt.AlignRight,
                       fmt_pct(v / total if total else 0, 1))
            y += 26
        p.end()


# ---------------------------------------------------------------- barre pesi
class WeightBars(QWidget):
    """Lista di barre orizzontali (ticker, peso, colore)."""

    ROW = 24

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows: list[tuple[str, str, float, str]] = []

    def set_rows(self, rows: list[tuple[str, str, float, str]]) -> None:
        self.rows = rows
        self.setMinimumHeight(max(1, len(rows)) * self.ROW + 4)
        self.updateGeometry()
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w = self.width()
        mx = max((r[2] for r in self.rows), default=1) or 1
        label_w = 64
        pct_w = 52
        bar_w = max(w - label_w - pct_w - 8, 10)
        for i, (tick, name, weight, color) in enumerate(self.rows):
            y = i * self.ROW
            p.setPen(QColor(theme.TEXT))
            p.setFont(QFont(theme.FONT_FAMILY, 9, QFont.Bold))
            p.drawText(QRectF(0, y, label_w, self.ROW), Qt.AlignVCenter | Qt.AlignLeft, tick)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(theme.SURFACE_3))
            p.drawRoundedRect(QRectF(label_w, y + 8, bar_w, 8), 4, 4)
            p.setBrush(QColor(color))
            p.drawRoundedRect(QRectF(label_w, y + 8, max(bar_w * weight / mx, 4), 8), 4, 4)
            p.setPen(QColor(theme.MUTED))
            p.setFont(QFont(theme.FONT_FAMILY, 9))
            p.drawText(QRectF(w - pct_w, y, pct_w, self.ROW), Qt.AlignVCenter | Qt.AlignRight, fmt_pct(weight, 1))
        p.end()

    def event(self, e):
        if e.type() == e.Type.ToolTip:
            i = int(e.pos().y() // self.ROW)
            if 0 <= i < len(self.rows):
                self.setToolTip(f"{self.rows[i][0]} — {self.rows[i][1]}")
        return super().event(e)


# ---------------------------------------------------------------- legenda
class Legend(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.lay = QHBoxLayout(self)
        self.lay.setContentsMargins(4, 0, 4, 0)
        self.lay.setSpacing(16)

    def set_items(self, items: list[tuple[str, str]]) -> None:
        while self.lay.count():
            it = self.lay.takeAt(0)
            if it.widget():
                it.widget().deleteLater()
        for name, color in items:
            dot = QLabel()
            dot.setFixedSize(10, 10)
            dot.setStyleSheet(f"background:{color}; border-radius:5px;")
            txt = label(name, "Muted")
            box = QHBoxLayout()
            box.setSpacing(6)
            w = QWidget()
            w.setLayout(box)
            box.setContentsMargins(0, 0, 0, 0)
            box.addWidget(dot)
            box.addWidget(txt)
            self.lay.addWidget(w)
        self.lay.addStretch(1)
