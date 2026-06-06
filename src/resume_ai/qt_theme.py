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


THEME_OPTIONS = ["Light", "Dark", "Dark blue", "Modern 3D Light", "Modern 3D Dark"]
VALID_THEMES = set(THEME_OPTIONS)

DARK_BLUE_QSS = """
QMainWindow, QDialog#SettingsWindow, QDialog#SilentDialog {
    background: #07111f;
}
QWidget {
    color: #eef5ff;
    font-family: "Segoe UI", "Inter", "Arial";
    font-size: 13px;
}

QDialog#SettingsWindow QWidget, QDialog#SilentDialog QWidget {
    background-color: transparent;
}
QDialog#SettingsWindow QScrollArea, QDialog#SettingsWindow QScrollArea > QWidget, QDialog#SettingsWindow QScrollArea > QWidget > QWidget {
    background-color: #07111f;
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
    width: 22px;
    margin: 0px;
    border-radius: 11px;
    border: 1px solid rgba(148, 163, 184, 0.10);
}
QScrollBar::groove:vertical { background: transparent; border-radius: 11px; }
QScrollBar::handle:vertical {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #38bdf8, stop:1 #7c3aed);
    min-height: 64px;
    border-radius: 9px;
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
    height: 22px;
    margin: 0px;
    border-radius: 11px;
    border: 1px solid rgba(148, 163, 184, 0.10);
}
QScrollBar::groove:horizontal { background: transparent; border-radius: 11px; }
QScrollBar::handle:horizontal {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #38bdf8, stop:1 #7c3aed);
    min-width: 64px;
    border-radius: 9px;
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
    padding: 6px;
}
QMenu::item {
    padding: 8px 46px 8px 16px;
    min-width: 260px;
    border-radius: 8px;
}
QMenu::item:selected {
    background: #1d4ed8;
}
QMenu::separator {
    height: 1px;
    background: rgba(148, 163, 184, 0.20);
    margin: 6px 8px;
}
"""


DARK_QSS = DARK_BLUE_QSS.replace("#07111f", "#0b0f17").replace("#0b1728", "#111827").replace("#101d31", "#171923").replace("#0b1424", "#111827").replace("#081322", "#0f172a")

LIGHT_QSS = """
QMainWindow, QDialog#SettingsWindow, QDialog#SilentDialog { background: #f4f7fb; }
QWidget { color: #172033; font-family: "Segoe UI", "Inter", "Arial"; font-size: 13px; }
QDialog#SettingsWindow QWidget, QDialog#SilentDialog QWidget { background-color: transparent; }
QDialog#SettingsWindow QScrollArea, QDialog#SettingsWindow QScrollArea > QWidget, QDialog#SettingsWindow QScrollArea > QWidget > QWidget { background-color: #f4f7fb; }
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
QScrollBar:vertical { background-color: #e2e8f0; width: 22px; margin: 0px; border-radius: 11px; border: 1px solid rgba(15, 23, 42, 0.08); }
QScrollBar::handle:vertical { background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #2563eb, stop:1 #7c3aed); min-height: 64px; border-radius: 9px; margin: 4px; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical, QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { background: transparent; height: 0px; }
QScrollBar:horizontal { background-color: #e2e8f0; height: 22px; margin: 0px; border-radius: 11px; border: 1px solid rgba(15, 23, 42, 0.08); }
QScrollBar::handle:horizontal { background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563eb, stop:1 #7c3aed); min-width: 64px; border-radius: 9px; margin: 4px; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal, QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { background: transparent; width: 0px; }
QMenuBar { background: #ffffff; color: #0f172a; border-bottom: 1px solid rgba(15, 23, 42, 0.10); }
QMenuBar::item:selected { background: #f1f5f9; }
QMenu { background: #ffffff; color: #0f172a; border: 1px solid rgba(15, 23, 42, 0.18); padding: 6px; }
QMenu::item { padding: 8px 46px 8px 16px; min-width: 260px; border-radius: 8px; }
QMenu::item:selected { background: #dbeafe; }
QMenu::separator { height: 1px; background: rgba(15, 23, 42, 0.12); margin: 6px 8px; }
"""


