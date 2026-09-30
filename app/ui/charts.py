"""Grafici interattivi basati su pyqtgraph."""
from __future__ import annotations

from typing import Callable

import numpy as np
import pandas as pd
import pyqtgraph as pg
from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from . import theme
from .widgets import Legend

pg.setConfigOptions(antialias=True, background=theme.SURFACE, foreground=theme.MUTED)

Formatter = Callable[[float], str]


class FmtAxis(pg.AxisItem):
    def __init__(self, fmt: Formatter, *a, **kw):
        super().__init__(*a, **kw)
        self.fmt = fmt

    def tickStrings(self, values, scale, spacing):
        return [self.fmt(v) for v in values]


class YearAxis(pg.AxisItem):
    def tickStrings(self, values, scale, spacing):
        return [str(int(round(v))) for v in values]


def _style_axes(plot: pg.PlotItem) -> None:
    font = QFont(theme.FONT_FAMILY, 8)
    for name in ("left", "bottom"):
        ax = plot.getAxis(name)
        ax.setPen(pg.mkPen(theme.BORDER))
        ax.setTextPen(pg.mkPen(theme.MUTED))
        ax.setStyle(tickFont=font, tickLength=0, tickTextOffset=8)
        ax.enableAutoSIPrefix(False)
    plot.getAxis("left").setWidth(62)
    plot.showGrid(x=False, y=True, alpha=0.12)
    plot.setMenuEnabled(False)
    plot.hideButtons()


class _Tooltip(QLabel):
    def __init__(self, parent):
        super().__init__(parent)
        self.setStyleSheet(
            f"background: rgba(26,31,46,0.96); border: 1px solid {theme.BORDER};"
            "border-radius: 8px; padding: 8px 10px;"
        )
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.hide()

    def show_at(self, html: str, x: float, y: float) -> None:
        self.setText(html)
        self.adjustSize()
        pw = self.parentWidget().width()
        nx = x + 16 if x + 16 + self.width() < pw else x - 16 - self.width()
        self.move(int(nx), int(max(4, y - self.height() / 2)))
        self.show()
        self.raise_()


class ChartBase(QWidget):
    def __init__(self, parent=None, axis_items: dict | None = None, legend: bool = True):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)
        self.legend = Legend()
        if legend:
            lay.addWidget(self.legend)
        self.pw = pg.PlotWidget(axisItems=axis_items or {})
        self.pw.setMinimumHeight(260)
        self.plot = self.pw.getPlotItem()
        _style_axes(self.plot)
        lay.addWidget(self.pw, 1)
        self.tip = _Tooltip(self.pw)
        self.pw.scene().sigMouseMoved.connect(self._on_move)
        self.pw.leaveEvent = lambda e: self._on_leave()

    def _on_leave(self):
        self.tip.hide()

    def _on_move(self, pos):  # sovrascritto
        pass


