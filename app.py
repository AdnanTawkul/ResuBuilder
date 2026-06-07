"""Primary entry point for ResuBuilder.

The PySide6/Qt interface is now the main application shell.
Run with:
    python app.py
"""

from src.resume_ai.qt_gui import run_qt_app


if __name__ == "__main__":
    run_qt_app()
