from __future__ import annotations

import json
import re
import sys
import threading
import traceback
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, QRegularExpression, QRectF, Qt, QUrl, Signal
from PySide6.QtGui import QAction, QColor, QDesktopServices, QIcon, QImage, QLinearGradient, QPainter, QPixmap, QRegularExpressionValidator
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QScrollArea,
    QScrollBar,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

try:
    from PySide6.QtSvg import QSvgRenderer
except Exception:  # pragma: no cover - QtSvg may be unavailable in rare PySide installs.
    QSvgRenderer = None

from .ai_service import AIService
from .models import AISettings, CandidateProfile, GenerationRequest
from .application_package_exporter import export_application_package
from .pdf_exporter import export_markdown_to_pdf
from .pdf_templates import get_pdf_template_names
from .document_layout import (
    extract_markdown_sections,
    insert_page_break_after_section,
    remove_page_break_markers,
    reorder_markdown_sections,
)
from .quality_checker import analyze_document, format_quality_report
from .settings_manager import AppSettings, load_app_settings, save_app_settings
from .app_paths import applications_dir, data_dir, exports_dir, logs_dir, profile_path
from .storage import load_json, save_json
from .templates import get_template_names
from .workspace_manager import (
    ensure_applications_dir,
    load_application_snapshot,
    save_application_snapshot,
    suggested_application_filename,
)
from .qt_theme import DARK_BLUE_QSS, THEME_OPTIONS, theme_qss


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
ASSET_DIR = Path(__file__).resolve().parent / "assets"
LOGO_PATH = ASSET_DIR / "resubuilder_logo.svg"
PROFILE_PATH = profile_path()

OLLAMA_MODEL_OPTIONS = [
    "qwen3:8b",
    "qwen3:14b",
    "qwen2.5:7b",
    "llama3.1:8b",
    "gemma3:12b",
]

OPENAI_MODEL_OPTIONS = [
    "gpt-4.1-mini",
    "gpt-4.1",
    "gpt-4o-mini",
    "gpt-4o",
]

OUTPUT_LANGUAGE_OPTIONS = ["English", "German"]


class QMessageBox:
    """Silent replacement for QMessageBox convenience dialogs.

    Native QMessageBox convenience functions trigger the Windows system notification sound.
    The Qt app uses this small modal dialog so save/load/generate notices stay quiet.
    It intentionally mimics the subset of QMessageBox used in this file.
    """

    class StandardButton:
        Yes = 1
        No = 2

    @staticmethod
    def _show(parent: QWidget | None, title: str, text: str, level: str = "Info") -> int:
        dialog = QDialog(parent)
        dialog.setWindowTitle(title)
        dialog.setModal(True)
        dialog.setObjectName("SilentDialog")
        dialog.setMinimumWidth(460)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(14)

        heading = QLabel(level)
        heading.setObjectName("CardTitle")
        layout.addWidget(heading)

        message = QLabel(text)
        message.setObjectName("CardText")
        message.setWordWrap(True)
        message.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(message)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        ok_button = QPushButton("OK")
        ok_button.setObjectName("SecondaryButton")
        ok_button.setMinimumWidth(120)
        ok_button.clicked.connect(dialog.accept)
        button_row.addWidget(ok_button)
        layout.addLayout(button_row)

        ok_button.setFocus()
        dialog.exec()
        return QMessageBox.StandardButton.Yes

    @staticmethod
    def information(parent: QWidget | None, title: str, text: str) -> int:
        return QMessageBox._show(parent, title, text, "Info")

    @staticmethod
    def warning(parent: QWidget | None, title: str, text: str) -> int:
        return QMessageBox._show(parent, title, text, "Warning")

    @staticmethod
    def critical(parent: QWidget | None, title: str, text: str) -> int:
        return QMessageBox._show(parent, title, text, "Error")

    @staticmethod
    def question(
        parent: QWidget | None,
        title: str,
        text: str,
        buttons: int | None = None,
        default_button: int | None = None,
    ) -> int:
        dialog = QDialog(parent)
        dialog.setWindowTitle(title)
        dialog.setModal(True)
        dialog.setObjectName("SilentDialog")
        dialog.setMinimumWidth(520)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(22, 18, 22, 18)
        layout.setSpacing(14)

        heading = QLabel("Confirm")
        heading.setObjectName("CardTitle")
        layout.addWidget(heading)

        message = QLabel(text)
        message.setObjectName("CardText")
        message.setWordWrap(True)
        message.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(message)

        result = {"value": QMessageBox.StandardButton.No}

        button_row = QHBoxLayout()
        button_row.addStretch(1)

        no_button = QPushButton("No")
        no_button.setObjectName("SecondaryButton")
        no_button.setMinimumWidth(120)
        yes_button = QPushButton("Yes")
        yes_button.setObjectName("PrimaryButton")
        yes_button.setMinimumWidth(120)

        def choose_no() -> None:
            result["value"] = QMessageBox.StandardButton.No
            dialog.accept()

        def choose_yes() -> None:
            result["value"] = QMessageBox.StandardButton.Yes
            dialog.accept()

        no_button.clicked.connect(choose_no)
        yes_button.clicked.connect(choose_yes)
        button_row.addWidget(no_button)
        button_row.addWidget(yes_button)
        layout.addLayout(button_row)

        if default_button == QMessageBox.StandardButton.Yes:
            yes_button.setFocus()
        else:
            no_button.setFocus()

        dialog.exec()
        return result["value"]



@dataclass
class QtGenerationContext:
    document_type: str
    request: GenerationRequest


class GenerationSignals(QObject):
    """Signals used by the background generation thread.

    Using Python threading here is deliberate. The first Qt prototype used QThread, which can be easy to
    misuse and can make the app appear to close without a useful error when the worker
    lifecycle is wrong. These signals keep all UI updates on the main Qt thread while the AI call runs in
    a normal Python thread.
    """

    finished = Signal(int, str, str)
    failed = Signal(int, str)


class JobFitSignals(QObject):
    """Signals for the Ollama job-fit analyzer embedded in the Generate page."""

    finished = Signal(int, str)
    failed = Signal(int, str)


class AIReviewSignals(QObject):
    """Signals for the background AI quality review task."""

    finished = Signal(int, str)
    failed = Signal(int, str)


class ImproveSignals(QObject):
    """Signals for the background quality-fix improvement task."""

    finished = Signal(int, str, str)
    failed = Signal(int, str)




class RoundedScrollBar(QScrollBar):
    """Custom-painted scrollbar with a genuinely rounded moving handle.

    Qt stylesheets can leave native scrollbar thumbs with square ends on Windows,
    even when border-radius is specified. Painting the thumb ourselves gives the
    Modern 3D themes the pill-shaped scrollbar the UI is aiming for.
    """

    def __init__(self, orientation: Qt.Orientation, parent: QWidget | None = None) -> None:
        super().__init__(orientation, parent)
        self.setFixedWidth(20) if orientation == Qt.Orientation.Vertical else self.setFixedHeight(20)
        self.setMouseTracking(True)

    def _theme_name(self) -> str:
        app = QApplication.instance()
        value = app.property("resubuilder_theme") if app is not None else None
        return str(value or "Dark blue")

    def _colors(self) -> tuple[QColor, QColor, QColor]:
        theme = self._theme_name()
        if theme == "Modern 3D Light":
            return QColor("#dfe6f1"), QColor("#1d6df2"), QColor("#22c7dc")
        if theme == "Modern 3D Dark":
            return QColor("#202020"), QColor("#ff8a5b"), QColor("#7c3aed")
        if theme == "Light":
            return QColor("#e2e8f0"), QColor("#2563eb"), QColor("#7c3aed")
        if theme == "Dark":
            return QColor("#232323"), QColor("#ff8a5b"), QColor("#7c3aed")
        return QColor("#0a1627"), QColor("#38bdf8"), QColor("#7c3aed")

    def _slider_rect(self) -> QRectF:
        groove = self.rect().adjusted(5, 5, -5, -5)
        minimum = self.minimum()
        maximum = self.maximum()
        page = max(1, self.pageStep())
        if self.orientation() == Qt.Orientation.Vertical:
            available = max(1, groove.height())
            total = max(1, maximum - minimum + page)
            handle_len = max(54, int(available * page / total))
            handle_len = min(handle_len, available)
            travel = max(1, available - handle_len)
            ratio = 0 if maximum <= minimum else (self.value() - minimum) / (maximum - minimum)
            y = groove.top() + int(travel * ratio)
            return QRectF(groove.left(), y, groove.width(), handle_len)
        available = max(1, groove.width())
        total = max(1, maximum - minimum + page)
        handle_len = max(54, int(available * page / total))
        handle_len = min(handle_len, available)
        travel = max(1, available - handle_len)
        ratio = 0 if maximum <= minimum else (self.value() - minimum) / (maximum - minimum)
        x = groove.left() + int(travel * ratio)
        return QRectF(x, groove.top(), handle_len, groove.height())

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt method name
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)

        track, start, end = self._colors()
        track.setAlpha(210)
        track_rect = QRectF(self.rect().adjusted(3, 3, -3, -3))
        track_radius = min(track_rect.width(), track_rect.height()) / 2
        painter.setBrush(track)
        painter.drawRoundedRect(track_rect, track_radius, track_radius)

        handle = self._slider_rect()
        if handle.width() <= 0 or handle.height() <= 0:
            return
        if self.orientation() == Qt.Orientation.Vertical:
            gradient = QLinearGradient(handle.center().x(), handle.top(), handle.center().x(), handle.bottom())
        else:
            gradient = QLinearGradient(handle.left(), handle.center().y(), handle.right(), handle.center().y())
        gradient.setColorAt(0.0, start)
        gradient.setColorAt(1.0, end)
        radius = min(handle.width(), handle.height()) / 2
        painter.setBrush(gradient)
        painter.drawRoundedRect(handle, radius, radius)

