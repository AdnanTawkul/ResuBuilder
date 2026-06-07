"""Legacy Tkinter entry point for ResuBuilder.

This keeps the old GUI available while the Qt interface becomes primary.
Run with:
    python app_legacy.py
"""

from src.resume_ai.gui import ResumeAIApp


if __name__ == "__main__":
    app = ResumeAIApp()
    app.mainloop()
