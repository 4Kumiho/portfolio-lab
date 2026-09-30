"""Palette colori e foglio di stile (tema scuro)."""
from __future__ import annotations

BG = "#0B0E14"
SURFACE = "#131722"
SURFACE_2 = "#1A1F2E"
SURFACE_3 = "#232A3B"
BORDER = "#262D3F"
TEXT = "#E7EAF3"
MUTED = "#8B93A7"
FAINT = "#5A6278"
ACCENT = "#5B8CFF"
ACCENT_2 = "#8A6BFF"
POSITIVE = "#2ED3A0"
NEGATIVE = "#FF5C7A"
WARNING = "#FFB547"

# colori per le serie nei grafici (in ordine)
SERIES = ["#5B8CFF", "#2ED3A0", "#FFB547", "#FF6B8B", "#B78CFF", "#4FD1E8", "#F28CFF", "#9BE15D"]

FONT_FAMILY = "Segoe UI"

QSS = f"""
* {{
    font-family: "{FONT_FAMILY}";
    font-size: 10pt;
    color: {TEXT};
    outline: none;
}}
QMainWindow, QWidget#Root {{ background: {BG}; }}
QWidget {{ background: transparent; }}
QToolTip {{
    background: {SURFACE_3}; color: {TEXT}; border: 1px solid {BORDER};
    padding: 6px 8px; border-radius: 6px;
}}

/* ---------- sidebar ---------- */
QFrame#Sidebar {{ background: {SURFACE}; border-right: 1px solid {BORDER}; }}
QLabel#Logo {{ font-size: 15pt; font-weight: 700; color: {TEXT}; }}
QLabel#LogoSub {{ color: {MUTED}; font-size: 8.5pt; }}
QPushButton#NavButton {{
    text-align: left; padding: 10px 14px; border-radius: 10px;
    color: {MUTED}; font-weight: 600; background: transparent; border: none;
}}
QPushButton#NavButton:hover {{ background: {SURFACE_2}; color: {TEXT}; }}
QPushButton#NavButton:checked {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(91,140,255,0.22), stop:1 rgba(138,107,255,0.10));
    color: {TEXT};
}}

/* ---------- cards ---------- */
QFrame#Card {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 14px; }}
QFrame#KpiCard {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 12px; }}
QFrame#Banner {{ background: rgba(255,181,71,0.08); border: 1px solid rgba(255,181,71,0.35); border-radius: 10px; }}
QFrame#SettingsBar {{ background: {SURFACE}; border-bottom: 1px solid {BORDER}; }}
QLabel#CardTitle {{ font-size: 11.5pt; font-weight: 700; }}
QLabel#PageTitle {{ font-size: 18pt; font-weight: 700; }}
QLabel#PageSub {{ color: {MUTED}; }}
QLabel#Muted {{ color: {MUTED}; }}
QLabel#Faint {{ color: {FAINT}; font-size: 9pt; }}
QLabel#KpiTitle {{ color: {MUTED}; font-size: 8.5pt; font-weight: 600; letter-spacing: 0.5px; }}
QLabel#KpiValue {{ font-size: 16pt; font-weight: 700; }}
QLabel#KpiSub {{ color: {MUTED}; font-size: 8.5pt; }}
QLabel#FieldLabel {{ color: {MUTED}; font-size: 8.5pt; font-weight: 600; }}

/* ---------- buttons ---------- */
QPushButton {{
    background: {SURFACE_2}; border: 1px solid {BORDER}; border-radius: 9px;
    padding: 7px 14px; font-weight: 600;
}}
QPushButton:hover {{ background: {SURFACE_3}; border-color: #34405A; }}
QPushButton:pressed {{ background: {BORDER}; }}
QPushButton:disabled {{ color: {FAINT}; background: {SURFACE}; }}
QPushButton#Primary {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {ACCENT}, stop:1 {ACCENT_2});
    border: none; color: white; padding: 9px 18px;
}}
QPushButton#Primary:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #6E9BFF, stop:1 #9A80FF);
}}
QPushButton#Primary:disabled {{ background: {SURFACE_3}; color: {FAINT}; }}
QPushButton#Ghost {{ background: transparent; border: none; color: {MUTED}; padding: 4px 8px; }}
QPushButton#Ghost:hover {{ color: {TEXT}; background: {SURFACE_2}; }}
QPushButton#Chip {{
    background: {SURFACE_2}; border: 1px solid {BORDER}; border-radius: 14px;
    padding: 4px 12px; color: {MUTED}; font-weight: 600; font-size: 9pt;
}}
QPushButton#Chip:checked {{ background: rgba(91,140,255,0.18); border-color: {ACCENT}; color: {TEXT}; }}
QPushButton#Remove {{
    background: transparent; border: none; color: {FAINT}; font-size: 12pt; padding: 0px;
}}
QPushButton#Remove:hover {{ color: {NEGATIVE}; }}

/* ---------- inputs ---------- */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background: {SURFACE_2}; border: 1px solid {BORDER}; border-radius: 8px;
    padding: 6px 10px; selection-background-color: {ACCENT};
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{ border-color: {ACCENT}; }}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{ width: 0px; border: none; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{
    background: {SURFACE_2}; border: 1px solid {BORDER}; selection-background-color: {SURFACE_3};
    padding: 4px; border-radius: 8px;
}}
QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{
    width: 16px; height: 16px; border-radius: 5px; border: 1px solid #3A4460; background: {SURFACE_2};
}}
QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}
QRadioButton::indicator {{
    width: 14px; height: 14px; border-radius: 8px; border: 1px solid #3A4460; background: {SURFACE_2};
}}
QRadioButton::indicator:checked {{ background: {ACCENT}; border: 3px solid {SURFACE_2}; }}

/* ---------- tables ---------- */
QTableView, QTableWidget {{
    background: transparent; border: none; gridline-color: transparent;
    selection-background-color: rgba(91,140,255,0.16); selection-color: {TEXT};
    alternate-background-color: rgba(255,255,255,0.015);
}}
QTableView::item, QTableWidget::item {{ padding: 4px 6px; border-bottom: 1px solid {BORDER}; }}
QHeaderView::section {{
    background: transparent; color: {MUTED}; border: none; border-bottom: 1px solid {BORDER};
    padding: 6px; font-size: 8.5pt; font-weight: 700;
}}
QTableCornerButton::section {{ background: transparent; border: none; }}

/* ---------- tabs ---------- */
QTabWidget::pane {{ border: none; }}
QTabBar::tab {{
    background: transparent; color: {MUTED}; padding: 8px 14px; margin-right: 4px;
    border-bottom: 2px solid transparent; font-weight: 600;
}}
QTabBar::tab:selected {{ color: {TEXT}; border-bottom: 2px solid {ACCENT}; }}
QTabBar::tab:hover {{ color: {TEXT}; }}

/* ---------- scrollbars ---------- */
QScrollArea {{ border: none; background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {SURFACE_3}; border-radius: 4px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: #34405A; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {SURFACE_3}; border-radius: 4px; min-width: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: none; }}

QProgressBar {{
    background: {SURFACE_2}; border: none; border-radius: 4px; height: 8px; text-align: center;
}}
QProgressBar::chunk {{
    border-radius: 4px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {ACCENT}, stop:1 {ACCENT_2});
}}
QSplitter::handle {{ background: transparent; }}
QMessageBox {{ background: {SURFACE}; }}
"""
