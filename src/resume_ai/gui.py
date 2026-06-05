from __future__ import annotations

from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk

from .ai_service import AIService
from .models import CandidateProfile, GenerationRequest
from .pdf_exporter import export_markdown_to_pdf
from .storage import EXPORT_DIR, load_json, save_json, save_markdown
from .templates import get_template_names, TEMPLATES


class ResumeAIApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Resume AI 2")
        self.geometry("1100x760")
        self.minsize(950, 650)

        self.ai_service = AIService()
        self.single_line_fields: dict[str, tk.StringVar] = {}
        self.multi_line_fields: dict[str, tk.Text] = {}
        self.template_var = tk.StringVar(value="ATS Friendly")
        self.pdf_page_size_var = tk.StringVar(value="A4")
        self.status_var = tk.StringVar(value="Ready")
        self.last_document_type = "document"
        self.last_candidate_name = "candidate"

        self._build_ui()
        self._load_saved_profile()

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        notebook = ttk.Notebook(self)
        notebook.grid(row=0, column=0, sticky="nsew")

        personal_tab = ttk.Frame(notebook, padding=12)
        job_tab = ttk.Frame(notebook, padding=12)
        source_tab = ttk.Frame(notebook, padding=12)
        template_tab = ttk.Frame(notebook, padding=12)
        output_tab = ttk.Frame(notebook, padding=12)

        notebook.add(personal_tab, text="Personal Info")
        notebook.add(job_tab, text="Job Description")
        notebook.add(source_tab, text="Existing CV / Resume")
        notebook.add(template_tab, text="Templates")
        notebook.add(output_tab, text="Output")

        self._build_personal_tab(personal_tab)
        self._build_job_tab(job_tab)
        self._build_source_tab(source_tab)
        self._build_template_tab(template_tab)
        self._build_output_tab(output_tab)

        footer = ttk.Frame(self, padding=(12, 8))
        footer.grid(row=1, column=0, sticky="ew")
        footer.columnconfigure(0, weight=1)

        ttk.Label(footer, textvariable=self.status_var).grid(row=0, column=0, sticky="w")
        ttk.Button(footer, text="Save Profile", command=self._save_profile).grid(row=0, column=1, padx=6)
        ttk.Button(footer, text="Generate Tailored CV", command=lambda: self._generate("CV")).grid(row=0, column=2, padx=6)
        ttk.Button(footer, text="Generate Tailored Resume", command=lambda: self._generate("Resume")).grid(row=0, column=3, padx=6)

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

    def _build_job_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        ttk.Label(parent, text="Paste the full job description here. The stronger this input is, the better the tailoring.").grid(row=0, column=0, sticky="w")
        self.job_description_text = tk.Text(parent, wrap="word")
        self.job_description_text.grid(row=1, column=0, sticky="nsew", pady=8)

        button_frame = ttk.Frame(parent)
        button_frame.grid(row=2, column=0, sticky="ew")
        ttk.Button(button_frame, text="Load Job Description from .txt/.md", command=lambda: self._load_file_into_text(self.job_description_text)).pack(side="left")
        ttk.Button(button_frame, text="Clear", command=lambda: self._clear_text(self.job_description_text)).pack(side="left", padx=8)

    def _build_source_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.columnconfigure(1, weight=1)
        parent.rowconfigure(1, weight=1)

        ttk.Label(parent, text="General CV").grid(row=0, column=0, sticky="w")
        ttk.Label(parent, text="General Resume").grid(row=0, column=1, sticky="w")

        self.general_cv_text = tk.Text(parent, wrap="word")
        self.general_resume_text = tk.Text(parent, wrap="word")
        self.general_cv_text.grid(row=1, column=0, sticky="nsew", padx=(0, 6), pady=8)
        self.general_resume_text.grid(row=1, column=1, sticky="nsew", padx=(6, 0), pady=8)
        self.multi_line_fields["general_cv"] = self.general_cv_text
        self.multi_line_fields["general_resume"] = self.general_resume_text

        cv_buttons = ttk.Frame(parent)
        resume_buttons = ttk.Frame(parent)
        cv_buttons.grid(row=2, column=0, sticky="w")
        resume_buttons.grid(row=2, column=1, sticky="w")

        ttk.Button(cv_buttons, text="Load CV .txt/.md", command=lambda: self._load_file_into_text(self.general_cv_text)).pack(side="left")
        ttk.Button(cv_buttons, text="Clear", command=lambda: self._clear_text(self.general_cv_text)).pack(side="left", padx=8)
        ttk.Button(resume_buttons, text="Load Resume .txt/.md", command=lambda: self._load_file_into_text(self.general_resume_text)).pack(side="left")
        ttk.Button(resume_buttons, text="Clear", command=lambda: self._clear_text(self.general_resume_text)).pack(side="left", padx=8)

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
        ttk.Label(buttons, text="Page size").pack(side="left", padx=(12, 4))
        ttk.Combobox(buttons, textvariable=self.pdf_page_size_var, values=["A4", "Letter"], width=8, state="readonly").pack(side="left")
        ttk.Button(buttons, text="Clear Output", command=lambda: self._clear_text(self.output_text)).pack(side="left", padx=8)

    def _load_saved_profile(self) -> None:
        data = load_json()
        if not data:
            return
        for key, var in self.single_line_fields.items():
            var.set(data.get(key, ""))
        for key, widget in self.multi_line_fields.items():
            widget.delete("1.0", tk.END)
            widget.insert("1.0", data.get(key, ""))
        self.status_var.set("Loaded saved profile")

    def _collect_profile(self) -> CandidateProfile:
        data = {key: var.get().strip() for key, var in self.single_line_fields.items()}
        for key, widget in self.multi_line_fields.items():
            data[key] = widget.get("1.0", tk.END).strip()
        return CandidateProfile(**data)

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
        )
        self.status_var.set(f"Generating tailored {document_type.lower()}...")
        self.update_idletasks()

        result = self.ai_service.generate(request)
        self.last_document_type = document_type.lower()
        self.last_candidate_name = profile.name or "candidate"
        self.output_text.delete("1.0", tk.END)
        self.output_text.insert("1.0", result)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{document_type.lower()}_{profile.name}_{timestamp}.md"
        saved_path = save_markdown(filename, result)
        self.status_var.set(f"Generated {document_type.lower()} and saved to {saved_path}")

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
            initialdir=EXPORT_DIR,
            initialfile=safe_name,
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf")],
        )
        if not path:
            return

        try:
            saved_path = export_markdown_to_pdf(content, path, page_size=self.pdf_page_size_var.get())
        except Exception as exc:
            messagebox.showerror("PDF export failed", f"Could not export PDF:\n{exc}")
            self.status_var.set("PDF export failed")
            return

        self.status_var.set(f"PDF exported to {saved_path}")
        messagebox.showinfo("PDF exported", f"PDF exported to:\n{saved_path}")

    def _load_file_into_text(self, widget: tk.Text) -> None:
        path = filedialog.askopenfilename(
            filetypes=[("Text and Markdown", "*.txt *.md"), ("All files", "*.*")]
        )
        if not path:
            return
        try:
            content = Path(path).read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = Path(path).read_text(encoding="latin-1")
        widget.delete("1.0", tk.END)
        widget.insert("1.0", content)
        self.status_var.set(f"Loaded {path}")

    def _clear_text(self, widget: tk.Text) -> None:
        widget.delete("1.0", tk.END)

    def _safe_filename(self, filename: str) -> str:
        allowed = []
        for char in filename.strip().replace(" ", "_").lower():
            if char.isalnum() or char in {"_", "-", "."}:
                allowed.append(char)
        return "".join(allowed) or "document.pdf"

    def _update_template_description(self) -> None:
        selected = self.template_var.get()
        template = TEMPLATES.get(selected, TEMPLATES["ATS Friendly"])
        content = (
            f"{selected}\n\n"
            f"Purpose: {template['description']}\n\n"
            f"Tone: {template['tone']}\n\n"
            "Current version creates Markdown and PDF output. Later versions should add stronger visual templates, validation, and saved template presets."
        )
        self.template_description.configure(state="normal")
        self.template_description.delete("1.0", tk.END)
        self.template_description.insert("1.0", content)
        self.template_description.configure(state="disabled")