class TimeSeriesChart(ChartBase):
    """Linee nel tempo con crosshair e tooltip multi-serie."""

    def __init__(self, fmt: Formatter, parent=None):
        self.fmt = fmt
        super().__init__(parent, axis_items={"bottom": pg.DateAxisItem(), "left": FmtAxis(fmt, "left")})
        self.series: list[tuple[str, np.ndarray, np.ndarray, str]] = []
        self.vline = pg.InfiniteLine(angle=90, pen=pg.mkPen(theme.FAINT, width=1, style=Qt.DashLine))
        self.dots = pg.ScatterPlotItem(size=9, pen=pg.mkPen(theme.SURFACE, width=2))
        self.plot.getViewBox().setMouseEnabled(x=True, y=False)
        self.plot.getViewBox().setAutoVisible(y=True)

    def set_series(self, items: list[tuple[str, pd.Series, str]], fill_first: bool = False,
                   fill_level: float | None = None, dashed: set[str] | None = None) -> None:
        self.plot.clear()
        self.series.clear()
        dashed = dashed or set()
        for i, (name, s, color) in enumerate(items):
            s = s.dropna()
            if s.empty:
                continue
            x = s.index.to_numpy().astype("datetime64[s]").astype("int64").astype(float)
            y = s.to_numpy(dtype=float)
            style = Qt.DashLine if name in dashed else Qt.SolidLine
            pen = pg.mkPen(color, width=2.2 if i == 0 else 1.6, style=style)
            curve = pg.PlotDataItem(x, y, pen=pen)
            if (fill_first and i == 0) or fill_level is not None:
                c = QColor(color)
                c.setAlpha(38 if i == 0 else 22)
                level = fill_level if fill_level is not None else float(np.nanmin(y))
                curve.setFillLevel(level)
                curve.setBrush(QBrush(c))
            self.plot.addItem(curve)
            self.series.append((name, x, y, color))
        self.plot.addItem(self.vline, ignoreBounds=True)
        self.plot.addItem(self.dots)
        self.vline.hide()
        self.legend.set_items([(n, c) for n, _, _, c in self.series])
        self.plot.enableAutoRange()
        if self.series:
            x_min = min(x[0] for _, x, _, _ in self.series)
            x_max = max(x[-1] for _, x, _, _ in self.series)
            vb = self.plot.getViewBox()
            vb.setLimits(xMin=x_min, xMax=x_max)
            vb.setXRange(x_min, x_max, padding=0)

    def add_band(self, low: pd.Series, high: pd.Series, color: str, alpha: int = 40) -> None:
        """Area colorata tra due serie (es. scenari pessimistico/ottimistico)."""
        x = low.index.to_numpy().astype("datetime64[s]").astype("int64").astype(float)
        c_low = pg.PlotDataItem(x, low.to_numpy(dtype=float), pen=pg.mkPen(None))
        c_high = pg.PlotDataItem(x, high.to_numpy(dtype=float), pen=pg.mkPen(None))
        c = QColor(color)
        c.setAlpha(alpha)
        fill = pg.FillBetweenItem(c_low, c_high, brush=QBrush(c))
        fill.setZValue(-10)
        self.plot.addItem(fill)

    def _on_move(self, pos):
        if not self.series or not self.plot.sceneBoundingRect().contains(pos):
            self.tip.hide(); self.vline.hide(); self.dots.clear()
            return
        mp = self.plot.getViewBox().mapSceneToView(pos)
        x0 = self.series[0][1]
        i = int(np.clip(np.searchsorted(x0, mp.x()), 0, len(x0) - 1))
        if i > 0 and abs(x0[i - 1] - mp.x()) < abs(x0[i] - mp.x()):
            i -= 1
        xv = x0[i]
        date = pd.Timestamp(xv, unit="s")
        rows, spots = [], []
        for name, x, y, color in self.series:
            j = int(np.clip(np.searchsorted(x, xv), 0, len(x) - 1))
            if x[j] != xv:
                continue
            rows.append(f"<tr><td><span style='color:{color}'>●</span> {name}</td>"
                        f"<td align='right' style='padding-left:14px'><b>{self.fmt(y[j])}</b></td></tr>")
            spots.append({"pos": (xv, y[j]), "brush": pg.mkBrush(color)})
        months = ["gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic"]
        html = (f"<div style='color:{theme.MUTED}; font-size:8pt'>{months[date.month - 1]} {date.year}</div>"
                f"<table cellspacing='0' cellpadding='1'>{''.join(rows)}</table>")
        self.vline.setPos(xv); self.vline.show()
        self.dots.setData(spots)
        sp = self.pw.mapFromScene(pos)
        self.tip.show_at(html, sp.x(), sp.y())


