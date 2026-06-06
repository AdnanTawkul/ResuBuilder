from __future__ import annotations

import json
import re
import sys
import threading
import traceback
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, QRegularExpression, Qt, QUrl, Signal
from PySide6.QtGui import QAction, QDesktopServices, QRegularExpressionValidator
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
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
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .ai_service import AIService
from .models import AISettings, CandidateProfile, GenerationRequest
from .application_package_exporter import export_application_package
from .pdf_exporter import export_markdown_to_pdf
from .pdf_templates import get_pdf_template_names
from .quality_checker import analyze_document, format_quality_report
from .settings_manager import AppSettings, load_app_settings, save_app_settings
from .storage import load_json, save_json
from .templates import get_template_names
from .workspace_manager import (
    ensure_applications_dir,
    load_application_snapshot,
    save_application_snapshot,
    suggested_application_filename,
)
from .qt_theme import DARK_BLUE_QSS, theme_qss


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

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


class QMessageBox:
    """Silent replacement for QMessageBox convenience dialogs.

    Native QMessageBox convenience functions trigger the Windows system notification sound.
    The Qt experiment uses this small modal dialog instead so save/load/generate notices stay quiet.
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
    misuse and can make the experimental app appear to close without a useful error when the worker
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


class Card(QFrame):
    def __init__(self, title: str = "", subtitle: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
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


class ResuBuilderQtApp(QMainWindow):
    """Experimental PySide6 interface.

    This file intentionally lives beside the existing Tk/CustomTkinter GUI. Do not delete app.py or gui.py
    until the Qt interface reaches full feature parity.
    """

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("ResuBuilder Qt Experiment")
        self.resize(1380, 860)
        self.setMinimumSize(1180, 760)

        self.ai_service = AIService()
        self.app_settings: AppSettings = load_app_settings()
        self.generated_cv = ""
        self.generated_covering_letter = ""
        self.job_fit_analysis = ""
        self.ai_quality_review = ""
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

        self.setStyleSheet(theme_qss(getattr(self.app_settings, "ui_theme", "Dark blue")))
        self._build_menu()
        self._build_shell()
        self.show_page("Welcome")

    def _build_menu(self) -> None:
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("File")
        new_workspace_action = QAction("New Application Workspace", self)
        new_workspace_action.triggered.connect(self._new_workspace)
        open_workspace_action = QAction("Load Application Workspace...", self)
        open_workspace_action.triggered.connect(self._load_workspace)
        save_workspace_action = QAction("Save Application Workspace", self)
        save_workspace_action.triggered.connect(self._save_workspace)
        save_as_workspace_action = QAction("Save Application Workspace As...", self)
        save_as_workspace_action.triggered.connect(self._save_workspace_as)
        quit_action = QAction("Exit", self)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(new_workspace_action)
        file_menu.addAction(open_workspace_action)
        file_menu.addAction(save_workspace_action)
        file_menu.addAction(save_as_workspace_action)
        file_menu.addSeparator()
        file_menu.addAction(quit_action)

        workflow_menu = menu_bar.addMenu("Workflow")
        for page_name in ["Welcome", "Workspace", "Profile", "Evidence", "Job", "Generate", "Review", "Export", "Settings"]:
            action = QAction(page_name, self)
            action.triggered.connect(lambda checked=False, name=page_name: self.show_page(name))
            workflow_menu.addAction(action)

        help_menu = menu_bar.addMenu("Help")
        about_action = QAction("About Qt Experiment", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

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

        brand = QLabel("ResuBuilder")
        brand.setObjectName("BrandTitle")
        subtitle = QLabel("Qt GUI experiment")
        subtitle.setObjectName("BrandSubtitle")
        sidebar_layout.addWidget(brand)
        sidebar_layout.addWidget(subtitle)
        sidebar_layout.addSpacing(20)

        for page_name in ["Welcome", "Workspace", "Profile", "Evidence", "Job", "Generate", "Review", "Export", "Settings"]:
            button = QPushButton(page_name)
            button.setObjectName("NavButton")
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda checked=False, name=page_name: self.show_page(name))
            self.page_buttons[page_name] = button
            sidebar_layout.addWidget(button)

        sidebar_layout.addStretch(1)
        warning = QLabel("Experimental branch.\nKeep the old GUI alive until Qt reaches feature parity.")
        warning.setObjectName("WarningText")
        warning.setWordWrap(True)
        sidebar_layout.addWidget(warning)

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
        self.pages["Settings"] = self._build_settings_page()

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
            "A modern experiment shell for creating tailored CVs and covering letters with local AI.",
        )

        hero = QFrame()
        hero.setObjectName("HeroCard")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(28, 28, 28, 28)
        hero_layout.setSpacing(18)

        logo = QLabel("RB")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setFixedSize(78, 78)
        logo.setStyleSheet(
            "background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #ff7a59,stop:0.45 #ec4899,stop:1 #7c3aed);"
            "border-radius: 22px; color: white; font-size: 26px; font-weight: 900;"
        )
        hero_title = QLabel("Build stronger applications without losing truth control.")
        hero_title.setObjectName("PageTitle")
        hero_text = QLabel(
            "This Qt branch is a controlled UI experiment. The backend stays untouched while we test whether PySide6 can deliver the modern card-based interface you want."
        )
        hero_text.setObjectName("PageSubtitle")
        hero_text.setWordWrap(True)

        start_button = QPushButton("Start with Profile")
        start_button.setObjectName("PrimaryButton")
        start_button.setCursor(Qt.CursorShape.PointingHandCursor)
        start_button.clicked.connect(lambda: self.show_page("Profile"))

        hero_layout.addWidget(logo)
        hero_layout.addWidget(hero_title)
        hero_layout.addWidget(hero_text)
        hero_layout.addWidget(start_button, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(hero)

        card_row = QGridLayout()
        card_row.setSpacing(18)
        card_row.addWidget(Card("1. Profile", "Validate contact information and capture the candidate story."), 0, 0)
        card_row.addWidget(Card("2. Evidence", "Structure projects, tools, methods, and outcomes before generation."), 0, 1)
        card_row.addWidget(Card("3. Job", "Break the job post into company, role, responsibilities, and requirements."), 0, 2)
        card_row.addWidget(Card("4. Generate", "Use Ollama or OpenAI through the existing AI service layer."), 1, 0)
        layout.addLayout(card_row)
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
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
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

        evidence = Card("Evidence snapshot", "This is not the final evidence builder. It is enough to prove the Qt generation flow.")
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

        save_profile_button = QPushButton("Save Profile")
        save_profile_button.clicked.connect(self._save_current_profile)

        load_profile_button = QPushButton("Load Saved Profile")
        load_profile_button.clicked.connect(self._load_saved_profile)

        import_profile_button = QPushButton("Import Profile JSON")
        import_profile_button.clicked.connect(self._import_profile_json)

        export_profile_button = QPushButton("Export Profile JSON")
        export_profile_button.clicked.connect(self._export_profile_json)

        continue_button = QPushButton("Continue to Evidence")
        continue_button.clicked.connect(lambda: self.show_page("Evidence"))

        action_row.addWidget(validate_button)
        action_row.addWidget(save_profile_button)
        action_row.addWidget(load_profile_button)
        action_row.addWidget(import_profile_button)
        action_row.addWidget(export_profile_button)
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
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

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
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

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
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

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

        self.generate_button = QPushButton("Generate Document")
        self.generate_button.setObjectName("PrimaryButton")
        self.generate_button.setMinimumHeight(48)
        self.generate_button.setMinimumWidth(180)
        self.generate_button.clicked.connect(self._start_generation)

        self._prepare_form_control(self.document_type_combo, min_width=240)
        self._prepare_form_control(self.template_combo, min_width=280)
        self._add_labeled_field(controls_grid, 0, 0, "Document", self.document_type_combo)
        self._add_labeled_field(controls_grid, 0, 1, "Template", self.template_combo)
        controls_grid.addWidget(self.generate_button, 0, 2, alignment=Qt.AlignmentFlag.AlignBottom)
        controls.layout.addLayout(controls_grid)
        content_layout.addWidget(controls)

        output_card = QFrame()
        output_card.setObjectName("OutputCard")
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
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        content = QWidget()
        content.setObjectName("ScrollContent")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 14, 0)
        content_layout.setSpacing(20)

        controls = Card(
            "Quality review workflow",
            "Use the rule-based checker for reliable basics. Then run AI review for strategic critique, or improve the selected document using the quality report.",
        )
        row = QHBoxLayout()
        row.setSpacing(12)
        self.review_document_combo = QComboBox()
        self.review_document_combo.addItems(["CV", "Covering Letter"])
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

        row.addWidget(QLabel("Document"))
        row.addWidget(self.review_document_combo)
        row.addWidget(self.run_quality_button)
        row.addWidget(self.run_ai_review_button)
        row.addWidget(self.improve_quality_button)
        row.addWidget(show_button)
        row.addStretch(1)
        controls.layout.addLayout(row)
        content_layout.addWidget(controls)

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
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

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

        default_export_dir = getattr(self.app_settings, "last_export_dir", "") or str(Path("exports"))
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
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

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
        current_ollama_model = str(getattr(self.app_settings, "ollama_model", "qwen3:14b") or "qwen3:14b")
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

        for widget in (self.settings_template_combo, self.settings_pdf_template_combo, self.settings_page_size_combo):
            self._prepare_form_control(widget, min_width=360)

        self._add_labeled_field(document_grid, 0, 0, "Generation template", self.settings_template_combo)
        self._add_labeled_field(document_grid, 0, 1, "PDF template", self.settings_pdf_template_combo)
        self._add_labeled_field(document_grid, 1, 0, "PDF page size", self.settings_page_size_combo)
        document_card.layout.addLayout(document_grid)
        content_layout.addWidget(document_card)

        folders_card = Card("Default folders", "Remember where workspaces and exported application packages should be saved.")
        folders_grid = QGridLayout()
        folders_grid.setHorizontalSpacing(18)
        folders_grid.setVerticalSpacing(14)
        folders_grid.setColumnStretch(0, 1)

        self.settings_workspace_dir_edit = QLineEdit(getattr(self.app_settings, "last_workspace_dir", "") or str(Path("data/applications")))
        self.settings_export_dir_edit = QLineEdit(getattr(self.app_settings, "last_export_dir", "") or str(Path("exports")))
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

        appearance_card = Card("Appearance", "Switch the Qt interface theme. This only affects the experimental Qt app.")
        appearance_row = QHBoxLayout()
        appearance_row.setSpacing(12)
        self.settings_theme_combo = QComboBox()
        self.settings_theme_combo.addItems(["Light", "Dark", "Dark blue"])
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
        export_dir = self.export_dir_edit.text().strip() if hasattr(self, "export_dir_edit") else getattr(self.app_settings, "last_export_dir", "exports")
        return {
            "source": "PySide6 experiment",
            "metadata": metadata,
            "profile": self._profile_to_dict(),
            "structured_evidence_entries": [dict(entry) for entry in self.evidence_entries],
            "structured_evidence": self._structured_evidence_text(),
            "job_details": self._job_details_dict(),
            "job_description": self._combined_job_brief(),
            "generated_cv": self.generated_cv,
            "generated_covering_letter": self.generated_covering_letter,
            "quality_report": self._quality_report_text(),
            "ai_quality_review": self.ai_quality_review,
            "job_fit_analysis": self.job_fit_analysis,
            "ui_state": {
                "document_type": self.document_type_combo.currentText() if hasattr(self, "document_type_combo") else "CV",
                "template_name": template_name,
                "review_document": self.review_document_combo.currentText() if hasattr(self, "review_document_combo") else "CV",
                "export_document": self.export_document_combo.currentText() if hasattr(self, "export_document_combo") else "CV",
            },
            "settings": {
                "provider": self.app_settings.ai_provider,
                "ollama_model": self.app_settings.ollama_model,
                "openai_model": self.app_settings.openai_model,
                "generation_mode": self.app_settings.generation_mode,
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
            f"Quality report: {'yes' if self._quality_report_text() != 'No quality report exported from the Qt experiment.' else 'no'}\n"
            f"AI quality review: {'yes' if self.ai_quality_review.strip() else 'no'}"
        )

    def _suggest_workspace_path(self) -> Path:
        metadata = self._workspace_metadata()
        filename = suggested_application_filename(metadata.get("target_company", ""), metadata.get("target_role", ""))
        return ensure_applications_dir() / filename

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
        if hasattr(self, "job_fit_edit"):
            self.job_fit_edit.clear()
        if hasattr(self, "job_fit_status_label"):
            self.job_fit_status_label.setText("No job fit analysis yet. Generate without it only for quick tests.")
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
        self.workspace_path_edit.setText(str(saved_path))
        self._sync_export_metadata_from_workspace(force_empty_only=True)
        self._update_workspace_status("Workspace saved successfully.")
        QMessageBox.information(self, "Workspace saved", f"Application workspace saved to:\n{saved_path}")

    def _load_workspace(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Load application workspace",
            str(ensure_applications_dir()),
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
        self.workspace_path_edit.setText(str(self.current_workspace_path))
        self._update_workspace_status("Workspace loaded successfully.")
        self.show_page("Workspace")
        QMessageBox.information(self, "Workspace loaded", "Application workspace loaded into the Qt experiment.")

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
        # workspaces created during the PySide6 experiment.
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
        self.job_fit_analysis = str(snapshot.get("job_fit_analysis", "") or "")
        if hasattr(self, "job_fit_edit"):
            self.job_fit_edit.setPlainText(self.job_fit_analysis)
        if hasattr(self, "job_fit_status_label"):
            self.job_fit_status_label.setText("Job fit analysis loaded from workspace." if self.job_fit_analysis.strip() else "No job fit analysis saved in this workspace.")
        ui_state = snapshot.get("ui_state") or {}
        if ui_state.get("template_name"):
            self.template_combo.setCurrentText(str(ui_state.get("template_name")))
        if ui_state.get("review_document"):
            self.review_document_combo.setCurrentText(str(ui_state.get("review_document")))
        if ui_state.get("export_document"):
            self.export_document_combo.setCurrentText(str(ui_state.get("export_document")))
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
                "title": "Face-Aware FlowMag for Micro-Expression Spotting",
                "context": "Research-engineering project adapting self-supervised motion magnification to subtle facial micro-expression spotting on CASME II.",
                "tools": "Python, PyTorch, optical flow, CASME II, facial landmark masks, LBP-TOP, SVM",
                "methods": "Fine-tuned a pretrained FlowMag-style motion magnification model, added face-aware regularization with landmark-based masks, compared baseline inference, test-time adaptation, and face-aware training variants.",
                "outcome": "Produced a more spatially meaningful facial motion amplification pipeline and supported downstream micro-expression evaluation through motion analysis and feature-based classification.",
                "metrics": "Research repository, loss formulation, baseline comparison, motion error analysis, downstream LBP-TOP + SVM evaluation workflow.",
                "signals": "computer vision, deep learning, optical flow, model adaptation, transfer learning, algorithms, validation, neural engineering",
            }
        )
        QMessageBox.information(self, "Example loaded", "Example evidence loaded into the form. Review it, edit it, then click Add Evidence.")

    def _build_profile(self) -> CandidateProfile:
        return CandidateProfile(
            name=self.name_edit.text().strip(),
            email=self.email_edit.text().strip(),
            phone=self.phone_edit.text().strip(),
            location=self.location_edit.text().strip(),
            title=self.title_edit.text().strip(),
            summary=self.summary_edit.toPlainText().strip(),
            skills=self.skills_edit.toPlainText().strip(),
            projects=self.projects_edit.toPlainText().strip(),
            professions=self.professions_edit.toPlainText().strip(),
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
        QMessageBox.information(self, "Profile saved", "Profile saved to data/candidate_profile.json.")

    def _load_saved_profile(self) -> None:
        try:
            data = load_json()
        except Exception as exc:  # noqa: BLE001
            self._write_qt_log("Profile load failed:\n" + traceback.format_exc())
            QMessageBox.critical(self, "Profile load failed", str(exc))
            return
        if not data:
            QMessageBox.information(self, "No saved profile", "No saved profile was found in data/candidate_profile.json.")
            return
        self._apply_profile_data(data)
        QMessageBox.information(self, "Profile loaded", "Saved profile loaded into the Qt profile page.")

    def _import_profile_json(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import profile JSON",
            str(Path("data")),
            "JSON files (*.json);;All files (*.*)",
        )
        if not file_path:
            return
        try:
            data = json.loads(Path(file_path).read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("Profile JSON must contain a JSON object.")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Profile import failed", str(exc))
            return
        self._apply_profile_data(data)
        QMessageBox.information(self, "Profile imported", "Profile data imported. Validate and save it before generating.")

    def _export_profile_json(self) -> None:
        ok, message = self._validate_profile()
        if not ok:
            QMessageBox.warning(self, "Cannot export profile", message)
            return
        default_path = Path("data") / "candidate_profile_export.json"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export profile JSON",
            str(default_path),
            "JSON files (*.json)",
        )
        if not file_path:
            return
        try:
            path = Path(file_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(self._profile_to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            self._write_qt_log("Profile export failed:\n" + traceback.format_exc())
            QMessageBox.critical(self, "Profile export failed", str(exc))
            return
        QMessageBox.information(self, "Profile exported", f"Profile exported to:\n{path}")

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
            job_description=self._combined_job_brief(),
            template_name=self.template_combo.currentText(),
            document_type=document_type,
            ai_settings=self._settings_to_ai_settings(),
            job_fit_analysis=self.job_fit_analysis,
        )
        context = QtGenerationContext(document_type=document_type, request=request)

        self._generation_running = True
        self._generation_job_id += 1
        job_id = self._generation_job_id
        self.generate_button.setEnabled(False)
        self.status_label.setText(f"Generating {document_type} with {request.ai_settings.provider} / {request.ai_settings.ollama_model}...")
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
            log_dir = Path("data/logs")
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

    def _show_selected_review_document(self) -> None:
        document_type, text = self._selected_review_document_text()
        if not text.strip():
            QMessageBox.information(self, "No generated document", f"Generate a {document_type} before reviewing it.")
            return
        self.output_edit.setPlainText(text)
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
            job_description=self._combined_job_brief(),
            template_name=self.template_combo.currentText() if hasattr(self, "template_combo") else "ATS Friendly",
            document_type=document_type,
            ai_settings=self._settings_to_ai_settings(),
            job_fit_analysis=self.job_fit_analysis,
        )

    def _quality_report_ready_text(self) -> str:
        if not hasattr(self, "quality_report_edit"):
            return ""
        text = self.quality_report_edit.toPlainText().strip()
        if not text or text == "No report yet.":
            return ""
        return text

    def _set_review_action_buttons_enabled(self, enabled: bool) -> None:
        for name in ("run_quality_button", "run_ai_review_button", "improve_quality_button"):
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

        self._ai_review_running = True
        self._ai_review_job_id += 1
        job_id = self._ai_review_job_id
        request = self._build_review_generation_request(document_type)
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
        job_id = self._improvement_job_id
        request = self._build_review_generation_request(document_type)
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
        self.document_type_combo.setCurrentText(document_type)
        self.review_document_combo.setCurrentText(document_type)
        self.status_label.setText(f"{document_type} improved with quality fixes. Run Quality Check again before exporting.")
        self.review_status_label.setText("Improvement complete. Run Quality Check again before export.")
        self.ai_review_status_label.setText("Improvement complete. Previous AI review may no longer match the improved text.")
        self.ai_quality_review = ""
        self.ai_quality_review_edit.setPlainText("Improvement complete. Run AI Quality Review again if needed.")
        self.quality_report_edit.setPlainText("Improvement complete. Run Quality Check again to score the updated document.")
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
            return document_type, self.generated_cv
        return document_type, self.generated_covering_letter

    def _browse_export_dir(self) -> None:
        current = self.export_dir_edit.text().strip() if hasattr(self, "export_dir_edit") else str(Path("exports"))
        selected = QFileDialog.getExistingDirectory(self, "Select export folder", current or str(Path("exports")))
        if selected:
            self.export_dir_edit.setText(selected)
            self.app_settings.last_export_dir = selected
            try:
                save_app_settings(self.app_settings)
            except Exception:
                self._write_qt_log("Could not persist last export directory:\n" + traceback.format_exc())

    def _export_root(self) -> Path:
        value = self.export_dir_edit.text().strip() if hasattr(self, "export_dir_edit") else "exports"
        return Path(value or "exports")

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
        return "No quality report exported from the Qt experiment."

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
            "source": "PySide6 experiment",
            "profile": self._build_profile().__dict__,
            "job_details": self._job_details_dict(),
            "job_description": self._combined_job_brief(),
            "generated_cv": self.generated_cv,
            "generated_covering_letter": self.generated_covering_letter,
            "quality_report": self._quality_report_text(),
            "ai_quality_review": self.ai_quality_review,
            "settings": {
                "provider": self.app_settings.ai_provider,
                "ollama_model": self.app_settings.ollama_model,
                "pdf_template": template,
                "pdf_page_size": page_size,
            },
        }
        try:
            package_dir = export_application_package(
                export_root=export_root,
                metadata=metadata,
                cv_markdown=self.generated_cv,
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
        if theme not in {"Light", "Dark", "Dark blue"}:
            return "Dark blue"
        return theme

    def _preview_selected_theme(self) -> None:
        theme = self.settings_theme_combo.currentText() if hasattr(self, "settings_theme_combo") else "Dark blue"
        self.setStyleSheet(theme_qss(theme))
        if hasattr(self, "settings_status_label"):
            self.settings_status_label.setText("Theme preview applied. Click Save Settings to remember it after restart.")

    def _browse_settings_workspace_dir(self) -> None:
        current = self.settings_workspace_dir_edit.text().strip() if hasattr(self, "settings_workspace_dir_edit") else str(Path("data/applications"))
        selected = QFileDialog.getExistingDirectory(self, "Select workspace folder", current or str(Path("data/applications")))
        if selected and hasattr(self, "settings_workspace_dir_edit"):
            self.settings_workspace_dir_edit.setText(selected)

    def _browse_settings_export_dir(self) -> None:
        current = self.settings_export_dir_edit.text().strip() if hasattr(self, "settings_export_dir_edit") else str(Path("exports"))
        selected = QFileDialog.getExistingDirectory(self, "Select export folder", current or str(Path("exports")))
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
            self.app_settings.ollama_model = self.settings_ollama_model_combo.currentText().strip() or "qwen3:14b"
        if hasattr(self, "settings_openai_model_combo"):
            self.app_settings.openai_model = self.settings_openai_model_combo.currentText().strip() or "gpt-4.1-mini"
        if hasattr(self, "settings_timeout_spin"):
            self.app_settings.timeout_seconds = int(self.settings_timeout_spin.value())
        if hasattr(self, "settings_template_combo"):
            self.app_settings.template_name = self.settings_template_combo.currentText()
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
        if hasattr(self, "export_pdf_template_combo"):
            self.export_pdf_template_combo.setCurrentText(getattr(self.app_settings, "pdf_template", "ATS Friendly"))
        if hasattr(self, "export_page_size_combo"):
            self.export_page_size_combo.setCurrentText(getattr(self.app_settings, "pdf_page_size", "A4"))
        if hasattr(self, "export_dir_edit") and getattr(self.app_settings, "last_export_dir", ""):
            self.export_dir_edit.setText(getattr(self.app_settings, "last_export_dir", ""))
        self.setStyleSheet(theme_qss(getattr(self.app_settings, "ui_theme", "Dark blue")))

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
            self.settings_ollama_model_combo.setCurrentText(getattr(self.app_settings, "ollama_model", "qwen3:14b"))
            self.settings_openai_model_combo.setCurrentText(getattr(self.app_settings, "openai_model", "gpt-4.1-mini"))
            self.settings_timeout_spin.setValue(int(getattr(self.app_settings, "timeout_seconds", 120)))
            self.settings_template_combo.setCurrentText(getattr(self.app_settings, "template_name", "ATS Friendly"))
            self.settings_pdf_template_combo.setCurrentText(getattr(self.app_settings, "pdf_template", "ATS Friendly"))
            self.settings_page_size_combo.setCurrentText(getattr(self.app_settings, "pdf_page_size", "A4"))
            self.settings_workspace_dir_edit.setText(getattr(self.app_settings, "last_workspace_dir", "") or str(Path("data/applications")))
            self.settings_export_dir_edit.setText(getattr(self.app_settings, "last_export_dir", "") or str(Path("exports")))
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
            "About ResuBuilder Qt Experiment",
            "This is an experimental PySide6 interface for ResuBuilder.\n\n"
            "It should prove the modern UI direction without replacing the working Tk/CustomTkinter app yet.",
        )


def run_qt_app() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("ResuBuilder")
    window = ResuBuilderQtApp()
    window.show()
    sys.exit(app.exec())
