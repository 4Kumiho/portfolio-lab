"""Avvio dell'applicazione."""
from __future__ import annotations

import sys

from PySide6.QtCore import QLocale
from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication

from .ui import theme
from .ui.main_window import MainWindow


def main() -> int:
    QLocale.setDefault(QLocale(QLocale.Italian, QLocale.Italy))
    app = QApplication(sys.argv)
    app.setApplicationName("Portfolio Lab")
    app.setStyle("Fusion")
    pal = QPalette()
    for role, color in ((QPalette.Window, theme.BG), (QPalette.Base, theme.SURFACE_2),
                        (QPalette.Text, theme.TEXT), (QPalette.WindowText, theme.TEXT),
                        (QPalette.Button, theme.SURFACE_2), (QPalette.ButtonText, theme.TEXT),
                        (QPalette.Highlight, theme.ACCENT), (QPalette.ToolTipBase, theme.SURFACE_3),
                        (QPalette.ToolTipText, theme.TEXT)):
        pal.setColor(role, QColor(color))
    app.setPalette(pal)
    app.setFont(QFont(theme.FONT_FAMILY, 10))
    app.setStyleSheet(theme.QSS)
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
