from __future__ import annotations


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
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox {
    background: #0b1424;
    color: #eef5ff;
    border: 1px solid rgba(148, 163, 184, 0.24);
    border-radius: 12px;
    padding: 9px 11px;
    selection-background-color: #7c3aed;
}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus {
    border: 1px solid #38bdf8;
}
QComboBox::drop-down {
    border: none;
    padding-right: 8px;
}
QComboBox QAbstractItemView {
    background: #0b1424;
    color: #eef5ff;
    selection-background-color: #1d4ed8;
    border: 1px solid rgba(148, 163, 184, 0.24);
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
