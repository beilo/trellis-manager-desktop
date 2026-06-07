from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.run_paseo_workflow import (  # noqa: E402
    CommandResult,
    PaseoAdapter,
    WorkflowError,
    build_context,
    load_workflow,
    run_workflow,
)


class FakeRunner:
    def __init__(self, *, fail_run: bool = False) -> None:
        self.fail_run = fail_run
        self.calls: list[tuple[list[str], Path | None]] = []

    def run(self, command: Sequence[str], *, cwd: Path | None = None, timeout: int = 60) -> CommandResult:
        normalized = [str(part) for part in command]
        self.calls.append((normalized, cwd))
        if normalized[:3] == ["paseo", "status", "--json"]:
            return CommandResult(normalized, cwd, 0, '{"localDaemon":"running"}', "", 1)
        if normalized[:3] == ["paseo", "run", "--json"]:
            if self.fail_run:
                return CommandResult(normalized, cwd, 1, "", "agent failed", 1)
            return CommandResult(normalized, cwd, 0, json.dumps({"agentId": "agent-1", "status": "completed"}), "", 1)
        return CommandResult(normalized, cwd, 1, "", "unexpected command", 1)


class PaseoWorkflowTest(unittest.TestCase):
    def _write_workflow(self, root: Path, *, requires_artifact: bool = False) -> Path:
        workflow_dir = root / ".agents" / "workflows"
        workflow_dir.mkdir(parents=True)
        requires = ["prd.md"] if requires_artifact else []
        (workflow_dir / "demo.json").write_text(
            json.dumps(
                {
                    "name": "demo",
                    "description": "demo workflow",
                    "inputs": {
                        "task": {"required": True},
                        "cwd": {"required": True},
                    },
                    "steps": [
                        {
                            "id": "plan",
                            "title": "Plan {{task}}",
                            "provider": "codex/gpt-5.4",
                            "cwd": "{{cwd}}",
                            "prompt": "Plan {{task}}",
                            "wait": True,
                            "stopOnFailure": True,
                            "requiresArtifacts": requires,
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        return workflow_dir

    def test_dry_run_resolves_steps_without_calling_paseo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflow_dir = self._write_workflow(root)
            workflow = load_workflow(workflow_dir, "demo")
            context = build_context(workflow, {"task": "Add workflow", "cwd": str(root)}, root)
            runner = FakeRunner()

            result = run_workflow(workflow, context, PaseoAdapter(runner), dry_run=True)

            self.assertEqual(result.status, "ok")
            self.assertEqual(runner.calls, [])
            self.assertEqual(result.steps[0].status, "planned")
            self.assertIn("Plan Add workflow", result.steps[0].command)

    def test_missing_required_input_fails_before_execution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflow_dir = self._write_workflow(root)
            workflow = load_workflow(workflow_dir, "demo")

            with self.assertRaises(WorkflowError) as context:
                build_context(workflow, {"cwd": str(root)}, root)

            self.assertEqual(context.exception.code, "MISSING_INPUT")

    def test_execution_checks_daemon_and_runs_step(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflow_dir = self._write_workflow(root)
            workflow = load_workflow(workflow_dir, "demo")
            context = build_context(workflow, {"task": "Add workflow", "cwd": str(root)}, root)
            runner = FakeRunner()

            result = run_workflow(workflow, context, PaseoAdapter(runner), dry_run=False)

            self.assertEqual(result.status, "ok")
            self.assertEqual(runner.calls[0][0], ["paseo", "status", "--json"])
            self.assertEqual(result.steps[0].agent_id, "agent-1")
            self.assertIn("--provider", runner.calls[1][0])
            self.assertIn("codex/gpt-5.4", runner.calls[1][0])

    def test_step_failure_stops_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflow_dir = self._write_workflow(root)
            workflow = load_workflow(workflow_dir, "demo")
            context = build_context(workflow, {"task": "Add workflow", "cwd": str(root)}, root)

            result = run_workflow(workflow, context, PaseoAdapter(FakeRunner(fail_run=True)), dry_run=False)

            self.assertEqual(result.status, "failed")
            self.assertEqual(result.error["code"], "PASEO_STEP_FAILED")
            self.assertEqual(result.steps[0].status, "failed")

    def test_required_artifact_missing_fails_step(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflow_dir = self._write_workflow(root, requires_artifact=True)
            workflow = load_workflow(workflow_dir, "demo")
            context = build_context(workflow, {"task": "Add workflow", "cwd": str(root)}, root)

            result = run_workflow(workflow, context, PaseoAdapter(FakeRunner()), dry_run=True)

            self.assertEqual(result.status, "failed")
            self.assertEqual(result.error["code"], "MISSING_ARTIFACT")


if __name__ == "__main__":
    unittest.main()
