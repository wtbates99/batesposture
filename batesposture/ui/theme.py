from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtGui import QPalette
from PyQt6.QtWidgets import QApplication


@dataclass(frozen=True)
class ThemeColors:
    canvas: str
    surface: str
    surface_alt: str
    text: str
    muted: str
    border: str
    accent: str
    accent_hover: str
    accent_soft: str
    highlight: str
    danger: str
    sidebar: str
    sidebar_text: str


LIGHT = ThemeColors(
    canvas="#f4f6f3",
    surface="#ffffff",
    surface_alt="#eef2ec",
    text="#1d2520",
    muted="#657069",
    border="#d9e1da",
    accent="#2f7d4a",
    accent_hover="#25683d",
    accent_soft="#e6f2e9",
    highlight="#a8751f",
    danger="#b4232c",
    sidebar="#202923",
    sidebar_text="#dce5de",
)

DARK = ThemeColors(
    canvas="#151a17",
    surface="#1d2420",
    surface_alt="#252e28",
    text="#f1f5f2",
    muted="#a8b2ab",
    border="#39443c",
    accent="#65bd7d",
    accent_hover="#78cc8e",
    accent_soft="#243d2b",
    highlight="#d2a64f",
    danger="#ff858b",
    sidebar="#101612",
    sidebar_text="#dce5de",
)


def is_dark_theme(preference: str) -> bool:
    if preference == "dark":
        return True
    if preference == "light":
        return False
    app = QApplication.instance()
    palette = app.palette() if app else QPalette()
    color = palette.color(QPalette.ColorRole.Window)
    luminance = 0.299 * color.red() + 0.587 * color.green() + 0.114 * color.blue()
    return luminance < 128


def theme_colors(preference: str) -> ThemeColors:
    return DARK if is_dark_theme(preference) else LIGHT


def settings_stylesheet(preference: str) -> str:
    c = theme_colors(preference)
    return f"""
QDialog {{ background: {c.canvas}; color: {c.text}; }}
QWidget#sidebar {{ background: {c.sidebar}; }}
QLabel#brandName {{ color: #ffffff; font-size: 16px; font-weight: 700; }}
QLabel#brandDetail {{ color: {c.sidebar_text}; font-size: 11px; }}
QListWidget#navList {{ background: transparent; border: none; outline: none; padding: 8px 0; }}
QListWidget#navList::item {{ color: {c.sidebar_text}; padding: 9px 12px; border-radius: 6px; margin: 2px 8px; }}
QListWidget#navList::item:hover {{ background: {c.surface_alt}; color: {c.text}; }}
QListWidget#navList::item:selected {{ background: {c.accent}; color: #ffffff; }}
QCheckBox#advancedToggle {{ color: {c.sidebar_text}; font-size: 11px; padding: 10px 16px 14px 16px; }}
QScrollArea, QScrollArea > QWidget > QWidget {{ border: none; background: transparent; }}
QFrame#card {{ background: {c.surface}; border: 1px solid {c.border}; border-radius: 8px; }}
QLabel#cardHeader {{ color: {c.text}; font-size: 12px; font-weight: 700; background: transparent; }}
QFrame#cardSep {{ background: {c.border}; border: none; min-height: 1px; max-height: 1px; }}
QWidget#cardBody {{ background: transparent; }}
QLabel {{ color: {c.text}; font-size: 13px; background: transparent; }}
QLabel#pageTitle {{ color: {c.text}; font-size: 20px; font-weight: 700; }}
QLabel#pageSubtitle, QLabel#statusLabel {{ color: {c.muted}; font-size: 12px; }}
QLabel#helpText {{ color: {c.muted}; font-size: 11px; }}
QLabel#errorText {{ color: {c.danger}; font-size: 11px; }}
QSpinBox, QDoubleSpinBox, QComboBox, QLineEdit {{
    background: {c.surface}; color: {c.text}; border: 1px solid {c.border};
    border-radius: 6px; padding: 5px 9px; min-height: 30px; selection-background-color: {c.accent};
}}
QSpinBox:hover, QDoubleSpinBox:hover, QComboBox:hover, QLineEdit:hover {{ border-color: {c.muted}; }}
QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus, QLineEdit:focus {{ border: 2px solid {c.accent}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{ background: {c.surface}; color: {c.text}; border: 1px solid {c.border}; selection-background-color: {c.accent_soft}; selection-color: {c.text}; outline: none; }}
QCheckBox {{ color: {c.text}; spacing: 8px; background: transparent; }}
QPushButton {{ background: {c.surface}; color: {c.text}; border: 1px solid {c.border}; border-radius: 6px; padding: 6px 14px; min-height: 32px; font-weight: 600; }}
QPushButton:hover {{ background: {c.surface_alt}; border-color: {c.muted}; }}
QPushButton:pressed {{ background: {c.accent_soft}; }}
QPushButton:disabled {{ color: {c.muted}; background: {c.surface_alt}; }}
QPushButton#primaryButton, QPushButton#addBtn {{ background: {c.accent}; color: #ffffff; border-color: {c.accent}; }}
QPushButton#primaryButton:hover, QPushButton#addBtn:hover {{ background: {c.accent_hover}; border-color: {c.accent_hover}; }}
QPushButton#removeBtn {{ color: {c.danger}; }}
QTableWidget {{ background: {c.surface}; color: {c.text}; border: 1px solid {c.border}; border-radius: 6px; gridline-color: {c.border}; alternate-background-color: {c.canvas}; selection-background-color: {c.accent_soft}; selection-color: {c.text}; outline: none; }}
QTableWidget::item {{ padding: 6px 10px; border: none; }}
QHeaderView::section {{ background: {c.surface_alt}; color: {c.muted}; font-weight: 700; padding: 7px 10px; border: none; border-bottom: 1px solid {c.border}; }}
QFrame#bottomBar {{ background: {c.surface}; border-top: 1px solid {c.border}; }}
QToolTip {{ background: {c.surface}; color: {c.text}; border: 1px solid {c.border}; padding: 5px; }}
"""