class Card(QFrame):
    def __init__(self, title: str = "", subtitle: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self._add_outer_shadow()
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(22, 20, 22, 20)
        self.layout.setSpacing(12)
        if title:
            title_label = QLabel(title)
            title_label.setObjectName("CardTitle")
            self.layout.addWidget(title_label)
        if subtitle:
            subtitle_label = QLabel(subtitle)
            subtitle_label.setObjectName("CardText")
            subtitle_label.setWordWrap(True)
            self.layout.addWidget(subtitle_label)

    def _add_outer_shadow(self) -> None:
        """Add a directional shadow on the lower-right side of cards.

        The previous 3D shadow was centered enough to create a halo on the
        top and left edges. That made the cards look heavy. A positive X/Y
        offset keeps the visible depth mostly on the right and bottom, which
        gives the cleaner floating effect requested for the release UI.
        """
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(22)
        shadow.setOffset(12, 14)
        shadow.setColor(QColor(0, 0, 0, 92))
        self.setGraphicsEffect(shadow)


class ResuBuilderQtApp(QMainWindow):
    """Primary PySide6 interface.

    This file contains the primary ResuBuilder desktop interface. The legacy Tkinter GUI is kept available through app_legacy.py as a backup during transition.
    """

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("ResuBuilder")
        self.resize(1380, 860)
        self.setMinimumSize(1180, 760)

        self.ai_service = AIService()
        self.app_settings: AppSettings = load_app_settings()
        self.generated_cv = ""
        self.generated_covering_letter = ""
        self.job_fit_analysis = ""
        self.ai_quality_review = ""
        self.manual_edit_instructions = ""
        self.evidence_entries: list[dict[str, str]] = []
        self._legacy_structured_evidence_text = ""
        self.current_workspace_path: Path | None = None
        self._generation_running = False
        self._generation_job_id = 0
        self._job_fit_running = False
        self._job_fit_job_id = 0
        self._ai_review_running = False
        self._ai_review_job_id = 0
        self._improvement_running = False
        self._improvement_job_id = 0
        self._improvement_reason = "quality fixes"
        self.generation_signals = GenerationSignals()
        self.generation_signals.finished.connect(self._generation_finished)
        self.generation_signals.failed.connect(self._generation_failed)
        self.job_fit_signals = JobFitSignals()
        self.job_fit_signals.finished.connect(self._job_fit_finished)
        self.job_fit_signals.failed.connect(self._job_fit_failed)
        self.ai_review_signals = AIReviewSignals()
        self.ai_review_signals.finished.connect(self._ai_review_finished)
        self.ai_review_signals.failed.connect(self._ai_review_failed)
        self.improve_signals = ImproveSignals()
        self.improve_signals.finished.connect(self._improvement_finished)
        self.improve_signals.failed.connect(self._improvement_failed)

        self.page_buttons: dict[str, QPushButton] = {}
        self.pages: dict[str, QWidget] = {}

        self._apply_theme_styles(getattr(self.app_settings, "ui_theme", "Dark blue"))
        self._apply_window_icon()
        self._build_menu()
        self._build_shell()
        self.show_page("Welcome")

    def _menu_action(self, label: str, callback) -> QAction:
        action = QAction(label, self)
        action.triggered.connect(lambda checked=False, cb=callback: cb())
        return action

    def _open_page_action(self, page_name: str, label: str | None = None) -> QAction:
        return self._menu_action(label or f"Open {page_name}", lambda checked=False, name=page_name: self.show_page(name))

    def _set_menu_width(self, menu, width: int) -> None:
        """Set safe menu width without walking transient Qt menu objects.

        PySide6 can delete temporary submenu wrappers while the menu bar is being built on
        Windows. A previous dynamic-width helper walked child QMenu objects and could crash
        at startup with: "Internal C++ object (QMenu) already deleted". Fixed widths are
        safer here and still keep every menu label readable.
        """
        try:
            menu.setMinimumWidth(width)
        except RuntimeError:
            # Do not crash the app because a transient Qt menu wrapper was already released.
            pass

    def _disable_horizontal_scroll(self, scroll: QScrollArea) -> None:
        """Keep workflow pages readable without horizontal scrollbars.

        If a page needs a horizontal scrollbar, the layout is too wide. We solve that by
        wrapping/splitting controls instead of making the user slide sideways.
        """
        self._install_rounded_scrollbars(scroll)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

    def _add_frame_shadow(self, frame: QFrame) -> None:
        """Apply a lower-right directional shadow to non-Card frames."""
        shadow = QGraphicsDropShadowEffect(frame)
        shadow.setBlurRadius(22)
        shadow.setOffset(12, 14)
        shadow.setColor(QColor(0, 0, 0, 88))
        frame.setGraphicsEffect(shadow)

    def _logo_pixmap(self, size: int) -> QPixmap | None:
        """Load the optional SVG logo from src/resume_ai/assets/resubuilder_logo.svg."""
        if not LOGO_PATH.exists():
            return None
        pixmap = QPixmap(str(LOGO_PATH))
        if pixmap.isNull() and QSvgRenderer is not None:
            try:
                renderer = QSvgRenderer(str(LOGO_PATH))
                image = QImage(size, size, QImage.Format.Format_ARGB32)
                image.fill(Qt.GlobalColor.transparent)
                painter = QPainter(image)
                renderer.render(painter)
                painter.end()
                pixmap = QPixmap.fromImage(image)
            except Exception:
                pixmap = QPixmap()
        if pixmap.isNull():
            return None
        return pixmap.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)

    def _apply_window_icon(self) -> None:
        if LOGO_PATH.exists():
            self.setWindowIcon(QIcon(str(LOGO_PATH)))

    def _logo_label(self, size: int, fallback_text: str = "RB") -> QLabel:
        label = QLabel(fallback_text)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setFixedSize(size, size)
        pixmap = self._logo_pixmap(size)
        if pixmap is not None:
            label.setPixmap(pixmap)
            label.setStyleSheet("background: transparent; border: none;")
        else:
            radius = max(12, int(size * 0.28))
            font_size = max(16, int(size * 0.33))
            label.setStyleSheet(
                f"background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #ff7a59,stop:0.45 #ec4899,stop:1 #7c3aed);"
                f"border-radius: {radius}px; color: white; font-size: {font_size}px; font-weight: 900;"
            )
        return label

    def _apply_theme_styles(self, theme_name: str) -> None:
        theme = self._normalized_theme(theme_name) if hasattr(self, "_normalized_theme") else (theme_name or "Dark blue")
        app = QApplication.instance()
        if app is not None:
            app.setProperty("resubuilder_theme", theme)
        QMainWindow.setStyleSheet(self, theme_qss(theme))
        self._refresh_custom_scrollbars()

    def _install_rounded_scrollbars(self, widget: QWidget) -> None:
        if hasattr(widget, "setVerticalScrollBar"):
            widget.setVerticalScrollBar(RoundedScrollBar(Qt.Orientation.Vertical, widget))
        if hasattr(widget, "setHorizontalScrollBar"):
            widget.setHorizontalScrollBar(RoundedScrollBar(Qt.Orientation.Horizontal, widget))

    def _refresh_custom_scrollbars(self) -> None:
        for bar in self.findChildren(RoundedScrollBar):
            bar.update()

    def _build_menu(self) -> None:
        """Build a compact top menu.

        The sidebar remains the main workflow navigation. The menu bar is for app-level actions,
        quick settings, and help, matching the simpler legacy structure.
        """
        menu_bar = self.menuBar()

        self.file_menu = menu_bar.addMenu("File")
        self.file_menu.addAction(self._menu_action("New Application Workspace", self._new_workspace))
        self.file_menu.addAction(self._menu_action("Load Application Workspace...", self._load_workspace))
        self.file_menu.addAction(self._menu_action("Save Application Workspace", self._save_workspace))
        self.file_menu.addAction(self._menu_action("Save Application Workspace As...", self._save_workspace_as))
        self.file_menu.addSeparator()
        self.file_menu.addAction(self._menu_action("Load Profile...", self._load_profile))
        self.file_menu.addAction(self._menu_action("Save Profile", self._save_current_profile))
        self.file_menu.addAction(self._menu_action("Save Profile As...", self._save_profile_as))
        self.file_menu.addSeparator()
        self.file_menu.addAction(self._menu_action("Export Application Package", self._export_application_package))
        self.file_menu.addAction(self._menu_action("Open Export Folder", self._open_export_dir))
        self.file_menu.addSeparator()
        self.file_menu.addAction(self._menu_action("Exit", self.close))

        self.settings_menu = menu_bar.addMenu("Settings")
        self.settings_menu.addAction(self._menu_action("Open Settings...", self._open_settings_window))
        self.theme_menu = self.settings_menu.addMenu("UI Theme")
        for theme_name in THEME_OPTIONS:
            self.theme_menu.addAction(self._menu_action(theme_name, lambda theme=theme_name: self._set_theme_from_menu(theme)))
        self.settings_menu.addSeparator()
        self.settings_menu.addAction(self._menu_action("Save App Settings", self._save_settings))
        self.settings_menu.addAction(self._menu_action("Restore App Settings", self._reset_settings))

        self.help_menu = menu_bar.addMenu("Help")
        self.help_menu.addAction(self._menu_action("Workflow Guide", self._show_workflow_help))
        self.help_menu.addAction(self._menu_action("Options Help", self._show_options_help))
        self.help_menu.addSeparator()
        self.help_menu.addAction(self._menu_action("About ResuBuilder", self._show_about))

        self._set_menu_width(self.file_menu, 380)
        self._set_menu_width(self.settings_menu, 300)
        self._set_menu_width(self.theme_menu, 320)
        self._set_menu_width(self.help_menu, 260)

    def _set_theme_from_menu(self, theme_name: str) -> None:
        """Apply a theme immediately from the compact top menu and remember it."""
        theme = self._normalized_theme(theme_name)
        self.app_settings.ui_theme = theme
        if hasattr(self, "settings_theme_combo"):
            self.settings_theme_combo.setCurrentText(theme)
        self._apply_theme_styles(theme)
        try:
            save_app_settings(self.app_settings)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Theme", f"Theme changed, but could not save settings: {exc}")
            return
        if hasattr(self, "settings_status_label"):
            self.settings_status_label.setText(f"Theme changed to {theme} and saved.")

    def _refresh_settings_page_controls(self) -> None:
        """Refresh the sidebar Settings page from self.app_settings when settings changed elsewhere."""
        if not hasattr(self, "settings_provider_combo"):
            return
        self.settings_provider_combo.setCurrentText(getattr(self.app_settings, "ai_provider", "Ollama Local"))
        self.settings_generation_mode_combo.setCurrentText(getattr(self.app_settings, "generation_mode", "Balanced"))
        self.settings_ollama_url_edit.setText(getattr(self.app_settings, "ollama_base_url", "http://localhost:11434"))
        self.settings_ollama_model_combo.setCurrentText(getattr(self.app_settings, "ollama_model", "qwen3:8b"))
        self.settings_openai_model_combo.setCurrentText(getattr(self.app_settings, "openai_model", "gpt-4.1-mini"))
        self.settings_timeout_spin.setValue(int(getattr(self.app_settings, "timeout_seconds", 120)))
        self.settings_template_combo.setCurrentText(getattr(self.app_settings, "template_name", "ATS Friendly"))
        self.settings_pdf_template_combo.setCurrentText(getattr(self.app_settings, "pdf_template", "ATS Friendly"))
        self.settings_page_size_combo.setCurrentText(getattr(self.app_settings, "pdf_page_size", "A4"))
        if hasattr(self, "settings_output_language_combo"):
            self.settings_output_language_combo.setCurrentText(getattr(self.app_settings, "output_language", "English"))
        self.settings_workspace_dir_edit.setText(getattr(self.app_settings, "last_workspace_dir", "") or str(applications_dir()))
        self.settings_export_dir_edit.setText(getattr(self.app_settings, "last_export_dir", "") or str(exports_dir()))
        self.settings_theme_combo.setCurrentText(self._normalized_theme(getattr(self.app_settings, "ui_theme", "Dark blue")))

    def _open_settings_window(self) -> None:
        """Open settings in a standalone modal window from the top menu."""
        dialog = QDialog(self)
        dialog.setWindowTitle("ResuBuilder Settings")
        dialog.setModal(True)
        dialog.resize(960, 760)
        dialog.setObjectName("SettingsWindow")

        root = QVBoxLayout(dialog)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(16)

        title = QLabel("Settings")
        title.setObjectName("PageTitle")
        subtitle = QLabel("Adjust AI, document, folder, and appearance defaults without leaving the current workflow step.")
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)
        root.addWidget(title)
        root.addWidget(subtitle)

        scroll = QScrollArea()
        scroll.setObjectName("PageScrollArea")
        scroll.setWidgetResizable(True)
        self._disable_horizontal_scroll(scroll)
        content = QWidget()
        content.setObjectName("ScrollContent")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 14, 0)
        content_layout.setSpacing(18)

        ai_card = Card("AI settings", "Controls used by generation, job fit analysis, AI review, and quality-fix improvement.")
        ai_grid = QGridLayout()
        ai_grid.setHorizontalSpacing(18)
        ai_grid.setVerticalSpacing(14)
        ai_grid.setColumnStretch(0, 1)
        ai_grid.setColumnStretch(1, 1)

        provider_combo = QComboBox()
        provider_combo.addItems(["Ollama Local", "OpenAI"])
        provider_combo.setCurrentText(getattr(self.app_settings, "ai_provider", "Ollama Local"))
        generation_mode_combo = QComboBox()
        generation_mode_combo.addItems(["Conservative", "Balanced", "Aggressive"])
        generation_mode_combo.setCurrentText(getattr(self.app_settings, "generation_mode", "Balanced"))
        ollama_url_edit = QLineEdit(getattr(self.app_settings, "ollama_base_url", "http://localhost:11434"))
        ollama_model_combo = QComboBox()
        ollama_model_combo.addItems(OLLAMA_MODEL_OPTIONS)
        current_ollama_model = str(getattr(self.app_settings, "ollama_model", "qwen3:8b") or "qwen3:8b")
        if current_ollama_model not in OLLAMA_MODEL_OPTIONS:
            ollama_model_combo.addItem(current_ollama_model)
        ollama_model_combo.setCurrentText(current_ollama_model)
        openai_model_combo = QComboBox()
        openai_model_combo.addItems(OPENAI_MODEL_OPTIONS)
        current_openai_model = str(getattr(self.app_settings, "openai_model", "gpt-4.1-mini") or "gpt-4.1-mini")
        if current_openai_model not in OPENAI_MODEL_OPTIONS:
            openai_model_combo.addItem(current_openai_model)
        openai_model_combo.setCurrentText(current_openai_model)
        timeout_spin = QSpinBox()
        timeout_spin.setRange(30, 600)
        timeout_spin.setSingleStep(10)
        timeout_spin.setSuffix(" seconds")
        timeout_spin.setValue(int(getattr(self.app_settings, "timeout_seconds", 120) or 120))
        for widget in (provider_combo, generation_mode_combo, ollama_url_edit, ollama_model_combo, openai_model_combo, timeout_spin):
            self._prepare_form_control(widget, min_width=340)
        self._add_labeled_field(ai_grid, 0, 0, "AI provider", provider_combo)
        self._add_labeled_field(ai_grid, 0, 1, "Generation mode", generation_mode_combo)
        self._add_labeled_field(ai_grid, 1, 0, "Ollama base URL", ollama_url_edit)
        self._add_labeled_field(ai_grid, 1, 1, "Ollama model", ollama_model_combo)
        self._add_labeled_field(ai_grid, 2, 0, "OpenAI model", openai_model_combo)
        self._add_labeled_field(ai_grid, 2, 1, "AI timeout", timeout_spin)
        ai_card.layout.addLayout(ai_grid)
        ai_actions = QHBoxLayout()
        ai_actions.setSpacing(12)
        check_ollama_button = QPushButton("Check Ollama Setup")
        check_ollama_button.clicked.connect(lambda: self._check_ollama_dialog_values(base_url_edit=ollama_url_edit, model_combo=ollama_model_combo))
        ollama_help_button = QPushButton("Ollama Help")
        ollama_help_button.clicked.connect(self._show_ollama_setup_help)
        ai_actions.addWidget(check_ollama_button)
        ai_actions.addWidget(ollama_help_button)
        ai_actions.addStretch(1)
        ai_card.layout.addLayout(ai_actions)
        content_layout.addWidget(ai_card)

        doc_card = Card("Document defaults", "Default generation and PDF settings.")
        doc_grid = QGridLayout()
        doc_grid.setHorizontalSpacing(18)
        doc_grid.setVerticalSpacing(14)
        doc_grid.setColumnStretch(0, 1)
        doc_grid.setColumnStretch(1, 1)
        template_combo = QComboBox()
        template_combo.addItems(get_template_names())
        template_combo.setCurrentText(getattr(self.app_settings, "template_name", "ATS Friendly"))
        pdf_template_combo = QComboBox()
        pdf_template_combo.addItems(get_pdf_template_names())
        pdf_template_combo.setCurrentText(getattr(self.app_settings, "pdf_template", "ATS Friendly"))
        page_size_combo = QComboBox()
        page_size_combo.addItems(["A4", "Letter"])
        page_size_combo.setCurrentText(getattr(self.app_settings, "pdf_page_size", "A4"))
        language_combo = QComboBox()
        language_combo.addItems(OUTPUT_LANGUAGE_OPTIONS)
        language_combo.setCurrentText(getattr(self.app_settings, "output_language", "English"))
        for widget in (template_combo, pdf_template_combo, page_size_combo, language_combo):
            self._prepare_form_control(widget, min_width=340)
        self._add_labeled_field(doc_grid, 0, 0, "Generation template", template_combo)
        self._add_labeled_field(doc_grid, 0, 1, "Output language", language_combo)
        self._add_labeled_field(doc_grid, 1, 0, "PDF template", pdf_template_combo)
        self._add_labeled_field(doc_grid, 1, 1, "PDF page size", page_size_combo)
        doc_card.layout.addLayout(doc_grid)
        content_layout.addWidget(doc_card)

        folder_card = Card("Default folders", "Where workspaces and application packages are stored by default.")
        folder_grid = QGridLayout()
        folder_grid.setHorizontalSpacing(12)
        folder_grid.setVerticalSpacing(14)
        workspace_dir_edit = QLineEdit(getattr(self.app_settings, "last_workspace_dir", "") or str(applications_dir()))
        export_dir_edit = QLineEdit(getattr(self.app_settings, "last_export_dir", "") or str(exports_dir()))
        self._prepare_form_control(workspace_dir_edit, min_width=520)
        self._prepare_form_control(export_dir_edit, min_width=520)
        self._add_labeled_field(folder_grid, 0, 0, "Workspace folder", workspace_dir_edit)
        self._add_labeled_field(folder_grid, 1, 0, "Export folder", export_dir_edit)
        folder_card.layout.addLayout(folder_grid)
        content_layout.addWidget(folder_card)

        appearance_card = Card("Appearance", "Select a theme for the Qt interface.")
        theme_combo = QComboBox()
        theme_combo.addItems(THEME_OPTIONS)
        theme_combo.setCurrentText(self._normalized_theme(getattr(self.app_settings, "ui_theme", "Dark blue")))
        self._prepare_form_control(theme_combo, min_width=260)
        appearance_row = QHBoxLayout()
        appearance_row.setSpacing(12)
        appearance_row.addWidget(theme_combo)
        preview_button = QPushButton("Preview Theme")
        preview_button.clicked.connect(lambda: self._apply_theme_styles(self._normalized_theme(theme_combo.currentText())))
        appearance_row.addWidget(preview_button)
        appearance_row.addStretch(1)
        appearance_card.layout.addLayout(appearance_row)
        content_layout.addWidget(appearance_card)

        status_label = QLabel("Settings loaded. Click Save Settings to make changes permanent.")
        status_label.setObjectName("CardText")
        status_label.setWordWrap(True)
        content_layout.addWidget(status_label)
        content_layout.addStretch(1)
        scroll.setWidget(content)
        root.addWidget(scroll, 1)

        def save_dialog_settings() -> None:
            self.app_settings.ai_provider = provider_combo.currentText()
            self.app_settings.generation_mode = generation_mode_combo.currentText()
            self.app_settings.ollama_base_url = ollama_url_edit.text().strip() or "http://localhost:11434"
            self.app_settings.ollama_model = ollama_model_combo.currentText().strip() or "qwen3:8b"
            self.app_settings.openai_model = openai_model_combo.currentText().strip() or "gpt-4.1-mini"
            self.app_settings.timeout_seconds = int(timeout_spin.value())
            self.app_settings.template_name = template_combo.currentText()
            self.app_settings.output_language = language_combo.currentText()
            self.app_settings.pdf_template = pdf_template_combo.currentText()
            self.app_settings.pdf_page_size = page_size_combo.currentText()
            self.app_settings.last_workspace_dir = workspace_dir_edit.text().strip()
            self.app_settings.last_export_dir = export_dir_edit.text().strip()
            self.app_settings.ui_theme = self._normalized_theme(theme_combo.currentText())
            self._refresh_settings_page_controls()
            self._apply_settings_to_existing_controls()
            try:
                save_app_settings(self.app_settings)
            except Exception as exc:  # noqa: BLE001
                status_label.setText(f"Could not save settings: {exc}")
                QMessageBox.critical(self, "Settings", f"Could not save settings: {exc}")
                return
            status_label.setText("Settings saved. Current workflow controls were updated.")
            if hasattr(self, "settings_status_label"):
                self.settings_status_label.setText("Settings saved from the top-menu settings window.")

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        save_button = QPushButton("Save Settings")
        save_button.setObjectName("PrimaryButton")
        save_button.clicked.connect(save_dialog_settings)
        close_button = QPushButton("Close")
        close_button.clicked.connect(dialog.accept)
        button_row.addWidget(save_button)
        button_row.addWidget(close_button)
        root.addLayout(button_row)
        dialog.exec()

    def _show_workflow_help(self) -> None:
        QMessageBox.information(
            self,
            "Workflow Guide",
            "Recommended workflow:\n\n"
            "1. Workspace: create or load an application workspace.\n"
            "2. Profile: load or enter candidate profile data.\n"
            "3. Evidence: add strong proof blocks.\n"
            "4. Job: structure the target job details.\n"
            "5. Generate: analyze job fit, then generate CV and covering letter.\n"
            "6. Review: run quality checks, AI review, and improvement.\n"
            "7. Export: export PDFs or a full application package.\n\n"
            "Use the sidebar for page navigation. Use File for workspace/profile/export actions."
        )

    def _show_options_help(self) -> None:
        QMessageBox.information(
            self,
            "Options Help",
            "File menu:\n"
            "- Workspace actions create, load, and save complete application sessions.\n"
            "- Profile actions import/export reusable candidate data.\n"
            "- Export Application Package creates the final application folder.\n\n"
            "Settings menu:\n"
            "- Open Settings opens a standalone settings window.\n"
            "- UI Theme changes the interface quickly.\n"
            "- Output language controls whether generated documents are written in English or German.\n"
            "- Save App Settings writes current settings to data/settings.json.\n"
            "- Restore App Settings resets defaults.\n\n"
            "Help menu:\n"
            "- Workflow Guide explains the intended application process.\n"
            "- Options Help explains menu actions."
        )

    def _build_shell(self) -> None:
        shell = QWidget()
        shell.setObjectName("AppShell")
        root = QHBoxLayout(shell)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(260)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(24, 28, 24, 24)
        sidebar_layout.setSpacing(12)

        brand_row = QHBoxLayout()
        brand_row.setContentsMargins(0, 0, 0, 0)
        brand_row.setSpacing(12)
        brand_row.addWidget(self._logo_label(42))
        brand_text = QVBoxLayout()
        brand_text.setContentsMargins(0, 0, 0, 0)
        brand_text.setSpacing(2)
        brand = QLabel("ResuBuilder")
        brand.setObjectName("BrandTitle")
        subtitle = QLabel("AI application builder")
        subtitle.setObjectName("BrandSubtitle")
        brand_text.addWidget(brand)
        brand_text.addWidget(subtitle)
        brand_row.addLayout(brand_text, 1)
        sidebar_layout.addLayout(brand_row)
        sidebar_layout.addSpacing(20)

        for page_name in ["Welcome", "Workspace", "Profile", "Evidence", "Job", "Generate", "Review", "Export"]:
            button = QPushButton(page_name)
            button.setObjectName("NavButton")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda checked=False, name=page_name: self.show_page(name))
            self.page_buttons[page_name] = button
            sidebar_layout.addWidget(button)

        sidebar_layout.addStretch(1)

        self.stack = QStackedWidget()
        self.stack.setObjectName("MainStack")
        self.stack.setContentsMargins(0, 0, 0, 0)

        self.pages["Welcome"] = self._build_welcome_page()
        self.pages["Workspace"] = self._build_workspace_page()
        self.pages["Profile"] = self._build_profile_page()
        self.pages["Evidence"] = self._build_evidence_page()
        self.pages["Job"] = self._build_job_page()
        self.pages["Generate"] = self._build_generate_page()
        self.pages["Review"] = self._build_review_page()
        self.pages["Export"] = self._build_export_page()

        for page in self.pages.values():
            self.stack.addWidget(page)

        root.addWidget(sidebar)
        root.addWidget(self.stack, 1)
        self.setCentralWidget(shell)

    def _page_container(self, title: str, subtitle: str) -> tuple[QWidget, QVBoxLayout]:
        page = QWidget()
        page.setObjectName("Page")
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(34, 30, 34, 30)
        page_layout.setSpacing(20)

        title_label = QLabel(title)
        title_label.setObjectName("PageTitle")
        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("PageSubtitle")
        subtitle_label.setWordWrap(True)
        page_layout.addWidget(title_label)
        page_layout.addWidget(subtitle_label)
        return page, page_layout

    def _build_welcome_page(self) -> QWidget:
        page, layout = self._page_container(
            "Welcome to ResuBuilder",
            "A modern desktop app for creating tailored CVs and covering letters with local or cloud AI.",
        )

        hero = QFrame()
        hero.setObjectName("HeroCard")
        self._add_frame_shadow(hero)
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(28, 28, 28, 28)
        hero_layout.setSpacing(18)

        hero_header = QHBoxLayout()
        hero_header.setSpacing(22)
        hero_header.setAlignment(Qt.AlignmentFlag.AlignTop)

        logo = self._logo_label(78)
        logo.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        hero_copy = QVBoxLayout()
        hero_copy.setSpacing(10)
        hero_title = QLabel("Build stronger applications without losing truth control.")
        hero_title.setObjectName("PageTitle")
        hero_title.setWordWrap(True)
        hero_text = QLabel(
            "ResuBuilder helps you structure your profile, match it to a role, generate tailored documents, review quality, and export a complete application package."
        )
        hero_text.setObjectName("PageSubtitle")
        hero_text.setWordWrap(True)
        hero_copy.addWidget(hero_title)
        hero_copy.addWidget(hero_text)
        hero_copy.addStretch(1)

        hero_header.addWidget(logo, 0, Qt.AlignmentFlag.AlignTop)
        hero_header.addLayout(hero_copy, 1)

        start_button = QPushButton("Start with Profile")
        start_button.setObjectName("PrimaryButton")
        start_button.setCursor(Qt.CursorShape.PointingHandCursor)
        start_button.clicked.connect(lambda: self.show_page("Profile"))

        hero_layout.addLayout(hero_header)
        hero_layout.addWidget(start_button, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(hero)

        card_row = QGridLayout()
        card_row.setSpacing(18)
        card_row.addWidget(Card("1. Profile", "Validate contact information and capture the candidate story."), 0, 0)
        card_row.addWidget(Card("2. Evidence", "Structure projects, tools, methods, and outcomes before generation."), 0, 1)
        card_row.addWidget(Card("3. Job", "Break the job post into company, role, responsibilities, and requirements."), 0, 2)
        card_row.addWidget(Card("4. Generate", "Use Ollama or OpenAI through the existing AI service layer."), 1, 0)
        layout.addLayout(card_row)

        setup_card = Card(
            "Local AI setup",
            "New computer? Check that Ollama is running and that the selected model is installed before generating documents.",
        )
        setup_row = QHBoxLayout()
        setup_row.setSpacing(12)
        check_button = QPushButton("Check Ollama")
        check_button.setObjectName("PrimaryButton")
        check_button.clicked.connect(lambda: self._check_ollama_ready(show_success=True))
        help_button = QPushButton("Show Setup Help")
        help_button.clicked.connect(self._show_ollama_setup_help)
        download_button = QPushButton("Open Ollama Download")
        download_button.clicked.connect(self._open_ollama_download)
        setup_row.addWidget(check_button)
        setup_row.addWidget(help_button)
        setup_row.addWidget(download_button)
        setup_row.addStretch(1)
        setup_card.layout.addLayout(setup_row)
        layout.addWidget(setup_card)
        layout.addStretch(1)
        return page

    def _build_workspace_page(self) -> QWidget:
        page, layout = self._page_container(
            "Workspace",
            "Save and reload a complete job application session so testing does not depend on retyping everything.",
        )

        card = Card("Application workspace", "Keep one workspace per application. Job company and role now live in the Job page, not Export.")
        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(14)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)

        self.workspace_name_edit = QLineEdit()
        self.workspace_name_edit.setPlaceholderText("Example: Audatic Deep Learning Engineer")
        self.workspace_path_edit = QLineEdit()
        self.workspace_path_edit.setReadOnly(True)
        self.workspace_path_edit.setPlaceholderText("No workspace file saved yet")

        for widget in (
            self.workspace_name_edit,
            self.workspace_path_edit,
        ):
            self._prepare_form_control(widget, min_width=420)

        self._add_labeled_field(grid, 0, 0, "Application name", self.workspace_name_edit)
        self._add_labeled_field(grid, 0, 1, "Workspace file", self.workspace_path_edit)
        card.layout.addLayout(grid)

        actions = QHBoxLayout()
        actions.setSpacing(12)
        new_button = QPushButton("New Workspace")
        new_button.clicked.connect(self._new_workspace)
        save_button = QPushButton("Save Workspace")
        save_button.setObjectName("PrimaryButton")
        save_button.clicked.connect(self._save_workspace)
        save_as_button = QPushButton("Save As")
        save_as_button.clicked.connect(self._save_workspace_as)
        load_button = QPushButton("Load Workspace")
        load_button.clicked.connect(self._load_workspace)
        continue_button = QPushButton("Continue to Profile")
        continue_button.clicked.connect(lambda: self.show_page("Profile"))
        for button in (new_button, save_button, save_as_button, load_button, continue_button):
            button.setMinimumHeight(46)
            actions.addWidget(button)
        actions.addStretch(1)
        card.layout.addLayout(actions)
        layout.addWidget(card)

        summary_card = QFrame()
        summary_card.setObjectName("OutputCard")
        summary_layout = QVBoxLayout(summary_card)
        summary_layout.setContentsMargins(22, 20, 22, 20)
        summary_layout.setSpacing(12)
        title = QLabel("Workspace status")
        title.setObjectName("CardTitle")
        self.workspace_status_edit = QPlainTextEdit()
        self.workspace_status_edit.setReadOnly(True)
        self.workspace_status_edit.setMinimumHeight(260)
        self.workspace_status_edit.setPlainText(
            "No workspace loaded. Create or load an application workspace before long testing sessions."
        )
        summary_layout.addWidget(title)
        summary_layout.addWidget(self.workspace_status_edit, 1)
        layout.addWidget(summary_card, 1)
        return page

    def _build_profile_page(self) -> QWidget:
        page, layout = self._page_container(
            "Profile",
            "Collect candidate data. This first Qt pass validates phone and email before generation.",
        )

        scroll = QScrollArea()
        scroll.setObjectName("PageScrollArea")
        scroll.setWidgetResizable(True)
        self._disable_horizontal_scroll(scroll)
        content = QWidget()
        content.setObjectName("ScrollContent")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(18)

        contact = Card("Contact details", "Email must be valid. Telephone accepts numbers only in this prototype.")
        grid = QGridLayout()
        grid.setSpacing(12)
        self.name_edit = QLineEdit()
        self.email_edit = QLineEdit()
        self.phone_edit = QLineEdit()
        self.location_edit = QLineEdit()
        self.phone_edit.setValidator(QRegularExpressionValidator(QRegularExpression(r"^\d{0,24}$")))
        self._add_labeled_field(grid, 0, 0, "Name", self.name_edit)
        self._add_labeled_field(grid, 0, 1, "Email", self.email_edit)
        self._add_labeled_field(grid, 1, 0, "Telephone", self.phone_edit)
        self._add_labeled_field(grid, 1, 1, "Location", self.location_edit)
        contact.layout.addLayout(grid)
        content_layout.addWidget(contact)

        identity = Card("Professional identity", "Keep this concrete. The AI performs better with specific tools, domains, and evidence.")
        self.title_edit = QLineEdit()
        self.summary_edit = QTextEdit()
        self.summary_edit.setMinimumHeight(120)
        identity_grid = QGridLayout()
        identity_grid.setSpacing(12)
        self._add_labeled_field(identity_grid, 0, 0, "Target/current title", self.title_edit)
        identity.layout.addLayout(identity_grid)
        identity.layout.addWidget(QLabel("Professional summary"))
        identity.layout.addWidget(self.summary_edit)
        content_layout.addWidget(identity)

        background = Card(
            "Education, languages, and links",
            "Add reusable profile facts once so CVs and covering letters do not miss basic sections.",
        )
        self.education_edit = QTextEdit()
        self.education_edit.setMinimumHeight(110)
        self.education_edit.setPlaceholderText(
            "Example:\nM.Sc. Neural Engineering, HTW Saar, 2022-2025\nB.Sc. Biomedical Engineering, HTW Saar, 2018-2022"
        )
        self.languages_edit = QTextEdit()
        self.languages_edit.setMinimumHeight(80)
        self.languages_edit.setPlaceholderText("Example: English - Professional, German - B2, Arabic - Native")
        self.links_edit = QTextEdit()
        self.links_edit.setMinimumHeight(80)
        self.links_edit.setPlaceholderText(
            "Example:\nLinkedIn: https://www.linkedin.com/in/your-name\nGitHub: https://github.com/your-name\nPortfolio: https://your-site.com"
        )
        background.layout.addWidget(QLabel("Education"))
        background.layout.addWidget(self.education_edit)
        background.layout.addWidget(QLabel("Languages"))
        background.layout.addWidget(self.languages_edit)
        background.layout.addWidget(QLabel("Links"))
        background.layout.addWidget(self.links_edit)
        content_layout.addWidget(background)

        evidence = Card("Evidence snapshot", "Use this for quick notes. Use the Evidence page for stronger structured proof.")
        self.skills_edit = QTextEdit()
        self.skills_edit.setMinimumHeight(90)
        self.projects_edit = QTextEdit()
        self.projects_edit.setMinimumHeight(110)
        self.professions_edit = QTextEdit()
        self.professions_edit.setMinimumHeight(110)
        evidence.layout.addWidget(QLabel("Skills"))
        evidence.layout.addWidget(self.skills_edit)
        evidence.layout.addWidget(QLabel("Projects"))
        evidence.layout.addWidget(self.projects_edit)
        evidence.layout.addWidget(QLabel("Professional experience"))
        evidence.layout.addWidget(self.professions_edit)
        content_layout.addWidget(evidence)

        action_row = QHBoxLayout()
        validate_button = QPushButton("Validate Profile")
        validate_button.setObjectName("PrimaryButton")
        validate_button.clicked.connect(self._validate_profile_with_message)

        load_profile_button = QPushButton("Load Profile...")
        load_profile_button.clicked.connect(self._load_profile)

        save_profile_button = QPushButton("Save Profile")
        save_profile_button.clicked.connect(self._save_current_profile)

        save_profile_as_button = QPushButton("Save Profile As...")
        save_profile_as_button.clicked.connect(self._save_profile_as)

        continue_button = QPushButton("Continue to Evidence")
        continue_button.clicked.connect(lambda: self.show_page("Evidence"))

        action_row.addWidget(validate_button)
        action_row.addWidget(load_profile_button)
        action_row.addWidget(save_profile_button)
        action_row.addWidget(save_profile_as_button)
        action_row.addWidget(continue_button)
        action_row.addStretch(1)
        content_layout.addLayout(action_row)

        scroll.setWidget(content)
        layout.addWidget(scroll, 1)
        return page

    def _build_evidence_page(self) -> QWidget:
        page, layout = self._page_container(
            "Evidence",
            "Structure proof before generation. The AI performs better when projects are broken into tools, actions, outcomes, and job signals.",
        )

        scroll = QScrollArea()
        scroll.setObjectName("PageScrollArea")
        scroll.setWidgetResizable(True)
        self._disable_horizontal_scroll(scroll)

        content = QWidget()
        content.setObjectName("ScrollContent")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 14, 0)
        content_layout.setSpacing(20)

        builder_card = Card(
            "Structured evidence builder",
            "Add one block per project, role achievement, study, or technical proof. Do not invent unsupported metrics or technologies.",
        )
        builder_card.setMinimumHeight(520)

        builder_grid = QGridLayout()
        builder_grid.setHorizontalSpacing(20)
        builder_grid.setVerticalSpacing(14)
        builder_grid.setColumnStretch(0, 1)
        builder_grid.setColumnStretch(1, 2)

        self.evidence_list = QListWidget()
        self.evidence_list.setMinimumHeight(360)
        self.evidence_list.currentRowChanged.connect(self._load_selected_evidence)
        builder_grid.addWidget(self.evidence_list, 0, 0, 8, 1)

        self.evidence_type_combo = QComboBox()
        self.evidence_type_combo.addItems(["Project", "Work achievement", "Study", "Certification", "Other"])
        self.evidence_title_edit = QLineEdit()
        self.evidence_title_edit.setPlaceholderText("Example: Face-Aware FlowMag for Micro-Expression Spotting")
        self.evidence_context_edit = QTextEdit()
        self.evidence_context_edit.setMinimumHeight(90)
        self.evidence_context_edit.setPlaceholderText("What was the situation or problem?")
        self.evidence_tools_edit = QLineEdit()
        self.evidence_tools_edit.setPlaceholderText("Python, PyTorch, optical flow, CASME II, LBP-TOP, SVM")
        self.evidence_methods_edit = QTextEdit()
        self.evidence_methods_edit.setMinimumHeight(100)
        self.evidence_methods_edit.setPlaceholderText("What did you actually do?")
        self.evidence_outcome_edit = QTextEdit()
        self.evidence_outcome_edit.setMinimumHeight(90)
        self.evidence_outcome_edit.setPlaceholderText("What did it enable, improve, validate, or prove?")
        self.evidence_metrics_edit = QLineEdit()
        self.evidence_metrics_edit.setPlaceholderText("Repository, report, benchmark, validation result, measurable metric if truthful")
        self.evidence_signals_edit = QLineEdit()
        self.evidence_signals_edit.setPlaceholderText("computer vision, deep learning, model training, algorithms, validation")

        for widget in (
            self.evidence_type_combo,
            self.evidence_title_edit,
            self.evidence_context_edit,
            self.evidence_tools_edit,
            self.evidence_methods_edit,
            self.evidence_outcome_edit,
            self.evidence_metrics_edit,
            self.evidence_signals_edit,
        ):
            self._prepare_form_control(widget, min_width=560)

        self._add_labeled_field(builder_grid, 0, 1, "Evidence type", self.evidence_type_combo)
        self._add_labeled_field(builder_grid, 1, 1, "Title", self.evidence_title_edit)
        self._add_labeled_field(builder_grid, 2, 1, "Context / situation", self.evidence_context_edit)
        self._add_labeled_field(builder_grid, 3, 1, "Tools / technologies", self.evidence_tools_edit)
        self._add_labeled_field(builder_grid, 4, 1, "Methods / actions", self.evidence_methods_edit)
        self._add_labeled_field(builder_grid, 5, 1, "Outcome / purpose", self.evidence_outcome_edit)
        self._add_labeled_field(builder_grid, 6, 1, "Metrics / proof", self.evidence_metrics_edit)
        self._add_labeled_field(builder_grid, 7, 1, "Relevant job signals", self.evidence_signals_edit)
        builder_card.layout.addLayout(builder_grid)

        actions = QHBoxLayout()
        actions.setSpacing(12)
        add_button = QPushButton("Add Evidence")
        add_button.setObjectName("PrimaryButton")
        add_button.clicked.connect(self._add_evidence_entry)
        update_button = QPushButton("Update Selected")
        update_button.clicked.connect(self._update_selected_evidence)
        delete_button = QPushButton("Delete Selected")
        delete_button.clicked.connect(self._delete_selected_evidence)
        clear_button = QPushButton("Clear Form")
        clear_button.clicked.connect(self._clear_evidence_form)
        example_button = QPushButton("Load Example")
        example_button.clicked.connect(self._load_evidence_example)
        continue_button = QPushButton("Continue to Generate")
        continue_button.clicked.connect(lambda: self.show_page("Generate"))
        for button in (add_button, update_button, delete_button, clear_button, example_button, continue_button):
            button.setMinimumHeight(46)
            actions.addWidget(button)
        actions.addStretch(1)
        builder_card.layout.addLayout(actions)
        content_layout.addWidget(builder_card)

        preview_card = QFrame()
        preview_card.setObjectName("OutputCard")
        preview_layout = QVBoxLayout(preview_card)
        preview_layout.setContentsMargins(22, 20, 22, 20)
        preview_layout.setSpacing(12)
        preview_title = QLabel("Evidence prompt preview")
        preview_title.setObjectName("CardTitle")
        self.evidence_preview_edit = QPlainTextEdit()
        self.evidence_preview_edit.setReadOnly(True)
        self.evidence_preview_edit.setMinimumHeight(260)
        self.evidence_preview_edit.setPlainText("No structured evidence yet. Add evidence blocks before generation.")
        preview_layout.addWidget(preview_title)
        preview_layout.addWidget(self.evidence_preview_edit, 1)
        content_layout.addWidget(preview_card)
        content_layout.addStretch(1)

        scroll.setWidget(content)
        layout.addWidget(scroll, 1)
        return page

    def _build_job_page(self) -> QWidget:
        page, layout = self._page_container(
            "Job",
            "Break the target job into structured sections. This gives the AI cleaner input than one pasted wall of text.",
        )

        scroll = QScrollArea()
        scroll.setObjectName("PageScrollArea")
        scroll.setWidgetResizable(True)
        self._disable_horizontal_scroll(scroll)

        content = QWidget()
        content.setObjectName("ScrollContent")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 14, 0)
        content_layout.setSpacing(20)

        identity_card = Card("Job identity", "Use the exact company and role names from the job post. These names are also used for workspace metadata and exported file names.")
        identity_grid = QGridLayout()
        identity_grid.setHorizontalSpacing(18)
        identity_grid.setVerticalSpacing(14)
        identity_grid.setColumnStretch(0, 1)
        identity_grid.setColumnStretch(1, 1)
        self.job_company_edit = QLineEdit()
        self.job_company_edit.setPlaceholderText("Example: Audatic")
        self.job_title_edit = QLineEdit()
        self.job_title_edit.setPlaceholderText("Example: Deep Learning Engineer")
        self._prepare_form_control(self.job_company_edit, min_width=420)
        self._prepare_form_control(self.job_title_edit, min_width=420)
        self._add_labeled_field(identity_grid, 0, 0, "Company", self.job_company_edit)
        self._add_labeled_field(identity_grid, 0, 1, "Job title", self.job_title_edit)
        identity_card.layout.addLayout(identity_grid)
        content_layout.addWidget(identity_card)

        description_card = Card("Full job description", "Paste the complete posting here. Keep the original text so the analyzer can see the full context.")
        self.job_description_edit = QTextEdit()
        self.job_description_edit.setMinimumHeight(260)
        self.job_description_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        description_card.layout.addWidget(self.job_description_edit)
        content_layout.addWidget(description_card)

        responsibilities_card = Card("Key responsibilities", "Paste the section usually called 'In this role you will', 'Responsibilities', or similar.")
        self.job_responsibilities_edit = QTextEdit()
        self.job_responsibilities_edit.setMinimumHeight(190)
        self.job_responsibilities_edit.setPlaceholderText("Example: Develop models, optimize inference, collaborate with engineers, validate results...")
        self.job_responsibilities_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        responsibilities_card.layout.addWidget(self.job_responsibilities_edit)
        content_layout.addWidget(responsibilities_card)

        requirements_card = Card("Required experience and skills", "Paste the must-have skills, technologies, experience level, education, domain knowledge, and preferred qualifications.")
        self.job_requirements_edit = QTextEdit()
        self.job_requirements_edit.setMinimumHeight(190)
        self.job_requirements_edit.setPlaceholderText("Example: Python, PyTorch, audio processing, embedded deployment, research experience...")
        self.job_requirements_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        requirements_card.layout.addWidget(self.job_requirements_edit)
        content_layout.addWidget(requirements_card)

        actions = QHBoxLayout()
        actions.setSpacing(12)
        analyze_button = QPushButton("Continue to Generate")
        analyze_button.setObjectName("PrimaryButton")
        analyze_button.setMinimumHeight(46)
        analyze_button.clicked.connect(lambda: self.show_page("Generate"))
        actions.addWidget(analyze_button)
        actions.addStretch(1)
        content_layout.addLayout(actions)
        content_layout.addStretch(1)

        scroll.setWidget(content)
        layout.addWidget(scroll, 1)
        return page

    def _build_generate_page(self) -> QWidget:
        page, layout = self._page_container(
            "Generate",
            "Analyze fit and generate a CV or covering letter using the structured Job page and candidate evidence.",
        )

        scroll = QScrollArea()
        scroll.setObjectName("PageScrollArea")
        scroll.setWidgetResizable(True)
        self._disable_horizontal_scroll(scroll)

        content = QWidget()
        content.setObjectName("ScrollContent")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 14, 0)
        content_layout.setSpacing(20)

        fit_card = Card(
            "Job fit analyzer",
            "Run this before generation. It tells the generator what to emphasize, what is weak, and what must not be claimed.",
        )
        fit_row = QHBoxLayout()
        fit_row.setSpacing(12)
        self.job_fit_button = QPushButton("Analyze Job Fit with Ollama")
        self.job_fit_button.setObjectName("PrimaryButton")
        self.job_fit_button.setMinimumHeight(48)
        self.job_fit_button.clicked.connect(self._start_job_fit_analysis)
        self.job_fit_status_label = QLabel("No job fit analysis yet. Generate without it only for quick tests.")
        self.job_fit_status_label.setObjectName("CardText")
        self.job_fit_status_label.setWordWrap(True)
        fit_row.addWidget(self.job_fit_button)
        fit_row.addWidget(self.job_fit_status_label, 1)
        fit_card.layout.addLayout(fit_row)
        self.job_fit_edit = QPlainTextEdit()
        self.job_fit_edit.setMinimumHeight(240)
        self.job_fit_edit.setPlaceholderText("Job fit analysis will appear here and will be included automatically in the next CV or covering-letter prompt.")
        fit_card.layout.addWidget(self.job_fit_edit, 1)
        content_layout.addWidget(fit_card)

        controls = Card("Generation controls", "Use the job fit strategy above when available. Keep prompts conservative while testing the new GUI.")
        controls.setMinimumHeight(176)
        controls_grid = QGridLayout()
        controls_grid.setHorizontalSpacing(18)
        controls_grid.setVerticalSpacing(14)
        controls_grid.setColumnStretch(0, 1)
        controls_grid.setColumnStretch(1, 1)
        controls_grid.setColumnStretch(2, 0)

        self.document_type_combo = QComboBox()
        self.document_type_combo.addItems(["CV", "Covering Letter"])
        self.template_combo = QComboBox()
        self.template_combo.addItems(get_template_names())
        if self.app_settings.template_name:
            index = self.template_combo.findText(self.app_settings.template_name)
            if index >= 0:
                self.template_combo.setCurrentIndex(index)

        self.output_language_combo = QComboBox()
        self.output_language_combo.addItems(OUTPUT_LANGUAGE_OPTIONS)
        self.output_language_combo.setCurrentText(getattr(self.app_settings, "output_language", "English"))
        self.output_language_combo.setToolTip("Choose the language used for generated CVs and covering letters. German output is translated by the selected AI provider.")

        self.generate_button = QPushButton("Generate Document")
        self.generate_button.setObjectName("PrimaryButton")
        self.generate_button.setMinimumHeight(48)
        self.generate_button.setMinimumWidth(180)
        self.generate_button.clicked.connect(self._start_generation)

        self._prepare_form_control(self.document_type_combo, min_width=240)
        self._prepare_form_control(self.template_combo, min_width=280)
        self._prepare_form_control(self.output_language_combo, min_width=240)
        self._add_labeled_field(controls_grid, 0, 0, "Document", self.document_type_combo)
        self._add_labeled_field(controls_grid, 0, 1, "Template", self.template_combo)
        self._add_labeled_field(controls_grid, 1, 0, "Output language", self.output_language_combo)
        controls_grid.addWidget(self.generate_button, 1, 2, alignment=Qt.AlignmentFlag.AlignBottom)
        controls.layout.addLayout(controls_grid)
        content_layout.addWidget(controls)

        output_card = QFrame()
        output_card.setObjectName("OutputCard")
        self._add_frame_shadow(output_card)
        output_card.setMinimumHeight(360)
        output_layout = QVBoxLayout(output_card)
        output_layout.setContentsMargins(22, 20, 22, 20)
        output_layout.setSpacing(12)
        output_title = QLabel("Generated output")
        output_title.setObjectName("CardTitle")
        self.status_label = QLabel("Ready.")
        self.status_label.setObjectName("CardText")
        self.output_edit = QPlainTextEdit()
        self.output_edit.setMinimumHeight(280)
        self.output_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        output_layout.addWidget(output_title)
        output_layout.addWidget(self.status_label)
        output_layout.addWidget(self.output_edit, 1)
        content_layout.addWidget(output_card)
        content_layout.addStretch(1)

        scroll.setWidget(content)
        layout.addWidget(scroll, 1)
        return page

    def _build_review_page(self) -> QWidget:
        page, layout = self._page_container(
            "Review",
            "Run the deterministic quality checker first, then use AI review and improvement only when the basic report exists.",
        )

        scroll = QScrollArea()
        scroll.setObjectName("PageScrollArea")
        scroll.setWidgetResizable(True)
        self._disable_horizontal_scroll(scroll)

        content = QWidget()
        content.setObjectName("ScrollContent")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 14, 0)
        content_layout.setSpacing(20)

        controls = Card(
            "Quality review workflow",
            "Use the rule-based checker for reliable basics. Then run AI review for strategic critique, or improve the selected document using the quality report.",
        )
        review_grid = QGridLayout()
        review_grid.setHorizontalSpacing(12)
        review_grid.setVerticalSpacing(12)
        review_grid.setColumnStretch(0, 0)
        review_grid.setColumnStretch(1, 1)
        review_grid.setColumnStretch(2, 1)
        review_grid.setColumnStretch(3, 1)

        self.review_document_combo = QComboBox()
        self.review_document_combo.addItems(["CV", "Covering Letter"])
        self.review_document_combo.currentTextChanged.connect(lambda _value: self._refresh_review_page_break_sections())
        self._prepare_form_control(self.review_document_combo, min_width=220)

        self.run_quality_button = QPushButton("Run Quality Check")
        self.run_quality_button.setObjectName("PrimaryButton")
        self.run_quality_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.run_quality_button.clicked.connect(self._run_quality_check)

        self.run_ai_review_button = QPushButton("Run AI Quality Review")
        self.run_ai_review_button.clicked.connect(self._start_ai_quality_review)

        self.improve_quality_button = QPushButton("Improve with Quality Fixes")
        self.improve_quality_button.setObjectName("PrimaryButton")
        self.improve_quality_button.clicked.connect(self._start_quality_improvement)

        show_button = QPushButton("Show Selected Document")
        show_button.clicked.connect(self._show_selected_review_document)

        for button in (self.run_quality_button, self.run_ai_review_button, self.improve_quality_button, show_button):
            button.setMinimumHeight(46)
            button.setMinimumWidth(190)

        review_grid.addWidget(QLabel("Document"), 0, 0)
        review_grid.addWidget(self.review_document_combo, 0, 1)
        review_grid.addWidget(self.run_quality_button, 0, 2)
        review_grid.addWidget(self.run_ai_review_button, 0, 3)
        review_grid.addWidget(self.improve_quality_button, 1, 2)
        review_grid.addWidget(show_button, 1, 3)
        controls.layout.addLayout(review_grid)
        content_layout.addWidget(controls)

        edit_card = Card(
            "AI edit instructions",
            "Optional. After generation, tell the AI exactly how to revise the selected CV or covering letter. Use this for focused edits such as reordering skills, emphasizing specific evidence, tightening tone, or removing weak sections.",
        )
        edit_card.layout.addWidget(QLabel("Instructions for selected document"))
        self.manual_edit_instructions_edit = QPlainTextEdit()
        self.manual_edit_instructions_edit.setMinimumHeight(130)
        self.manual_edit_instructions_edit.setPlaceholderText(
            "Examples:\n"
            "- Move Python and PyTorch to the start of the skills section.\n"
            "- Focus more on computer vision, model validation, and research engineering.\n"
            "- Make the covering letter more concise and less generic.\n"
            "- Remove unsupported claims and keep the tone direct."
        )
        edit_card.layout.addWidget(self.manual_edit_instructions_edit)
        edit_actions = QHBoxLayout()
        edit_actions.addStretch(1)
        self.apply_custom_edit_button = QPushButton("Apply AI Edit Instructions")
        self.apply_custom_edit_button.setObjectName("PrimaryButton")
        self.apply_custom_edit_button.setMinimumHeight(46)
        self.apply_custom_edit_button.setMinimumWidth(230)
        self.apply_custom_edit_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.apply_custom_edit_button.clicked.connect(self._start_custom_ai_edit)
        edit_actions.addWidget(self.apply_custom_edit_button)
        edit_card.layout.addLayout(edit_actions)
        content_layout.addWidget(edit_card)

        score_row = QGridLayout()
        score_row.setSpacing(18)
        self.review_score_label = QLabel("No quality check run yet")
        self.review_score_label.setObjectName("MetricNumber")
        self.review_status_label = QLabel("Generate a CV or covering letter first, then run the checker.")
        self.review_status_label.setObjectName("CardText")
        self.review_status_label.setWordWrap(True)
        score_card = Card("Latest score", "")
        score_card.layout.addWidget(self.review_score_label)
        score_card.layout.addWidget(self.review_status_label)
        tip_card = Card(
            "Correct order",
            "Quality Check -> AI Quality Review -> Improve with Quality Fixes -> Quality Check again. Do not export before verifying the final text.",
        )
        score_row.addWidget(score_card, 0, 0)
        score_row.addWidget(tip_card, 0, 1)
        content_layout.addLayout(score_row)

        report_card = QFrame()
        report_card.setObjectName("OutputCard")
        self._add_frame_shadow(report_card)
        report_layout = QVBoxLayout(report_card)
        report_layout.setContentsMargins(22, 20, 22, 20)
        report_layout.setSpacing(12)
        report_title = QLabel("Quality report")
        report_title.setObjectName("CardTitle")
        self.quality_report_edit = QPlainTextEdit()
        self.quality_report_edit.setMinimumHeight(300)
        self.quality_report_edit.setPlainText("No report yet.")
        report_layout.addWidget(report_title)
        report_layout.addWidget(self.quality_report_edit, 1)
        content_layout.addWidget(report_card)

        ai_card = QFrame()
        ai_card.setObjectName("OutputCard")
        ai_layout = QVBoxLayout(ai_card)
        ai_layout.setContentsMargins(22, 20, 22, 20)
        ai_layout.setSpacing(12)
        ai_title = QLabel("AI quality review")
        ai_title.setObjectName("CardTitle")
        self.ai_review_status_label = QLabel("No AI review yet.")
        self.ai_review_status_label.setObjectName("CardText")
        self.ai_quality_review_edit = QPlainTextEdit()
        self.ai_quality_review_edit.setMinimumHeight(300)
        self.ai_quality_review_edit.setPlainText("No AI review yet. Run the quality check first.")
        ai_layout.addWidget(ai_title)
        ai_layout.addWidget(self.ai_review_status_label)
        ai_layout.addWidget(self.ai_quality_review_edit, 1)
        content_layout.addWidget(ai_card)
        content_layout.addStretch(1)

        scroll.setWidget(content)
        layout.addWidget(scroll, 1)
        return page

    def _build_export_page(self) -> QWidget:
        page, layout = self._page_container(
            "Export",
            "Export the generated CV and covering letter as PDFs, or create a complete application package folder.",
        )

        scroll = QScrollArea()
        scroll.setObjectName("PageScrollArea")
        scroll.setWidgetResizable(True)
        self._disable_horizontal_scroll(scroll)

        content = QWidget()
        content.setObjectName("ScrollContent")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 14, 0)
        content_layout.setSpacing(20)

        settings_card = Card("Export settings", "Company and role are taken from the Job page so export settings stay focused on files and formatting.")
        settings_card.setMinimumHeight(240)
        settings_grid = QGridLayout()
        settings_grid.setHorizontalSpacing(20)
        settings_grid.setVerticalSpacing(18)
        settings_grid.setColumnStretch(0, 1)
        settings_grid.setColumnStretch(1, 1)

        self.export_document_combo = QComboBox()
        self.export_document_combo.addItems(["CV", "Covering Letter"])
        self.export_document_combo.currentTextChanged.connect(lambda _value: self._refresh_section_order_list())

        self.export_pdf_template_combo = QComboBox()
        self.export_pdf_template_combo.addItems(get_pdf_template_names())
        pdf_template_index = self.export_pdf_template_combo.findText(getattr(self.app_settings, "pdf_template", "ATS Friendly"))
        if pdf_template_index >= 0:
            self.export_pdf_template_combo.setCurrentIndex(pdf_template_index)

        self.export_page_size_combo = QComboBox()
        self.export_page_size_combo.addItems(["A4", "Letter"])
        page_size_index = self.export_page_size_combo.findText(getattr(self.app_settings, "pdf_page_size", "A4"))
        if page_size_index >= 0:
            self.export_page_size_combo.setCurrentIndex(page_size_index)

        for export_widget in (
            self.export_document_combo,
            self.export_pdf_template_combo,
            self.export_page_size_combo,
        ):
            self._prepare_form_control(export_widget, min_width=420)

        default_export_dir = getattr(self.app_settings, "last_export_dir", "") or str(exports_dir())
        self.export_dir_edit = QLineEdit(default_export_dir)
        self._prepare_form_control(self.export_dir_edit, min_width=420)
        browse_button = QPushButton("Browse")
        browse_button.setMinimumHeight(46)
        browse_button.setMinimumWidth(110)
        browse_button.clicked.connect(self._browse_export_dir)

        self._add_labeled_field(settings_grid, 0, 0, "Single-document export", self.export_document_combo)
        self._add_labeled_field(settings_grid, 0, 1, "PDF template", self.export_pdf_template_combo)
        self._add_labeled_field(settings_grid, 1, 0, "Page size", self.export_page_size_combo)

        export_dir_wrapper = QWidget()
        export_dir_wrapper.setMinimumHeight(82)
        export_dir_layout = QVBoxLayout(export_dir_wrapper)
        export_dir_layout.setContentsMargins(0, 0, 0, 0)
        export_dir_layout.setSpacing(8)
        export_dir_layout.addWidget(QLabel("Export folder"))
        export_dir_row = QHBoxLayout()
        export_dir_row.setContentsMargins(0, 0, 0, 0)
        export_dir_row.setSpacing(10)
        export_dir_row.addWidget(self.export_dir_edit, 1)
        export_dir_row.addWidget(browse_button)
        export_dir_layout.addLayout(export_dir_row)
        settings_grid.addWidget(export_dir_wrapper, 1, 1)

        settings_card.layout.addLayout(settings_grid)
        content_layout.addWidget(settings_card)

        layout_card = Card(
            "Template preview and section order",
            "Preview the selected document and reorder top-level sections before export. PDF export keeps project-style subsections together where possible.",
        )
        layout_card.setMinimumHeight(360)
        layout_grid = QGridLayout()
        layout_grid.setHorizontalSpacing(18)
        layout_grid.setVerticalSpacing(14)
        layout_grid.setColumnStretch(0, 2)
        layout_grid.setColumnStretch(1, 1)

        self.section_order_list = QListWidget()
        self.section_order_list.setMinimumHeight(220)
        layout_grid.addWidget(self.section_order_list, 0, 0, 4, 1)

        refresh_sections_button = QPushButton("Refresh Sections")
        refresh_sections_button.clicked.connect(self._refresh_section_order_list)
        move_up_button = QPushButton("Move Up")
        move_up_button.clicked.connect(lambda: self._move_section_order(-1))
        move_down_button = QPushButton("Move Down")
        move_down_button.clicked.connect(lambda: self._move_section_order(1))
        apply_order_button = QPushButton("Apply Order to Document")
        apply_order_button.setObjectName("PrimaryButton")
        apply_order_button.clicked.connect(self._apply_section_order_to_document)
        preview_button = QPushButton("Preview Ordered Document")
        preview_button.clicked.connect(self._preview_ordered_document)

        for button in (refresh_sections_button, move_up_button, move_down_button, apply_order_button, preview_button):
            button.setMinimumHeight(42)

        layout_grid.addWidget(refresh_sections_button, 0, 1)
        layout_grid.addWidget(move_up_button, 1, 1)
        layout_grid.addWidget(move_down_button, 2, 1)
        layout_grid.addWidget(apply_order_button, 3, 1)
        layout_grid.addWidget(preview_button, 4, 1)

        layout_tip = QLabel(
            "Tip: keep project entries under ### headings. The PDF exporter tries to keep each project block together so descriptions are less likely to split across pages."
        )
        layout_tip.setObjectName("CardText")
        layout_tip.setWordWrap(True)
        layout_grid.addWidget(layout_tip, 4, 0)

        layout_card.layout.addLayout(layout_grid)
        content_layout.addWidget(layout_card)
        self._refresh_section_order_list()

        page_break_card = Card(
            "Manual PDF page breaks",
            "Optional. Add a page split after a CV section so the next section starts on a new PDF page. Keep this with export layout controls, not content review.",
        )
        break_grid = QGridLayout()
        break_grid.setHorizontalSpacing(12)
        break_grid.setVerticalSpacing(12)
        break_grid.setColumnStretch(0, 1)
        break_grid.setColumnStretch(1, 0)
        break_grid.setColumnStretch(2, 0)
        break_grid.setColumnStretch(3, 0)

        self.page_break_section_combo = QComboBox()
        self._prepare_form_control(self.page_break_section_combo, min_width=420)

        self.refresh_page_break_sections_button = QPushButton("Refresh Sections")
        self.refresh_page_break_sections_button.clicked.connect(self._refresh_review_page_break_sections)
        self.insert_page_break_button = QPushButton("Add Page Split After Section")
        self.insert_page_break_button.setObjectName("PrimaryButton")
        self.insert_page_break_button.clicked.connect(self._insert_page_break_after_selected_section)
        self.remove_page_breaks_button = QPushButton("Remove Page Splits")
        self.remove_page_breaks_button.clicked.connect(self._remove_manual_page_breaks)

        for button in (self.refresh_page_break_sections_button, self.insert_page_break_button, self.remove_page_breaks_button):
            button.setMinimumHeight(44)
            button.setCursor(Qt.CursorShape.PointingHandCursor)

        break_grid.addWidget(QLabel("Split after CV section"), 0, 0)
        break_grid.addWidget(self.refresh_page_break_sections_button, 0, 1)
        break_grid.addWidget(self.insert_page_break_button, 0, 2)
        break_grid.addWidget(self.remove_page_breaks_button, 0, 3)
        break_grid.addWidget(self.page_break_section_combo, 1, 0, 1, 4)
        page_break_note = QLabel("Example: choose Education, then Add Page Split After Section. The next section starts on a new page during PDF export.")
        page_break_note.setObjectName("CardText")
        page_break_note.setWordWrap(True)
        page_break_card.layout.addLayout(break_grid)
        page_break_card.layout.addWidget(page_break_note)
        content_layout.addWidget(page_break_card)
        self._refresh_review_page_break_sections()

        actions_card = Card("Export actions", "Export one document for quick testing, or export the full application package when both documents are ready.")
        actions_card.setMinimumHeight(160)
        action_row = QHBoxLayout()
        action_row.setSpacing(12)
        self.export_pdf_button = QPushButton("Export Selected PDF")
        self.export_pdf_button.setObjectName("PrimaryButton")
        self.export_pdf_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.export_pdf_button.clicked.connect(self._export_selected_pdf)

        self.save_markdown_button = QPushButton("Save Selected Markdown")
        self.save_markdown_button.clicked.connect(self._save_selected_markdown)

        self.export_package_button = QPushButton("Export Application Package")
        self.export_package_button.setObjectName("PrimaryButton")
        self.export_package_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.export_package_button.clicked.connect(self._export_application_package)

        self.open_export_dir_button = QPushButton("Open Export Folder")
        self.open_export_dir_button.clicked.connect(self._open_export_dir)

        for button in (
            self.export_pdf_button,
            self.save_markdown_button,
            self.export_package_button,
            self.open_export_dir_button,
        ):
            button.setMinimumHeight(46)

        action_row.addWidget(self.export_pdf_button)
        action_row.addWidget(self.save_markdown_button)
        action_row.addWidget(self.export_package_button)
        action_row.addWidget(self.open_export_dir_button)
        action_row.addStretch(1)
        actions_card.layout.addLayout(action_row)
        content_layout.addWidget(actions_card)

        status_card = QFrame()
        status_card.setObjectName("OutputCard")
        status_card.setMinimumHeight(260)
        status_layout = QVBoxLayout(status_card)
        status_layout.setContentsMargins(22, 20, 22, 20)
        status_layout.setSpacing(12)
        status_title = QLabel("Export status")
        status_title.setObjectName("CardTitle")
        self.export_status_edit = QPlainTextEdit()
        self.export_status_edit.setMinimumHeight(220)
        self.export_status_edit.setReadOnly(True)
        self.export_status_edit.setPlainText(
            "No export yet. Generate the CV and covering letter first, then export the package."
        )
        status_layout.addWidget(status_title)
        status_layout.addWidget(self.export_status_edit, 1)
        content_layout.addWidget(status_card)
        content_layout.addStretch(1)

        scroll.setWidget(content)
        layout.addWidget(scroll, 1)
        return page

    def _build_settings_page(self) -> QWidget:
        page, layout = self._page_container(
            "Settings",
            "Control AI provider, generation behavior, document defaults, folders, and UI theme directly in the Qt app.",
        )

        scroll = QScrollArea()
        scroll.setObjectName("PageScrollArea")
        scroll.setWidgetResizable(True)
        self._disable_horizontal_scroll(scroll)

        content = QWidget()
        content.setObjectName("ScrollContent")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 14, 0)
        content_layout.setSpacing(20)

        ai_card = Card("AI settings", "Choose the provider and model used by generation, job fit analysis, AI review, and quality-fix improvement.")
        ai_grid = QGridLayout()
        ai_grid.setHorizontalSpacing(18)
        ai_grid.setVerticalSpacing(14)
        ai_grid.setColumnStretch(0, 1)
        ai_grid.setColumnStretch(1, 1)

        self.settings_provider_combo = QComboBox()
        self.settings_provider_combo.addItems(["Ollama Local", "OpenAI"])
        self.settings_provider_combo.setCurrentText(getattr(self.app_settings, "ai_provider", "Ollama Local"))

        self.settings_generation_mode_combo = QComboBox()
        self.settings_generation_mode_combo.addItems(["Conservative", "Balanced", "Aggressive"])
        self.settings_generation_mode_combo.setCurrentText(getattr(self.app_settings, "generation_mode", "Balanced"))

        self.settings_ollama_url_edit = QLineEdit(getattr(self.app_settings, "ollama_base_url", "http://localhost:11434"))

        self.settings_ollama_model_combo = QComboBox()
        self.settings_ollama_model_combo.addItems(OLLAMA_MODEL_OPTIONS)
        current_ollama_model = str(getattr(self.app_settings, "ollama_model", "qwen3:8b") or "qwen3:8b")
        if current_ollama_model not in OLLAMA_MODEL_OPTIONS:
            self.settings_ollama_model_combo.addItem(current_ollama_model)
        self.settings_ollama_model_combo.setCurrentText(current_ollama_model)

        self.settings_openai_model_combo = QComboBox()
        self.settings_openai_model_combo.addItems(OPENAI_MODEL_OPTIONS)
        current_openai_model = str(getattr(self.app_settings, "openai_model", "gpt-4.1-mini") or "gpt-4.1-mini")
        if current_openai_model not in OPENAI_MODEL_OPTIONS:
            self.settings_openai_model_combo.addItem(current_openai_model)
        self.settings_openai_model_combo.setCurrentText(current_openai_model)

        self.settings_timeout_spin = QSpinBox()
        self.settings_timeout_spin.setRange(30, 600)
        self.settings_timeout_spin.setSingleStep(10)
        self.settings_timeout_spin.setSuffix(" seconds")
        self.settings_timeout_spin.setValue(int(getattr(self.app_settings, "timeout_seconds", 120) or 120))

        for widget in (
            self.settings_provider_combo,
            self.settings_generation_mode_combo,
            self.settings_ollama_url_edit,
            self.settings_ollama_model_combo,
            self.settings_openai_model_combo,
            self.settings_timeout_spin,
        ):
            self._prepare_form_control(widget, min_width=360)

        self._add_labeled_field(ai_grid, 0, 0, "AI provider", self.settings_provider_combo)
        self._add_labeled_field(ai_grid, 0, 1, "Generation mode", self.settings_generation_mode_combo)
        self._add_labeled_field(ai_grid, 1, 0, "Ollama base URL", self.settings_ollama_url_edit)
        self._add_labeled_field(ai_grid, 1, 1, "Ollama model", self.settings_ollama_model_combo)
        self._add_labeled_field(ai_grid, 2, 0, "OpenAI model", self.settings_openai_model_combo)
        self._add_labeled_field(ai_grid, 2, 1, "AI timeout", self.settings_timeout_spin)
        ai_card.layout.addLayout(ai_grid)
        ai_actions = QHBoxLayout()
        ai_actions.setSpacing(12)
        check_ollama_button = QPushButton("Check Ollama Setup")
        check_ollama_button.clicked.connect(lambda: self._check_ollama_from_settings(show_success=True))
        ollama_help_button = QPushButton("Ollama Help")
        ollama_help_button.clicked.connect(self._show_ollama_setup_help)
        ai_actions.addWidget(check_ollama_button)
        ai_actions.addWidget(ollama_help_button)
        ai_actions.addStretch(1)
        ai_card.layout.addLayout(ai_actions)
        content_layout.addWidget(ai_card)

        document_card = Card("Document defaults", "Set the default generation template and export format used by the Generate and Export pages.")
        document_grid = QGridLayout()
        document_grid.setHorizontalSpacing(18)
        document_grid.setVerticalSpacing(14)
        document_grid.setColumnStretch(0, 1)
        document_grid.setColumnStretch(1, 1)

        self.settings_template_combo = QComboBox()
        self.settings_template_combo.addItems(get_template_names())
        self.settings_template_combo.setCurrentText(getattr(self.app_settings, "template_name", "ATS Friendly"))

        self.settings_pdf_template_combo = QComboBox()
        self.settings_pdf_template_combo.addItems(get_pdf_template_names())
        self.settings_pdf_template_combo.setCurrentText(getattr(self.app_settings, "pdf_template", "ATS Friendly"))

        self.settings_page_size_combo = QComboBox()
        self.settings_page_size_combo.addItems(["A4", "Letter"])
        self.settings_page_size_combo.setCurrentText(getattr(self.app_settings, "pdf_page_size", "A4"))

        self.settings_output_language_combo = QComboBox()
        self.settings_output_language_combo.addItems(OUTPUT_LANGUAGE_OPTIONS)
        self.settings_output_language_combo.setCurrentText(getattr(self.app_settings, "output_language", "English"))

        for widget in (self.settings_template_combo, self.settings_output_language_combo, self.settings_pdf_template_combo, self.settings_page_size_combo):
            self._prepare_form_control(widget, min_width=360)

        self._add_labeled_field(document_grid, 0, 0, "Generation template", self.settings_template_combo)
        self._add_labeled_field(document_grid, 0, 1, "Output language", self.settings_output_language_combo)
        self._add_labeled_field(document_grid, 1, 0, "PDF template", self.settings_pdf_template_combo)
        self._add_labeled_field(document_grid, 1, 1, "PDF page size", self.settings_page_size_combo)
        document_card.layout.addLayout(document_grid)
        content_layout.addWidget(document_card)

        folders_card = Card("Default folders", "Remember where workspaces and exported application packages should be saved.")
        folders_grid = QGridLayout()
        folders_grid.setHorizontalSpacing(18)
        folders_grid.setVerticalSpacing(14)
        folders_grid.setColumnStretch(0, 1)

        self.settings_workspace_dir_edit = QLineEdit(getattr(self.app_settings, "last_workspace_dir", "") or str(applications_dir()))
        self.settings_export_dir_edit = QLineEdit(getattr(self.app_settings, "last_export_dir", "") or str(exports_dir()))
        self._prepare_form_control(self.settings_workspace_dir_edit, min_width=520)
        self._prepare_form_control(self.settings_export_dir_edit, min_width=520)

        workspace_browse = QPushButton("Browse")
        workspace_browse.setMinimumHeight(46)
        workspace_browse.clicked.connect(self._browse_settings_workspace_dir)
        export_browse = QPushButton("Browse")
        export_browse.setMinimumHeight(46)
        export_browse.clicked.connect(self._browse_settings_export_dir)

        workspace_row = QWidget()
        workspace_row_layout = QHBoxLayout(workspace_row)
        workspace_row_layout.setContentsMargins(0, 0, 0, 0)
        workspace_row_layout.setSpacing(10)
        workspace_row_layout.addWidget(self.settings_workspace_dir_edit, 1)
        workspace_row_layout.addWidget(workspace_browse)

        export_row = QWidget()
        export_row_layout = QHBoxLayout(export_row)
        export_row_layout.setContentsMargins(0, 0, 0, 0)
        export_row_layout.setSpacing(10)
        export_row_layout.addWidget(self.settings_export_dir_edit, 1)
        export_row_layout.addWidget(export_browse)

        self._add_labeled_field(folders_grid, 0, 0, "Workspace folder", workspace_row)
        self._add_labeled_field(folders_grid, 1, 0, "Export folder", export_row)
        folders_card.layout.addLayout(folders_grid)
        content_layout.addWidget(folders_card)

        appearance_card = Card("Appearance", "Switch the ResuBuilder interface theme.")
        appearance_row = QHBoxLayout()
        appearance_row.setSpacing(12)
        self.settings_theme_combo = QComboBox()
        self.settings_theme_combo.addItems(THEME_OPTIONS)
        self.settings_theme_combo.setCurrentText(self._normalized_theme(getattr(self.app_settings, "ui_theme", "Dark blue")))
        self._prepare_form_control(self.settings_theme_combo, min_width=260)
        preview_button = QPushButton("Preview Theme")
        preview_button.clicked.connect(self._preview_selected_theme)
        appearance_row.addWidget(self.settings_theme_combo)
        appearance_row.addWidget(preview_button)
        appearance_row.addStretch(1)
        appearance_card.layout.addLayout(appearance_row)
        content_layout.addWidget(appearance_card)

        action_card = Card("Actions", "Save settings after changing them. OpenAI API keys are still not saved here.")
        action_row = QHBoxLayout()
        action_row.setSpacing(12)
        save_button = QPushButton("Save Settings")
        save_button.setObjectName("PrimaryButton")
        save_button.clicked.connect(self._save_settings)
        reset_button = QPushButton("Reset to Defaults")
        reset_button.clicked.connect(self._reset_settings)
        action_row.addWidget(save_button)
        action_row.addWidget(reset_button)
        action_row.addStretch(1)
        action_card.layout.addLayout(action_row)
        self.settings_status_label = QLabel("Settings loaded from data/settings.json. Unsaved changes affect the form only until you save.")
        self.settings_status_label.setObjectName("CardText")
        self.settings_status_label.setWordWrap(True)
        action_card.layout.addWidget(self.settings_status_label)
        content_layout.addWidget(action_card)
        content_layout.addStretch(1)

        scroll.setWidget(content)
        layout.addWidget(scroll, 1)
        return page

    def _build_placeholder_page(self, title: str, message: str) -> QWidget:
        page, layout = self._page_container(title, message)
        card = Card("Not wired yet", "This page is intentionally a placeholder. Wire it only after Profile and Generate are stable.")
        layout.addWidget(card)
        layout.addStretch(1)
        return page

    def _prepare_form_control(self, widget: QWidget, min_width: int = 260) -> None:
        if isinstance(widget, (QLineEdit, QComboBox, QSpinBox)):
            widget.setMinimumHeight(46)
            widget.setMinimumWidth(min_width)
            widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        elif isinstance(widget, (QTextEdit, QPlainTextEdit)):
            self._install_rounded_scrollbars(widget)
            widget.setMinimumWidth(min_width)
            widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def _add_labeled_field(self, grid: QGridLayout, row: int, column: int, label: str, widget: QWidget) -> None:
        self._prepare_form_control(widget)
        wrapper = QWidget()
        wrapper.setMinimumHeight(82)
        wrapper_layout = QVBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(0, 0, 0, 0)
        wrapper_layout.setSpacing(8)
        wrapper_layout.addWidget(QLabel(label))
        wrapper_layout.addWidget(widget)
        grid.addWidget(wrapper, row, column)

    def show_page(self, page_name: str) -> None:
        page = self.pages.get(page_name)
        if page is None:
            return
        self.stack.setCurrentWidget(page)
        for name, button in self.page_buttons.items():
            button.setObjectName("NavButtonActive" if name == page_name else "NavButton")
            button.style().unpolish(button)
            button.style().polish(button)
            button.update()

    def _job_company(self) -> str:
        return self.job_company_edit.text().strip() if hasattr(self, "job_company_edit") else ""

    def _job_title(self) -> str:
        return self.job_title_edit.text().strip() if hasattr(self, "job_title_edit") else ""

    def _job_details_dict(self) -> dict[str, str]:
        return {
            "company": self._job_company(),
            "job_title": self._job_title(),
            "full_description": self.job_description_edit.toPlainText().strip() if hasattr(self, "job_description_edit") else "",
            "responsibilities": self.job_responsibilities_edit.toPlainText().strip() if hasattr(self, "job_responsibilities_edit") else "",
            "requirements": self.job_requirements_edit.toPlainText().strip() if hasattr(self, "job_requirements_edit") else "",
        }

    def _selected_output_language(self) -> str:
        if hasattr(self, "output_language_combo"):
            value = self.output_language_combo.currentText().strip()
        else:
            value = getattr(self.app_settings, "output_language", "English")
        return value if value in OUTPUT_LANGUAGE_OPTIONS else "English"

    def _language_instruction_block(self) -> str:
        language = self._selected_output_language()
        if language == "German":
            return (
                "Output language requirement:\n"
                "Write the final CV or covering letter in German. Translate all necessary candidate, job, and evidence information into natural professional German. "
                "Keep names, email addresses, phone numbers, URLs, company names, product names, programming languages, libraries, frameworks, model names, dates, degree names, and exact numbers unchanged unless a German wording is clearly standard. "
                "Use formal professional German suitable for a job application. Do not explain that a translation was performed. Return only the final document text."
            )
        return "Output language requirement:\nWrite the final CV or covering letter in English."

    def _combined_job_brief_for_generation(self) -> str:
        base = self._combined_job_brief()
        language_block = self._language_instruction_block()
        return f"{language_block}\n\n{base}".strip()

    def _combined_job_brief(self) -> str:
        details = self._job_details_dict()
        sections: list[str] = []
        if details["company"]:
            sections.append(f"Target company: {details['company']}")
        if details["job_title"]:
            sections.append(f"Target role: {details['job_title']}")
        if details["full_description"]:
            sections.append("Full job description:\n" + details["full_description"])
        if details["responsibilities"]:
            sections.append("Key responsibilities:\n" + details["responsibilities"])
        if details["requirements"]:
            sections.append("Required experience and skills:\n" + details["requirements"])
        return "\n\n".join(sections).strip()

    def _validate_job_details(self) -> tuple[bool, str]:
        if not self._job_title():
            return False, "Enter the job title on the Job page before continuing."
        details = self._job_details_dict()
        if not (details["full_description"] or details["responsibilities"] or details["requirements"]):
            return False, "Add the job description, responsibilities, or required skills before generating."
        return True, "Job details look usable."

    def _workspace_metadata(self) -> dict[str, str]:
        company = self._job_company()
        role = self._job_title()
        name = self.workspace_name_edit.text().strip() if hasattr(self, "workspace_name_edit") else ""
        if not name:
            name = f"{company} {role}".strip() or "Untitled application"
        return {
            "application_name": name,
            "target_company": company,
            "target_role": role,
            "modified_at": datetime.now().isoformat(timespec="seconds"),
        }

    def _current_workspace_snapshot(self) -> dict:
        metadata = self._workspace_metadata()
        template_name = self.template_combo.currentText() if hasattr(self, "template_combo") else getattr(self.app_settings, "template_name", "ATS Friendly")
        pdf_template = self.export_pdf_template_combo.currentText() if hasattr(self, "export_pdf_template_combo") else getattr(self.app_settings, "pdf_template", "ATS Friendly")
        pdf_page_size = self.export_page_size_combo.currentText() if hasattr(self, "export_page_size_combo") else getattr(self.app_settings, "pdf_page_size", "A4")
        export_dir = self.export_dir_edit.text().strip() if hasattr(self, "export_dir_edit") else getattr(self.app_settings, "last_export_dir", str(exports_dir()))
        return {
            "source": "ResuBuilder",
            "metadata": metadata,
            "profile": self._profile_to_dict(),
            "structured_evidence_entries": [dict(entry) for entry in self.evidence_entries],
            "structured_evidence": self._structured_evidence_text(),
            "job_details": self._job_details_dict(),
            "job_description": self._combined_job_brief(),
            "generated_cv": self._document_with_current_section_order(self.generated_cv) if hasattr(self, "section_order_list") else self.generated_cv,
            "generated_covering_letter": self.generated_covering_letter,
            "quality_report": self._quality_report_text(),
            "ai_quality_review": self.ai_quality_review,
            "manual_edit_instructions": self._manual_edit_instructions_text(),
            "job_fit_analysis": self.job_fit_analysis,
            "ui_state": {
                "document_type": self.document_type_combo.currentText() if hasattr(self, "document_type_combo") else "CV",
                "template_name": template_name,
                "output_language": self._selected_output_language(),
                "review_document": self.review_document_combo.currentText() if hasattr(self, "review_document_combo") else "CV",
                "export_document": self.export_document_combo.currentText() if hasattr(self, "export_document_combo") else "CV",
                "cv_section_order": self._current_section_order() if hasattr(self, "section_order_list") else [],
            },
            "settings": {
                "provider": self.app_settings.ai_provider,
                "ollama_model": self.app_settings.ollama_model,
                "openai_model": self.app_settings.openai_model,
                "generation_mode": self.app_settings.generation_mode,
                "output_language": self._selected_output_language(),
                "pdf_template": pdf_template,
                "pdf_page_size": pdf_page_size,
                "export_dir": export_dir,
            },
        }

    def _update_workspace_status(self, message: str) -> None:
        if not hasattr(self, "workspace_status_edit"):
            return
        path_text = str(self.current_workspace_path) if self.current_workspace_path else "Not saved yet"
        metadata = self._workspace_metadata() if hasattr(self, "workspace_name_edit") else {}
        self.workspace_status_edit.setPlainText(
            f"{message}\n\n"
            f"Application: {metadata.get('application_name', '')}\n"
            f"Company: {metadata.get('target_company', '')}\n"
            f"Role: {metadata.get('target_role', '')}\n"
            f"Workspace file: {path_text}\n\n"
            f"CV generated: {'yes' if self.generated_cv.strip() else 'no'}\n"
            f"Covering letter generated: {'yes' if self.generated_covering_letter.strip() else 'no'}\n"
            f"Structured evidence blocks: {len(self.evidence_entries)}\n"
            f"Job fit analysis: {'yes' if self.job_fit_analysis.strip() else 'no'}\n"
            f"Quality report: {'yes' if self._quality_report_text() != 'No quality report exported from ResuBuilder.' else 'no'}\n"
            f"AI quality review: {'yes' if self.ai_quality_review.strip() else 'no'}\n"
            f"Manual edit instructions: {'yes' if self._manual_edit_instructions_text().strip() else 'no'}"
        )

    def _workspace_open_dir(self) -> Path:
        configured = getattr(self.app_settings, "last_workspace_dir", "") or ""
        if configured:
            path = Path(configured)
            try:
                path.mkdir(parents=True, exist_ok=True)
                return path
            except OSError:
                pass
        return ensure_applications_dir()

    def _suggest_workspace_path(self) -> Path:
        metadata = self._workspace_metadata()
        filename = suggested_application_filename(metadata.get("target_company", ""), metadata.get("target_role", ""))
        return self._workspace_open_dir() / filename

    def _remember_workspace_dir(self, path: Path) -> None:
        try:
            folder = path.parent.resolve()
        except OSError:
            folder = path.parent
        self.app_settings.last_workspace_dir = str(folder)
        if hasattr(self, "settings_workspace_dir_edit"):
            self.settings_workspace_dir_edit.setText(str(folder))
        try:
            save_app_settings(self.app_settings)
        except Exception:  # noqa: BLE001
            self._write_qt_log("Workspace directory setting save failed:\n" + traceback.format_exc())

    def _new_workspace(self) -> None:
        answer = QMessageBox.question(
            self,
            "New workspace",
            "Create a new application workspace? This clears job description, generated documents, and review output. Profile fields are kept so you do not need to retype your identity.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.current_workspace_path = None
        self.workspace_name_edit.clear()
        self.workspace_path_edit.clear()
        if hasattr(self, "job_company_edit"):
            self.job_company_edit.clear()
        if hasattr(self, "job_title_edit"):
            self.job_title_edit.clear()
        if hasattr(self, "job_description_edit"):
            self.job_description_edit.clear()
        if hasattr(self, "job_responsibilities_edit"):
            self.job_responsibilities_edit.clear()
        if hasattr(self, "job_requirements_edit"):
            self.job_requirements_edit.clear()
        self.generated_cv = ""
        self.generated_covering_letter = ""
        self.job_fit_analysis = ""
        self.ai_quality_review = ""
        self.manual_edit_instructions = ""
        if hasattr(self, "manual_edit_instructions_edit"):
            self.manual_edit_instructions_edit.clear()
        if hasattr(self, "job_fit_edit"):
            self.job_fit_edit.clear()
        if hasattr(self, "job_fit_status_label"):
            self.job_fit_status_label.setText("No job fit analysis yet. Generate without it only for quick tests.")
        if hasattr(self, "output_language_combo"):
            self.output_language_combo.setCurrentText(getattr(self.app_settings, "output_language", "English"))
        if hasattr(self, "output_edit"):
            self.output_edit.clear()
        if hasattr(self, "quality_report_edit"):
            self.quality_report_edit.setPlainText("No report yet.")
        if hasattr(self, "ai_quality_review_edit"):
            self.ai_quality_review_edit.setPlainText("No AI review yet. Run the quality check first.")
        if hasattr(self, "ai_review_status_label"):
            self.ai_review_status_label.setText("No AI review yet.")
        if hasattr(self, "review_score_label"):
            self.review_score_label.setText("No quality check run yet")
        if hasattr(self, "review_status_label"):
            self.review_status_label.setText("Generate a CV or covering letter first, then run the checker.")
        self._update_workspace_status("New workspace started. Add job details on the Job page, then save when ready.")
        self.show_page("Workspace")

    def _save_workspace(self) -> None:
        if self.current_workspace_path is None:
            self._save_workspace_as()
            return
        self._write_workspace_to_path(self.current_workspace_path)

    def _save_workspace_as(self) -> None:
        default_path = self._suggest_workspace_path()
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save application workspace",
            str(default_path),
            "Application workspace (*.json);;JSON files (*.json)",
        )
        if not file_path:
            return
        self._write_workspace_to_path(Path(file_path))

    def _write_workspace_to_path(self, path: Path) -> None:
        try:
            saved_path = save_application_snapshot(path, self._current_workspace_snapshot())
        except Exception as exc:  # noqa: BLE001
            self._write_qt_log("Workspace save failed:\n" + traceback.format_exc())
            QMessageBox.critical(self, "Workspace save failed", str(exc))
            return
        self.current_workspace_path = saved_path
        self._remember_workspace_dir(saved_path)
        self.workspace_path_edit.setText(str(saved_path))
        self._sync_export_metadata_from_workspace(force_empty_only=True)
        self._update_workspace_status("Workspace saved successfully.")
        QMessageBox.information(self, "Workspace saved", f"Application workspace saved to:\n{saved_path}")

    def _load_workspace(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Load application workspace",
            str(self._workspace_open_dir()),
            "Application workspace (*.json);;JSON files (*.json);;All files (*.*)",
        )
        if not file_path:
            return
        try:
            snapshot = load_application_snapshot(file_path)
            self._apply_workspace_snapshot(snapshot)
        except Exception as exc:  # noqa: BLE001
            self._write_qt_log("Workspace load failed:\n" + traceback.format_exc())
            QMessageBox.critical(self, "Workspace load failed", str(exc))
            return
        self.current_workspace_path = Path(file_path)
        self._remember_workspace_dir(self.current_workspace_path)
        self.workspace_path_edit.setText(str(self.current_workspace_path))
        self._update_workspace_status("Workspace loaded successfully.")
        self.show_page("Workspace")
        QMessageBox.information(self, "Workspace loaded", "Application workspace loaded into ResuBuilder.")

    def _apply_workspace_snapshot(self, snapshot: dict) -> None:
        metadata = snapshot.get("metadata") or {}
        if not metadata:
            metadata = {
                "application_name": snapshot.get("application_name", ""),
                "target_company": snapshot.get("target_company", ""),
                "target_role": snapshot.get("target_role", ""),
            }
        self.workspace_name_edit.setText(str(metadata.get("application_name", "") or ""))
        job_details = snapshot.get("job_details") or {}
        if not isinstance(job_details, dict):
            job_details = {}
        if hasattr(self, "job_company_edit"):
            self.job_company_edit.setText(str(job_details.get("company") or metadata.get("target_company", "") or ""))
        if hasattr(self, "job_title_edit"):
            self.job_title_edit.setText(str(job_details.get("job_title") or metadata.get("target_role", "") or ""))
        profile_data = dict(snapshot.get("profile") or {})
        # Qt workspaces now store evidence both inside the profile and at the top level.
        # The top-level copy is deliberate: it makes workspace load robust even if an older
        # profile serializer drops unknown fields. It also lets us recover evidence from
        # workspaces created during earlier PySide6 builds.
        top_level_entries = snapshot.get("structured_evidence_entries")
        if top_level_entries and not profile_data.get("structured_evidence_entries"):
            profile_data["structured_evidence_entries"] = top_level_entries
        if snapshot.get("structured_evidence") and not profile_data.get("structured_evidence"):
            profile_data["structured_evidence"] = snapshot.get("structured_evidence")
        self._apply_profile_data(profile_data)
        self.job_description_edit.setPlainText(str(job_details.get("full_description") or snapshot.get("job_description", "") or ""))
        if hasattr(self, "job_responsibilities_edit"):
            self.job_responsibilities_edit.setPlainText(str(job_details.get("responsibilities", "") or ""))
        if hasattr(self, "job_requirements_edit"):
            self.job_requirements_edit.setPlainText(str(job_details.get("requirements", "") or ""))
        self.generated_cv = str(snapshot.get("generated_cv", "") or "")
        self.generated_covering_letter = str(snapshot.get("generated_covering_letter", "") or "")
        if self.generated_cv:
            self.document_type_combo.setCurrentText("CV")
            self.output_edit.setPlainText(self.generated_cv)
        elif self.generated_covering_letter:
            self.document_type_combo.setCurrentText("Covering Letter")
            self.output_edit.setPlainText(self.generated_covering_letter)
        else:
            self.output_edit.clear()
        quality_report = str(snapshot.get("quality_report", "") or "")
        self.quality_report_edit.setPlainText(quality_report or "No report yet.")
        self.ai_quality_review = str(snapshot.get("ai_quality_review", "") or "")
        if hasattr(self, "ai_quality_review_edit"):
            self.ai_quality_review_edit.setPlainText(self.ai_quality_review or "No AI review saved in this workspace.")
        if hasattr(self, "ai_review_status_label"):
            self.ai_review_status_label.setText("AI review loaded from workspace." if self.ai_quality_review.strip() else "No AI review saved in this workspace.")
        self.manual_edit_instructions = str(snapshot.get("manual_edit_instructions", "") or "")
        if hasattr(self, "manual_edit_instructions_edit"):
            self.manual_edit_instructions_edit.setPlainText(self.manual_edit_instructions)
        self.job_fit_analysis = str(snapshot.get("job_fit_analysis", "") or "")
        if hasattr(self, "job_fit_edit"):
            self.job_fit_edit.setPlainText(self.job_fit_analysis)
        if hasattr(self, "job_fit_status_label"):
            self.job_fit_status_label.setText("Job fit analysis loaded from workspace." if self.job_fit_analysis.strip() else "No job fit analysis saved in this workspace.")
        ui_state = snapshot.get("ui_state") or {}
        if ui_state.get("template_name"):
            self.template_combo.setCurrentText(str(ui_state.get("template_name")))
        if ui_state.get("output_language") and hasattr(self, "output_language_combo"):
            self.output_language_combo.setCurrentText(str(ui_state.get("output_language")))
        elif (snapshot.get("settings") or {}).get("output_language") and hasattr(self, "output_language_combo"):
            self.output_language_combo.setCurrentText(str((snapshot.get("settings") or {}).get("output_language")))
        if ui_state.get("review_document"):
            self.review_document_combo.setCurrentText(str(ui_state.get("review_document")))
        if ui_state.get("export_document"):
            self.export_document_combo.setCurrentText(str(ui_state.get("export_document")))
        if hasattr(self, "section_order_list"):
            self._refresh_section_order_list(ui_state.get("cv_section_order") or None)
        self._refresh_review_page_break_sections()
        settings = snapshot.get("settings") or {}
        if settings.get("pdf_template"):
            self.export_pdf_template_combo.setCurrentText(str(settings.get("pdf_template")))
        if settings.get("pdf_page_size"):
            self.export_page_size_combo.setCurrentText(str(settings.get("pdf_page_size")))
        if settings.get("export_dir"):
            self.export_dir_edit.setText(str(settings.get("export_dir")))
        self._sync_export_metadata_from_workspace(force_empty_only=False)

    def _sync_export_metadata_from_workspace(self, force_empty_only: bool = True) -> None:
        # Export metadata is now derived from the Job page. This method remains as a compatibility hook.
        return

    def _evidence_form_to_dict(self) -> dict[str, str]:
        return {
            "type": self.evidence_type_combo.currentText().strip() if hasattr(self, "evidence_type_combo") else "Project",
            "title": self.evidence_title_edit.text().strip() if hasattr(self, "evidence_title_edit") else "",
            "context": self.evidence_context_edit.toPlainText().strip() if hasattr(self, "evidence_context_edit") else "",
            "tools": self.evidence_tools_edit.text().strip() if hasattr(self, "evidence_tools_edit") else "",
            "methods": self.evidence_methods_edit.toPlainText().strip() if hasattr(self, "evidence_methods_edit") else "",
            "outcome": self.evidence_outcome_edit.toPlainText().strip() if hasattr(self, "evidence_outcome_edit") else "",
            "metrics": self.evidence_metrics_edit.text().strip() if hasattr(self, "evidence_metrics_edit") else "",
            "signals": self.evidence_signals_edit.text().strip() if hasattr(self, "evidence_signals_edit") else "",
        }

    def _evidence_title_for_list(self, entry: dict[str, str]) -> str:
        title = (entry.get("title") or "Untitled evidence").strip()
        entry_type = (entry.get("type") or "Evidence").strip()
        signals = (entry.get("signals") or "").strip()
        if signals:
            first_signal = signals.split(",")[0].strip()
            if first_signal:
                return f"{entry_type}: {title}  ·  {first_signal}"
        return f"{entry_type}: {title}"

    def _refresh_evidence_list(self) -> None:
        if not hasattr(self, "evidence_list"):
            return
        current_row = self.evidence_list.currentRow()
        self.evidence_list.blockSignals(True)
        self.evidence_list.clear()
        for entry in self.evidence_entries:
            self.evidence_list.addItem(self._evidence_title_for_list(entry))
        self.evidence_list.blockSignals(False)
        if self.evidence_entries:
            self.evidence_list.setCurrentRow(min(max(current_row, 0), len(self.evidence_entries) - 1))
        self._refresh_evidence_preview()

    def _refresh_evidence_preview(self) -> None:
        if not hasattr(self, "evidence_preview_edit"):
            return
        text = self._structured_evidence_text()
        self.evidence_preview_edit.setPlainText(text or "No structured evidence yet. Add evidence blocks before generation.")

    def _structured_evidence_text(self) -> str:
        if self.evidence_entries:
            blocks: list[str] = []
            for index, entry in enumerate(self.evidence_entries, start=1):
                blocks.append(
                    f"Evidence {index}: {entry.get('title', '').strip() or 'Untitled evidence'}\n"
                    f"Type: {entry.get('type', '').strip()}\n"
                    f"Context / situation: {entry.get('context', '').strip()}\n"
                    f"Tools / technologies: {entry.get('tools', '').strip()}\n"
                    f"Methods / actions: {entry.get('methods', '').strip()}\n"
                    f"Outcome / purpose: {entry.get('outcome', '').strip()}\n"
                    f"Metrics / proof: {entry.get('metrics', '').strip()}\n"
                    f"Relevant job signals: {entry.get('signals', '').strip()}"
                )
            return "\n\n---\n\n".join(blocks).strip()
        return self._legacy_structured_evidence_text.strip()

    def _set_evidence_form(self, entry: dict[str, str]) -> None:
        if not hasattr(self, "evidence_title_edit"):
            return
        self.evidence_type_combo.setCurrentText(str(entry.get("type", "Project") or "Project"))
        self.evidence_title_edit.setText(str(entry.get("title", "") or ""))
        self.evidence_context_edit.setPlainText(str(entry.get("context", "") or ""))
        self.evidence_tools_edit.setText(str(entry.get("tools", "") or ""))
        self.evidence_methods_edit.setPlainText(str(entry.get("methods", "") or ""))
        self.evidence_outcome_edit.setPlainText(str(entry.get("outcome", "") or ""))
        self.evidence_metrics_edit.setText(str(entry.get("metrics", "") or ""))
        self.evidence_signals_edit.setText(str(entry.get("signals", "") or ""))

    def _clear_evidence_form(self) -> None:
        if not hasattr(self, "evidence_title_edit"):
            return
        self.evidence_type_combo.setCurrentIndex(0)
        self.evidence_title_edit.clear()
        self.evidence_context_edit.clear()
        self.evidence_tools_edit.clear()
        self.evidence_methods_edit.clear()
        self.evidence_outcome_edit.clear()
        self.evidence_metrics_edit.clear()
        self.evidence_signals_edit.clear()

    def _load_selected_evidence(self, row: int) -> None:
        if row < 0 or row >= len(self.evidence_entries):
            return
        self._set_evidence_form(self.evidence_entries[row])

    def _add_evidence_entry(self) -> None:
        entry = self._evidence_form_to_dict()
        if not entry.get("title"):
            QMessageBox.warning(self, "Cannot add evidence", "Evidence title is required.")
            return
        if not (entry.get("tools") or entry.get("methods") or entry.get("outcome")):
            QMessageBox.warning(self, "Cannot add evidence", "Add tools, methods, or outcome so the evidence is useful for generation.")
            return
        self.evidence_entries.append(entry)
        self._legacy_structured_evidence_text = ""
        self._refresh_evidence_list()
        self.evidence_list.setCurrentRow(len(self.evidence_entries) - 1)
        self._update_workspace_status("Structured evidence added. Save the workspace to preserve it.")

    def _update_selected_evidence(self) -> None:
        row = self.evidence_list.currentRow() if hasattr(self, "evidence_list") else -1
        if row < 0 or row >= len(self.evidence_entries):
            QMessageBox.information(self, "No evidence selected", "Select an evidence block before updating.")
            return
        entry = self._evidence_form_to_dict()
        if not entry.get("title"):
            QMessageBox.warning(self, "Cannot update evidence", "Evidence title is required.")
            return
        self.evidence_entries[row] = entry
        self._legacy_structured_evidence_text = ""
        self._refresh_evidence_list()
        self.evidence_list.setCurrentRow(row)
        self._update_workspace_status("Structured evidence updated. Save the workspace to preserve it.")

    def _delete_selected_evidence(self) -> None:
        row = self.evidence_list.currentRow() if hasattr(self, "evidence_list") else -1
        if row < 0 or row >= len(self.evidence_entries):
            QMessageBox.information(self, "No evidence selected", "Select an evidence block before deleting.")
            return
        del self.evidence_entries[row]
        self._clear_evidence_form()
        self._refresh_evidence_list()
        self._update_workspace_status("Structured evidence deleted. Save the workspace to preserve the change.")

    def _load_evidence_example(self) -> None:
        self._set_evidence_form(
            {
                "type": "Project",
                "title": "Data Automation and Reporting Tool",
                "context": "Internal project created to reduce repetitive manual reporting work and make recurring data checks easier to review.",
                "tools": "Python, pandas, CSV/Excel files, Git, basic data validation",
                "methods": "Built scripts to load structured data, clean inconsistent fields, validate required values, generate summary outputs, and document the workflow so it could be repeated reliably.",
                "outcome": "Improved the consistency of recurring reports and gave the team a clearer way to review data quality before using the results in decisions.",
                "metrics": "Example evidence only. Replace with truthful proof such as time saved, error reduction, number of files processed, user feedback, repository link, or validation notes.",
                "signals": "Python, automation, data processing, quality, documentation, problem solving, Git",
            }
        )
        QMessageBox.information(self, "Example loaded", "Generic example evidence loaded into the form. Replace it with truthful candidate evidence before adding it.")

    def _build_profile(self) -> CandidateProfile:
        return CandidateProfile(
            name=self.name_edit.text().strip(),
            email=self.email_edit.text().strip(),
            phone=self.phone_edit.text().strip(),
            location=self.location_edit.text().strip(),
            title=self.title_edit.text().strip(),
            summary=self.summary_edit.toPlainText().strip(),
            studies=self.education_edit.toPlainText().strip() if hasattr(self, "education_edit") else "",
            professions=self.professions_edit.toPlainText().strip(),
            projects=self.projects_edit.toPlainText().strip(),
            skills=self.skills_edit.toPlainText().strip(),
            languages=self.languages_edit.toPlainText().strip() if hasattr(self, "languages_edit") else "",
            links=self.links_edit.toPlainText().strip() if hasattr(self, "links_edit") else "",
            structured_evidence=self._structured_evidence_text(),
        )

    def _validate_profile(self) -> tuple[bool, str]:
        profile = self._build_profile()
        if not profile.name:
            return False, "Name is required."
        if not profile.email or not EMAIL_RE.match(profile.email):
            return False, "Enter a valid email address before generating."
        if profile.phone and not profile.phone.isdigit():
            return False, "Telephone must contain numbers only."
        if not profile.title:
            return False, "Target/current title is required."
        return True, "Profile looks usable."

    def _validate_profile_with_message(self) -> None:
        ok, message = self._validate_profile()
        if ok:
            QMessageBox.information(self, "Profile validation", message)
        else:
            QMessageBox.warning(self, "Profile validation", message)

    def _profile_to_dict(self) -> dict:
        profile = self._build_profile()
        if hasattr(profile, "to_dict"):
            data = profile.to_dict()
        else:
            data = dict(profile.__dict__)
        data["structured_evidence"] = self._structured_evidence_text()
        data["structured_evidence_entries"] = self.evidence_entries
        return data

    def _normalize_evidence_entries(self, raw_entries: object) -> list[dict[str, str]]:
        if not isinstance(raw_entries, list):
            return []
        normalized: list[dict[str, str]] = []
        for raw_entry in raw_entries:
            if not isinstance(raw_entry, dict):
                continue
            normalized.append(
                {
                    "type": str(raw_entry.get("type", "Project") or "Project"),
                    "title": str(raw_entry.get("title", "") or ""),
                    "context": str(raw_entry.get("context", "") or ""),
                    "tools": str(raw_entry.get("tools", "") or ""),
                    "methods": str(raw_entry.get("methods", "") or ""),
                    "outcome": str(raw_entry.get("outcome", "") or ""),
                    "metrics": str(raw_entry.get("metrics", "") or ""),
                    "signals": str(raw_entry.get("signals", "") or ""),
                }
            )
        return normalized

    def _apply_profile_data(self, data: dict) -> None:
        self.name_edit.setText(str(data.get("name", "") or ""))
        self.email_edit.setText(str(data.get("email", "") or ""))
        self.phone_edit.setText(str(data.get("phone", "") or ""))
        self.location_edit.setText(str(data.get("location", "") or ""))
        self.title_edit.setText(str(data.get("title", "") or ""))
        self.summary_edit.setPlainText(str(data.get("summary", "") or ""))
        if hasattr(self, "education_edit"):
            self.education_edit.setPlainText(str(data.get("studies", data.get("education", "")) or ""))
        if hasattr(self, "languages_edit"):
            self.languages_edit.setPlainText(str(data.get("languages", "") or ""))
        if hasattr(self, "links_edit"):
            self.links_edit.setPlainText(str(data.get("links", "") or ""))
        self.skills_edit.setPlainText(str(data.get("skills", "") or ""))
        self.projects_edit.setPlainText(str(data.get("projects", "") or ""))
        self.professions_edit.setPlainText(str(data.get("professions", "") or ""))
        self.evidence_entries = self._normalize_evidence_entries(data.get("structured_evidence_entries") or [])
        self._legacy_structured_evidence_text = str(data.get("structured_evidence", "") or "")
        if hasattr(self, "evidence_list"):
            self._refresh_evidence_list()
            if not self.evidence_entries:
                self._clear_evidence_form()
                self._refresh_evidence_preview()
            else:
                self.evidence_list.setCurrentRow(0)

    def _save_current_profile(self) -> None:
        """Save the active profile to the default project profile file."""
        ok, message = self._validate_profile()
        if not ok:
            QMessageBox.warning(self, "Cannot save profile", message)
            return
        try:
            save_json(self._profile_to_dict())
        except Exception as exc:  # noqa: BLE001
            self._write_qt_log("Profile save failed:\n" + traceback.format_exc())
            QMessageBox.critical(self, "Profile save failed", str(exc))
            return
        QMessageBox.information(self, "Profile saved", f"Profile saved to:\n{PROFILE_PATH}")

    def _save_profile_as(self) -> None:
        """Save the active profile to a user-selected JSON file."""
        ok, message = self._validate_profile()
        if not ok:
            QMessageBox.warning(self, "Cannot save profile", message)
            return
        PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save profile as",
            str(PROFILE_PATH),
            "Profile JSON (*.json);;JSON files (*.json)",
        )
        if not file_path:
            return
        try:
            path = Path(file_path)
            if path.suffix.lower() != ".json":
                path = path.with_suffix(".json")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(self._profile_to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            self._write_qt_log("Profile save-as failed:\n" + traceback.format_exc())
            QMessageBox.critical(self, "Profile save failed", str(exc))
            return
        QMessageBox.information(self, "Profile saved", f"Profile saved to:\n{path}")

    def _load_profile(self) -> None:
        """Load a profile JSON from the profile data folder.

        This replaces the old separate "Load Saved Profile" and "Import Profile JSON"
        actions. One loader handles both the default saved profile and any user-selected
        profile JSON file.
        """
        PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
        start_path = PROFILE_PATH if PROFILE_PATH.exists() else PROFILE_PATH.parent
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Load profile",
            str(start_path),
            "Profile JSON (*.json);;JSON files (*.json);;All files (*.*)",
        )
        if not file_path:
            return
        try:
            data = json.loads(Path(file_path).read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("Profile JSON must contain a JSON object.")
        except Exception as exc:  # noqa: BLE001
            self._write_qt_log("Profile load failed:\n" + traceback.format_exc())
            QMessageBox.critical(self, "Profile load failed", str(exc))
            return
        self._apply_profile_data(data)
        QMessageBox.information(self, "Profile loaded", f"Profile loaded from:\n{file_path}")

    # Backward-compatible aliases for older menu/action references.
    def _load_saved_profile(self) -> None:
        self._load_profile()

    def _import_profile_json(self) -> None:
        self._load_profile()

    def _export_profile_json(self) -> None:
        self._save_profile_as()

    def _normalized_ollama_base_url(self, base_url: str | None = None) -> str:
        value = str(base_url or getattr(self.app_settings, "ollama_base_url", "http://localhost:11434") or "http://localhost:11434").strip()
        return value.rstrip("/") or "http://localhost:11434"

    def _fetch_ollama_models(self, base_url: str, timeout_seconds: int = 5) -> tuple[bool, list[str], str]:
        """Return installed Ollama model names from the local Ollama API."""
        url = f"{self._normalized_ollama_base_url(base_url)}/api/tags"
        try:
            request = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(request, timeout=max(2, timeout_seconds)) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            return False, [], f"Could not connect to Ollama at {url}. {exc}"
        except TimeoutError:
            return False, [], f"Timed out while connecting to Ollama at {url}."
        except Exception as exc:  # noqa: BLE001
            return False, [], f"Could not read Ollama model list from {url}. {exc}"

        models: list[str] = []
        for item in payload.get("models", []):
            if isinstance(item, dict):
                name = str(item.get("name", "") or "").strip()
                if name:
                    models.append(name)
        return True, sorted(set(models)), ""

    def _ollama_setup_message(self, base_url: str, model: str, detail: str = "") -> str:
        detail_text = f"\n\nDetails:\n{detail}" if detail else ""
        return (
            "Ollama is not ready on this computer.\n\n"
            f"ResuBuilder is configured to use:\n{base_url}\n\n"
            "To use local AI on this computer:\n"
            "1. Install Ollama for Windows from https://ollama.com/download/windows\n"
            "2. Open PowerShell\n"
            f"3. Run: ollama pull {model}\n"
            "4. Start Ollama if it is not already running\n"
            "5. Restart ResuBuilder or click Check Ollama Setup again\n\n"
            "Recommended models:\n"
            "- qwen3:8b for most computers\n"
            "- qwen3:14b for stronger computers\n"
            "- llama3.1:8b as a backup option"
            f"{detail_text}"
        )

    def _check_ollama_dialog_values(self, base_url_edit: QLineEdit, model_combo: QComboBox) -> bool:
        base_url = self._normalized_ollama_base_url(base_url_edit.text())
        model = model_combo.currentText().strip() or "qwen3:8b"
        return self._check_ollama_ready(show_success=True, base_url=base_url, model=model)

    def _check_ollama_from_settings(self, show_success: bool = True) -> bool:
        self._sync_settings_from_controls()
        return self._check_ollama_ready(show_success=show_success)

    def _check_ollama_ready(self, show_success: bool = False, base_url: str | None = None, model: str | None = None) -> bool:
        base_url = self._normalized_ollama_base_url(base_url)
        model = str(model or getattr(self.app_settings, "ollama_model", "qwen3:8b") or "qwen3:8b").strip()
        ok, installed_models, error = self._fetch_ollama_models(base_url, timeout_seconds=5)
        if not ok:
            QMessageBox.warning(self, "Ollama setup needed", self._ollama_setup_message(base_url, model, error))
            return False
        if model not in installed_models:
            installed = "\n".join(f"- {name}" for name in installed_models) if installed_models else "No local models found."
            detail = f"Selected model '{model}' is not installed.\n\nInstalled models:\n{installed}"
            QMessageBox.warning(self, "Ollama model missing", self._ollama_setup_message(base_url, model, detail))
            return False
        if show_success:
            QMessageBox.information(
                self,
                "Ollama ready",
                f"Ollama is reachable at {base_url}.\n\nInstalled model ready: {model}",
            )
        return True

    def _ensure_ai_ready(self, settings: AISettings, action_name: str) -> bool:
        if settings.provider != "Ollama Local":
            return True
        return self._check_ollama_ready(show_success=False, base_url=settings.ollama_base_url, model=settings.ollama_model)

    def _show_ollama_setup_help(self) -> None:
        model = str(getattr(self.app_settings, "ollama_model", "qwen3:8b") or "qwen3:8b")
        base_url = self._normalized_ollama_base_url()
        QMessageBox.information(self, "Ollama setup help", self._ollama_setup_message(base_url, model))

    def _open_ollama_download(self) -> None:
        QDesktopServices.openUrl(QUrl("https://ollama.com/download/windows"))

    def _settings_to_ai_settings(self) -> AISettings:
        return AISettings(
            use_ai=self.app_settings.use_ai,
            provider=self.app_settings.ai_provider,
            model=self.app_settings.openai_model,
            generation_mode=self.app_settings.generation_mode,
            ollama_base_url=self.app_settings.ollama_base_url,
            ollama_model=self.app_settings.ollama_model,
            timeout_seconds=self.app_settings.timeout_seconds,
        )

    def _start_job_fit_analysis(self) -> None:
        ok, message = self._validate_profile()
        if not ok:
            QMessageBox.warning(self, "Cannot analyze job fit", message)
            return
        ok, message = self._validate_job_details()
        if not ok:
            QMessageBox.warning(self, "Cannot analyze job fit", message)
            return
        job_description = self._combined_job_brief()
        if self._job_fit_running:
            QMessageBox.information(self, "Job fit analysis running", "Wait for the current job fit analysis to finish.")
            return

        self._job_fit_running = True
        self._job_fit_job_id += 1
        job_id = self._job_fit_job_id
        settings = self._settings_to_ai_settings()
        if not self._ensure_ai_ready(settings, "job fit analysis"):
            return
        company = self._job_company()
        role = self._job_title()

        self.job_fit_button.setEnabled(False)
        self.job_fit_status_label.setText(f"Analyzing fit with Ollama / {settings.ollama_model}. This can take a while.")
        self.job_fit_edit.setPlainText("Working. The result will be used automatically by the next CV or covering-letter generation.")
        self._write_qt_log(f"Job fit analysis started: job_id={job_id}, model={settings.ollama_model}")

        thread = threading.Thread(
            target=self._run_job_fit_worker,
            args=(job_id, self._build_profile(), job_description, settings, company, role),
            daemon=True,
        )
        thread.start()

    def _run_job_fit_worker(self, job_id: int, profile: CandidateProfile, job_description: str, settings: AISettings, company: str, role: str) -> None:
        try:
            result = self.ai_service.analyze_job_fit(
                profile=profile,
                job_description=job_description,
                settings=settings,
                target_company=company,
                target_role=role,
            )
            if result is None:
                raise RuntimeError("AI service returned no job fit analysis.")
        except Exception as exc:  # noqa: BLE001
            self._write_qt_log("Job fit analysis failed:\n" + traceback.format_exc())
            self.job_fit_signals.failed.emit(job_id, str(exc))
            return
        self._write_qt_log(f"Job fit analysis finished: job_id={job_id}, chars={len(str(result))}")
        self.job_fit_signals.finished.emit(job_id, str(result))

    def _job_fit_finished(self, job_id: int, text: str) -> None:
        if job_id != self._job_fit_job_id:
            return
        self._job_fit_running = False
        self.job_fit_button.setEnabled(True)
        self.job_fit_analysis = text.strip()
        self.job_fit_edit.setPlainText(self.job_fit_analysis)
        self.job_fit_status_label.setText("Job fit analysis complete. The next generated document will use this strategy.")
        self._update_workspace_status("Job fit analysis complete. Save the workspace to preserve it.")

    def _job_fit_failed(self, job_id: int, error: str) -> None:
        if job_id != self._job_fit_job_id:
            return
        self._job_fit_running = False
        self.job_fit_button.setEnabled(True)
        self.job_fit_edit.setPlainText("")
        self.job_fit_status_label.setText("Job fit analysis failed.")
        QMessageBox.critical(self, "Job fit analysis failed", error)

    def _start_generation(self) -> None:
        ok, message = self._validate_profile()
        if not ok:
            QMessageBox.warning(self, "Cannot generate", message)
            return
        ok, message = self._validate_job_details()
        if not ok:
            QMessageBox.warning(self, "Cannot generate", message)
            return
        if self._generation_running:
            QMessageBox.information(self, "Generation already running", "Wait for the current generation to finish.")
            return

        document_type = self.document_type_combo.currentText()
        request = GenerationRequest(
            profile=self._build_profile(),
            job_description=self._combined_job_brief_for_generation(),
            template_name=self.template_combo.currentText(),
            document_type=document_type,
            ai_settings=self._settings_to_ai_settings(),
            job_fit_analysis=self.job_fit_analysis,
        )
        context = QtGenerationContext(document_type=document_type, request=request)
        if not self._ensure_ai_ready(request.ai_settings, "generation"):
            return

        self._generation_running = True
        self._generation_job_id += 1
        job_id = self._generation_job_id
        self.generate_button.setEnabled(False)
        self.status_label.setText(f"Generating {document_type} in {self._selected_output_language()} with {request.ai_settings.provider} / {request.ai_settings.ollama_model}...")
        self.output_edit.setPlainText("Working. Do not close the app. Local AI can take a while on the first run.")
        self._write_qt_log(f"Generation started: job_id={job_id}, type={document_type}, provider={request.ai_settings.provider}, model={request.ai_settings.ollama_model}")

        thread = threading.Thread(target=self._run_generation_worker, args=(job_id, context), daemon=True)
        thread.start()

    def _run_generation_worker(self, job_id: int, context: QtGenerationContext) -> None:
        try:
            result = self.ai_service.generate(context.request)
            if result is None:
                raise RuntimeError("AI service returned no text.")
        except Exception as exc:  # noqa: BLE001, GUI worker should surface all failures.
            self._write_qt_log("Generation failed:\n" + traceback.format_exc())
            self.generation_signals.failed.emit(job_id, str(exc))
            return
        self._write_qt_log(f"Generation finished: job_id={job_id}, chars={len(str(result))}")
        self.generation_signals.finished.emit(job_id, context.document_type, str(result))

    def _generation_finished(self, job_id: int, document_type: str, text: str) -> None:
        if job_id != self._generation_job_id:
            return
        self._generation_running = False
        self.generate_button.setEnabled(True)
        if document_type == "CV":
            self.generated_cv = text
        else:
            self.generated_covering_letter = text
        self.output_edit.setPlainText(text)
        if document_type == "CV" and hasattr(self, "section_order_list"):
            self._refresh_section_order_list()
        self._refresh_review_page_break_sections()
        self.status_label.setText(f"{document_type} generated. Verify every claim, then run Review > Quality Check.")
        self._update_workspace_status(f"{document_type} generated. Save the workspace to preserve this output.")

    def _generation_failed(self, job_id: int, error: str) -> None:
        if job_id != self._generation_job_id:
            return
        self._generation_running = False
        self.generate_button.setEnabled(True)
        self.output_edit.setPlainText("")
        self.status_label.setText("Generation failed.")
        QMessageBox.critical(self, "Generation failed", error)

    def closeEvent(self, event) -> None:  # noqa: N802, Qt override name.
        if self._generation_running or self._job_fit_running or self._ai_review_running or self._improvement_running:
            if self._generation_running:
                active_task = "AI generation"
            elif self._job_fit_running:
                active_task = "job fit analysis"
            elif self._ai_review_running:
                active_task = "AI quality review"
            else:
                active_task = "quality improvement"
            answer = QMessageBox.question(
                self,
                "AI task running",
                f"{active_task} is still running. Closing now will cancel the visible result. Close anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        event.accept()

    def _write_qt_log(self, message: str) -> None:
        try:
            log_dir = logs_dir()
            log_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with (log_dir / "qt_gui.log").open("a", encoding="utf-8") as handle:
                handle.write(f"[{timestamp}] {message}\n")
        except Exception:
            # Logging must never crash the GUI.
            pass

    def _selected_review_document_text(self) -> tuple[str, str]:
        document_type = self.review_document_combo.currentText() if hasattr(self, "review_document_combo") else "CV"
        if document_type == "CV":
            return document_type, self.generated_cv
        return document_type, self.generated_covering_letter

    def _set_selected_review_document_text(self, document_type: str, text: str) -> None:
        if document_type == "CV":
            self.generated_cv = text
            if hasattr(self, "section_order_list"):
                self._refresh_section_order_list()
        else:
            self.generated_covering_letter = text
        if hasattr(self, "document_type_combo"):
            self.document_type_combo.setCurrentText(document_type)
        if hasattr(self, "review_document_combo"):
            self.review_document_combo.setCurrentText(document_type)
        if hasattr(self, "output_edit"):
            self.output_edit.setPlainText(text)
        self._refresh_review_page_break_sections()

    def _refresh_review_page_break_sections(self) -> None:
        if not hasattr(self, "page_break_section_combo"):
            return
        text = self.generated_cv
        self.page_break_section_combo.clear()
        sections = extract_markdown_sections(text)
        headings = [section.heading for section in sections]
        if not headings:
            self.page_break_section_combo.addItem("No level-2 CV sections found yet. Generate a CV first.")
            self.page_break_section_combo.setEnabled(False)
            if hasattr(self, "insert_page_break_button"):
                self.insert_page_break_button.setEnabled(False)
            return
        self.page_break_section_combo.setEnabled(True)
        if hasattr(self, "insert_page_break_button"):
            self.insert_page_break_button.setEnabled(True)
        self.page_break_section_combo.addItems(headings)

    def _insert_page_break_after_selected_section(self) -> None:
        text = self.generated_cv
        if not text.strip():
            QMessageBox.warning(self, "No CV generated", "Generate a CV before adding manual page splits.")
            return
        if not hasattr(self, "page_break_section_combo") or not self.page_break_section_combo.isEnabled():
            QMessageBox.warning(self, "No section selected", "Refresh sections and select a CV section first.")
            return
        heading = self.page_break_section_combo.currentText().strip()
        if not heading or heading.startswith("No level-2"):
            QMessageBox.warning(self, "No section selected", "Select a valid CV section first.")
            return
        updated = insert_page_break_after_section(text, heading)
        if updated == text:
            QMessageBox.information(self, "Manual page split", f"A page split already exists after {heading}, or the section could not be found.")
            return
        self._set_selected_review_document_text("CV", updated)
        if hasattr(self, "quality_report_edit"):
            self.quality_report_edit.setPlainText("Manual page split added. Run Quality Check again if you also changed content.")
        if hasattr(self, "review_score_label"):
            self.review_score_label.setText("Layout updated")
        if hasattr(self, "review_status_label"):
            self.review_status_label.setText(f"PDF page split added after {heading}. Export the CV PDF to verify the final page layout.")
        self._update_workspace_status("Manual CV page split added. Save the workspace to preserve it.")

    def _remove_manual_page_breaks(self) -> None:
        document_type = "CV"
        text = self.generated_cv
        if not text.strip():
            QMessageBox.warning(self, "No generated CV", "Generate a CV before removing manual page splits.")
            return
        updated = remove_page_break_markers(text)
        if updated == text:
            QMessageBox.information(self, "Manual page splits", "No manual page splits were found in the selected document.")
            return
        self._set_selected_review_document_text(document_type, updated)
        if hasattr(self, "review_status_label"):
            self.review_status_label.setText(f"Manual page splits removed from {document_type}.")
        self._update_workspace_status(f"Manual page splits removed from {document_type}. Save the workspace to preserve it.")

    def _show_selected_review_document(self) -> None:
        document_type, text = self._selected_review_document_text()
        if not text.strip():
            QMessageBox.information(self, "No generated document", f"Generate a {document_type} before reviewing it.")
            return
        self.output_edit.setPlainText(text)
        if document_type == "CV" and hasattr(self, "section_order_list"):
            self._refresh_section_order_list()
        self.document_type_combo.setCurrentText(document_type)
        self.show_page("Generate")

    def _run_quality_check(self) -> None:
        document_type, text = self._selected_review_document_text()
        if not text.strip():
            QMessageBox.warning(self, "Cannot run quality check", f"Generate a {document_type} first.")
            return
        ok, message = self._validate_job_details()
        if not ok:
            QMessageBox.warning(self, "Cannot run quality check", message)
            return
        job_description = self._combined_job_brief()
        ok, message = self._validate_profile()
        if not ok:
            QMessageBox.warning(self, "Cannot run quality check", message)
            return

        try:
            report = analyze_document(
                document_text=text,
                job_description=job_description,
                profile=self._build_profile(),
                document_type=document_type,
            )
            formatted = format_quality_report(report)
        except Exception as exc:  # noqa: BLE001
            self._write_qt_log("Quality check failed:\n" + traceback.format_exc())
            QMessageBox.critical(self, "Quality check failed", str(exc))
            return

        self.quality_report_edit.setPlainText(formatted)
        self.review_score_label.setText(f"{report.score}/100")
        self.review_status_label.setText(report.verdict)
        self.ai_quality_review = ""
        if hasattr(self, "ai_quality_review_edit"):
            self.ai_quality_review_edit.setPlainText("AI review cleared because a new quality check was run.")
        if hasattr(self, "ai_review_status_label"):
            self.ai_review_status_label.setText("Run AI Quality Review when you are ready for strategic critique.")

    def _build_review_generation_request(self, document_type: str) -> GenerationRequest:
        return GenerationRequest(
            profile=self._build_profile(),
            job_description=self._combined_job_brief_for_generation(),
            template_name=self.template_combo.currentText() if hasattr(self, "template_combo") else "ATS Friendly",
            document_type=document_type,
            ai_settings=self._settings_to_ai_settings(),
            job_fit_analysis=self.job_fit_analysis,
        )

    def _manual_edit_instructions_text(self) -> str:
        if hasattr(self, "manual_edit_instructions_edit"):
            self.manual_edit_instructions = self.manual_edit_instructions_edit.toPlainText().strip()
        return self.manual_edit_instructions.strip()

    def _manual_instruction_report(self, document_type: str, instructions: str) -> str:
        return (
            "# User AI Edit Instructions\n\n"
            f"The user wants targeted edits to the selected {document_type}. Follow these instructions exactly, but do not invent employers, dates, degrees, metrics, tools, or achievements. Preserve truthful candidate evidence and keep the document ATS-friendly.\n\n"
            "## Requested edits\n"
            f"{instructions.strip()}\n\n"
            "## Hard rules\n"
            "- Apply the user's requested changes when they are compatible with the available evidence.\n"
            "- If a requested emphasis is unsupported, keep it modest or omit it.\n"
            "- Return only the revised document text.\n"
        )

    def _quality_report_ready_text(self) -> str:
        if not hasattr(self, "quality_report_edit"):
            return ""
        text = self.quality_report_edit.toPlainText().strip()
        if not text or text == "No report yet.":
            return ""
        return text

    def _set_review_action_buttons_enabled(self, enabled: bool) -> None:
        for name in ("run_quality_button", "run_ai_review_button", "improve_quality_button", "apply_custom_edit_button", "refresh_page_break_sections_button", "insert_page_break_button", "remove_page_breaks_button"):
            button = getattr(self, name, None)
            if button is not None:
                button.setEnabled(enabled)

    def _start_ai_quality_review(self) -> None:
        document_type, text = self._selected_review_document_text()
        if not text.strip():
            QMessageBox.warning(self, "Cannot run AI review", f"Generate a {document_type} first.")
            return
        ok, message = self._validate_profile()
        if not ok:
            QMessageBox.warning(self, "Cannot run AI review", message)
            return
        ok, message = self._validate_job_details()
        if not ok:
            QMessageBox.warning(self, "Cannot run AI review", message)
            return
        heuristic_report = self._quality_report_ready_text()
        if not heuristic_report:
            QMessageBox.warning(self, "Run quality check first", "Run the rule-based Quality Check before AI Quality Review.")
            return
        if self._ai_review_running or self._improvement_running:
            QMessageBox.information(self, "Review task running", "Wait for the current review or improvement task to finish.")
            return

        request = self._build_review_generation_request(document_type)
        if not self._ensure_ai_ready(request.ai_settings, "AI quality review"):
            return

        self._ai_review_running = True
        self._ai_review_job_id += 1
        job_id = self._ai_review_job_id
        self._set_review_action_buttons_enabled(False)
        self.ai_review_status_label.setText(f"Running AI quality review with {request.ai_settings.provider} / {request.ai_settings.ollama_model}...")
        self.ai_quality_review_edit.setPlainText("Working. The AI is reading the selected document, job details, candidate evidence, and quality report.")
        self._write_qt_log(f"AI quality review started: job_id={job_id}, type={document_type}")

        thread = threading.Thread(
            target=self._run_ai_review_worker,
            args=(job_id, request, text, heuristic_report),
            daemon=True,
        )
        thread.start()

    def _run_ai_review_worker(self, job_id: int, request: GenerationRequest, document_text: str, heuristic_report: str) -> None:
        try:
            result = self.ai_service.review_document(
                request=request,
                generated_document=document_text,
                heuristic_report=heuristic_report,
            )
            if result is None:
                raise RuntimeError("AI service returned no review text.")
        except Exception as exc:  # noqa: BLE001
            self._write_qt_log("AI quality review failed:\n" + traceback.format_exc())
            self.ai_review_signals.failed.emit(job_id, str(exc))
            return
        self._write_qt_log(f"AI quality review finished: job_id={job_id}, chars={len(str(result))}")
        self.ai_review_signals.finished.emit(job_id, str(result))

    def _ai_review_finished(self, job_id: int, text: str) -> None:
        if job_id != self._ai_review_job_id:
            return
        self._ai_review_running = False
        self._set_review_action_buttons_enabled(True)
        self.ai_quality_review = text.strip()
        self.ai_quality_review_edit.setPlainText(self.ai_quality_review or "AI review returned empty text.")
        self.ai_review_status_label.setText("AI quality review complete. Use Improve with Quality Fixes only after reading it.")
        self._update_workspace_status("AI quality review complete. Save the workspace to preserve it.")

    def _ai_review_failed(self, job_id: int, error: str) -> None:
        if job_id != self._ai_review_job_id:
            return
        self._ai_review_running = False
        self._set_review_action_buttons_enabled(True)
        self.ai_review_status_label.setText("AI quality review failed.")
        self.ai_quality_review_edit.setPlainText("AI quality review failed. Check data/logs/qt_gui.log for details.")
        QMessageBox.critical(self, "AI review failed", error)

    def _start_custom_ai_edit(self) -> None:
        document_type, text = self._selected_review_document_text()
        if not text.strip():
            QMessageBox.warning(self, "Cannot edit document", f"Generate a {document_type} first.")
            return
        ok, message = self._validate_profile()
        if not ok:
            QMessageBox.warning(self, "Cannot edit document", message)
            return
        ok, message = self._validate_job_details()
        if not ok:
            QMessageBox.warning(self, "Cannot edit document", message)
            return
        instructions = self._manual_edit_instructions_text()
        if not instructions:
            QMessageBox.warning(self, "No edit instructions", "Write specific instructions before applying an AI edit.")
            return
        if self._ai_review_running or self._improvement_running:
            QMessageBox.information(self, "Review task running", "Wait for the current review or improvement task to finish.")
            return

        answer = QMessageBox.question(
            self,
            "Apply AI edit instructions",
            f"Apply the instructions to the selected {document_type}? This replaces the current generated {document_type} text. Save your workspace first if you want to preserve the current version.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        self._improvement_running = True
        self._improvement_job_id += 1
        self._improvement_reason = "AI edit instructions"
        job_id = self._improvement_job_id
        request = self._build_review_generation_request(document_type)
        if not self._ensure_ai_ready(request.ai_settings, "AI edit instructions"):
            self._improvement_running = False
            return
        heuristic_report = self._manual_instruction_report(document_type, instructions)
        ai_review = self.ai_quality_review_edit.toPlainText().strip() if hasattr(self, "ai_quality_review_edit") else self.ai_quality_review
        if ai_review.startswith("No AI review") or ai_review.startswith("AI review cleared") or ai_review.startswith("Improvement complete"):
            ai_review = ""

        self._set_review_action_buttons_enabled(False)
        self.review_status_label.setText(f"Applying AI edit instructions to {document_type} with {request.ai_settings.provider} / {request.ai_settings.ollama_model}...")
        self.ai_review_status_label.setText("AI edit running. Do not close the app.")
        self.output_edit.setPlainText(f"Applying AI edit instructions to {document_type}. The revised text will replace this screen when finished.")
        self.document_type_combo.setCurrentText(document_type)
        self.show_page("Generate")
        self._write_qt_log(f"Manual AI edit started: job_id={job_id}, type={document_type}")

        thread = threading.Thread(
            target=self._run_improvement_worker,
            args=(job_id, request, text, heuristic_report, ai_review),
            daemon=True,
        )
        thread.start()

    def _start_quality_improvement(self) -> None:
        document_type, text = self._selected_review_document_text()
        if not text.strip():
            QMessageBox.warning(self, "Cannot improve document", f"Generate a {document_type} first.")
            return
        ok, message = self._validate_profile()
        if not ok:
            QMessageBox.warning(self, "Cannot improve document", message)
            return
        ok, message = self._validate_job_details()
        if not ok:
            QMessageBox.warning(self, "Cannot improve document", message)
            return
        heuristic_report = self._quality_report_ready_text()
        if not heuristic_report:
            QMessageBox.warning(self, "Run quality check first", "Run the rule-based Quality Check before improving the document.")
            return
        if self._ai_review_running or self._improvement_running:
            QMessageBox.information(self, "Review task running", "Wait for the current review or improvement task to finish.")
            return

        answer = QMessageBox.question(
            self,
            "Improve selected document",
            f"Improve the selected {document_type}? This replaces the current generated {document_type} text. Save your workspace first if you want to preserve the current version.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        self._improvement_running = True
        self._improvement_job_id += 1
        self._improvement_reason = "quality fixes"
        job_id = self._improvement_job_id
        request = self._build_review_generation_request(document_type)
        if not self._ensure_ai_ready(request.ai_settings, "quality improvement"):
            self._improvement_running = False
            return
        ai_review = self.ai_quality_review_edit.toPlainText().strip() if hasattr(self, "ai_quality_review_edit") else self.ai_quality_review
        if ai_review.startswith("No AI review") or ai_review.startswith("AI review cleared"):
            ai_review = ""

        self._set_review_action_buttons_enabled(False)
        self.review_status_label.setText(f"Improving {document_type} with {request.ai_settings.provider} / {request.ai_settings.ollama_model}...")
        self.ai_review_status_label.setText("Improvement running. Do not close the app.")
        self.output_edit.setPlainText(f"Improving {document_type} with quality fixes. The improved text will replace this screen when finished.")
        self.document_type_combo.setCurrentText(document_type)
        self.show_page("Generate")
        self._write_qt_log(f"Quality improvement started: job_id={job_id}, type={document_type}")

        thread = threading.Thread(
            target=self._run_improvement_worker,
            args=(job_id, request, text, heuristic_report, ai_review),
            daemon=True,
        )
        thread.start()

    def _run_improvement_worker(
        self,
        job_id: int,
        request: GenerationRequest,
        document_text: str,
        heuristic_report: str,
        ai_review: str,
    ) -> None:
        try:
            result = self.ai_service.improve_document(
                request=request,
                generated_document=document_text,
                heuristic_report=heuristic_report,
                ai_review=ai_review,
            )
            if result is None:
                raise RuntimeError("AI service returned no improved document.")
        except Exception as exc:  # noqa: BLE001
            self._write_qt_log("Quality improvement failed:\n" + traceback.format_exc())
            self.improve_signals.failed.emit(job_id, str(exc))
            return
        self._write_qt_log(f"Quality improvement finished: job_id={job_id}, chars={len(str(result))}")
        self.improve_signals.finished.emit(job_id, request.document_type, str(result))

    def _improvement_finished(self, job_id: int, document_type: str, text: str) -> None:
        if job_id != self._improvement_job_id:
            return
        self._improvement_running = False
        self._set_review_action_buttons_enabled(True)
        if document_type == "CV":
            self.generated_cv = text
        else:
            self.generated_covering_letter = text
        self.output_edit.setPlainText(text)
        if document_type == "CV" and hasattr(self, "section_order_list"):
            self._refresh_section_order_list()
        self.document_type_combo.setCurrentText(document_type)
        self.review_document_combo.setCurrentText(document_type)
        self._refresh_review_page_break_sections()
        reason = getattr(self, "_improvement_reason", "quality fixes")
        self.status_label.setText(f"{document_type} updated with {reason}. Run Quality Check again before exporting.")
        self.review_status_label.setText(f"Update complete using {reason}. Run Quality Check again before export.")
        self.ai_review_status_label.setText("Document updated. Previous AI review may no longer match the revised text.")
        self.ai_quality_review = ""
        self.ai_quality_review_edit.setPlainText("Document updated. Run AI Quality Review again if needed.")
        self.quality_report_edit.setPlainText("Document updated. Run Quality Check again to score the revised document.")
        self.review_score_label.setText("Needs new quality check")
        self._update_workspace_status(f"{document_type} improved. Save the workspace to preserve the updated document.")
        self.show_page("Generate")

    def _improvement_failed(self, job_id: int, error: str) -> None:
        if job_id != self._improvement_job_id:
            return
        self._improvement_running = False
        self._set_review_action_buttons_enabled(True)
        self.review_status_label.setText("Improvement failed.")
        self.ai_review_status_label.setText("Improvement failed.")
        QMessageBox.critical(self, "Improvement failed", error)

    def _selected_export_document_text(self) -> tuple[str, str]:
        document_type = self.export_document_combo.currentText() if hasattr(self, "export_document_combo") else "CV"
        if document_type == "CV":
            return document_type, self._document_with_current_section_order(self.generated_cv)
        return document_type, self.generated_covering_letter

    def _raw_selected_export_document_text(self) -> tuple[str, str]:
        document_type = self.export_document_combo.currentText() if hasattr(self, "export_document_combo") else "CV"
        if document_type == "CV":
            return document_type, self.generated_cv
        return document_type, self.generated_covering_letter

    def _current_section_order(self) -> list[str]:
        if not hasattr(self, "section_order_list"):
            return []
        return [self.section_order_list.item(index).text() for index in range(self.section_order_list.count())]

    def _document_with_current_section_order(self, text: str) -> str:
        order = self._current_section_order()
        if not order or not text.strip():
            return text
        return reorder_markdown_sections(text, order)

    def _refresh_section_order_list(self, preferred_order: list[str] | None = None) -> None:
        if not hasattr(self, "section_order_list"):
            return
        document_type, text = self._raw_selected_export_document_text() if hasattr(self, "export_document_combo") else ("CV", self.generated_cv)
        self.section_order_list.clear()
        if document_type != "CV":
            self.section_order_list.addItem("Covering letters usually do not need section reordering.")
            self.section_order_list.setEnabled(False)
            return
        self.section_order_list.setEnabled(True)
        sections = extract_markdown_sections(text)
        headings = [section.heading for section in sections]
        if preferred_order:
            preferred = [heading for heading in preferred_order if heading in headings]
            headings = preferred + [heading for heading in headings if heading not in preferred]
        if not headings:
            self.section_order_list.addItem("No level-2 sections found yet. Generate a CV first.")
            return
        for heading in headings:
            self.section_order_list.addItem(heading)

    def _move_section_order(self, direction: int) -> None:
        if not hasattr(self, "section_order_list") or not self.section_order_list.isEnabled():
            return
        row = self.section_order_list.currentRow()
        if row < 0:
            return
        new_row = row + direction
        if new_row < 0 or new_row >= self.section_order_list.count():
            return
        item = self.section_order_list.takeItem(row)
        self.section_order_list.insertItem(new_row, item)
        self.section_order_list.setCurrentRow(new_row)

    def _apply_section_order_to_document(self) -> None:
        document_type, text = self._raw_selected_export_document_text()
        if document_type != "CV":
            QMessageBox.information(self, "Section order", "Section reordering is intended for CV exports. Covering letters keep their paragraph order.")
            return
        if not text.strip():
            QMessageBox.warning(self, "No CV generated", "Generate a CV before changing section order.")
            return
        updated = self._document_with_current_section_order(text)
        self.generated_cv = updated
        self.output_edit.setPlainText(updated)
        self.document_type_combo.setCurrentText("CV")
        self._refresh_section_order_list()
        self.export_status_edit.setPlainText("CV section order applied. Run Review again if you changed the final layout substantially.")
        self._update_workspace_status("CV section order updated. Save the workspace to preserve the layout.")

    def _preview_ordered_document(self) -> None:
        document_type, text = self._selected_export_document_text()
        if not text.strip():
            QMessageBox.warning(self, "Nothing to preview", f"Generate a {document_type} first.")
            return
        dialog = QDialog(self)
        dialog.setWindowTitle(f"{document_type} Preview")
        dialog.setModal(False)
        dialog.resize(820, 720)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)
        title = QLabel(f"Preview: {document_type} | Template: {self.export_pdf_template_combo.currentText()} | Page size: {self.export_page_size_combo.currentText()}")
        title.setObjectName("CardTitle")
        title.setWordWrap(True)
        preview = QPlainTextEdit()
        preview.setReadOnly(True)
        preview.setPlainText(text)
        close_row = QHBoxLayout()
        close_row.addStretch(1)
        close_button = QPushButton("Close")
        close_button.setMinimumWidth(120)
        close_button.clicked.connect(dialog.accept)
        close_row.addWidget(close_button)
        layout.addWidget(title)
        layout.addWidget(preview, 1)
        layout.addLayout(close_row)
        dialog.exec()

    def _browse_export_dir(self) -> None:
        current = self.export_dir_edit.text().strip() if hasattr(self, "export_dir_edit") else str(exports_dir())
        selected = QFileDialog.getExistingDirectory(self, "Select export folder", current or str(exports_dir()))
        if selected:
            self.export_dir_edit.setText(selected)
            self.app_settings.last_export_dir = selected
            try:
                save_app_settings(self.app_settings)
            except Exception:
                self._write_qt_log("Could not persist last export directory:\n" + traceback.format_exc())

    def _export_root(self) -> Path:
        value = self.export_dir_edit.text().strip() if hasattr(self, "export_dir_edit") else str(exports_dir())
        return Path(value or str(exports_dir()))

    def _clean_filename_part(self, value: str, fallback: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9]+", "_", (value or "").strip()).strip("_")
        return cleaned or fallback

    def _quality_report_text(self) -> str:
        parts: list[str] = []
        if hasattr(self, "quality_report_edit"):
            text = self.quality_report_edit.toPlainText().strip()
            if text and text != "No report yet." and not text.startswith("Improvement complete"):
                parts.append(text)
        review_text = ""
        if hasattr(self, "ai_quality_review_edit"):
            review_text = self.ai_quality_review_edit.toPlainText().strip()
        review_text = review_text or self.ai_quality_review.strip()
        if review_text and not review_text.startswith("No AI review") and not review_text.startswith("AI review cleared") and not review_text.startswith("Improvement complete"):
            if review_text.lstrip().startswith("# AI Quality Review"):
                parts.append(review_text)
            else:
                parts.append("# AI Quality Review\n\n" + review_text)
        if parts:
            return "\n\n---\n\n".join(parts)
        return "No quality report exported from ResuBuilder."

    def _export_settings(self) -> tuple[str, str]:
        template = self.export_pdf_template_combo.currentText() if hasattr(self, "export_pdf_template_combo") else "ATS Friendly"
        page_size = self.export_page_size_combo.currentText() if hasattr(self, "export_page_size_combo") else "A4"
        self.app_settings.pdf_template = template
        self.app_settings.pdf_page_size = page_size
        self.app_settings.last_export_dir = str(self._export_root())
        try:
            save_app_settings(self.app_settings)
        except Exception:
            self._write_qt_log("Could not persist export settings:\n" + traceback.format_exc())
        return template, page_size

    def _save_selected_markdown(self) -> None:
        document_type, text = self._selected_export_document_text()
        if not text.strip():
            QMessageBox.warning(self, "Cannot save Markdown", f"Generate a {document_type} first.")
            return
        metadata = self._workspace_metadata()
        company = self._clean_filename_part(metadata.get("target_company", ""), "company")
        role = self._clean_filename_part(metadata.get("target_role", ""), "role")
        prefix = "CV" if document_type == "CV" else "Covering_Letter"
        default_path = self._export_root() / f"{prefix}_{company}_{role}.md"
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Markdown", str(default_path), "Markdown files (*.md);;Text files (*.txt)")
        if not file_path:
            return
        try:
            path = Path(file_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text.strip() + "\n", encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            self._write_qt_log("Markdown save failed:\n" + traceback.format_exc())
            QMessageBox.critical(self, "Markdown save failed", str(exc))
            return
        self.export_status_edit.setPlainText(f"Markdown saved:\n{path}")

    def _export_selected_pdf(self) -> None:
        document_type, text = self._selected_export_document_text()
        if not text.strip():
            QMessageBox.warning(self, "Cannot export PDF", f"Generate a {document_type} first.")
            return
        template, page_size = self._export_settings()
        metadata = self._workspace_metadata()
        company = self._clean_filename_part(metadata.get("target_company", ""), "company")
        role = self._clean_filename_part(metadata.get("target_role", ""), "role")
        prefix = "CV" if document_type == "CV" else "Covering_Letter"
        default_path = self._export_root() / f"{prefix}_{company}_{role}.pdf"
        file_path, _ = QFileDialog.getSaveFileName(self, "Export PDF", str(default_path), "PDF files (*.pdf)")
        if not file_path:
            return
        try:
            saved_path = export_markdown_to_pdf(text, file_path, page_size=page_size, template_name=template)
        except Exception as exc:  # noqa: BLE001
            self._write_qt_log("PDF export failed:\n" + traceback.format_exc())
            QMessageBox.critical(self, "PDF export failed", str(exc))
            return
        self.export_status_edit.setPlainText(f"PDF exported:\n{saved_path}")
        QMessageBox.information(self, "PDF exported", f"PDF exported to:\n{saved_path}")

    def _export_application_package(self) -> None:
        if not self.generated_cv.strip():
            QMessageBox.warning(self, "Cannot export package", "Generate the CV first.")
            return
        if not self.generated_covering_letter.strip():
            QMessageBox.warning(self, "Cannot export package", "Generate the covering letter first.")
            return
        template, page_size = self._export_settings()
        export_root = self._export_root()
        workspace_metadata = self._workspace_metadata() if hasattr(self, "workspace_name_edit") else {}
        metadata = {
            "application_name": workspace_metadata.get("application_name") or f"{workspace_metadata.get('target_company', '')} {workspace_metadata.get('target_role', '')}".strip(),
            "target_company": workspace_metadata.get("target_company") or "company",
            "target_role": workspace_metadata.get("target_role") or "role",
            "created_at": "",
            "modified_at": datetime.now().isoformat(timespec="seconds"),
        }
        snapshot = {
            "source": "ResuBuilder",
            "profile": self._build_profile().__dict__,
            "job_details": self._job_details_dict(),
            "job_description": self._combined_job_brief(),
            "generated_cv": self._document_with_current_section_order(self.generated_cv) if hasattr(self, "section_order_list") else self.generated_cv,
            "generated_covering_letter": self.generated_covering_letter,
            "quality_report": self._quality_report_text(),
            "ai_quality_review": self.ai_quality_review,
            "manual_edit_instructions": self._manual_edit_instructions_text(),
            "settings": {
                "provider": self.app_settings.ai_provider,
                "ollama_model": self.app_settings.ollama_model,
                "output_language": self._selected_output_language(),
                "pdf_template": template,
                "pdf_page_size": page_size,
            },
        }
        try:
            package_dir = export_application_package(
                export_root=export_root,
                metadata=metadata,
                cv_markdown=self._document_with_current_section_order(self.generated_cv) if hasattr(self, "section_order_list") else self.generated_cv,
                covering_letter_markdown=self.generated_covering_letter,
                quality_report_markdown=self._quality_report_text(),
                application_snapshot=snapshot,
                page_size=page_size,
                template_name=template,
            )
        except Exception as exc:  # noqa: BLE001
            self._write_qt_log("Application package export failed:\n" + traceback.format_exc())
            QMessageBox.critical(self, "Package export failed", str(exc))
            return
        self.export_status_edit.setPlainText(
            "Application package exported:\n"
            f"{package_dir}\n\n"
            "Expected files:\n"
            "- CV PDF\n"
            "- Covering letter PDF\n"
            "- cv.md\n"
            "- covering_letter.md\n"
            "- quality_report.md\n"
            "- application_summary.json"
        )
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(package_dir.resolve())))

    def _open_export_dir(self) -> None:
        path = self._export_root()
        path.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.resolve())))

    def _normalized_theme(self, theme_name: str) -> str:
        theme = (theme_name or "Dark blue").strip()
        if theme == "Soft Blue":
            return "Dark blue"
        if theme not in set(THEME_OPTIONS):
            return "Dark blue"
        return theme

    def _preview_selected_theme(self) -> None:
        theme = self.settings_theme_combo.currentText() if hasattr(self, "settings_theme_combo") else "Dark blue"
        self._apply_theme_styles(theme)
        if hasattr(self, "settings_status_label"):
            self.settings_status_label.setText("Theme preview applied. Click Save Settings to remember it after restart.")

    def _browse_settings_workspace_dir(self) -> None:
        current = self.settings_workspace_dir_edit.text().strip() if hasattr(self, "settings_workspace_dir_edit") else str(applications_dir())
        selected = QFileDialog.getExistingDirectory(self, "Select workspace folder", current or str(applications_dir()))
        if selected and hasattr(self, "settings_workspace_dir_edit"):
            self.settings_workspace_dir_edit.setText(selected)

    def _browse_settings_export_dir(self) -> None:
        current = self.settings_export_dir_edit.text().strip() if hasattr(self, "settings_export_dir_edit") else str(exports_dir())
        selected = QFileDialog.getExistingDirectory(self, "Select export folder", current or str(exports_dir()))
        if selected and hasattr(self, "settings_export_dir_edit"):
            self.settings_export_dir_edit.setText(selected)

    def _sync_settings_from_controls(self) -> None:
        if hasattr(self, "settings_provider_combo"):
            self.app_settings.ai_provider = self.settings_provider_combo.currentText()
        if hasattr(self, "settings_generation_mode_combo"):
            self.app_settings.generation_mode = self.settings_generation_mode_combo.currentText()
        if hasattr(self, "settings_ollama_url_edit"):
            self.app_settings.ollama_base_url = self.settings_ollama_url_edit.text().strip() or "http://localhost:11434"
        if hasattr(self, "settings_ollama_model_combo"):
            self.app_settings.ollama_model = self.settings_ollama_model_combo.currentText().strip() or "qwen3:8b"
        if hasattr(self, "settings_openai_model_combo"):
            self.app_settings.openai_model = self.settings_openai_model_combo.currentText().strip() or "gpt-4.1-mini"
        if hasattr(self, "settings_timeout_spin"):
            self.app_settings.timeout_seconds = int(self.settings_timeout_spin.value())
        if hasattr(self, "settings_template_combo"):
            self.app_settings.template_name = self.settings_template_combo.currentText()
        if hasattr(self, "settings_output_language_combo"):
            self.app_settings.output_language = self.settings_output_language_combo.currentText()
        elif hasattr(self, "output_language_combo"):
            self.app_settings.output_language = self.output_language_combo.currentText()
        if hasattr(self, "settings_pdf_template_combo"):
            self.app_settings.pdf_template = self.settings_pdf_template_combo.currentText()
        if hasattr(self, "settings_page_size_combo"):
            self.app_settings.pdf_page_size = self.settings_page_size_combo.currentText()
        if hasattr(self, "settings_workspace_dir_edit"):
            self.app_settings.last_workspace_dir = self.settings_workspace_dir_edit.text().strip()
        if hasattr(self, "settings_export_dir_edit"):
            self.app_settings.last_export_dir = self.settings_export_dir_edit.text().strip()
        if hasattr(self, "settings_theme_combo"):
            self.app_settings.ui_theme = self._normalized_theme(self.settings_theme_combo.currentText())

    def _apply_settings_to_existing_controls(self) -> None:
        if hasattr(self, "template_combo"):
            self.template_combo.setCurrentText(getattr(self.app_settings, "template_name", "ATS Friendly"))
        if hasattr(self, "output_language_combo"):
            self.output_language_combo.setCurrentText(getattr(self.app_settings, "output_language", "English"))
        if hasattr(self, "export_pdf_template_combo"):
            self.export_pdf_template_combo.setCurrentText(getattr(self.app_settings, "pdf_template", "ATS Friendly"))
        if hasattr(self, "export_page_size_combo"):
            self.export_page_size_combo.setCurrentText(getattr(self.app_settings, "pdf_page_size", "A4"))
        if hasattr(self, "export_dir_edit") and getattr(self.app_settings, "last_export_dir", ""):
            self.export_dir_edit.setText(getattr(self.app_settings, "last_export_dir", ""))
        self._apply_theme_styles(getattr(self.app_settings, "ui_theme", "Dark blue"))

    def _reset_settings(self) -> None:
        response = QMessageBox.question(
            self,
            "Reset settings",
            "Reset app settings to defaults? This will not delete profiles, workspaces, generated documents, or exported packages.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if response != QMessageBox.StandardButton.Yes:
            return
        self.app_settings = AppSettings()
        if hasattr(self, "settings_provider_combo"):
            self.settings_provider_combo.setCurrentText(getattr(self.app_settings, "ai_provider", "Ollama Local"))
            self.settings_generation_mode_combo.setCurrentText(getattr(self.app_settings, "generation_mode", "Balanced"))
            self.settings_ollama_url_edit.setText(getattr(self.app_settings, "ollama_base_url", "http://localhost:11434"))
            self.settings_ollama_model_combo.setCurrentText(getattr(self.app_settings, "ollama_model", "qwen3:8b"))
            self.settings_openai_model_combo.setCurrentText(getattr(self.app_settings, "openai_model", "gpt-4.1-mini"))
            self.settings_timeout_spin.setValue(int(getattr(self.app_settings, "timeout_seconds", 120)))
            self.settings_template_combo.setCurrentText(getattr(self.app_settings, "template_name", "ATS Friendly"))
            self.settings_pdf_template_combo.setCurrentText(getattr(self.app_settings, "pdf_template", "ATS Friendly"))
            self.settings_page_size_combo.setCurrentText(getattr(self.app_settings, "pdf_page_size", "A4"))
            if hasattr(self, "settings_output_language_combo"):
                self.settings_output_language_combo.setCurrentText(getattr(self.app_settings, "output_language", "English"))
            self.settings_workspace_dir_edit.setText(getattr(self.app_settings, "last_workspace_dir", "") or str(applications_dir()))
            self.settings_export_dir_edit.setText(getattr(self.app_settings, "last_export_dir", "") or str(exports_dir()))
            self.settings_theme_combo.setCurrentText(self._normalized_theme(getattr(self.app_settings, "ui_theme", "Dark blue")))
        self._apply_settings_to_existing_controls()
        try:
            save_app_settings(self.app_settings)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Settings", f"Could not reset settings: {exc}")
            return
        if hasattr(self, "settings_status_label"):
            self.settings_status_label.setText("Settings reset to defaults and saved.")
        QMessageBox.information(self, "Settings", "Settings reset to defaults.")

    def _save_settings(self) -> None:
        self._sync_settings_from_controls()
        self._apply_settings_to_existing_controls()
        try:
            save_app_settings(self.app_settings)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Settings", f"Could not save settings: {exc}")
            return
        if hasattr(self, "settings_status_label"):
            self.settings_status_label.setText("Settings saved. Generation, review, export, and theme defaults now use these values.")
        QMessageBox.information(self, "Settings", "Settings saved.")

    def _show_about(self) -> None:
        QMessageBox.information(
            self,
            "About ResuBuilder",
            "ResuBuilder is a desktop application for creating tailored CVs and covering letters.\n\n"
            "It helps structure candidate evidence, analyze job fit, generate documents with local or cloud AI, review quality, and export complete application packages.",
        )


def run_qt_app() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("ResuBuilder")
    window = ResuBuilderQtApp()
    window.show()
    sys.exit(app.exec())
