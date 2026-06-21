# Project selection for CV generation

ResuBuilder ranks supplied project evidence against the target job instead of dumping every project into the CV.

## Current rule

For CVs, the generator should:

- include at least 3 truthful project entries when 3 or more are supplied;
- order projects from strongest job fit to weaker fit;
- omit weaker extra projects unless they add clear value;
- use `### Project Name` headings so PDF export can keep short project blocks together;
- consider strategic domain relevance, not only exact keyword overlap.

## Defence and mission-critical AI jobs

For roles involving defence, mission-critical AI, sovereign technology, signals, sensors, robustness, deployment, or AI systems, the generator now treats these project signals as high priority:

- RF signal intelligence;
- raw IQ or sensor processing;
- modulation recognition;
- channel-shift or distribution-shift detection;
- robustness experiments;
- GPU inference and deployment benchmarking;
- research-to-application engineering.

For a Helsing-style defence AI role, `RF Signal Intelligence Lab` should normally be selected over weaker biomedical or generic validation projects unless the candidate has at least three projects with more direct foundation-model, LLM/VLM, transformer, distributed-training, or multimodal evidence.

## Debugging project selection

If a strong project is still omitted:

1. Put the project in Structured Evidence with `Type: Project`.
2. Make the title explicit, for example `RF Signal Intelligence Lab`.
3. Add job-specific signals in the evidence, such as `defence AI`, `signal intelligence`, `robustness`, `PyTorch`, `deployment inference`, and `channel-shift detection`.
4. Run Job Fit Analysis before generation.
5. Use AI edit instructions after generation to force a replacement if needed, for example:

```text
Replace the weakest project with RF Signal Intelligence Lab. Keep at least 3 projects. Order the projects by relevance to this Helsing defence AI role.
```