def dashboard_stylesheet(preference: str) -> str:
    c = theme_colors(preference)
    return f"""
QDialog {{ background: {c.canvas}; color: {c.text}; }}
QLabel {{ color: {c.text}; background: transparent; }}
QLabel#dashboardTitle {{ font-size: 18px; font-weight: 700; }}
QLabel#dashboardSubtitle {{ color: {c.muted}; font-size: 11px; }}
QLabel#liveScore {{ font-size: 28px; font-weight: 700; color: {c.accent}; }}
QLabel#videoFeed {{ background: #101411; border: 1px solid {c.border}; border-radius: 8px; color: {c.muted}; }}
QLabel#statCard {{ background: {c.surface}; border: 1px solid {c.border}; border-radius: 8px; padding: 8px; }}
QLabel#feedback {{ background: {c.accent_soft}; border: 1px solid {c.border}; border-radius: 8px; color: {c.text}; padding: 10px 12px; font-weight: 600; }}
"""


def wizard_stylesheet(preference: str) -> str:
    c = theme_colors(preference)
    return f"""
QWizard {{ background: {c.canvas}; color: {c.text}; }}
QWizardPage {{ background: {c.canvas}; }}
QLabel {{ color: {c.text}; background: transparent; font-size: 13px; }}
QLabel#brandName {{ color: {c.text}; font-size: 24px; font-weight: 700; }}
QLabel#heroText {{ color: {c.text}; font-size: 15px; font-weight: 600; }}
QLabel#supportText {{ color: {c.muted}; }}
QLabel#cameraPreview {{ background: #101411; color: {c.muted}; border: 1px solid {c.border}; border-radius: 8px; }}
QLabel#resultPanel {{ background: {c.accent_soft}; border: 1px solid {c.border}; border-radius: 8px; padding: 10px; }}
QPushButton {{ background: {c.surface}; color: {c.text}; border: 1px solid {c.border}; border-radius: 6px; padding: 7px 15px; min-height: 32px; font-weight: 600; }}
QPushButton:hover {{ background: {c.surface_alt}; }}
QPushButton#primaryButton {{ background: {c.accent}; color: #ffffff; border-color: {c.accent}; }}
QPushButton#primaryButton:hover {{ background: {c.accent_hover}; }}
"""