class AnnualBarChart(ChartBase):
    """Rendimenti annuali: barre verdi/rosse."""

    def __init__(self, parent=None):
        super().__init__(parent, axis_items={"bottom": YearAxis("bottom"),
                                             "left": FmtAxis(lambda v: f"{v * 100:.0f}%", "left")},
                         legend=False)
        self.years = np.array([])
        self.vals = np.array([])
        self.bench: np.ndarray | None = None
        self.bench_name = ""
        self.plot.getViewBox().setMouseEnabled(x=False, y=False)

    def set_data(self, s: pd.Series, bench: pd.Series | None = None, bench_name: str = "") -> None:
        self.plot.clear()
        self.years = s.index.to_numpy(dtype=float)
        self.vals = s.to_numpy(dtype=float)
        brushes = [pg.mkBrush(theme.POSITIVE if v >= 0 else theme.NEGATIVE) for v in self.vals]
        width = 0.62 if bench is None else 0.4
        off = 0 if bench is None else -0.21
        self.plot.addItem(pg.BarGraphItem(x=self.years + off, height=self.vals, width=width,
                                          brushes=brushes, pen=pg.mkPen(None)))
        self.bench = None
        if bench is not None:
            b = bench.reindex(s.index)
            self.bench = b.to_numpy(dtype=float)
            self.bench_name = bench_name
            self.plot.addItem(pg.BarGraphItem(x=self.years + 0.21, height=np.nan_to_num(self.bench), width=0.4,
                                              brush=pg.mkBrush(QColor(139, 147, 167, 110)), pen=pg.mkPen(None)))
        self.plot.addItem(pg.InfiniteLine(pos=0, angle=0, pen=pg.mkPen(theme.FAINT)))
        ax = self.plot.getAxis("bottom")
        step = 1 if len(self.years) <= 14 else 2
        ax.setTicks([[(y, str(int(y))) for y in self.years[::step]]])
        self.plot.enableAutoRange()

    def _on_move(self, pos):
        if not len(self.years) or not self.plot.sceneBoundingRect().contains(pos):
            self.tip.hide()
            return
        mp = self.plot.getViewBox().mapSceneToView(pos)
        i = int(np.argmin(np.abs(self.years - mp.x())))
        if abs(self.years[i] - mp.x()) > 0.5:
            self.tip.hide()
            return
        v = self.vals[i]
        c = theme.POSITIVE if v >= 0 else theme.NEGATIVE
        html = (f"<div style='color:{theme.MUTED}; font-size:8pt'>{int(self.years[i])}</div>"
                f"<div>Portafoglio <b style='color:{c}'>{v * 100:+.1f}%</b></div>")
        if self.bench is not None and not np.isnan(self.bench[i]):
            html += f"<div>{self.bench_name} <b>{self.bench[i] * 100:+.1f}%</b></div>"
        sp = self.pw.mapFromScene(pos)
        self.tip.show_at(html, sp.x(), sp.y())


class FrontierChart(ChartBase):
    """Rischio (volatilita') vs rendimento: asset, frontiera e soluzioni."""

    def __init__(self, parent=None):
        pct = lambda v: f"{v * 100:.0f}%"
        super().__init__(parent, axis_items={"bottom": FmtAxis(pct, "bottom"), "left": FmtAxis(pct, "left")})
        self.plot.showGrid(x=True, y=True, alpha=0.10)
        self.plot.setLabel("bottom", "Volatilità (rischio annuo)", color=theme.MUTED)
        self.plot.setLabel("left", "Rendimento medio annuo", color=theme.MUTED)
        self.plot.getAxis("left").setWidth(70)

    def set_data(self, assets: pd.DataFrame, colors: dict[str, str], names: dict[str, str],
                 frontier: tuple[np.ndarray, np.ndarray],
                 solutions: list[tuple[str, float, float, str]]) -> None:
        self.plot.clear()
        spots = [{"pos": (r.vol, r.ret), "brush": pg.mkBrush(QColor(colors[t]).lighter(100)),
                  "pen": pg.mkPen(None), "size": 7, "data": t} for t, r in assets.iterrows()]
        tip = lambda x, y, data: f"{data} — {names.get(data, '')}\nRischio {x * 100:.1f}%  ·  Rend. {y * 100:.1f}%"
        sc = pg.ScatterPlotItem(spots=spots, hoverable=True, tip=tip,
                                hoverPen=pg.mkPen("w", width=1.5), hoverSize=11)
        sc.setOpacity(0.75)
        self.plot.addItem(sc)
        fv, fr = frontier
        self.plot.plot(fv, fr, pen=pg.mkPen(theme.TEXT, width=2.2))
        for name, vol, ret, color in solutions:
            star = pg.ScatterPlotItem([vol], [ret], symbol="star", size=22, brush=pg.mkBrush(color),
                                      pen=pg.mkPen(theme.BG, width=1.5), hoverable=True,
                                      tip=lambda x, y, data, n=name: f"{n}\nRischio {x * 100:.1f}%  ·  Rend. {y * 100:.1f}%")
            self.plot.addItem(star)
        legend = [("Frontiera efficiente", theme.TEXT)] + [(n, c) for n, _, _, c in solutions]
        legend += [(cat, col) for cat, col in _category_legend(colors)]
        self.legend.set_items(legend)
        self.plot.enableAutoRange()


def _category_legend(colors: dict[str, str]) -> list[tuple[str, str]]:
    from ..universe import BY_TICKER
    seen: dict[str, str] = {}
    for t, c in colors.items():
        seen.setdefault(BY_TICKER[t].category, c)
    return list(seen.items())