MODERN_3D_LIGHT_QSS = """
QMainWindow, QDialog#SettingsWindow, QDialog#SilentDialog {
    background: #edf1f7;
}
QWidget {
    color: #687084;
    font-family: "Segoe UI", "Inter", "Arial";
    font-size: 13px;
}
QDialog#SettingsWindow QWidget, QDialog#SilentDialog QWidget { background-color: transparent; }
QDialog#SettingsWindow QScrollArea, QDialog#SettingsWindow QScrollArea > QWidget, QDialog#SettingsWindow QScrollArea > QWidget > QWidget { background-color: #edf1f7; }
#AppShell, #Page, #ScrollContent, QStackedWidget { background-color: #edf1f7; }
#Sidebar {
    background: #e9eef6;
    border-right: 1px solid rgba(148, 163, 184, 0.35);
}
#BrandTitle { color: #3f4656; font-size: 24px; font-weight: 900; letter-spacing: 0.4px; }
#BrandSubtitle, #PageSubtitle, #CardText { color: #778095; }
#PageTitle { color: #3f4656; font-size: 26px; font-weight: 900; }
#HeroCard, #Card, #OutputCard, #MetricCard {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #f8fbff, stop:1 #e7ecf4);
    border-top: 1px solid rgba(255,255,255,0.95);
    border-left: 1px solid rgba(255,255,255,0.95);
    border-right: 1px solid rgba(184, 194, 210, 0.55);
    border-bottom: 1px solid rgba(184, 194, 210, 0.55);
    border-radius: 24px;
}
#HeroCard {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #fbfdff, stop:0.55 #eef3fb, stop:1 #e3e9f4);
}
#CardTitle { color: #3f4656; font-size: 16px; font-weight: 900; }
#MetricNumber { color: #3f4656; font-size: 36px; font-weight: 900; }
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #e7ecf4, stop:1 #f7faff);
    color: #495063;
    border-top: 1px solid rgba(176, 187, 204, 0.80);
    border-left: 1px solid rgba(176, 187, 204, 0.80);
    border-right: 1px solid rgba(255, 255, 255, 0.85);
    border-bottom: 1px solid rgba(255, 255, 255, 0.85);
    border-radius: 18px;
    padding: 11px 14px;
    selection-background-color: #27c7dc;
}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QSpinBox:focus {
    border: 1px solid #1d6df2;
}
QComboBox { padding-right: 56px; }
QComboBox::drop-down {
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 48px;
    border: none;
    border-top-right-radius: 18px;
    border-bottom-right-radius: 18px;
    background: rgba(255,255,255,0.35);
}
QComboBox::drop-down:hover { background: rgba(29, 109, 242, 0.12); }
QComboBox::down-arrow { image: url("__CHEVRON_BLUE__"); width: 20px; height: 20px; margin: 0px; }
QSpinBox { padding-right: 56px; }
QSpinBox::up-button, QSpinBox::down-button {
    subcontrol-origin: border;
    width: 48px;
    border: none;
    background: rgba(255,255,255,0.35);
    margin: 0px;
}
QSpinBox::up-button { subcontrol-position: top right; border-top-right-radius: 18px; }
QSpinBox::down-button { subcontrol-position: bottom right; border-bottom-right-radius: 18px; }
QSpinBox::up-button:hover, QSpinBox::down-button:hover { background: rgba(29,109,242,0.12); }
QSpinBox::up-arrow { image: url("__CHEVRON_UP_BLUE__"); width: 16px; height: 16px; margin: 0px; }
QSpinBox::down-arrow { image: url("__CHEVRON_BLUE__"); width: 16px; height: 16px; margin: 0px; }
QComboBox QAbstractItemView {
    background: #f4f7fc;
    color: #495063;
    selection-background-color: #dbeafe;
    border: 1px solid rgba(148, 163, 184, 0.35);
}
QListWidget {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #e7ecf4, stop:1 #f7faff);
    color: #495063;
    border: 1px solid rgba(176, 187, 204, 0.70);
    border-radius: 18px;
    padding: 8px;
}
QListWidget::item { padding: 10px 12px; border-radius: 12px; margin: 3px; }
QListWidget::item:selected { background: #dce9ff; color: #1d4ed8; }
QListWidget::item:hover { background: rgba(29,109,242,0.08); }
QPushButton {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #f8fbff, stop:1 #dde5f0);
    color: #687084;
    border-top: 1px solid rgba(255,255,255,0.95);
    border-left: 1px solid rgba(255,255,255,0.95);
    border-right: 1px solid rgba(179,189,206,0.58);
    border-bottom: 1px solid rgba(179,189,206,0.58);
    border-radius: 18px;
    padding: 12px 18px;
    font-weight: 800;
}
QPushButton:hover { background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ffffff, stop:1 #dfe8f5); color: #3f4656; }
QPushButton:pressed { background-color: #dbe3ef; border-top: 1px solid rgba(179,189,206,0.80); border-left: 1px solid rgba(179,189,206,0.80); border-right: 1px solid rgba(255,255,255,0.90); border-bottom: 1px solid rgba(255,255,255,0.90); }
QPushButton:disabled { color: #a6afc0; background: #edf1f7; border: 1px solid rgba(176,187,204,0.45); }
QPushButton#PrimaryButton {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1d6df2, stop:0.55 #21c7df, stop:1 #8b5cf6);
    color: white;
    border: none;
    border-radius: 20px;
    padding: 13px 20px;
    font-weight: 900;
}
QPushButton#PrimaryButton:hover { background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #2563eb, stop:0.55 #22d3ee, stop:1 #7c3aed); }
QPushButton#PrimaryButton:pressed {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #185abc, stop:0.55 #0891b2, stop:1 #6d28d9);
    border-top: 1px solid rgba(54, 75, 105, 0.65);
    border-left: 1px solid rgba(54, 75, 105, 0.65);
    border-right: 1px solid rgba(255,255,255,0.55);
    border-bottom: 1px solid rgba(255,255,255,0.55);
}
QPushButton#NavButton {
    background: transparent;
    color: #687084;
    border: none;
    border-radius: 18px;
    padding: 12px 14px;
    text-align: left;
    font-weight: 800;
}
QPushButton#NavButton:hover { background: rgba(255,255,255,0.55); color: #3f4656; }
QPushButton#NavButtonActive {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #ffffff, stop:1 #dfe8f5);
    color: #1d6df2;
    border-top: 1px solid rgba(255,255,255,0.95);
    border-left: 1px solid rgba(255,255,255,0.95);
    border-right: 1px solid rgba(179,189,206,0.55);
    border-bottom: 1px solid rgba(179,189,206,0.55);
    border-radius: 18px;
    padding: 12px 14px;
    text-align: left;
    font-weight: 900;
}
QLabel#WarningText { color: #b45309; }
QLabel#SuccessText { color: #047857; }
QScrollArea, QScrollArea#PageScrollArea, QScrollArea > QWidget, QScrollArea > QWidget > QWidget { border: none; background-color: #edf1f7; }
QScrollBar:vertical { background-color: #dfe6f1; width: 22px; margin: 0px; border-radius: 11px; border: 1px solid rgba(148,163,184,0.22); }
QScrollBar::handle:vertical { background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #1d6df2, stop:1 #22c7dc); min-height: 64px; border-radius: 9px; margin: 4px; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical, QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { background: transparent; height: 0px; }
QScrollBar:horizontal { background-color: #dfe6f1; height: 22px; margin: 0px; border-radius: 11px; border: 1px solid rgba(148,163,184,0.22); }
QScrollBar::handle:horizontal { background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1d6df2, stop:1 #22c7dc); min-width: 64px; border-radius: 9px; margin: 4px; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal, QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { background: transparent; width: 0px; }
QMenuBar { background: #edf1f7; color: #4b5565; border-bottom: 1px solid rgba(148,163,184,0.28); }
QMenuBar::item:selected { background: #f8fbff; color: #1d6df2; }
QMenu { background: #f4f7fc; color: #495063; border: 1px solid rgba(148,163,184,0.35); padding: 6px; }
QMenu::item { padding: 9px 54px 9px 16px; min-width: 300px; border-radius: 10px; }
QMenu::item:selected { background: #dbeafe; color: #1d4ed8; }
QMenu::separator { height: 1px; background: rgba(148,163,184,0.30); margin: 6px 8px; }
"""

