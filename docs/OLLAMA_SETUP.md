# Ollama setup for ResuBuilder

ResuBuilder does not bundle Ollama or local AI models inside the Windows executable.

On each computer that should use local AI, install Ollama and download a model first.

## Recommended setup

1. Install Ollama for Windows from:

```text
https://ollama.com/download/windows
```

2. Open PowerShell.

3. Download the recommended default model:

```powershell
ollama pull qwen3:8b
```

4. Test the model:

```powershell
ollama run qwen3:8b
```

5. Open ResuBuilder.

6. Go to:

```text
Settings > Open Settings...
```

7. Set:

```text
AI provider: Ollama Local
Ollama base URL: http://localhost:11434
Ollama model: qwen3:8b
```

8. Click:

```text
Check Ollama Setup
```

## Model recommendations

```text
qwen3:8b       Recommended default for most computers
qwen3:14b      Better quality, stronger computers only
llama3.1:8b    Backup option
```

## Common problems

### Ollama generation failed

Usually this means one of these is true:

```text
Ollama is not installed
Ollama is not running
The selected model is not downloaded
The app is pointing to the wrong Ollama URL
The computer is too weak for the selected model
```

### Selected model is missing

Run:

```powershell
ollama pull qwen3:8b
```

or choose a model that is already installed.

### Stronger model is too slow

Use:

```text
qwen3:8b
```

instead of:

```text
qwen3:14b
```
