from __future__ import annotations

from pathlib import Path


_ASSET_DIR = Path(__file__).resolve().parent / "assets"


def _asset_url(filename: str) -> str:
    return (_ASSET_DIR / filename).as_posix()


def _with_asset_urls(qss: str) -> str:
    return (
        qss.replace("__CHEVRON_LIGHT__", _asset_url("chevron_down_light.svg"))
        .replace("__CHEVRON_BLUE__", _asset_url("chevron_down_blue.svg"))
        .replace("__CHEVRON_UP_LIGHT__", _asset_url("chevron_up_light.svg"))
        .replace("__CHEVRON_UP_BLUE__", _asset_url("chevron_up_blue.svg"))
    )


DARK_BLUE_QSS = """
QMainWindow {
    background: #07111f;
}
QWidget {
    color: #eef5ff;
    font-family: "Segoe UI", "Inter", "Arial";
    font-size: 13px;
}
#AppShell {
    background: #07111f;
}
#Sidebar {
    background: #0b1728;
    border-right: 1px solid rgba(148, 163, 184, 0.20);
}
#BrandTitle {
    color: #ffffff;
    font-size: 24px;
    font-weight: 800;
    letter-spacing: 0.4px;
}
#BrandSubtitle {
    color: #93a4b8;
    font-size: 12px;
}
#PageTitle {
    color: #ffffff;
    font-size: 26px;
    font-weight: 800;
}
#PageSubtitle {
    color: #9fb0c4;
    font-size: 13px;
}
#HeroCard, #Card, #OutputCard {
    background-color: #101d31;
    border: 1px solid rgba(148, 163, 184, 0.18);
    border-radius: 22px;
}
#HeroCard {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #14243c, stop:1 #0d1728);
}
#MetricCard {
    background-color: #101d31;
    border: 1px solid rgba(148, 163, 184, 0.16);
    border-radius: 18px;
}
#CardTitle {
    color: #ffffff;
    font-size: 16px;
    font-weight: 800;
}
#CardText {
    color: #9fb0c4;
    line-height: 1.4;
}
#MetricNumber {
    color: #ffffff;
    font-size: 36px;
    font-weight: 900;
}
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox {
    background: #0b1424;
    color: #eef5ff;
    border: 1px solid rgba(148, 163, 184, 0.24);
    border-radius: 12px;
    padding: 9px 11px;
    selection-background-color: #7c3aed;
}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QSpinBox:focus {
    border: 1px solid #38bdf8;
}
QComboBox {
    padding-right: 52px;
}
QComboBox::drop-down {
    subcontrol-origin: border;
    subcontrol-position: top right;
    border: none;
    width: 44px;
    border-top-right-radius: 12px;
    border-bottom-right-radius: 12px;
    background: rgba(56, 189, 248, 0.05);
}
QComboBox::drop-down:hover {
    background: rgba(56, 189, 248, 0.12);
}
QComboBox::down-arrow {
    image: url("__CHEVRON_LIGHT__");
    width: 20px;
    height: 20px;
    margin: 0px;
}
QSpinBox {
    padding-right: 52px;
}
QSpinBox::up-button, QSpinBox::down-button {
    subcontrol-origin: border;
    width: 44px;
    border: none;
    background: rgba(56, 189, 248, 0.05);
    margin: 0px;
}
QSpinBox::up-button {
    subcontrol-position: top right;
    border-top-right-radius: 12px;
}
QSpinBox::down-button {
    subcontrol-position: bottom right;
    border-bottom-right-radius: 12px;
}
QSpinBox::up-button:hover, QSpinBox::down-button:hover {
    background: rgba(56, 189, 248, 0.12);
}
QSpinBox::up-arrow {
    image: url("__CHEVRON_UP_LIGHT__");
    width: 16px;
    height: 16px;
    margin: 0px;
}
QSpinBox::down-arrow {
    image: url("__CHEVRON_LIGHT__");
    width: 16px;
    height: 16px;
    margin: 0px;
}
QComboBox QAbstractItemView {
    background: #0b1424;
    color: #eef5ff;
    selection-background-color: #1d4ed8;
    border: 1px solid rgba(148, 163, 184, 0.24);
}

QListWidget {
    background: #0b1424;
    color: #eef5ff;
    border: 1px solid rgba(148, 163, 184, 0.24);
    border-radius: 14px;
    padding: 8px;
}
QListWidget::item {
    padding: 10px 12px;
    border-radius: 10px;
    margin: 3px;
}
QListWidget::item:selected {
    background: rgba(59, 130, 246, 0.28);
    color: #ffffff;
}
QListWidget::item:hover {
    background: rgba(56, 189, 248, 0.10);
}
QPushButton {
    background: #172a46;
    color: #eef5ff;
    border: 1px solid rgba(148, 163, 184, 0.22);
    border-radius: 12px;
    padding: 10px 14px;
    font-weight: 700;
}
QPushButton:hover {
    background: #203b61;
}
QPushButton:pressed {
    background: #0f2037;
}
QPushButton:disabled {
    color: #64748b;
    background: #0d1728;
    border: 1px solid rgba(100, 116, 139, 0.16);
}
QPushButton#PrimaryButton {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ff7a59, stop:0.45 #ec4899, stop:1 #7c3aed);
    color: white;
    border: none;
    border-radius: 14px;
    padding: 12px 18px;
    font-weight: 800;
}
QPushButton#PrimaryButton:hover {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ff8d6f, stop:0.45 #f35ca8, stop:1 #8b5cf6);
}
QPushButton#NavButton {
    background: transparent;
    color: #9fb0c4;
    border: none;
    border-radius: 14px;
    padding: 12px 14px;
    text-align: left;
    font-weight: 700;
}
QPushButton#NavButton:hover {
    background: rgba(56, 189, 248, 0.08);
    color: #ffffff;
}
QPushButton#NavButtonActive {
    background: rgba(59, 130, 246, 0.18);
    color: #ffffff;
    border: 1px solid rgba(56, 189, 248, 0.32);
    border-radius: 14px;
    padding: 12px 14px;
    text-align: left;
    font-weight: 800;
}
QLabel#WarningText {
    color: #fbbf24;
}
QLabel#SuccessText {
    color: #34d399;
}
QStackedWidget, QWidget#Page, QWidget#ScrollContent {
    background-color: #07111f;
}
QScrollArea {
    border: none;
    background-color: #07111f;
}
QScrollArea > QWidget, QScrollArea > QWidget > QWidget {
    background-color: #07111f;
}
QScrollArea#PageScrollArea {
    background-color: #07111f;
}
QScrollBar:vertical {
    background-color: #0a1627;
    width: 20px;
    margin: 0px;
    border-left: 1px solid rgba(148, 163, 184, 0.16);
}
QScrollBar::handle:vertical {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #38bdf8, stop:1 #7c3aed);
    min-height: 56px;
    border-radius: 8px;
    margin: 4px;
}
QScrollBar::handle:vertical:hover {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #67e8f9, stop:1 #8b5cf6);
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
    background: transparent;
}
QScrollBar:horizontal {
    background-color: #0a1627;
    height: 20px;
    margin: 0px;
    border-top: 1px solid rgba(148, 163, 184, 0.16);
}
QScrollBar::handle:horizontal {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #38bdf8, stop:1 #7c3aed);
    min-width: 56px;
    border-radius: 8px;
    margin: 4px;
}
QScrollBar::handle:horizontal:hover {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #67e8f9, stop:1 #8b5cf6);
}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: transparent;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
    background: transparent;
}
QMenuBar {
    background: #081322;
    color: #e2e8f0;
    border-bottom: 1px solid rgba(148, 163, 184, 0.14);
}
QMenuBar::item:selected {
    background: #172a46;
}
QMenu {
    background: #0b1424;
    color: #e2e8f0;
    border: 1px solid rgba(148, 163, 184, 0.24);
}
QMenu::item:selected {
    background: #1d4ed8;
}
"""


