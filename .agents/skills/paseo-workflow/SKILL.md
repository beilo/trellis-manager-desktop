---
name: paseo-workflow
description: "Run project-local reusable Paseo workflows, especially PRD -> Implement -> Review multi-agent flows."
---

# Paseo Workflow

Use this skill when the user asks to run a reusable Paseo workflow by name, or asks the main agent to orchestrate planning, implementation, and review through Paseo.

## Contract

- Workflow definitions live under `.agents/workflows/`.
- The executor is `scripts/run_paseo_workflow.py`.
- Dry-run is safe and does not start agents.
- Real execution requires `paseo` on PATH and a reachable Paseo daemon.
- Do not install, uninstall, start, or stop Paseo unless the user explicitly asks.

## Default Workflow

`prd-impl-review` runs:

1. Codex plans Trellis `prd.md`, `design.md`, and `implement.md`.
2. Claude Code implements from those artifacts.
3. Codex reviews implementation against those artifacts.

## Commands

Preview:

```bash
python3 scripts/run_paseo_workflow.py prd-impl-review \
  --cwd /path/to/repo \
  --task "用户需求" \
  --dry-run
```

Execute:

```bash
python3 scripts/run_paseo_workflow.py prd-impl-review \
  --cwd /path/to/repo \
  --task "用户需求"
```

Machine-readable output:

```bash
python3 scripts/run_paseo_workflow.py prd-impl-review \
  --cwd /path/to/repo \
  --task "用户需求" \
  --json
```

## Operating Rules

- Run dry-run first when the workflow or input is new.
- If execution fails, report the failed step id, error code, and next recovery action.
- Keep workflow prompts explicit; do not depend on hidden chat memory.
- Workflow files must not contain secrets.
