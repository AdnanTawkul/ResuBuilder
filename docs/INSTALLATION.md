# Installation Guide

This guide explains how to run ResuBuilder from source and how to use the Windows executable.

## Option 1: Run from source

### 1. Install Python

Install Python 3.10 or newer.

During installation, enable:

```text
Add Python to PATH
```

### 2. Clone the repository

Use GitHub Desktop or the command line.

With GitHub Desktop:

```text
File > Clone Repository
```

Choose the ResuBuilder repository and clone it locally.

### 3. Open in PyCharm

Open the project folder in PyCharm.

### 4. Create a virtual environment

In the PyCharm terminal:

```powershell
python -m venv .venv
.\.venv\Scripts\activate
```

### 5. Install dependencies

```powershell
pip install -r requirements.txt
```

### 6. Run the app

```powershell
python app.py
```

## Option 2: Use the Windows executable

After building or downloading the release package, run:

```text
ResuBuilder.exe
```

The executable is usually located in:

```text
dist/ResuBuilder/ResuBuilder.exe
```

## Local AI setup with Ollama

Install Ollama, then pull a model:

```powershell
ollama pull qwen3:14b
```

Confirm it works:

```powershell
ollama run qwen3:14b
```

In ResuBuilder settings, use:

```text
AI provider: Ollama Local
Ollama base URL: http://localhost:11434
Ollama model: qwen3:14b
Timeout: 180
```

## Optional OpenAI setup

Set your OpenAI API key as an environment variable:

```powershell
setx OPENAI_API_KEY "your_api_key_here"
```

Close and reopen PyCharm or the terminal after setting it.

Do not commit API keys to GitHub.
