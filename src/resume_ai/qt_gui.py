from __future__ import annotations

import re
import sys
import threading
import traceback
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, QRegularExpression, Qt, Signal
from PySide6.QtGui import QAction, QRegularExpressionValidator
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
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
from .settings_manager import AppSettings, load_app_settings, save_app_settings
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
        self.pages["Review"] = self._build_placeholder_page(
            "Review",
            "Quality check and AI review will be wired after the core Qt flow is proven.",
        )
        self.pages["Export"] = self._build_placeholder_page(
            "Export",
            "PDF and application package export will be connected after generation works reliably.",
        )
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
        continue_button = QPushButton("Continue to Generate")
        continue_button.clicked.connect(lambda: self.show_page("Generate"))
        action_row.addWidget(validate_button)
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

    def _add_labeled_field(self, grid: QGridLayout, row: int, column: int, label: str, widget: QWidget) -> None:
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
        self.status_label.setText(f"{document_type} generated. Verify every claim before exporting.")

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
