# Skill Selection

ResuBuilder should not copy generic job-signal words into the CV Core Skills section.

## Problem

A generated CV can become weak when the Core Skills section is built from extracted job keywords or quality-report signals instead of the candidate's real skills inventory.

Bad example:

```text
software engineering, machine learning, deep learning, training, research, customer, pytorch, python, models
```

This is weak because it includes vague standalone terms such as `customer`, `research`, `training`, and `models`.

## Correct behavior

For CV generation, the app should:

- Select skills from the candidate's supplied skills inventory and structured evidence.
- Keep the skills section compact.
- Prioritize skills that match the target job.
- Prefer concrete tools, methods, model types, workflows, and evaluation concepts.
- Avoid copying generic job signals or quality-checker keywords.
- Avoid unsupported claims.

## Good example for a Helsing-style AI Research Engineer CV

```text
Python, PyTorch, deep learning, CNNs, self-supervised learning, transfer learning, model adaptation, custom loss functions, optical flow, RAFT, YOLO, raw IQ signal processing, RF modulation recognition, channel-shift detection, robustness evaluation, model evaluation, AUC-ROC, F1-score, reproducible ML workflows, CUDA, Git/GitHub
```

This list is compact but stronger because it uses specific, truthful skills from the candidate's actual evidence.

## Notes

Do not add unsupported terms such as LLM training, VLM fine-tuning, JAX, transformers, attention mechanisms, or distributed training unless the candidate has evidence for them.
