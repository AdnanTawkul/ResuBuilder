from __future__ import annotations

from datetime import datetime
from pathlib import Path
import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk

from .ai_service import AIService
from .application_package_exporter import export_application_package
from .document_importer import load_document_text
from .models import AISettings, CandidateProfile, GenerationRequest
from .pdf_exporter import export_markdown_to_pdf
from .pdf_templates import get_pdf_template_names, PDF_TEMPLATES
from .settings_manager import AppSettings, load_app_settings, save_app_settings
from .quality_checker import analyze_document, format_quality_report
from .storage import EXPORT_DIR, load_json, save_json, save_markdown
from .templates import get_template_names, TEMPLATES
from .workspace_manager import (
    APPLICATIONS_DIR,
    ensure_applications_dir,
    load_application_snapshot,
    save_application_snapshot,
    suggested_application_filename,
)


OPENAI_MODEL_OPTIONS = [
    "gpt-4.1-mini",
    "gpt-4o-mini",
    "gpt-5.5",
]

OLLAMA_MODEL_OPTIONS = [
    "qwen3:14b",
    "qwen3:8b",
    "llama3.1:8b",
    "gemma3:12b",
]

AI_PROVIDER_OPTIONS = [
    "Ollama Local",
    "OpenAI",
]

GENERATION_MODES = [
    "Conservative",
    "Balanced",
    "Aggressive",
]


class ResumeAIApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Resume AI 2")
        self.geometry("1120x800")
        self.minsize(980, 680)

        self.ai_service = AIService()
        self.app_settings = load_app_settings()
        self.single_line_fields: dict[str, tk.StringVar] = {}
        self.multi_line_fields: dict[str, tk.Text] = {}
        self.template_var = tk.StringVar(value=self.app_settings.template_name)
        self.pdf_page_size_var = tk.StringVar(value=self.app_settings.pdf_page_size)
        self.pdf_template_var = tk.StringVar(value=self.app_settings.pdf_template)
        self.status_var = tk.StringVar(value="Ready")
        self.application_name_var = tk.StringVar(value="")
        self.application_company_var = tk.StringVar(value="")
        self.application_role_var = tk.StringVar(value="")
        self.application_created_var = tk.StringVar(value="")
        self.application_modified_var = tk.StringVar(value="")
        self.application_path_var = tk.StringVar(value="No application workspace loaded")
        self.current_application_path: Path | None = None
        self.last_document_type = "document"
        self.last_candidate_name = "candidate"
        self.last_generation_request: GenerationRequest | None = None
        self.last_quality_report_markdown = ""
        self.last_quality_heuristic_markdown = ""
        self.last_ai_review_markdown = ""
        self.active_quality_improvement_job_id = 0
        self.quality_improvement_original_output = ""
        self.generated_cv_markdown = ""
        self.generated_covering_letter_markdown = ""
        self.cv_quality_report_markdown = ""
        self.covering_letter_quality_report_markdown = ""
        self.last_job_fit_analysis_markdown = ""

        default_ai_settings = self.ai_service.get_default_settings()
        self.ai_enabled_var = tk.BooleanVar(value=self.app_settings.use_ai)
        self.ai_provider_var = tk.StringVar(value=self.app_settings.ai_provider or default_ai_settings.provider)
        self.ai_api_key_var = tk.StringVar(value="")
        self.ai_model_var = tk.StringVar(value=self.app_settings.openai_model or default_ai_settings.model)
        self.ollama_base_url_var = tk.StringVar(value=self.app_settings.ollama_base_url or default_ai_settings.ollama_base_url)
        self.ollama_model_var = tk.StringVar(value=self.app_settings.ollama_model or default_ai_settings.ollama_model)
        self.ai_timeout_var = tk.StringVar(value=str(self.app_settings.timeout_seconds or default_ai_settings.timeout_seconds))
        self.ai_mode_var = tk.StringVar(value=self.app_settings.generation_mode or default_ai_settings.generation_mode)
        self.prompt_preview_type_var = tk.StringVar(value="Covering Letter")
        self.evidence_type_var = tk.StringVar(value="Project")
        self.evidence_title_var = tk.StringVar(value="")
        self.evidence_context_var = tk.StringVar(value="")
        self.evidence_tools_var = tk.StringVar(value="")
        self.evidence_methods_var = tk.StringVar(value="")
        self.evidence_outcome_var = tk.StringVar(value="")
        self.evidence_metrics_var = tk.StringVar(value="")
        self.evidence_signals_var = tk.StringVar(value="")
        self.generate_buttons: list[ttk.Button] = []
        self.improvement_buttons: list[ttk.Button] = []
        self.ai_review_buttons: list[ttk.Button] = []
        self.quality_check_buttons: list[ttk.Button] = []
        self.job_fit_buttons: list[ttk.Button] = []

        self._build_ui()
        self._load_saved_profile()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        notebook = ttk.Notebook(self)
        notebook.grid(row=0, column=0, sticky="nsew")

        workspace_tab = ttk.Frame(notebook, padding=12)
        personal_tab = ttk.Frame(notebook, padding=12)
        evidence_tab = ttk.Frame(notebook, padding=12)
        job_tab = ttk.Frame(notebook, padding=12)
        job_fit_tab = ttk.Frame(notebook, padding=12)
        source_tab = ttk.Frame(notebook, padding=12)
        template_tab = ttk.Frame(notebook, padding=12)
        ai_tab = ttk.Frame(notebook, padding=12)
        quality_tab = ttk.Frame(notebook, padding=12)
        output_tab = ttk.Frame(notebook, padding=12)

        notebook.add(workspace_tab, text="Workspace")
        notebook.add(personal_tab, text="Personal Info")
        notebook.add(evidence_tab, text="Evidence Builder")
        notebook.add(job_tab, text="Job Description")
        notebook.add(job_fit_tab, text="Job Fit Analyzer")
        notebook.add(source_tab, text="Existing CV / Covering Letter")
        notebook.add(template_tab, text="Templates")
        notebook.add(ai_tab, text="AI Settings")
        notebook.add(quality_tab, text="Quality Check")
        notebook.add(output_tab, text="Output")

        self._build_workspace_tab(workspace_tab)
        self._build_personal_tab(personal_tab)
        self._build_evidence_tab(evidence_tab)
        self._build_job_tab(job_tab)
        self._build_job_fit_tab(job_fit_tab)
        self._build_source_tab(source_tab)
        self._build_template_tab(template_tab)
        self._build_ai_tab(ai_tab)
        self._build_quality_tab(quality_tab)
        self._build_output_tab(output_tab)

        footer = ttk.Frame(self, padding=(12, 8))
        footer.grid(row=1, column=0, sticky="ew")
        footer.columnconfigure(0, weight=1)

        ttk.Label(footer, textvariable=self.status_var).grid(row=0, column=0, sticky="w")
        ttk.Button(footer, text="Save Profile", command=self._save_profile).grid(row=0, column=1, padx=6)
        cv_button = ttk.Button(footer, text="Generate Tailored CV", command=lambda: self._generate("CV"))
        cover_letter_button = ttk.Button(footer, text="Generate Tailored Covering Letter", command=lambda: self._generate("Covering Letter"))
        cv_button.grid(row=0, column=2, padx=6)
        cover_letter_button.grid(row=0, column=3, padx=6)
        self.generate_buttons = [cv_button, cover_letter_button]


    def _build_workspace_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(1, weight=1)
        parent.rowconfigure(7, weight=1)

        ttk.Label(parent, text="Application workspace").grid(row=0, column=0, sticky="w", pady=(0, 8))
        ttk.Label(
            parent,
            text="Save one complete job application package at a time: profile, job description, generated documents, quality reports, and selected settings.",
        ).grid(row=0, column=1, sticky="w", pady=(0, 8))

        ttk.Label(parent, text="Application name").grid(row=1, column=0, sticky="w", pady=6)
        ttk.Entry(parent, textvariable=self.application_name_var).grid(row=1, column=1, sticky="ew", pady=6)

        ttk.Label(parent, text="Target company").grid(row=2, column=0, sticky="w", pady=6)
        ttk.Entry(parent, textvariable=self.application_company_var).grid(row=2, column=1, sticky="ew", pady=6)

        ttk.Label(parent, text="Target role").grid(row=3, column=0, sticky="w", pady=6)
        ttk.Entry(parent, textvariable=self.application_role_var).grid(row=3, column=1, sticky="ew", pady=6)

        ttk.Label(parent, text="Created").grid(row=4, column=0, sticky="w", pady=6)
        ttk.Label(parent, textvariable=self.application_created_var).grid(row=4, column=1, sticky="w", pady=6)

        ttk.Label(parent, text="Last modified").grid(row=5, column=0, sticky="w", pady=6)
        ttk.Label(parent, textvariable=self.application_modified_var).grid(row=5, column=1, sticky="w", pady=6)

        ttk.Label(parent, text="Workspace file").grid(row=6, column=0, sticky="w", pady=6)
        ttk.Label(parent, textvariable=self.application_path_var, wraplength=820).grid(row=6, column=1, sticky="w", pady=6)

        button_frame = ttk.Frame(parent)
        button_frame.grid(row=7, column=0, columnspan=2, sticky="nw", pady=(14, 8))
        ttk.Button(button_frame, text="New Application", command=self._new_application_workspace).pack(side="left")
        ttk.Button(button_frame, text="Save Application", command=lambda: self._save_application_workspace(save_as=False)).pack(side="left", padx=8)
        ttk.Button(button_frame, text="Save Application As", command=lambda: self._save_application_workspace(save_as=True)).pack(side="left")
        ttk.Button(button_frame, text="Load Application", command=self._load_application_workspace).pack(side="left", padx=8)

        help_text = tk.Text(parent, height=9, wrap="word")
        help_text.grid(row=8, column=0, columnspan=2, sticky="nsew", pady=(16, 0))
        help_text.insert(
            "1.0",
            "Workflow:\n"
            "1. Create a new application workspace for each job.\n"
            "2. Paste the job description and generate the CV or covering letter.\n"
            "3. Run quality checks and AI review.\n"
            "4. Save the application before closing the app.\n\n"
            "This is not just convenience. Without saved application workspaces, you cannot manage multiple applications professionally.",
        )
        help_text.configure(state="disabled")

    def _build_personal_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(1, weight=1)
        parent.columnconfigure(3, weight=1)
        parent.rowconfigure(6, weight=1)

        fields = [
            ("name", "Name"),
            ("email", "Email"),
            ("phone", "Telephone"),
            ("location", "Location"),
            ("title", "Target / Current Title"),
            ("links", "LinkedIn / Portfolio / GitHub"),
        ]

        for index, (key, label) in enumerate(fields):
            row = index // 2
            col = (index % 2) * 2
            ttk.Label(parent, text=label).grid(row=row, column=col, sticky="w", padx=(0, 8), pady=6)
            var = tk.StringVar()
            entry = ttk.Entry(parent, textvariable=var)
            entry.grid(row=row, column=col + 1, sticky="ew", pady=6)
            self.single_line_fields[key] = var

        multi_fields = [
            ("summary", "Professional Summary"),
            ("studies", "Studies / Education"),
            ("professions", "Professions / Work Experience"),
            ("projects", "Projects"),
            ("skills", "Skills"),
            ("languages", "Languages"),
        ]

        row_start = 3
        for i, (key, label) in enumerate(multi_fields):
            row = row_start + i
            ttk.Label(parent, text=label).grid(row=row, column=0, sticky="nw", padx=(0, 8), pady=6)
            text = tk.Text(parent, height=4, wrap="word")
            text.grid(row=row, column=1, columnspan=3, sticky="nsew", pady=6)
            self.multi_line_fields[key] = text

    def _build_evidence_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(1, weight=1)
        parent.columnconfigure(3, weight=1)
        parent.rowconfigure(9, weight=1)

        ttk.Label(
            parent,
            text="Build truthful evidence blocks. This gives the AI stronger raw material than vague project/job text.",
        ).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 8))

        ttk.Label(parent, text="Evidence type").grid(row=1, column=0, sticky="w", pady=5)
        ttk.Combobox(
            parent,
            textvariable=self.evidence_type_var,
            values=["Project", "Work experience", "Education", "Research", "Volunteer", "Other"],
            state="readonly",
        ).grid(row=1, column=1, sticky="ew", pady=5)

        ttk.Label(parent, text="Title").grid(row=1, column=2, sticky="w", padx=(12, 8), pady=5)
        ttk.Entry(parent, textvariable=self.evidence_title_var).grid(row=1, column=3, sticky="ew", pady=5)

        ttk.Label(parent, text="Context / situation").grid(row=2, column=0, sticky="w", pady=5)
        ttk.Entry(parent, textvariable=self.evidence_context_var).grid(row=2, column=1, columnspan=3, sticky="ew", pady=5)

        ttk.Label(parent, text="Tools / technologies").grid(row=3, column=0, sticky="w", pady=5)
        ttk.Entry(parent, textvariable=self.evidence_tools_var).grid(row=3, column=1, columnspan=3, sticky="ew", pady=5)

        ttk.Label(parent, text="Methods / actions").grid(row=4, column=0, sticky="w", pady=5)
        ttk.Entry(parent, textvariable=self.evidence_methods_var).grid(row=4, column=1, columnspan=3, sticky="ew", pady=5)

        ttk.Label(parent, text="Outcome / purpose").grid(row=5, column=0, sticky="w", pady=5)
        ttk.Entry(parent, textvariable=self.evidence_outcome_var).grid(row=5, column=1, columnspan=3, sticky="ew", pady=5)

        ttk.Label(parent, text="Metrics / proof").grid(row=6, column=0, sticky="w", pady=5)
        ttk.Entry(parent, textvariable=self.evidence_metrics_var).grid(row=6, column=1, columnspan=3, sticky="ew", pady=5)

        ttk.Label(parent, text="Relevant job signals").grid(row=7, column=0, sticky="w", pady=5)
        ttk.Entry(parent, textvariable=self.evidence_signals_var).grid(row=7, column=1, columnspan=3, sticky="ew", pady=5)

        button_frame = ttk.Frame(parent)
        button_frame.grid(row=8, column=0, columnspan=4, sticky="w", pady=(8, 8))
        ttk.Button(button_frame, text="Add Evidence Block", command=self._add_structured_evidence).pack(side="left")
        ttk.Button(button_frame, text="Clear Builder Fields", command=self._clear_evidence_builder).pack(side="left", padx=8)
        ttk.Button(button_frame, text="Clear All Evidence", command=lambda: self._clear_text(self.structured_evidence_text)).pack(side="left")

        ttk.Label(parent, text="Structured Evidence").grid(row=9, column=0, sticky="nw", pady=(8, 0))
        self.structured_evidence_text = tk.Text(parent, height=12, wrap="word")
        self.structured_evidence_text.grid(row=9, column=1, columnspan=3, sticky="nsew", pady=(8, 0))
        self.multi_line_fields["structured_evidence"] = self.structured_evidence_text

        help_text = (
            "Example: Project | Pneumonia Detection | Built a CNN classifier using TensorFlow/Keras | "
            "trained and evaluated image-classification models | supported diagnostic screening workflow | "
            "proof: course project, GitHub repository | signals: deep learning, model training, medical imaging."
        )
        ttk.Label(parent, text=help_text, wraplength=900).grid(row=10, column=0, columnspan=4, sticky="w", pady=(10, 0))

    def _add_structured_evidence(self) -> None:
        values = {
            "type": self.evidence_type_var.get().strip(),
            "title": self.evidence_title_var.get().strip(),
            "context": self.evidence_context_var.get().strip(),
            "tools": self.evidence_tools_var.get().strip(),
            "methods": self.evidence_methods_var.get().strip(),
            "outcome": self.evidence_outcome_var.get().strip(),
            "metrics": self.evidence_metrics_var.get().strip(),
            "signals": self.evidence_signals_var.get().strip(),
        }
        if not values["title"] and not values["context"] and not values["tools"] and not values["methods"]:
            messagebox.showwarning("Missing evidence", "Add at least a title, context, tool, or method before creating an evidence block.")
            return

        block_lines = [
            f"### {values['type']}: {values['title'] or 'Untitled evidence'}",
            f"- Context: {values['context'] or 'Not specified'}",
            f"- Tools/technologies: {values['tools'] or 'Not specified'}",
            f"- Methods/actions: {values['methods'] or 'Not specified'}",
            f"- Outcome/purpose: {values['outcome'] or 'Not specified'}",
            f"- Metrics/proof: {values['metrics'] or 'Not specified'}",
            f"- Relevant job signals: {values['signals'] or 'Not specified'}",
        ]
        existing = self.structured_evidence_text.get("1.0", tk.END).strip()
        insert_text = "\n\n".join([part for part in [existing, "\n".join(block_lines)] if part]).strip()
        self.structured_evidence_text.delete("1.0", tk.END)
        self.structured_evidence_text.insert("1.0", insert_text)
        self.application_modified_var.set(datetime.now().isoformat(timespec="seconds"))
        self.status_var.set("Structured evidence block added")
        self._clear_evidence_builder()

    def _clear_evidence_builder(self) -> None:
        self.evidence_type_var.set("Project")
        self.evidence_title_var.set("")
        self.evidence_context_var.set("")
        self.evidence_tools_var.set("")
        self.evidence_methods_var.set("")
        self.evidence_outcome_var.set("")
        self.evidence_metrics_var.set("")
        self.evidence_signals_var.set("")

    def _build_job_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        ttk.Label(parent, text="Paste the full job description here. The stronger this input is, the better the tailoring.").grid(row=0, column=0, sticky="w")
        self.job_description_text = tk.Text(parent, wrap="word")
        self.job_description_text.grid(row=1, column=0, sticky="nsew", pady=8)

        button_frame = ttk.Frame(parent)
        button_frame.grid(row=2, column=0, sticky="ew")
        ttk.Button(button_frame, text="Load Job Description from PDF/Text", command=lambda: self._load_file_into_text(self.job_description_text)).pack(side="left")
        ttk.Button(button_frame, text="Clear", command=lambda: self._clear_text(self.job_description_text)).pack(side="left", padx=8)

    def _build_job_fit_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(2, weight=1)

        intro = (
            "Analyze the job before generating documents. This uses Ollama locally to decide which job signals are supported, "
            "which are weak, and which must not be claimed without more evidence."
        )
        ttk.Label(parent, text=intro, wraplength=980).grid(row=0, column=0, sticky="w", pady=(0, 8))

        buttons = ttk.Frame(parent)
        buttons.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        analyze_button = ttk.Button(buttons, text="Analyze Job Fit with Ollama", command=self._run_job_fit_analysis)
        analyze_button.pack(side="left")
        ttk.Button(buttons, text="Use Analysis in Next Generation", command=self._use_visible_job_fit_analysis).pack(side="left", padx=8)
        ttk.Button(buttons, text="Clear Job Fit Analysis", command=self._clear_job_fit_analysis).pack(side="left")
        self.job_fit_buttons = [analyze_button]

        self.job_fit_text = tk.Text(parent, wrap="word")
        self.job_fit_text.grid(row=2, column=0, sticky="nsew")
        self.job_fit_text.insert(
            "1.0",
            "Run the analyzer after adding the job description and structured evidence. "
            "The resulting strategy will be included automatically in CV and covering-letter generation prompts.",
        )

    def _build_source_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.columnconfigure(1, weight=1)
        parent.rowconfigure(1, weight=1)

        ttk.Label(parent, text="General CV").grid(row=0, column=0, sticky="w")
        ttk.Label(parent, text="General Covering Letter").grid(row=0, column=1, sticky="w")

        self.general_cv_text = tk.Text(parent, wrap="word")
        self.general_cover_letter_text = tk.Text(parent, wrap="word")
        # Legacy alias. Older app versions called this field general_resume.
        self.general_resume_text = self.general_cover_letter_text
        self.general_cv_text.grid(row=1, column=0, sticky="nsew", padx=(0, 6), pady=8)
        self.general_cover_letter_text.grid(row=1, column=1, sticky="nsew", padx=(6, 0), pady=8)
        self.multi_line_fields["general_cv"] = self.general_cv_text
        self.multi_line_fields["general_cover_letter"] = self.general_cover_letter_text

        cv_buttons = ttk.Frame(parent)
        cover_letter_buttons = ttk.Frame(parent)
        cv_buttons.grid(row=2, column=0, sticky="w")
        cover_letter_buttons.grid(row=2, column=1, sticky="w")

        ttk.Button(cv_buttons, text="Load CV PDF/Text", command=lambda: self._load_file_into_text(self.general_cv_text)).pack(side="left")
        ttk.Button(cv_buttons, text="Clear", command=lambda: self._clear_text(self.general_cv_text)).pack(side="left", padx=8)
        ttk.Button(cover_letter_buttons, text="Load Covering Letter PDF/Text", command=lambda: self._load_file_into_text(self.general_cover_letter_text)).pack(side="left")
        ttk.Button(cover_letter_buttons, text="Clear", command=lambda: self._clear_text(self.general_cover_letter_text)).pack(side="left", padx=8)

    def _build_template_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(1, weight=1)
        parent.rowconfigure(1, weight=1)

        ttk.Label(parent, text="Choose a template style").grid(row=0, column=0, sticky="w", pady=(0, 8))
        combo = ttk.Combobox(parent, textvariable=self.template_var, values=get_template_names(), state="readonly")
        combo.grid(row=0, column=1, sticky="ew", pady=(0, 8))
        combo.bind("<<ComboboxSelected>>", lambda event: self._update_template_description())

        self.template_description = tk.Text(parent, height=12, wrap="word", state="disabled")
        self.template_description.grid(row=1, column=0, columnspan=2, sticky="nsew")
        self._update_template_description()

    def _build_ai_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(1, weight=1)
        parent.rowconfigure(12, weight=1)

        env_status = "Detected" if self.ai_service.has_environment_api_key() else "Not detected"

        ttk.Checkbutton(parent, text="Use AI generation", variable=self.ai_enabled_var).grid(row=0, column=1, sticky="w", pady=6)

        ttk.Label(parent, text="AI provider").grid(row=1, column=0, sticky="w", pady=6)
        provider_combo = ttk.Combobox(parent, textvariable=self.ai_provider_var, values=AI_PROVIDER_OPTIONS, state="readonly")
        provider_combo.grid(row=1, column=1, sticky="ew", pady=6)
        provider_combo.bind("<<ComboboxSelected>>", lambda event: self._refresh_ai_provider_help())

        ttk.Label(parent, text="Generation mode").grid(row=2, column=0, sticky="w", pady=6)
        ttk.Combobox(parent, textvariable=self.ai_mode_var, values=GENERATION_MODES, state="readonly").grid(row=2, column=1, sticky="ew", pady=6)

        ttk.Label(parent, text="Timeout seconds").grid(row=3, column=0, sticky="w", pady=6)
        ttk.Entry(parent, textvariable=self.ai_timeout_var, width=12).grid(row=3, column=1, sticky="w", pady=6)

        separator_one = ttk.Separator(parent, orient="horizontal")
        separator_one.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(10, 8))

        ttk.Label(parent, text="Ollama base URL").grid(row=5, column=0, sticky="w", pady=6)
        ttk.Entry(parent, textvariable=self.ollama_base_url_var).grid(row=5, column=1, sticky="ew", pady=6)

        ttk.Label(parent, text="Ollama model").grid(row=6, column=0, sticky="w", pady=6)
        ttk.Combobox(parent, textvariable=self.ollama_model_var, values=OLLAMA_MODEL_OPTIONS, state="normal").grid(row=6, column=1, sticky="ew", pady=6)

        separator_two = ttk.Separator(parent, orient="horizontal")
        separator_two.grid(row=7, column=0, columnspan=2, sticky="ew", pady=(10, 8))

        ttk.Label(parent, text="OPENAI_API_KEY environment key").grid(row=8, column=0, sticky="w", pady=6)
        ttk.Label(parent, text=env_status).grid(row=8, column=1, sticky="w", pady=6)

        ttk.Label(parent, text="OpenAI session API key").grid(row=9, column=0, sticky="w", pady=6)
        key_entry = ttk.Entry(parent, textvariable=self.ai_api_key_var, show="*")
        key_entry.grid(row=9, column=1, sticky="ew", pady=6)

        ttk.Label(parent, text="OpenAI model").grid(row=10, column=0, sticky="nw", pady=6)
        ttk.Combobox(parent, textvariable=self.ai_model_var, values=OPENAI_MODEL_OPTIONS, state="normal").grid(row=10, column=1, sticky="ew", pady=6)

        button_frame = ttk.Frame(parent)
        button_frame.grid(row=11, column=0, columnspan=2, sticky="ew", pady=(8, 8))
        ttk.Button(button_frame, text="Test Selected AI Provider", command=self._test_ai_connection).pack(side="left")
        ttk.Button(button_frame, text="Preview Prompt", command=self._preview_ai_prompt).pack(side="left", padx=8)
        ttk.Button(button_frame, text="Save App Settings", command=lambda: self._save_app_settings(show_message=True)).pack(side="left")
        ttk.Button(button_frame, text="Reset App Settings", command=self._reset_app_settings).pack(side="left", padx=8)
        ttk.Button(button_frame, text="Clear Session API Key", command=lambda: self.ai_api_key_var.set("")).pack(side="left")
        ttk.Label(button_frame, text="Preview type").pack(side="left", padx=(18, 4))
        ttk.Combobox(button_frame, textvariable=self.prompt_preview_type_var, values=["Covering Letter", "CV"], width=10, state="readonly").pack(side="left")

        self.ai_help_text = tk.Text(parent, height=6, wrap="word")
        self.ai_help_text.grid(row=12, column=0, columnspan=2, sticky="nsew", pady=(8, 0))
        self._refresh_ai_provider_help()

    def _refresh_ai_provider_help(self) -> None:
        if not hasattr(self, "ai_help_text"):
            return

        selected_provider = self.ai_provider_var.get().strip() or "Ollama Local"
        if selected_provider == "Ollama Local":
            content = (
                "Ollama Local runs on your computer and does not use paid OpenAI API credits. "
                "Keep Ollama running, use base URL http://localhost:11434, and use qwen3:14b as the first serious local model. "
                "Local output still needs review. It can invent details if your input is weak, so verify every claim before exporting a PDF."
            )
        else:
            content = (
                "OpenAI uses your API key and can cost money. Session keys are not saved in the candidate profile. "
                "Use the Windows environment variable OPENAI_API_KEY for normal use, or paste a temporary session key here. "
                "Use OpenAI when you want stronger final quality or when the local model is not good enough."
            )

        self.ai_help_text.configure(state="normal")
        self.ai_help_text.delete("1.0", tk.END)
        self.ai_help_text.insert("1.0", content)
        self.ai_help_text.configure(state="disabled")

    def _build_quality_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        instruction = (
            "Run this before exporting. The checker catches obvious risks, but it does not replace human verification."
        )
        ttk.Label(parent, text=instruction).grid(row=0, column=0, sticky="w")

        self.quality_text = tk.Text(parent, wrap="word")
        self.quality_text.grid(row=1, column=0, sticky="nsew", pady=8)

        buttons = ttk.Frame(parent)
        buttons.grid(row=2, column=0, sticky="ew")
        quality_check_button = ttk.Button(buttons, text="Run Quality Check", command=self._run_quality_check)
        quality_check_button.pack(side="left")
        self.quality_check_buttons.append(quality_check_button)
        ai_review_button = ttk.Button(buttons, text="Run AI Quality Review", command=self._run_ai_quality_review)
        ai_review_button.pack(side="left", padx=8)
        self.ai_review_buttons.append(ai_review_button)
        improve_button = ttk.Button(buttons, text="Regenerate with Quality Fixes", command=self._regenerate_with_quality_fixes)
        improve_button.pack(side="left")
        self.improvement_buttons.append(improve_button)
        ttk.Button(buttons, text="Save Quality Report", command=self._save_quality_report).pack(side="left", padx=8)
        ttk.Button(buttons, text="Clear Quality Report", command=self._clear_quality_report).pack(side="left")

    def _build_output_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        instruction = "Generated documents appear here. Review them before sending. AI is useful, but blindly trusting it is how bad applications get submitted."
        ttk.Label(parent, text=instruction).grid(row=0, column=0, sticky="w")

        self.output_text = tk.Text(parent, wrap="word")
        self.output_text.grid(row=1, column=0, sticky="nsew", pady=8)

        buttons = ttk.Frame(parent)
        buttons.grid(row=2, column=0, sticky="ew")
        ttk.Button(buttons, text="Save Output as Markdown", command=self._save_output).pack(side="left")
        ttk.Button(buttons, text="Export Output as PDF", command=self._export_output_pdf).pack(side="left", padx=8)
        ttk.Button(buttons, text="Export Application Package", command=self._export_application_package).pack(side="left")
        ttk.Button(buttons, text="Show CV", command=self._show_generated_cv).pack(side="left", padx=(8, 0))
        ttk.Button(buttons, text="Show Covering Letter", command=self._show_generated_covering_letter).pack(side="left", padx=8)
        ttk.Button(buttons, text="Check Output Quality", command=self._run_quality_check).pack(side="left", padx=8)
        output_improve_button = ttk.Button(buttons, text="Improve with Quality Fixes", command=self._regenerate_with_quality_fixes)
        output_improve_button.pack(side="left")
        self.improvement_buttons.append(output_improve_button)
        ttk.Label(buttons, text="PDF template").pack(side="left", padx=(12, 4))
        ttk.Combobox(buttons, textvariable=self.pdf_template_var, values=get_pdf_template_names(), width=16, state="readonly").pack(side="left")
        ttk.Label(buttons, text="Page size").pack(side="left", padx=(12, 4))
        ttk.Combobox(buttons, textvariable=self.pdf_page_size_var, values=["A4", "Letter"], width=8, state="readonly").pack(side="left")
        ttk.Button(buttons, text="Clear Output", command=lambda: self._clear_text(self.output_text)).pack(side="left", padx=8)


    def _collect_application_workspace_snapshot(self) -> dict:
        now = datetime.now().isoformat(timespec="seconds")
        created = self.application_created_var.get().strip() or now
        profile = self._collect_profile()
        ai_settings = self._collect_ai_settings()
        return {
            "schema_version": 1,
            "saved_at": now,
            "metadata": {
                "application_name": self.application_name_var.get().strip(),
                "target_company": self.application_company_var.get().strip(),
                "target_role": self.application_role_var.get().strip(),
                "created_at": created,
                "modified_at": now,
            },
            "profile": profile.to_dict(),
            "job_description": self.job_description_text.get("1.0", tk.END).strip(),
            "general_cv": self.general_cv_text.get("1.0", tk.END).strip(),
            "general_cover_letter": self.general_cover_letter_text.get("1.0", tk.END).strip(),
            # Legacy key kept for old integrations and existing workspace tools.
            "general_resume": self.general_cover_letter_text.get("1.0", tk.END).strip(),
            "settings": {
                "template_name": self.template_var.get(),
                "pdf_template": self.pdf_template_var.get(),
                "pdf_page_size": self.pdf_page_size_var.get(),
                "ai": {
                    "use_ai": bool(self.ai_enabled_var.get()),
                    "provider": ai_settings.provider,
                    "model": ai_settings.model,
                    "generation_mode": ai_settings.generation_mode,
                    "ollama_base_url": ai_settings.ollama_base_url,
                    "ollama_model": ai_settings.ollama_model,
                    "timeout_seconds": ai_settings.timeout_seconds,
                },
            },
            "documents": {
                "last_document_type": self.last_document_type,
                "output_markdown": self.output_text.get("1.0", tk.END).strip(),
                "generated_cv_markdown": self.generated_cv_markdown,
                "generated_covering_letter_markdown": self.generated_covering_letter_markdown,
                "quality_report_markdown": self.last_quality_report_markdown,
                "quality_heuristic_markdown": self.last_quality_heuristic_markdown,
                "ai_review_markdown": self.last_ai_review_markdown,
                "cv_quality_report_markdown": self.cv_quality_report_markdown,
                "covering_letter_quality_report_markdown": self.covering_letter_quality_report_markdown,
                "job_fit_analysis_markdown": self.last_job_fit_analysis_markdown,
            },
        }

    def _apply_application_workspace_snapshot(self, data: dict, source_path: Path | None = None) -> None:
        metadata = data.get("metadata", {}) if isinstance(data.get("metadata", {}), dict) else {}
        profile_data = data.get("profile", {}) if isinstance(data.get("profile", {}), dict) else {}
        settings = data.get("settings", {}) if isinstance(data.get("settings", {}), dict) else {}
        ai_settings = settings.get("ai", {}) if isinstance(settings.get("ai", {}), dict) else {}
        documents = data.get("documents", {}) if isinstance(data.get("documents", {}), dict) else {}

        self.application_name_var.set(metadata.get("application_name", ""))
        self.application_company_var.set(metadata.get("target_company", ""))
        self.application_role_var.set(metadata.get("target_role", ""))
        self.application_created_var.set(metadata.get("created_at", ""))
        self.application_modified_var.set(metadata.get("modified_at", data.get("saved_at", "")))

        for key, var in self.single_line_fields.items():
            var.set(profile_data.get(key, ""))
        for key, widget in self.multi_line_fields.items():
            widget.delete("1.0", tk.END)
            widget.insert("1.0", profile_data.get(key, ""))

        self.job_description_text.delete("1.0", tk.END)
        self.job_description_text.insert("1.0", data.get("job_description", ""))

        self.general_cv_text.delete("1.0", tk.END)
        self.general_cv_text.insert("1.0", data.get("general_cv", profile_data.get("general_cv", "")))
        cover_letter_source = (
            data.get("general_cover_letter")
            or profile_data.get("general_cover_letter")
            or data.get("general_resume")
            or profile_data.get("general_resume", "")
        )
        self.general_cover_letter_text.delete("1.0", tk.END)
        self.general_cover_letter_text.insert("1.0", cover_letter_source)

        self.template_var.set(settings.get("template_name", self.template_var.get()))
        self.pdf_template_var.set(settings.get("pdf_template", self.pdf_template_var.get()))
        self.pdf_page_size_var.set(settings.get("pdf_page_size", self.pdf_page_size_var.get()))
        self.ai_enabled_var.set(bool(ai_settings.get("use_ai", self.ai_enabled_var.get())))
        self.ai_provider_var.set(ai_settings.get("provider", self.ai_provider_var.get()))
        self.ai_model_var.set(ai_settings.get("model", self.ai_model_var.get()))
        self.ai_mode_var.set(ai_settings.get("generation_mode", self.ai_mode_var.get()))
        self.ollama_base_url_var.set(ai_settings.get("ollama_base_url", self.ollama_base_url_var.get()))
        self.ollama_model_var.set(ai_settings.get("ollama_model", self.ollama_model_var.get()))
        self.ai_timeout_var.set(str(ai_settings.get("timeout_seconds", self.ai_timeout_var.get())))
        self.ai_api_key_var.set("")
        self._refresh_ai_provider_help()
        self._update_template_description()

        self.last_document_type = documents.get("last_document_type", "document")
        self.last_candidate_name = self.single_line_fields.get("name", tk.StringVar(value="candidate")).get() or "candidate"
        self.last_generation_request = None
        legacy_output = documents.get("output_markdown", "")
        self.generated_cv_markdown = documents.get("generated_cv_markdown", "")
        self.generated_covering_letter_markdown = documents.get("generated_covering_letter_markdown", "")
        if legacy_output and not self.generated_cv_markdown and self.last_document_type.lower() == "cv":
            self.generated_cv_markdown = legacy_output
        if legacy_output and not self.generated_covering_letter_markdown and self.last_document_type.lower() != "cv":
            self.generated_covering_letter_markdown = legacy_output
        self.cv_quality_report_markdown = documents.get("cv_quality_report_markdown", "")
        self.covering_letter_quality_report_markdown = documents.get("covering_letter_quality_report_markdown", "")
        self.last_quality_report_markdown = documents.get("quality_report_markdown", "")
        self.last_quality_heuristic_markdown = documents.get("quality_heuristic_markdown", "")
        self.last_ai_review_markdown = documents.get("ai_review_markdown", "")
        self.last_job_fit_analysis_markdown = documents.get("job_fit_analysis_markdown", "")
        if hasattr(self, "job_fit_text"):
            self.job_fit_text.delete("1.0", tk.END)
            if self.last_job_fit_analysis_markdown.strip():
                self.job_fit_text.insert("1.0", self.last_job_fit_analysis_markdown)
            else:
                self.job_fit_text.insert(
                    "1.0",
                    "Run the analyzer after adding the job description and structured evidence. "
                    "The resulting strategy will be included automatically in CV and covering-letter generation prompts.",
                )

        self.output_text.delete("1.0", tk.END)
        self.output_text.insert("1.0", legacy_output)
        self.quality_text.delete("1.0", tk.END)
        self.quality_text.insert("1.0", self.last_quality_report_markdown)

        self.current_application_path = source_path
        self.application_path_var.set(str(source_path) if source_path else "Unsaved application workspace")
        self.status_var.set("Application workspace loaded" if source_path else "New application workspace ready")

    def _new_application_workspace(self) -> None:
        proceed = messagebox.askyesno(
            "New application",
            "Start a new application workspace? Candidate profile fields will stay, but job description, output, and quality reports will be cleared.",
        )
        if not proceed:
            return

        now = datetime.now().isoformat(timespec="seconds")
        self.application_name_var.set("")
        self.application_company_var.set("")
        self.application_role_var.set("")
        self.application_created_var.set(now)
        self.application_modified_var.set("")
        self.current_application_path = None
        self.application_path_var.set("Unsaved application workspace")

        self.job_description_text.delete("1.0", tk.END)
        self.general_cv_text.delete("1.0", tk.END)
        self.general_cover_letter_text.delete("1.0", tk.END)
        self.output_text.delete("1.0", tk.END)
        self._clear_quality_report()
        self.last_generation_request = None
        self.last_document_type = "document"
        self.generated_cv_markdown = ""
        self.generated_covering_letter_markdown = ""
        self.cv_quality_report_markdown = ""
        self.covering_letter_quality_report_markdown = ""
        self._clear_job_fit_analysis()
        self.status_var.set("New application workspace ready")

    def _save_application_workspace(self, save_as: bool = False) -> None:
        ensure_applications_dir()
        snapshot = self._collect_application_workspace_snapshot()
        metadata = snapshot.get("metadata", {})
        suggested_name = suggested_application_filename(
            metadata.get("target_company", ""),
            metadata.get("target_role", ""),
        )

        target_path = self.current_application_path
        if save_as or target_path is None:
            selected = filedialog.asksaveasfilename(
                initialdir=self._application_dialog_initial_dir(),
                initialfile=suggested_name,
                defaultextension=".json",
                filetypes=[("Application workspace", "*.json"), ("All files", "*.*")],
            )
            if not selected:
                return
            target_path = Path(selected)

        try:
            saved_path = save_application_snapshot(target_path, snapshot)
        except Exception as exc:
            messagebox.showerror("Save failed", f"Could not save application workspace:\n{exc}")
            self.status_var.set("Application workspace save failed")
            return

        self.current_application_path = saved_path
        self.app_settings.last_workspace_dir = str(saved_path.parent)
        self._save_app_settings(show_message=False)
        self.application_modified_var.set(snapshot.get("saved_at", ""))
        if not self.application_created_var.get().strip():
            self.application_created_var.set(snapshot.get("metadata", {}).get("created_at", ""))
        self.application_path_var.set(str(saved_path))
        self.status_var.set(f"Application workspace saved to {saved_path}")
        messagebox.showinfo("Saved", f"Application workspace saved to:\n{saved_path}")

    def _load_application_workspace(self) -> None:
        ensure_applications_dir()
        selected = filedialog.askopenfilename(
            initialdir=self._application_dialog_initial_dir(),
            filetypes=[("Application workspace", "*.json"), ("All files", "*.*")],
        )
        if not selected:
            return

        source_path = Path(selected)
        try:
            data = load_application_snapshot(source_path)
            self.app_settings.last_workspace_dir = str(source_path.parent)
            self._apply_application_workspace_snapshot(data, source_path=source_path)
            self._save_app_settings(show_message=False)
        except Exception as exc:
            messagebox.showerror("Load failed", f"Could not load application workspace:\n{exc}")
            self.status_var.set("Application workspace load failed")


    def _application_dialog_initial_dir(self) -> Path:
        configured = Path(self.app_settings.last_workspace_dir) if self.app_settings.last_workspace_dir else APPLICATIONS_DIR
        return configured if configured.exists() else APPLICATIONS_DIR

    def _export_dialog_initial_dir(self) -> Path:
        configured = Path(self.app_settings.last_export_dir) if self.app_settings.last_export_dir else EXPORT_DIR
        return configured if configured.exists() else EXPORT_DIR

    def _collect_app_settings(self) -> AppSettings:
        try:
            timeout_seconds = int(self.ai_timeout_var.get().strip() or "120")
        except ValueError:
            timeout_seconds = 120
        timeout_seconds = max(30, min(timeout_seconds, 600))

        return AppSettings(
            template_name=self.template_var.get().strip() or "ATS Friendly",
            pdf_template=self.pdf_template_var.get().strip() or "ATS Friendly",
            pdf_page_size=self.pdf_page_size_var.get().strip() or "A4",
            use_ai=bool(self.ai_enabled_var.get()),
            ai_provider=self.ai_provider_var.get().strip() or AIService.PROVIDER_OLLAMA,
            openai_model=self.ai_model_var.get().strip() or AIService.DEFAULT_OPENAI_MODEL,
            generation_mode=self.ai_mode_var.get().strip() or "Balanced",
            ollama_base_url=self.ollama_base_url_var.get().strip() or AIService.DEFAULT_OLLAMA_BASE_URL,
            ollama_model=self.ollama_model_var.get().strip() or AIService.DEFAULT_OLLAMA_MODEL,
            timeout_seconds=timeout_seconds,
            last_workspace_dir=self.app_settings.last_workspace_dir,
            last_export_dir=self.app_settings.last_export_dir,
        )

    def _apply_app_settings(self, settings: AppSettings) -> None:
        self.app_settings = settings
        self.template_var.set(settings.template_name)
        self.pdf_template_var.set(settings.pdf_template)
        self.pdf_page_size_var.set(settings.pdf_page_size)
        self.ai_enabled_var.set(settings.use_ai)
        self.ai_provider_var.set(settings.ai_provider)
        self.ai_model_var.set(settings.openai_model)
        self.ai_mode_var.set(settings.generation_mode)
        self.ollama_base_url_var.set(settings.ollama_base_url)
        self.ollama_model_var.set(settings.ollama_model)
        self.ai_timeout_var.set(str(settings.timeout_seconds))
        self.ai_api_key_var.set("")
        self._refresh_ai_provider_help()
        self._update_template_description()

    def _save_app_settings(self, show_message: bool = False) -> None:
        self.app_settings = self._collect_app_settings()
        try:
            saved_path = save_app_settings(self.app_settings)
        except Exception as exc:
            self.status_var.set("App settings save failed")
            if show_message:
                messagebox.showerror("Settings save failed", f"Could not save app settings:\n{exc}")
            return

        self.status_var.set(f"App settings saved to {saved_path}")
        if show_message:
            messagebox.showinfo("Settings saved", f"App settings saved locally to:\n{saved_path}\n\nOpenAI session API keys are not saved.")

    def _reset_app_settings(self) -> None:
        proceed = messagebox.askyesno(
            "Reset app settings",
            "Reset AI, template, PDF, and folder defaults? This will not delete saved applications or your profile.",
        )
        if not proceed:
            return
        self._apply_app_settings(AppSettings())
        self._save_app_settings(show_message=True)

    def _on_close(self) -> None:
        self._save_app_settings(show_message=False)
        self.destroy()

    def _load_saved_profile(self) -> None:
        data = load_json()
        if not data:
            return
        for key, var in self.single_line_fields.items():
            var.set(data.get(key, ""))
        for key, widget in self.multi_line_fields.items():
            widget.delete("1.0", tk.END)
            value = data.get(key, "")
            if key == "general_cover_letter" and not value:
                value = data.get("general_resume", "")
            widget.insert("1.0", value)
        self.status_var.set("Loaded saved profile")

    def _collect_profile(self) -> CandidateProfile:
        data = {key: var.get().strip() for key, var in self.single_line_fields.items()}
        for key, widget in self.multi_line_fields.items():
            data[key] = widget.get("1.0", tk.END).strip()
        # Keep the legacy general_resume field mirrored so older workspace/profile files remain compatible.
        data["general_resume"] = data.get("general_cover_letter", "")
        return CandidateProfile(**data)

    def _collect_ai_settings(self) -> AISettings:
        try:
            timeout_seconds = int(self.ai_timeout_var.get().strip() or "120")
        except ValueError:
            timeout_seconds = 120

        timeout_seconds = max(30, min(timeout_seconds, 600))

        return AISettings(
            use_ai=bool(self.ai_enabled_var.get()),
            provider=self.ai_provider_var.get().strip() or AIService.PROVIDER_OLLAMA,
            api_key=self.ai_api_key_var.get().strip(),
            model=self.ai_model_var.get().strip() or AIService.DEFAULT_OPENAI_MODEL,
            generation_mode=self.ai_mode_var.get().strip() or "Balanced",
            ollama_base_url=self.ollama_base_url_var.get().strip() or AIService.DEFAULT_OLLAMA_BASE_URL,
            ollama_model=self.ollama_model_var.get().strip() or AIService.DEFAULT_OLLAMA_MODEL,
            timeout_seconds=timeout_seconds,
        )

    def _save_profile(self) -> None:
        profile = self._collect_profile()
        save_json(profile.to_dict())
        self.status_var.set("Profile saved")
        messagebox.showinfo("Saved", "Candidate profile saved locally.")

    def _generate(self, document_type: str) -> None:
        profile = self._collect_profile()
        job_description = self.job_description_text.get("1.0", tk.END).strip()

        if not profile.name or not profile.email:
            messagebox.showwarning("Missing basics", "Add at least your name and email first.")
            return
        if not job_description:
            messagebox.showwarning("Missing job description", "Paste the job description before generating.")
            return

        request = GenerationRequest(
            profile=profile,
            job_description=job_description,
            template_name=self.template_var.get(),
            document_type=document_type,
            ai_settings=self._collect_ai_settings(),
            job_fit_analysis=self._current_job_fit_analysis(),
        )
        self.status_var.set(f"Generating tailored {document_type.lower()}...")
        self._set_generating_state(True)

        thread = threading.Thread(target=self._generate_worker, args=(request,), daemon=True)
        thread.start()

    def _generate_worker(self, request: GenerationRequest) -> None:
        try:
            result = self.ai_service.generate(request)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            document_slug = self._document_slug(request.document_type)
            filename = f"{document_slug}_{request.profile.name}_{timestamp}.md"
            saved_path = save_markdown(filename, result)
            self.after(0, lambda: self._finish_generation(request, result, saved_path))
        except Exception as exc:
            self.after(0, lambda: self._fail_generation(exc))

    def _finish_generation(self, request: GenerationRequest, result: str, saved_path: Path) -> None:
        self.last_generation_request = request
        self.last_document_type = request.document_type.lower()
        self.last_candidate_name = request.profile.name or "candidate"
        self._store_generated_document(request.document_type, result)
        self.last_quality_report_markdown = ""
        self.last_quality_heuristic_markdown = ""
        self.last_ai_review_markdown = ""
        self._clear_stored_quality_for_document(request.document_type)
        self.quality_text.delete("1.0", tk.END)
        self.output_text.delete("1.0", tk.END)
        self.output_text.insert("1.0", result)
        self.application_modified_var.set(datetime.now().isoformat(timespec="seconds"))
        self.status_var.set(f"Generated {request.document_type.lower()} and saved to {saved_path}")
        self._set_generating_state(False)

    def _fail_generation(self, exc: Exception) -> None:
        self.status_var.set("Generation failed")
        self._set_generating_state(False)
        messagebox.showerror("Generation failed", f"Could not generate document:\n{exc}")

    def _set_generating_state(self, is_generating: bool) -> None:
        state = "disabled" if is_generating else "normal"
        for button in self.generate_buttons:
            button.configure(state=state)
        for button in getattr(self, "improvement_buttons", []):
            button.configure(state=state)
        for button in getattr(self, "ai_review_buttons", []):
            button.configure(state=state)
        for button in getattr(self, "quality_check_buttons", []):
            button.configure(state=state)
        for button in getattr(self, "job_fit_buttons", []):
            button.configure(state=state)

    def _set_ai_review_state(self, is_running: bool) -> None:
        state = "disabled" if is_running else "normal"
        for button in getattr(self, "ai_review_buttons", []):
            button.configure(state=state)
        for button in getattr(self, "improvement_buttons", []):
            button.configure(state=state)
        for button in getattr(self, "quality_check_buttons", []):
            button.configure(state=state)

    def _test_ai_connection(self) -> None:
        settings = self._collect_ai_settings()
        self.status_var.set("Testing AI connection...")
        thread = threading.Thread(target=self._test_ai_connection_worker, args=(settings,), daemon=True)
        thread.start()

    def _test_ai_connection_worker(self, settings: AISettings) -> None:
        result = self.ai_service.test_connection(settings)
        self.after(0, lambda: self._show_ai_test_result(result))

    def _show_ai_test_result(self, result: str) -> None:
        self.status_var.set(result)
        if "connection works" in result.lower():
            messagebox.showinfo("AI connection", result)
        else:
            messagebox.showwarning("AI connection", result)

    def _preview_ai_prompt(self) -> None:
        profile = self._collect_profile()
        job_description = self.job_description_text.get("1.0", tk.END).strip()
        request = GenerationRequest(
            profile=profile,
            job_description=job_description or "Paste a job description to preview the full prompt.",
            template_name=self.template_var.get(),
            document_type=self.prompt_preview_type_var.get(),
            ai_settings=self._collect_ai_settings(),
            job_fit_analysis=self._current_job_fit_analysis(),
        )
        preview = self.ai_service.build_prompt_preview(request)
        self.output_text.delete("1.0", tk.END)
        self.output_text.insert("1.0", preview)
        self.status_var.set("Prompt preview placed in Output tab")

    def _current_job_fit_analysis(self) -> str:
        visible = getattr(self, "job_fit_text", None)
        if visible is not None:
            text = visible.get("1.0", tk.END).strip()
            placeholder = "Run the analyzer after adding the job description"
            if text and placeholder not in text:
                return text
        return self.last_job_fit_analysis_markdown.strip()

    def _run_job_fit_analysis(self) -> None:
        profile = self._collect_profile()
        job_description = self.job_description_text.get("1.0", tk.END).strip()
        if not job_description:
            messagebox.showwarning("Missing job description", "Paste the job description before analyzing job fit.")
            return
        if not any([profile.summary, profile.professions, profile.projects, profile.skills, getattr(profile, "structured_evidence", ""), profile.general_cv]):
            messagebox.showwarning(
                "Missing candidate evidence",
                "Add profile details or structured evidence before analyzing job fit. Otherwise Ollama has nothing useful to compare.",
            )
            return

        settings = self._collect_ai_settings()
        provider = AIService.PROVIDER_OLLAMA
        model = settings.ollama_model.strip() or AIService.DEFAULT_OLLAMA_MODEL
        self.last_job_fit_analysis_markdown = ""
        self.job_fit_text.delete("1.0", tk.END)
        self.job_fit_text.insert(
            "1.0",
            "# Job Fit Analysis Running\n\n"
            "Status: Ollama is comparing the job description against the candidate evidence. Wait until this screen is replaced.\n\n"
            f"Provider: {provider}\n\n"
            f"Model: {model}\n\n"
            "Do not generate final documents until this completes if you want the strategy included in the prompts.\n",
        )
        self.status_var.set("Running Ollama job fit analysis...")
        self._set_job_fit_state(True)
        self.update_idletasks()

        thread = threading.Thread(
            target=self._run_job_fit_analysis_worker,
            args=(profile, job_description, settings, self.application_company_var.get().strip(), self.application_role_var.get().strip()),
            daemon=True,
        )
        thread.start()

    def _run_job_fit_analysis_worker(self, profile: CandidateProfile, job_description: str, settings: AISettings, company: str, role: str) -> None:
        try:
            result = self.ai_service.analyze_job_fit(
                profile=profile,
                job_description=job_description,
                settings=settings,
                target_company=company,
                target_role=role,
            )
            self.after(0, lambda: self._finish_job_fit_analysis(result))
        except Exception as exc:
            self.after(0, lambda: self._fail_job_fit_analysis(exc))

    def _finish_job_fit_analysis(self, result: str) -> None:
        self.last_job_fit_analysis_markdown = result.strip()
        self.job_fit_text.delete("1.0", tk.END)
        self.job_fit_text.insert("1.0", self.last_job_fit_analysis_markdown)
        self.application_modified_var.set(datetime.now().isoformat(timespec="seconds"))
        self.status_var.set("Job fit analysis complete. Strategy will be used in the next generation prompt.")
        self._set_job_fit_state(False)

    def _fail_job_fit_analysis(self, exc: Exception) -> None:
        self.status_var.set("Job fit analysis failed")
        self._set_job_fit_state(False)
        self.job_fit_text.delete("1.0", tk.END)
        self.job_fit_text.insert("1.0", f"# Job Fit Analysis Failed\n\n{exc}")
        messagebox.showerror("Job fit analysis failed", f"Could not analyze job fit:\n{exc}")

    def _set_job_fit_state(self, is_running: bool) -> None:
        state = "disabled" if is_running else "normal"
        for button in getattr(self, "job_fit_buttons", []):
            button.configure(state=state)
        for button in getattr(self, "generate_buttons", []):
            button.configure(state=state)

    def _use_visible_job_fit_analysis(self) -> None:
        text = self.job_fit_text.get("1.0", tk.END).strip()
        if not text or "Run the analyzer after" in text:
            messagebox.showwarning("No analysis", "Run the job fit analyzer first.")
            return
        self.last_job_fit_analysis_markdown = text
        self.status_var.set("Visible job fit analysis will be used in the next generation prompt")

    def _clear_job_fit_analysis(self) -> None:
        self.last_job_fit_analysis_markdown = ""
        self.job_fit_text.delete("1.0", tk.END)
        self.job_fit_text.insert(
            "1.0",
            "Run the analyzer after adding the job description and structured evidence. "
            "The resulting strategy will be included automatically in CV and covering-letter generation prompts.",
        )
        self.status_var.set("Job fit analysis cleared")

    def _build_quality_request(self) -> GenerationRequest:
        if self.last_generation_request is not None:
            request = self.last_generation_request
            return GenerationRequest(
                profile=self._collect_profile(),
                job_description=self.job_description_text.get("1.0", tk.END).strip() or request.job_description,
                template_name=self.template_var.get() or request.template_name,
                document_type=request.document_type,
                ai_settings=self._collect_ai_settings(),
                job_fit_analysis=self._current_job_fit_analysis() or getattr(request, "job_fit_analysis", ""),
            )

        document_type = "CV" if self.last_document_type.lower() == "cv" else "Covering Letter"
        return GenerationRequest(
            profile=self._collect_profile(),
            job_description=self.job_description_text.get("1.0", tk.END).strip(),
            template_name=self.template_var.get(),
            document_type=document_type,
            ai_settings=self._collect_ai_settings(),
            job_fit_analysis=self._current_job_fit_analysis(),
        )

    def _run_quality_check(self) -> None:
        content = self.output_text.get("1.0", tk.END).strip()
        if not content:
            messagebox.showwarning("No output", "Generate a document first, then run the quality check.")
            return

        request = self._build_quality_request()
        if not request.job_description.strip():
            messagebox.showwarning("Missing job description", "Paste the job description before running the quality check.")
            return

        report = analyze_document(
            document_text=content,
            job_description=request.job_description,
            profile=request.profile,
            document_type=request.document_type,
        )
        markdown_report = format_quality_report(report)
        self.last_quality_heuristic_markdown = markdown_report
        self.last_ai_review_markdown = ""
        self._render_quality_panel()
        self._store_current_quality_report()
        self.status_var.set(f"Quality check complete: {report.score}/100")

    def _run_ai_quality_review(self) -> None:
        content = self.output_text.get("1.0", tk.END).strip()
        if not content:
            messagebox.showwarning("No output", "Generate a document first, then run the AI quality review.")
            return

        request = self._build_quality_request()
        if not request.job_description.strip():
            messagebox.showwarning("Missing job description", "Paste the job description before running the AI quality review.")
            return

        if not self.last_quality_heuristic_markdown:
            report = analyze_document(
                document_text=content,
                job_description=request.job_description,
                profile=request.profile,
                document_type=request.document_type,
            )
            self.last_quality_heuristic_markdown = format_quality_report(report)

        settings = request.ai_settings
        provider = settings.provider.strip() or AIService.PROVIDER_OLLAMA
        model = settings.ollama_model.strip() if provider == AIService.PROVIDER_OLLAMA else settings.model.strip()
        self.last_ai_review_markdown = ""
        self._render_ai_review_wait_screen(provider=provider, model=model or "default")
        self.status_var.set("Running AI quality review...")
        self._set_ai_review_state(True)
        self.update_idletasks()

        thread = threading.Thread(
            target=self._ai_quality_review_worker,
            args=(request, content, self.last_quality_heuristic_markdown),
            daemon=True,
        )
        thread.start()

    def _ai_quality_review_worker(self, request: GenerationRequest, content: str, heuristic_report: str) -> None:
        try:
            result = self.ai_service.review_document(request, content, heuristic_report)
            self.after(0, lambda: self._finish_ai_quality_review(result))
        except Exception as exc:
            self.after(0, lambda: self._fail_ai_quality_review(exc))

    def _finish_ai_quality_review(self, result: str) -> None:
        self.last_ai_review_markdown = result.strip()
        self._render_quality_panel()
        self._store_current_quality_report()
        self.status_var.set("AI quality review complete")
        self._set_ai_review_state(False)

    def _fail_ai_quality_review(self, exc: Exception) -> None:
        self.last_ai_review_markdown = f"# AI Quality Review\n\nAI quality review failed: {exc}"
        self._render_quality_panel()
        self._store_current_quality_report()
        self.status_var.set("AI quality review failed")
        self._set_ai_review_state(False)
        messagebox.showerror("AI quality review failed", f"Could not complete the AI quality review:\n{exc}")

    def _render_quality_panel(self) -> None:
        parts = []
        if self.last_quality_heuristic_markdown.strip():
            parts.append(self.last_quality_heuristic_markdown.strip())
        if self.last_ai_review_markdown.strip():
            parts.append(self.last_ai_review_markdown.strip())
        combined = "\n\n---\n\n".join(parts)
        self.last_quality_report_markdown = combined
        self.quality_text.delete("1.0", tk.END)
        self.quality_text.insert("1.0", combined)

    def _render_ai_review_wait_screen(self, provider: str, model: str) -> None:
        wait_message = (
            "# AI Quality Review\n\n"
            "Status: running. Wait until this screen is replaced by the completed report.\n\n"
            f"Provider: {provider}\n\n"
            f"Model: {model}\n\n"
            "The heuristic quality report is hidden during the AI review so old output is not mistaken for a finished result. "
            "When the model finishes, the app will show the full quality report and the AI review together.\n"
        )
        self.last_quality_report_markdown = wait_message
        self.quality_text.delete("1.0", tk.END)
        self.quality_text.insert("1.0", wait_message)

    def _clear_quality_report(self) -> None:
        self.last_quality_report_markdown = ""
        self.last_quality_heuristic_markdown = ""
        self.last_ai_review_markdown = ""
        self._clear_stored_quality_for_document(self.last_document_type)
        self.quality_text.delete("1.0", tk.END)
        self.status_var.set("Quality report cleared")

    def _regenerate_with_quality_fixes(self) -> None:
        content = self.output_text.get("1.0", tk.END).strip()
        if not content:
            messagebox.showwarning("No output", "Generate a document first, then improve it.")
            return

        request = self._build_quality_request()
        if not request.job_description.strip():
            messagebox.showwarning("Missing job description", "Paste the job description before improving the output.")
            return

        report = analyze_document(
            document_text=content,
            job_description=request.job_description,
            profile=request.profile,
            document_type=request.document_type,
        )
        self.last_quality_heuristic_markdown = format_quality_report(report)
        self._render_quality_panel()

        if report.score >= 85:
            proceed = messagebox.askyesno(
                "Improve anyway?",
                f"The current quality score is already {report.score}/100. Improve it anyway?",
            )
            if not proceed:
                return

        settings = request.ai_settings
        provider = settings.provider.strip() or AIService.PROVIDER_OLLAMA
        model = settings.ollama_model.strip() if provider == AIService.PROVIDER_OLLAMA else settings.model.strip()
        try:
            timeout_seconds = int(settings.timeout_seconds or 180)
        except ValueError:
            timeout_seconds = 180

        self.active_quality_improvement_job_id += 1
        job_id = self.active_quality_improvement_job_id
        self.quality_improvement_original_output = content

        self._render_quality_improvement_wait_screen(provider=provider, model=model or "default", score=report.score, timeout_seconds=timeout_seconds)
        self.status_var.set("Regenerating with quality fixes...")
        self._set_generating_state(True)
        self.update_idletasks()

        self.after((timeout_seconds + 30) * 1000, lambda current_job_id=job_id: self._quality_improvement_timeout_guard(current_job_id, timeout_seconds))
        thread = threading.Thread(
            target=self._regenerate_with_quality_fixes_worker,
            args=(job_id, request, content, self.last_quality_heuristic_markdown, self.last_ai_review_markdown),
            daemon=True,
        )
        thread.start()

    def _regenerate_with_quality_fixes_worker(
        self,
        job_id: int,
        request: GenerationRequest,
        content: str,
        heuristic_report: str,
        ai_review: str,
    ) -> None:
        try:
            result = self.ai_service.improve_document(request, content, heuristic_report, ai_review)
            if " improvement failed:" in result.lower() or result.lower().startswith(("ollama improvement failed", "openai improvement failed", "ai improvement failed")):
                raise RuntimeError(result)

            report = analyze_document(
                document_text=result,
                job_description=request.job_description,
                profile=request.profile,
                document_type=request.document_type,
            )
            markdown_report = format_quality_report(report)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            document_slug = self._document_slug(request.document_type)
            filename = f"improved_{document_slug}_{request.profile.name}_{timestamp}.md"
            saved_path = save_markdown(filename, result)
            self.after(0, lambda current_job_id=job_id: self._finish_quality_improvement(current_job_id, request, result, saved_path, markdown_report, report.score))
        except Exception as exc:
            self.after(0, lambda current_job_id=job_id: self._fail_quality_improvement(current_job_id, exc))

    def _finish_quality_improvement(
        self,
        job_id: int,
        request: GenerationRequest,
        result: str,
        saved_path: Path,
        markdown_report: str,
        score: int,
    ) -> None:
        if job_id != self.active_quality_improvement_job_id:
            return
        self.active_quality_improvement_job_id = 0
        self.last_generation_request = request
        self.last_document_type = request.document_type.lower()
        self.last_candidate_name = request.profile.name or "candidate"
        self._store_generated_document(request.document_type, result)
        self.last_quality_heuristic_markdown = markdown_report
        self.last_ai_review_markdown = ""
        self.output_text.delete("1.0", tk.END)
        self.output_text.insert("1.0", result)
        self._render_quality_panel()
        self._store_current_quality_report()
        self.application_modified_var.set(datetime.now().isoformat(timespec="seconds"))
        self.status_var.set(f"Improved {request.document_type.lower()} saved to {saved_path}. New score: {score}/100")
        self._set_generating_state(False)

    def _render_quality_improvement_wait_screen(self, provider: str, model: str, score: int, timeout_seconds: int) -> None:
        wait_message = (
            "# Improving with Quality Fixes\n\n"
            "Status: running. Wait until this screen is replaced by the improved document.\n\n"
            f"Provider: {provider}\n\n"
            f"Model: {model}\n\n"
            f"Current quality score: {score}/100\n\n"
            f"Timeout window: {timeout_seconds} seconds plus a 30 second safety buffer.\n\n"
            "The original output is preserved internally. It will be restored if the improvement fails or times out.\n"
        )
        self.output_text.delete("1.0", tk.END)
        self.output_text.insert("1.0", wait_message)
        self.quality_text.delete("1.0", tk.END)
        self.quality_text.insert("1.0", wait_message)

    def _fail_quality_improvement(self, job_id: int, exc: Exception) -> None:
        if job_id != self.active_quality_improvement_job_id:
            return
        self.active_quality_improvement_job_id = 0
        if self.quality_improvement_original_output.strip():
            self.output_text.delete("1.0", tk.END)
            self.output_text.insert("1.0", self.quality_improvement_original_output)
        self._render_quality_panel()
        self.status_var.set("Quality improvement failed")
        self._set_generating_state(False)
        messagebox.showerror("Quality improvement failed", f"Could not improve the document:\n{exc}")

    def _quality_improvement_timeout_guard(self, job_id: int, timeout_seconds: int) -> None:
        if job_id != self.active_quality_improvement_job_id:
            return
        self.active_quality_improvement_job_id = 0
        if self.quality_improvement_original_output.strip():
            self.output_text.delete("1.0", tk.END)
            self.output_text.insert("1.0", self.quality_improvement_original_output)
        self._render_quality_panel()
        self.status_var.set("Quality improvement timed out")
        self._set_generating_state(False)
        messagebox.showerror(
            "Quality improvement timed out",
            "Ollama did not finish the improvement within the timeout window. "
            f"Current timeout: {timeout_seconds} seconds. Try again with qwen3:8b, increase the timeout, or shorten the document/job description. "
            "If Ollama finishes later, that stale result will be ignored.",
        )

    def _save_quality_report(self) -> None:
        content = self.quality_text.get("1.0", tk.END).strip()
        if not content:
            messagebox.showwarning("No quality report", "Run a quality check first.")
            return
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = save_markdown(f"quality_report_{timestamp}.md", content)
        self.status_var.set(f"Quality report saved to {path}")
        messagebox.showinfo("Saved", f"Quality report saved to:\n{path}")


    def _store_generated_document(self, document_type: str, content: str) -> None:
        if (document_type or "").strip().lower() == "cv":
            self.generated_cv_markdown = content.strip()
        else:
            self.generated_covering_letter_markdown = content.strip()

    def _clear_stored_quality_for_document(self, document_type: str) -> None:
        if (document_type or "").strip().lower() == "cv":
            self.cv_quality_report_markdown = ""
        else:
            self.covering_letter_quality_report_markdown = ""

    def _store_current_quality_report(self) -> None:
        report = self.last_quality_report_markdown.strip()
        if not report:
            return
        if self.last_document_type.strip().lower() == "cv":
            self.cv_quality_report_markdown = report
        else:
            self.covering_letter_quality_report_markdown = report

    def _show_generated_cv(self) -> None:
        if not self.generated_cv_markdown.strip():
            messagebox.showwarning("No CV", "Generate a tailored CV first.")
            return
        self.last_document_type = "cv"
        self.last_generation_request = GenerationRequest(
            profile=self._collect_profile(),
            job_description=self.job_description_text.get("1.0", tk.END).strip(),
            template_name=self.template_var.get(),
            document_type="CV",
            ai_settings=self._collect_ai_settings(),
            job_fit_analysis=self._current_job_fit_analysis(),
        )
        self.output_text.delete("1.0", tk.END)
        self.output_text.insert("1.0", self.generated_cv_markdown)
        self.last_quality_report_markdown = self.cv_quality_report_markdown
        self.last_quality_heuristic_markdown = self.cv_quality_report_markdown
        self.last_ai_review_markdown = ""
        self.quality_text.delete("1.0", tk.END)
        self.quality_text.insert("1.0", self.cv_quality_report_markdown)
        self.status_var.set("Showing generated CV")

    def _show_generated_covering_letter(self) -> None:
        if not self.generated_covering_letter_markdown.strip():
            messagebox.showwarning("No covering letter", "Generate a tailored covering letter first.")
            return
        self.last_document_type = "covering letter"
        self.last_generation_request = GenerationRequest(
            profile=self._collect_profile(),
            job_description=self.job_description_text.get("1.0", tk.END).strip(),
            template_name=self.template_var.get(),
            document_type="Covering Letter",
            ai_settings=self._collect_ai_settings(),
            job_fit_analysis=self._current_job_fit_analysis(),
        )
        self.output_text.delete("1.0", tk.END)
        self.output_text.insert("1.0", self.generated_covering_letter_markdown)
        self.last_quality_report_markdown = self.covering_letter_quality_report_markdown
        self.last_quality_heuristic_markdown = self.covering_letter_quality_report_markdown
        self.last_ai_review_markdown = ""
        self.quality_text.delete("1.0", tk.END)
        self.quality_text.insert("1.0", self.covering_letter_quality_report_markdown)
        self.status_var.set("Showing generated covering letter")

    def _combined_package_quality_report(self) -> str:
        parts = []
        if self.cv_quality_report_markdown.strip():
            parts.append("# CV Quality Report\n\n" + self.cv_quality_report_markdown.strip())
        if self.covering_letter_quality_report_markdown.strip():
            parts.append("# Covering Letter Quality Report\n\n" + self.covering_letter_quality_report_markdown.strip())
        if not parts and self.last_quality_report_markdown.strip():
            parts.append("# Latest Quality Report\n\n" + self.last_quality_report_markdown.strip())
        return "\n\n---\n\n".join(parts)

    def _export_application_package(self) -> None:
        cv_markdown = self.generated_cv_markdown.strip()
        covering_letter_markdown = self.generated_covering_letter_markdown.strip()
        current_output = self.output_text.get("1.0", tk.END).strip()
        if current_output and not cv_markdown and self.last_document_type.strip().lower() == "cv":
            cv_markdown = current_output
        if current_output and not covering_letter_markdown and self.last_document_type.strip().lower() != "cv":
            covering_letter_markdown = current_output

        missing = []
        if not cv_markdown:
            missing.append("tailored CV")
        if not covering_letter_markdown:
            missing.append("tailored covering letter")
        if missing:
            messagebox.showwarning(
                "Package incomplete",
                "Generate both documents before exporting an application package. Missing: " + ", ".join(missing),
            )
            return

        company = self.application_company_var.get().strip()
        role = self.application_role_var.get().strip()
        if not company or not role:
            messagebox.showwarning("Missing workspace metadata", "Fill Target company and Target role in the Workspace tab before exporting a package.")
            return

        snapshot = self._collect_application_workspace_snapshot()
        try:
            package_path = export_application_package(
                export_root=EXPORT_DIR,
                metadata=snapshot.get("metadata", {}),
                cv_markdown=cv_markdown,
                covering_letter_markdown=covering_letter_markdown,
                quality_report_markdown=self._combined_package_quality_report(),
                application_snapshot=snapshot,
                page_size=self.pdf_page_size_var.get(),
                template_name=self.pdf_template_var.get(),
            )
        except Exception as exc:
            messagebox.showerror("Package export failed", f"Could not export application package:\n{exc}")
            self.status_var.set("Application package export failed")
            return

        self.app_settings.last_export_dir = str(package_path.parent)
        self._save_app_settings(show_message=False)
        self.status_var.set(f"Application package exported to {package_path}")
        try:
            os.startfile(str(package_path))
        except Exception:
            pass
        messagebox.showinfo("Application package exported", f"Application package exported to:\n{package_path}")

    def _save_output(self) -> None:
        content = self.output_text.get("1.0", tk.END).strip()
        if not content:
            messagebox.showwarning("No output", "Generate a document first.")
            return
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = save_markdown(f"manual_output_{timestamp}.md", content)
        self.status_var.set(f"Output saved to {path}")
        messagebox.showinfo("Saved", f"Output saved to:\n{path}")

    def _export_output_pdf(self) -> None:
        content = self.output_text.get("1.0", tk.END).strip()
        if not content:
            messagebox.showwarning("No output", "Generate a document first.")
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = self._safe_filename(f"{self.last_document_type}_{self.last_candidate_name}_{timestamp}.pdf")
        path = filedialog.asksaveasfilename(
            initialdir=self._export_dialog_initial_dir(),
            initialfile=safe_name,
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf")],
        )
        if not path:
            return

        try:
            saved_path = export_markdown_to_pdf(
                content,
                path,
                page_size=self.pdf_page_size_var.get(),
                template_name=self.pdf_template_var.get(),
            )
        except Exception as exc:
            messagebox.showerror("PDF export failed", f"Could not export PDF:\n{exc}")
            self.status_var.set("PDF export failed")
            return

        self.status_var.set(f"PDF exported to {saved_path}")
        messagebox.showinfo("PDF exported", f"PDF exported to:\n{saved_path}")

    def _load_file_into_text(self, widget: tk.Text) -> None:
        path = filedialog.askopenfilename(
            filetypes=[
                ("Supported documents", "*.txt *.md *.pdf"),
                ("PDF files", "*.pdf"),
                ("Text and Markdown", "*.txt *.md"),
                ("All files", "*.*"),
            ]
        )
        if not path:
            return
        try:
            content = load_document_text(path)
        except Exception as exc:
            messagebox.showerror("Import failed", f"Could not import this document:\n{exc}")
            self.status_var.set("Document import failed")
            return

        widget.delete("1.0", tk.END)
        widget.insert("1.0", content)
        self.application_modified_var.set(datetime.now().isoformat(timespec="seconds"))
        self.status_var.set(f"Imported {Path(path).name}")

    def _clear_text(self, widget: tk.Text) -> None:
        widget.delete("1.0", tk.END)

    def _document_slug(self, document_type: str) -> str:
        return (document_type or "document").strip().lower().replace(" ", "_")

    def _safe_filename(self, filename: str) -> str:
        allowed = []
        for char in filename.strip().replace(" ", "_").lower():
            if char.isalnum() or char in {"_", "-", "."}:
                allowed.append(char)
        return "".join(allowed) or "document.pdf"

    def _update_template_description(self) -> None:
        selected = self.template_var.get()
        template = TEMPLATES.get(selected, TEMPLATES["ATS Friendly"])
        pdf_template = PDF_TEMPLATES.get(selected)
        pdf_note = pdf_template.description if pdf_template else "PDF export also supports selectable layouts in the Output tab."
        content = (
            f"{selected}\n\n"
            f"AI writing purpose: {template['description']}\n\n"
            f"AI writing tone: {template['tone']}\n\n"
            f"PDF layout: {pdf_note}\n\n"
            "Use the template selector for writing style, then choose the PDF template in the Output tab before exporting."
        )
        self.template_description.configure(state="normal")
        self.template_description.delete("1.0", tk.END)
        self.template_description.insert("1.0", content)
        self.template_description.configure(state="disabled")
