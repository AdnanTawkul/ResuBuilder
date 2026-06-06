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
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QScrollArea,
    QSizePolicy,
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
from .qt_theme import DARK_BLUE_QSS


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


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
        self._generation_running = False
        self._generation_job_id = 0
        self.generation_signals = GenerationSignals()
        self.generation_signals.finished.connect(self._generation_finished)
        self.generation_signals.failed.connect(self._generation_failed)

        self.page_buttons: dict[str, QPushButton] = {}
        self.pages: dict[str, QWidget] = {}

        self.setStyleSheet(DARK_BLUE_QSS)
        self._build_menu()
        self._build_shell()
        self.show_page("Welcome")

    def _build_menu(self) -> None:
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("File")
        quit_action = QAction("Exit", self)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        workflow_menu = menu_bar.addMenu("Workflow")
        for page_name in ["Welcome", "Profile", "Generate", "Review", "Export", "Settings"]:
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

        for page_name in ["Welcome", "Profile", "Generate", "Review", "Export", "Settings"]:
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
        self.stack.setContentsMargins(0, 0, 0, 0)

        self.pages["Welcome"] = self._build_welcome_page()
        self.pages["Profile"] = self._build_profile_page()
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
        card_row.addWidget(Card("2. Generate", "Use Ollama or OpenAI through the existing AI service layer."), 0, 1)
        card_row.addWidget(Card("3. Prove the UI", "Only after the prototype works do we wire review, export, and workspace logic."), 0, 2)
        layout.addLayout(card_row)
        layout.addStretch(1)
        return page

    def _build_profile_page(self) -> QWidget:
        page, layout = self._page_container(
            "Profile",
            "Collect candidate data. This first Qt pass validates phone and email before generation.",
        )

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
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

        continue_button = QPushButton("Continue to Generate")
        continue_button.clicked.connect(lambda: self.show_page("Generate"))

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

    def _build_generate_page(self) -> QWidget:
        page, layout = self._page_container(
            "Generate",
            "Generate a CV or covering letter through the existing AIService. This proves the Qt shell can use the backend.",
        )

        controls = Card("Generation controls", "Use Ollama first. Keep prompts conservative while testing the new GUI.")
        row = QHBoxLayout()
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
        self.generate_button.clicked.connect(self._start_generation)
        row.addWidget(QLabel("Document"))
        row.addWidget(self.document_type_combo)
        row.addWidget(QLabel("Template"))
        row.addWidget(self.template_combo)
        row.addWidget(self.generate_button)
        row.addStretch(1)
        controls.layout.addLayout(row)
        layout.addWidget(controls)

        job_card = Card("Job description", "Paste the target job. The stronger this input, the better the output.")
        self.job_description_edit = QTextEdit()
        self.job_description_edit.setMinimumHeight(160)
        job_card.layout.addWidget(self.job_description_edit)
        layout.addWidget(job_card)

        output_card = QFrame()
        output_card.setObjectName("OutputCard")
        output_layout = QVBoxLayout(output_card)
        output_layout.setContentsMargins(22, 20, 22, 20)
        output_layout.setSpacing(12)
        output_title = QLabel("Generated output")
        output_title.setObjectName("CardTitle")
        self.status_label = QLabel("Ready.")
        self.status_label.setObjectName("CardText")
        self.output_edit = QPlainTextEdit()
        self.output_edit.setMinimumHeight(280)
        output_layout.addWidget(output_title)
        output_layout.addWidget(self.status_label)
        output_layout.addWidget(self.output_edit, 1)
        layout.addWidget(output_card, 1)
        return page

    def _build_review_page(self) -> QWidget:
        page, layout = self._page_container(
            "Review",
            "Run the existing deterministic quality checker against the generated CV or covering letter.",
        )

        controls = Card("Quality check", "This is the fast rule-based review. AI quality review will be wired in a later Qt step.")
        row = QHBoxLayout()
        self.review_document_combo = QComboBox()
        self.review_document_combo.addItems(["CV", "Covering Letter"])
        run_button = QPushButton("Run Quality Check")
        run_button.setObjectName("PrimaryButton")
        run_button.setCursor(Qt.CursorShape.PointingHandCursor)
        run_button.clicked.connect(self._run_quality_check)
        show_button = QPushButton("Show Selected Document")
        show_button.clicked.connect(self._show_selected_review_document)
        row.addWidget(QLabel("Document"))
        row.addWidget(self.review_document_combo)
        row.addWidget(run_button)
        row.addWidget(show_button)
        row.addStretch(1)
        controls.layout.addLayout(row)
        layout.addWidget(controls)

        score_row = QGridLayout()
        score_row.setSpacing(18)
        self.review_score_label = QLabel("No quality check run yet")
        self.review_score_label.setObjectName("MetricNumber")
        self.review_status_label = QLabel("Generate a CV or covering letter first, then run the checker.")
        self.review_status_label.setObjectName("CardText")
        score_card = Card("Latest score", "")
        score_card.layout.addWidget(self.review_score_label)
        score_card.layout.addWidget(self.review_status_label)
        tip_card = Card(
            "Rule-based first",
            "This catches contact, ATS, evidence, and truth-supported keyword issues before you spend time on AI review.",
        )
        score_row.addWidget(score_card, 0, 0)
        score_row.addWidget(tip_card, 0, 1)
        layout.addLayout(score_row)

        report_card = QFrame()
        report_card.setObjectName("OutputCard")
        report_layout = QVBoxLayout(report_card)
        report_layout.setContentsMargins(22, 20, 22, 20)
        report_layout.setSpacing(12)
        report_title = QLabel("Quality report")
        report_title.setObjectName("CardTitle")
        self.quality_report_edit = QPlainTextEdit()
        self.quality_report_edit.setMinimumHeight(360)
        self.quality_report_edit.setPlainText("No report yet.")
        report_layout.addWidget(report_title)
        report_layout.addWidget(self.quality_report_edit, 1)
        layout.addWidget(report_card, 1)
        return page

    def _build_export_page(self) -> QWidget:
        page, layout = self._page_container(
            "Export",
            "Export the generated CV and covering letter as PDFs, or create a complete application package folder.",
        )

        settings_card = Card("Export settings", "Use a clear company and role name so generated files are easy to find later.")
        settings_grid = QGridLayout()
        settings_grid.setSpacing(16)
        settings_grid.setColumnStretch(0, 1)
        settings_grid.setColumnStretch(1, 1)

        self.export_company_edit = QLineEdit()
        self.export_company_edit.setPlaceholderText("Example: Audatic")
        self.export_role_edit = QLineEdit()
        self.export_role_edit.setPlaceholderText("Example: Machine Learning Engineer")

        self.export_document_combo = QComboBox()
        self.export_document_combo.addItems(["CV", "Covering Letter"])

        self.export_pdf_template_combo = QComboBox()
        self.export_pdf_template_combo.addItems(get_pdf_template_names())
        pdf_template_index = self.export_pdf_template_combo.findText(getattr(self.app_settings, "pdf_template", "ATS Friendly"))
        if pdf_template_index >= 0:
            self.export_pdf_template_combo.setCurrentIndex(pdf_template_index)

        self.export_page_size_combo = QComboBox()
        self.export_page_size_combo.addItems(["A4", "Letter"])
        for export_widget in (
            self.export_company_edit,
            self.export_role_edit,
            self.export_document_combo,
            self.export_pdf_template_combo,
            self.export_page_size_combo,
        ):
            self._prepare_form_control(export_widget, min_width=360)
        page_size_index = self.export_page_size_combo.findText(getattr(self.app_settings, "pdf_page_size", "A4"))
        if page_size_index >= 0:
            self.export_page_size_combo.setCurrentIndex(page_size_index)

        default_export_dir = getattr(self.app_settings, "last_export_dir", "") or str(Path("exports"))
        self.export_dir_edit = QLineEdit(default_export_dir)
        self._prepare_form_control(self.export_dir_edit, min_width=360)
        browse_button = QPushButton("Browse")
        browse_button.setMinimumHeight(42)
        browse_button.clicked.connect(self._browse_export_dir)

        self._add_labeled_field(settings_grid, 0, 0, "Target company", self.export_company_edit)
        self._add_labeled_field(settings_grid, 0, 1, "Target role", self.export_role_edit)
        self._add_labeled_field(settings_grid, 1, 0, "Single-document export", self.export_document_combo)
        self._add_labeled_field(settings_grid, 1, 1, "PDF template", self.export_pdf_template_combo)
        self._add_labeled_field(settings_grid, 2, 0, "Page size", self.export_page_size_combo)

        export_dir_wrapper = QWidget()
        export_dir_layout = QVBoxLayout(export_dir_wrapper)
        export_dir_layout.setContentsMargins(0, 0, 0, 0)
        export_dir_layout.setSpacing(6)
        export_dir_layout.addWidget(QLabel("Export folder"))
        export_dir_row = QHBoxLayout()
        export_dir_row.setContentsMargins(0, 0, 0, 0)
        export_dir_row.addWidget(self.export_dir_edit, 1)
        export_dir_row.addWidget(browse_button)
        export_dir_layout.addLayout(export_dir_row)
        settings_grid.addWidget(export_dir_wrapper, 2, 1)

        settings_card.layout.addLayout(settings_grid)
        layout.addWidget(settings_card)

        actions_card = Card("Export actions", "Export one document for quick testing, or export the full application package when both documents are ready.")
        action_row = QHBoxLayout()
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

        action_row.addWidget(self.export_pdf_button)
        action_row.addWidget(self.save_markdown_button)
        action_row.addWidget(self.export_package_button)
        action_row.addWidget(self.open_export_dir_button)
        action_row.addStretch(1)
        actions_card.layout.addLayout(action_row)
        layout.addWidget(actions_card)

        status_card = QFrame()
        status_card.setObjectName("OutputCard")
        status_layout = QVBoxLayout(status_card)
        status_layout.setContentsMargins(22, 20, 22, 20)
        status_layout.setSpacing(12)
        status_title = QLabel("Export status")
        status_title.setObjectName("CardTitle")
        self.export_status_edit = QPlainTextEdit()
        self.export_status_edit.setMinimumHeight(240)
        self.export_status_edit.setReadOnly(True)
        self.export_status_edit.setPlainText(
            "No export yet. Generate the CV and covering letter first, then export the package."
        )
        status_layout.addWidget(status_title)
        status_layout.addWidget(self.export_status_edit, 1)
        layout.addWidget(status_card, 1)
        return page

    def _build_settings_page(self) -> QWidget:
        page, layout = self._page_container(
            "Settings",
            "Minimal Qt settings view. Full settings persistence remains in the existing GUI until this experiment catches up.",
        )
        card = Card("Current AI settings", "Loaded from data/settings.json. API keys are intentionally not displayed or saved here.")
        settings_text = QPlainTextEdit()
        settings_text.setReadOnly(True)
        settings_text.setPlainText(
            f"Provider: {self.app_settings.ai_provider}\n"
            f"Ollama URL: {self.app_settings.ollama_base_url}\n"
            f"Ollama model: {self.app_settings.ollama_model}\n"
            f"OpenAI model: {self.app_settings.openai_model}\n"
            f"Generation mode: {self.app_settings.generation_mode}\n"
            f"Timeout: {self.app_settings.timeout_seconds}\n"
            f"Theme: {self.app_settings.ui_theme}\n"
        )
        card.layout.addWidget(settings_text)
        save_button = QPushButton("Save Current Settings")
        save_button.clicked.connect(self._save_settings)
        card.layout.addWidget(save_button, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(card)
        layout.addStretch(1)
        return page

    def _build_placeholder_page(self, title: str, message: str) -> QWidget:
        page, layout = self._page_container(title, message)
        card = Card("Not wired yet", "This page is intentionally a placeholder. Wire it only after Profile and Generate are stable.")
        layout.addWidget(card)
        layout.addStretch(1)
        return page

    def _prepare_form_control(self, widget: QWidget, min_width: int = 260) -> None:
        if isinstance(widget, (QLineEdit, QComboBox)):
            widget.setMinimumHeight(42)
            widget.setMinimumWidth(min_width)
            widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        elif isinstance(widget, (QTextEdit, QPlainTextEdit)):
            widget.setMinimumWidth(min_width)
            widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def _add_labeled_field(self, grid: QGridLayout, row: int, column: int, label: str, widget: QWidget) -> None:
        self._prepare_form_control(widget)
        wrapper = QWidget()
        wrapper_layout = QVBoxLayout(wrapper)
        wrapper_layout.setContentsMargins(0, 0, 0, 0)
        wrapper_layout.setSpacing(6)
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

    def _profile_to_dict(self) -> dict[str, str]:
        profile = self._build_profile()
        if hasattr(profile, "to_dict"):
            return profile.to_dict()
        return dict(profile.__dict__)

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

    def _start_generation(self) -> None:
        ok, message = self._validate_profile()
        if not ok:
            QMessageBox.warning(self, "Cannot generate", message)
            return
        if not self.job_description_edit.toPlainText().strip():
            QMessageBox.warning(self, "Cannot generate", "Paste a job description before generating.")
            return
        if self._generation_running:
            QMessageBox.information(self, "Generation already running", "Wait for the current generation to finish.")
            return

        document_type = self.document_type_combo.currentText()
        request = GenerationRequest(
            profile=self._build_profile(),
            job_description=self.job_description_edit.toPlainText().strip(),
            template_name=self.template_combo.currentText(),
            document_type=document_type,
            ai_settings=self._settings_to_ai_settings(),
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

    def _generation_failed(self, job_id: int, error: str) -> None:
        if job_id != self._generation_job_id:
            return
        self._generation_running = False
        self.generate_button.setEnabled(True)
        self.output_edit.setPlainText("")
        self.status_label.setText("Generation failed.")
        QMessageBox.critical(self, "Generation failed", error)

    def closeEvent(self, event) -> None:  # noqa: N802, Qt override name.
        if self._generation_running:
            answer = QMessageBox.question(
                self,
                "Generation running",
                "AI generation is still running. Closing now will cancel the visible result. Close anyway?",
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
        job_description = self.job_description_edit.toPlainText().strip()
        if not job_description:
            QMessageBox.warning(self, "Cannot run quality check", "Paste a job description before running the checker.")
            return
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
        if hasattr(self, "quality_report_edit"):
            text = self.quality_report_edit.toPlainText().strip()
            if text and text != "No report yet.":
                return text
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
        company = self._clean_filename_part(self.export_company_edit.text(), "company") if hasattr(self, "export_company_edit") else "company"
        role = self._clean_filename_part(self.export_role_edit.text(), "role") if hasattr(self, "export_role_edit") else "role"
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
        company = self._clean_filename_part(self.export_company_edit.text(), "company") if hasattr(self, "export_company_edit") else "company"
        role = self._clean_filename_part(self.export_role_edit.text(), "role") if hasattr(self, "export_role_edit") else "role"
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
        metadata = {
            "application_name": f"{self.export_company_edit.text().strip()} {self.export_role_edit.text().strip()}".strip(),
            "target_company": self.export_company_edit.text().strip() or "company",
            "target_role": self.export_role_edit.text().strip() or "role",
            "created_at": "",
            "modified_at": datetime.now().isoformat(timespec="seconds"),
        }
        snapshot = {
            "source": "PySide6 experiment",
            "profile": self._build_profile().__dict__,
            "job_description": self.job_description_edit.toPlainText().strip(),
            "generated_cv": self.generated_cv,
            "generated_covering_letter": self.generated_covering_letter,
            "quality_report": self._quality_report_text(),
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

    def _save_settings(self) -> None:
        try:
            save_app_settings(self.app_settings)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Settings", f"Could not save settings: {exc}")
            return
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