MODERN_3D_DARK_QSS = """
QMainWindow, QDialog#SettingsWindow, QDialog#SilentDialog {
    background: #262626;
}
QWidget {
    color: #f3f4f6;
    font-family: "Segoe UI", "Inter", "Arial";
    font-size: 13px;
}
QDialog#SettingsWindow QWidget, QDialog#SilentDialog QWidget { background-color: transparent; }
QDialog#SettingsWindow QScrollArea, QDialog#SettingsWindow QScrollArea > QWidget, QDialog#SettingsWindow QScrollArea > QWidget > QWidget { background-color: #262626; }
#AppShell, #Page, #ScrollContent, QStackedWidget { background-color: #262626; }
#Sidebar {
    background: #202020;
    border-right: 1px solid rgba(255,255,255,0.06);
}
#BrandTitle { color: #ffffff; font-size: 24px; font-weight: 900; letter-spacing: 0.4px; }
#BrandSubtitle, #PageSubtitle, #CardText { color: #a7a7ad; }
#PageTitle { color: #ffffff; font-size: 26px; font-weight: 900; }
#HeroCard, #Card, #OutputCard, #MetricCard {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #303030, stop:1 #222222);
    border-top: 1px solid rgba(255,255,255,0.08);
    border-left: 1px solid rgba(255,255,255,0.07);
    border-right: 1px solid rgba(0,0,0,0.60);
    border-bottom: 1px solid rgba(0,0,0,0.60);
    border-radius: 24px;
}
#HeroCard { background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #343434, stop:1 #232323); }
#CardTitle { color: #ffffff; font-size: 16px; font-weight: 900; }
#MetricNumber { color: #ffffff; font-size: 36px; font-weight: 900; }
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #202020, stop:1 #303030);
    color: #f3f4f6;
    border-top: 1px solid rgba(0,0,0,0.65);
    border-left: 1px solid rgba(0,0,0,0.65);
    border-right: 1px solid rgba(255,255,255,0.08);
    border-bottom: 1px solid rgba(255,255,255,0.08);
    border-radius: 18px;
    padding: 11px 14px;
    selection-background-color: #ec4899;
}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QSpinBox:focus { border: 1px solid #ff7a59; }
QComboBox { padding-right: 56px; }
QComboBox::drop-down {
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 48px;
    border: none;
    border-top-right-radius: 18px;
    border-bottom-right-radius: 18px;
    background: rgba(255,255,255,0.04);
}
QComboBox::drop-down:hover { background: rgba(255,122,89,0.12); }
QComboBox::down-arrow { image: url("__CHEVRON_LIGHT__"); width: 20px; height: 20px; margin: 0px; }
QSpinBox { padding-right: 56px; }
QSpinBox::up-button, QSpinBox::down-button {
    subcontrol-origin: border;
    width: 48px;
    border: none;
    background: rgba(255,255,255,0.04);
    margin: 0px;
}
QSpinBox::up-button { subcontrol-position: top right; border-top-right-radius: 18px; }
QSpinBox::down-button { subcontrol-position: bottom right; border-bottom-right-radius: 18px; }
QSpinBox::up-button:hover, QSpinBox::down-button:hover { background: rgba(255,122,89,0.12); }
QSpinBox::up-arrow { image: url("__CHEVRON_UP_LIGHT__"); width: 16px; height: 16px; margin: 0px; }
QSpinBox::down-arrow { image: url("__CHEVRON_LIGHT__"); width: 16px; height: 16px; margin: 0px; }
QComboBox QAbstractItemView {
    background: #262626;
    color: #f3f4f6;
    selection-background-color: #7c3aed;
    border: 1px solid rgba(255,255,255,0.10);
}
QListWidget {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #202020, stop:1 #303030);
    color: #f3f4f6;
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 18px;
    padding: 8px;
}
QListWidget::item { padding: 10px 12px; border-radius: 12px; margin: 3px; }
QListWidget::item:selected { background: rgba(236,72,153,0.30); color: #ffffff; }
QListWidget::item:hover { background: rgba(255,255,255,0.05); }
QPushButton {
    background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #333333, stop:1 #222222);
    color: #f3f4f6;
    border-top: 1px solid rgba(255,255,255,0.09);
    border-left: 1px solid rgba(255,255,255,0.08);
    border-right: 1px solid rgba(0,0,0,0.60);
    border-bottom: 1px solid rgba(0,0,0,0.60);
    border-radius: 18px;
    padding: 12px 18px;
    font-weight: 800;
}
QPushButton:hover { background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #3a3a3a, stop:1 #272727); }
QPushButton:pressed { background-color: #222222; border-top: 1px solid rgba(0,0,0,0.75); border-left: 1px solid rgba(0,0,0,0.75); border-right: 1px solid rgba(255,255,255,0.10); border-bottom: 1px solid rgba(255,255,255,0.10); }
QPushButton:disabled { color: #6b7280; background: #242424; border: 1px solid rgba(255,255,255,0.04); }
QPushButton#PrimaryButton {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #ff8a5b, stop:0.45 #ec4899, stop:1 #7c3aed);
    color: white;
    border: none;
    border-radius: 20px;
    padding: 13px 20px;
    font-weight: 900;
}
QPushButton#PrimaryButton:hover { background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #ff9b71, stop:0.45 #f35ca8, stop:1 #8b5cf6); }
QPushButton#PrimaryButton:pressed {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #d65f3d, stop:0.45 #be185d, stop:1 #6d28d9);
    border-top: 1px solid rgba(0,0,0,0.65);
    border-left: 1px solid rgba(0,0,0,0.65);
    border-right: 1px solid rgba(255,255,255,0.08);
    border-bottom: 1px solid rgba(255,255,255,0.08);
}
QPushButton#NavButton {
    background: transparent;
    color: #c7c7cc;
    border: none;
    border-radius: 18px;
    padding: 12px 14px;
    text-align: left;
    font-weight: 800;
}
QPushButton#NavButton:hover { background: rgba(255,255,255,0.05); color: #ffffff; }
QPushButton#NavButtonActive {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #333333, stop:1 #232323);
    color: #ff7a59;
    border-top: 1px solid rgba(255,255,255,0.09);
    border-left: 1px solid rgba(255,255,255,0.08);
    border-right: 1px solid rgba(0,0,0,0.60);
    border-bottom: 1px solid rgba(0,0,0,0.60);
    border-radius: 18px;
    padding: 12px 14px;
    text-align: left;
    font-weight: 900;
}
QLabel#WarningText { color: #fbbf24; }
QLabel#SuccessText { color: #34d399; }
QScrollArea, QScrollArea#PageScrollArea, QScrollArea > QWidget, QScrollArea > QWidget > QWidget { border: none; background-color: #262626; }
QScrollBar:vertical { background-color: #202020; width: 22px; margin: 0px; border-radius: 11px; border: 1px solid rgba(255,255,255,0.06); }
QScrollBar::handle:vertical { background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ff8a5b, stop:0.55 #ec4899, stop:1 #7c3aed); min-height: 64px; border-radius: 9px; margin: 4px; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical, QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { background: transparent; height: 0px; }
QScrollBar:horizontal { background-color: #202020; height: 22px; margin: 0px; border-radius: 11px; border: 1px solid rgba(255,255,255,0.06); }
QScrollBar::handle:horizontal { background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ff8a5b, stop:0.55 #ec4899, stop:1 #7c3aed); min-width: 64px; border-radius: 9px; margin: 4px; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal, QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { background: transparent; width: 0px; }
QMenuBar { background: #202020; color: #f3f4f6; border-bottom: 1px solid rgba(255,255,255,0.06); }
QMenuBar::item:selected { background: #303030; color: #ff8a5b; }
QMenu { background: #262626; color: #f3f4f6; border: 1px solid rgba(255,255,255,0.09); padding: 6px; }
QMenu::item { padding: 9px 54px 9px 16px; min-width: 300px; border-radius: 10px; }
QMenu::item:selected { background: rgba(236,72,153,0.24); color: #ffffff; }
QMenu::separator { height: 1px; background: rgba(255,255,255,0.08); margin: 6px 8px; }
"""


def theme_qss(theme_name: str) -> str:
    theme = (theme_name or "Dark blue").strip()
    if theme == "Soft Blue":
        theme = "Dark blue"
    if theme == "Light":
        return _with_asset_urls(LIGHT_QSS)
    if theme == "Dark":
        return _with_asset_urls(DARK_QSS)
    if theme == "Modern 3D Light":
        return _with_asset_urls(MODERN_3D_LIGHT_QSS)
    if theme == "Modern 3D Dark":
        return _with_asset_urls(MODERN_3D_DARK_QSS)
    return _with_asset_urls(DARK_BLUE_QSS)