DARK_QSS = DARK_BLUE_QSS.replace("#07111f", "#0b0f17").replace("#0b1728", "#111827").replace("#101d31", "#171923").replace("#0b1424", "#111827").replace("#081322", "#0f172a")

LIGHT_QSS = """
QMainWindow { background: #f4f7fb; }
QWidget { color: #172033; font-family: "Segoe UI", "Inter", "Arial"; font-size: 13px; }
#AppShell, #Page, #ScrollContent, QStackedWidget { background-color: #f4f7fb; }
#Sidebar { background: #ffffff; border-right: 1px solid rgba(15, 23, 42, 0.10); }
#BrandTitle { color: #0f172a; font-size: 24px; font-weight: 800; letter-spacing: 0.4px; }
#BrandSubtitle, #PageSubtitle, #CardText { color: #64748b; }
#PageTitle { color: #0f172a; font-size: 26px; font-weight: 800; }
#HeroCard, #Card, #OutputCard, #MetricCard { background-color: #ffffff; border: 1px solid rgba(15, 23, 42, 0.10); border-radius: 22px; }
#HeroCard { background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #ffffff, stop:1 #e8f1ff); }
#CardTitle { color: #0f172a; font-size: 16px; font-weight: 800; }
#MetricNumber { color: #0f172a; font-size: 36px; font-weight: 900; }
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox { background: #ffffff; color: #172033; border: 1px solid rgba(15, 23, 42, 0.18); border-radius: 12px; padding: 9px 11px; selection-background-color: #2563eb; }
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QSpinBox:focus { border: 1px solid #2563eb; }
QComboBox { padding-right: 52px; }
QComboBox::drop-down { subcontrol-origin: border; subcontrol-position: top right; border: none; width: 44px; border-top-right-radius: 12px; border-bottom-right-radius: 12px; background: rgba(37, 99, 235, 0.06); }
QComboBox::drop-down:hover { background: rgba(37, 99, 235, 0.12); }
QComboBox::down-arrow { image: url("__CHEVRON_BLUE__"); width: 20px; height: 20px; margin: 0px; }
QSpinBox { padding-right: 52px; }
QSpinBox::up-button, QSpinBox::down-button { subcontrol-origin: border; width: 44px; border: none; background: rgba(37, 99, 235, 0.06); margin: 0px; }
QSpinBox::up-button { subcontrol-position: top right; border-top-right-radius: 12px; }
QSpinBox::down-button { subcontrol-position: bottom right; border-bottom-right-radius: 12px; }
QSpinBox::up-button:hover, QSpinBox::down-button:hover { background: rgba(37, 99, 235, 0.12); }
QSpinBox::up-arrow { image: url("__CHEVRON_UP_BLUE__"); width: 16px; height: 16px; margin: 0px; }
QSpinBox::down-arrow { image: url("__CHEVRON_BLUE__"); width: 16px; height: 16px; margin: 0px; }
QComboBox QAbstractItemView { background: #ffffff; color: #172033; selection-background-color: #dbeafe; border: 1px solid rgba(15, 23, 42, 0.18); }
QListWidget { background: #ffffff; color: #172033; border: 1px solid rgba(15, 23, 42, 0.16); border-radius: 14px; padding: 8px; }
QListWidget::item { padding: 10px 12px; border-radius: 10px; margin: 3px; }
QListWidget::item:selected { background: #dbeafe; color: #0f172a; }
QPushButton { background: #eef2f7; color: #172033; border: 1px solid rgba(15, 23, 42, 0.12); border-radius: 12px; padding: 10px 14px; font-weight: 700; }
QPushButton:hover { background: #e2e8f0; }
QPushButton:disabled { color: #94a3b8; background: #f1f5f9; border: 1px solid rgba(148, 163, 184, 0.22); }
QPushButton#PrimaryButton { background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563eb, stop:1 #7c3aed); color: white; border: none; border-radius: 14px; padding: 12px 18px; font-weight: 800; }
QPushButton#PrimaryButton:hover { background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1d4ed8, stop:1 #6d28d9); }
QPushButton#NavButton { background: transparent; color: #64748b; border: none; border-radius: 14px; padding: 12px 14px; text-align: left; font-weight: 700; }
QPushButton#NavButton:hover { background: #f1f5f9; color: #0f172a; }
QPushButton#NavButtonActive { background: #e0ecff; color: #1d4ed8; border: 1px solid rgba(37, 99, 235, 0.22); border-radius: 14px; padding: 12px 14px; text-align: left; font-weight: 800; }
QLabel#WarningText { color: #b45309; }
QLabel#SuccessText { color: #047857; }
QScrollArea, QScrollArea#PageScrollArea, QScrollArea > QWidget, QScrollArea > QWidget > QWidget { border: none; background-color: #f4f7fb; }
QScrollBar:vertical { background-color: #e2e8f0; width: 20px; margin: 0px; border-left: 1px solid rgba(15, 23, 42, 0.08); }
QScrollBar::handle:vertical { background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #2563eb, stop:1 #7c3aed); min-height: 56px; border-radius: 8px; margin: 4px; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical, QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { background: transparent; height: 0px; }
QScrollBar:horizontal { background-color: #e2e8f0; height: 20px; margin: 0px; border-top: 1px solid rgba(15, 23, 42, 0.08); }
QScrollBar::handle:horizontal { background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563eb, stop:1 #7c3aed); min-width: 56px; border-radius: 8px; margin: 4px; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal, QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { background: transparent; width: 0px; }
QMenuBar { background: #ffffff; color: #0f172a; border-bottom: 1px solid rgba(15, 23, 42, 0.10); }
QMenuBar::item:selected { background: #f1f5f9; }
QMenu { background: #ffffff; color: #0f172a; border: 1px solid rgba(15, 23, 42, 0.18); }
QMenu::item:selected { background: #dbeafe; }
"""


def theme_qss(theme_name: str) -> str:
    theme = (theme_name or "Dark blue").strip()
    if theme == "Soft Blue":
        theme = "Dark blue"
    if theme == "Light":
        return _with_asset_urls(LIGHT_QSS)
    if theme == "Dark":
        return _with_asset_urls(DARK_QSS)
    return _with_asset_urls(DARK_BLUE_QSS)
