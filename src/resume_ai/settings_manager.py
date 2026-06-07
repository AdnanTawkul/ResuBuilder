from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any

from .app_paths import data_dir, settings_path


DATA_DIR = data_dir()
SETTINGS_PATH = settings_path()


@dataclass
class AppSettings:
    schema_version: int = 1
    ui_theme: str = "Dark blue"
    template_name: str = "ATS Friendly"
    pdf_template: str = "ATS Friendly"
    pdf_page_size: str = "A4"
    use_ai: bool = True
    ai_provider: str = "Ollama Local"
    openai_model: str = "gpt-4.1-mini"
    generation_mode: str = "Balanced"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3:14b"
    timeout_seconds: int = 120
    last_workspace_dir: str = ""
    last_export_dir: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AppSettings":
        defaults = cls()
        if not isinstance(data, dict):
            return defaults

        timeout = data.get("timeout_seconds", defaults.timeout_seconds)
        try:
            timeout = int(timeout)
        except (TypeError, ValueError):
            timeout = defaults.timeout_seconds
        timeout = max(30, min(timeout, 600))

        theme = str(data.get("ui_theme", defaults.ui_theme) or defaults.ui_theme)
        if theme == "Soft Blue":
            theme = "Dark blue"
        if theme not in {"Light", "Dark", "Dark blue", "Modern 3D Light", "Modern 3D Dark"}:
            theme = defaults.ui_theme

        provider = str(data.get("ai_provider", defaults.ai_provider) or defaults.ai_provider)
        if provider not in {"Ollama Local", "OpenAI"}:
            provider = defaults.ai_provider

        mode = str(data.get("generation_mode", defaults.generation_mode) or defaults.generation_mode)
        if mode not in {"Conservative", "Balanced", "Aggressive"}:
            mode = defaults.generation_mode

        page_size = str(data.get("pdf_page_size", defaults.pdf_page_size) or defaults.pdf_page_size)
        if page_size not in {"A4", "Letter"}:
            page_size = defaults.pdf_page_size

        return cls(
            schema_version=int(data.get("schema_version", defaults.schema_version) or defaults.schema_version),
            ui_theme=theme,
            template_name=str(data.get("template_name", defaults.template_name) or defaults.template_name),
            pdf_template=str(data.get("pdf_template", defaults.pdf_template) or defaults.pdf_template),
            pdf_page_size=page_size,
            use_ai=bool(data.get("use_ai", defaults.use_ai)),
            ai_provider=provider,
            openai_model=str(data.get("openai_model", defaults.openai_model) or defaults.openai_model),
            generation_mode=mode,
            ollama_base_url=str(data.get("ollama_base_url", defaults.ollama_base_url) or defaults.ollama_base_url),
            ollama_model=str(data.get("ollama_model", defaults.ollama_model) or defaults.ollama_model),
            timeout_seconds=timeout,
            last_workspace_dir=str(data.get("last_workspace_dir", defaults.last_workspace_dir) or defaults.last_workspace_dir),
            last_export_dir=str(data.get("last_export_dir", defaults.last_export_dir) or defaults.last_export_dir),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_app_settings(path: Path = SETTINGS_PATH) -> AppSettings:
    if not path.exists():
        return AppSettings()
    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, json.JSONDecodeError):
        return AppSettings()
    return AppSettings.from_dict(data)


def save_app_settings(settings: AppSettings, path: Path = SETTINGS_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(settings.to_dict(), file, indent=2, ensure_ascii=False)
    return path
