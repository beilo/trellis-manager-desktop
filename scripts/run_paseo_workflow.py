#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, Sequence


TEMPLATE_RE = re.compile(r"{{\s*([A-Za-z0-9_.-]+)\s*}}")


class WorkflowError(Exception):
    def __init__(self, code: str, message: str, *, step_id: str | None = None, details: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.step_id = step_id
        self.details = details

    def to_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "message": self.message,
            "stepId": self.step_id,
            "details": self.details,
        }


@dataclass(frozen=True)
class CommandResult:
    command: list[str]
    cwd: Path | None
    returncode: int | None
    stdout: str
    stderr: str
    duration_ms: int
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and self.error is None


class CommandRunner(Protocol):
    def run(self, command: Sequence[str], *, cwd: Path | None = None, timeout: int = 60) -> CommandResult:
        ...


class SubprocessRunner:
    def run(self, command: Sequence[str], *, cwd: Path | None = None, timeout: int = 60) -> CommandResult:
        normalized = [str(part) for part in command]
        started = time.monotonic()
        try:
            completed = subprocess.run(
                normalized,
                cwd=str(cwd) if cwd is not None else None,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                shell=False,
                check=False,
            )
            return CommandResult(
                command=normalized,
                cwd=cwd,
                returncode=completed.returncode,
                stdout=completed.stdout,
                stderr=completed.stderr,
                duration_ms=int((time.monotonic() - started) * 1000),
            )
        except subprocess.TimeoutExpired as error:
            return CommandResult(
                command=normalized,
                cwd=cwd,
                returncode=None,
                stdout=error.stdout or "",
                stderr=error.stderr or "",
                duration_ms=int((time.monotonic() - started) * 1000),
                error=f"命令超时：{timeout} 秒内没有完成。",
            )
        except OSError as error:
            return CommandResult(
                command=normalized,
                cwd=cwd,
                returncode=None,
                stdout="",
                stderr="",
                duration_ms=int((time.monotonic() - started) * 1000),
                error=f"命令无法执行：{error}",
            )


@dataclass(frozen=True)
class WorkflowStep:
    id: str
    title: str
    provider: str
    prompt: str
    cwd: str
    wait: bool = True
    stop_on_failure: bool = True
    mode: str | None = None
    worktree: str | None = None
    wait_timeout: str | None = None
    requires_artifacts: tuple[str, ...] = ()


@dataclass(frozen=True)
class Workflow:
    name: str
    description: str
    inputs: dict[str, dict[str, Any]]
    steps: tuple[WorkflowStep, ...]


@dataclass(frozen=True)
class StepResult:
    id: str
    title: str
    provider: str
    cwd: str
    status: str
    command: list[str]
    agent_id: str | None = None
    summary: str | None = None
    error: dict[str, object] | None = None


@dataclass
class WorkflowRunResult:
    workflow: str
    dry_run: bool
    status: str
    steps: list[StepResult] = field(default_factory=list)
    error: dict[str, object] | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "workflow": self.workflow,
            "dryRun": self.dry_run,
            "status": self.status,
            "steps": [
                {
                    "id": step.id,
                    "title": step.title,
                    "provider": step.provider,
                    "cwd": step.cwd,
                    "status": step.status,
                    "command": step.command,
                    "agentId": step.agent_id,
                    "summary": step.summary,
                    "error": step.error,
                }
                for step in self.steps
            ],
            "error": self.error,
        }


def _as_mapping(value: Any, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise WorkflowError("INVALID_CONFIG", f"`{field_name}` 必须是对象。")
    return value


def load_workflow(workflow_dir: Path, name: str) -> Workflow:
    path = workflow_dir / f"{name}.json"
    if not path.exists():
        raise WorkflowError("WORKFLOW_NOT_FOUND", f"找不到 workflow 配置：{path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise WorkflowError("INVALID_JSON", f"workflow JSON 无法解析：{path}", details=str(error)) from error

    root = _as_mapping(data, "workflow")
    workflow_name = root.get("name")
    if workflow_name != name:
        raise WorkflowError("INVALID_CONFIG", f"workflow name 必须是 `{name}`。")
    inputs = _as_mapping(root.get("inputs", {}), "inputs")
    raw_steps = root.get("steps")
    if not isinstance(raw_steps, list) or not raw_steps:
        raise WorkflowError("INVALID_CONFIG", "`steps` 必须是非空数组。")

    steps: list[WorkflowStep] = []
    seen_ids: set[str] = set()
    for index, raw_step in enumerate(raw_steps):
        step = _as_mapping(raw_step, f"steps[{index}]")
        step_id = _required_string(step, "id", index)
        if step_id in seen_ids:
            raise WorkflowError("INVALID_CONFIG", f"重复的 step id：{step_id}", step_id=step_id)
        seen_ids.add(step_id)
        requires = step.get("requiresArtifacts", [])
        if not isinstance(requires, list) or any(not isinstance(item, str) for item in requires):
            raise WorkflowError("INVALID_CONFIG", "`requiresArtifacts` 必须是字符串数组。", step_id=step_id)
        steps.append(
            WorkflowStep(
                id=step_id,
                title=_required_string(step, "title", index),
                provider=_required_string(step, "provider", index),
                prompt=_required_string(step, "prompt", index),
                cwd=_required_string(step, "cwd", index),
                wait=bool(step.get("wait", True)),
                stop_on_failure=bool(step.get("stopOnFailure", True)),
                mode=_optional_string(step, "mode"),
                worktree=_optional_string(step, "worktree"),
                wait_timeout=_optional_string(step, "waitTimeout"),
                requires_artifacts=tuple(requires),
            )
        )

    return Workflow(
        name=workflow_name,
        description=str(root.get("description", "")),
        inputs=inputs,
        steps=tuple(steps),
    )


def _required_string(step: dict[str, Any], key: str, index: int) -> str:
    value = step.get(key)
    if not isinstance(value, str) or not value.strip():
        raise WorkflowError("INVALID_CONFIG", f"`steps[{index}].{key}` 必须是非空字符串。")
    return value


def _optional_string(step: dict[str, Any], key: str) -> str | None:
    value = step.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise WorkflowError("INVALID_CONFIG", f"`{key}` 必须是非空字符串。")
    return value


def build_context(workflow: Workflow, cli_inputs: dict[str, str], default_cwd: Path) -> dict[str, str]:
    context: dict[str, str] = {"cwd": str(default_cwd)}
    for name, spec in workflow.inputs.items():
        if not isinstance(spec, dict):
            raise WorkflowError("INVALID_CONFIG", f"`inputs.{name}` 必须是对象。")
        if name in cli_inputs:
            context[name] = cli_inputs[name]
            continue
        default = spec.get("default")
        if isinstance(default, str):
            context[name] = render_template(default, context)
            continue
        if spec.get("required") is True:
            raise WorkflowError("MISSING_INPUT", f"缺少必填输入：{name}")
    context.update(cli_inputs)
    return context


def render_template(template: str, context: dict[str, str]) -> str:
    missing: list[str] = []

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        value = context.get(key)
        if value is None:
            missing.append(key)
            return match.group(0)
        return value

    rendered = TEMPLATE_RE.sub(replace, template)
    if missing:
        raise WorkflowError("UNRESOLVED_TEMPLATE", f"模板变量未提供：{', '.join(sorted(set(missing)))}")
    return rendered


def parse_key_value(values: list[str]) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise WorkflowError("INVALID_INPUT", f"输入必须是 key=value：{value}")
        key, raw = value.split("=", 1)
        if not key.strip():
            raise WorkflowError("INVALID_INPUT", f"输入 key 不能为空：{value}")
        parsed[key.strip()] = raw
    return parsed


class PaseoAdapter:
    def __init__(self, runner: CommandRunner, *, paseo_bin: str = "paseo") -> None:
        self.runner = runner
        self.paseo_bin = paseo_bin

    def check_daemon(self, cwd: Path) -> None:
        result = self.runner.run([self.paseo_bin, "status", "--json"], cwd=cwd, timeout=15)
        if not result.ok:
            raise WorkflowError(
                "PASEO_DAEMON_UNAVAILABLE",
                "Paseo daemon 不可用，请先启动 Paseo。",
                details=_result_details(result),
            )

    def build_run_command(self, step: WorkflowStep, *, cwd: str, prompt: str, title: str) -> list[str]:
        command = [
            self.paseo_bin,
            "run",
            "--json",
            "--provider",
            step.provider,
            "--title",
            title,
            "--cwd",
            cwd,
        ]
        if step.mode:
            command.extend(["--mode", step.mode])
        if step.worktree:
            command.extend(["--worktree", step.worktree])
        if step.wait:
            if step.wait_timeout:
                command.extend(["--wait-timeout", step.wait_timeout])
        else:
            command.append("--detach")
        command.append(prompt)
        return command

    def run_step(self, step: WorkflowStep, *, cwd: str, prompt: str, title: str) -> tuple[CommandResult, str | None, str | None]:
        command = self.build_run_command(step, cwd=cwd, prompt=prompt, title=title)
        result = self.runner.run(command, cwd=Path(cwd), timeout=24 * 60 * 60)
        if not result.ok:
            return result, None, None
        agent_id, summary = _parse_agent_output(result.stdout)
        return result, agent_id, summary


def _parse_agent_output(stdout: str) -> tuple[str | None, str | None]:
    if not stdout.strip():
        return None, None
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return None, stdout.strip().splitlines()[-1][:500]
    if isinstance(payload, list) and payload:
        payload = payload[0]
    if not isinstance(payload, dict):
        return None, None
    agent_id = _first_string(payload, ("agentId", "id", "shortId"))
    summary = _first_string(payload, ("summary", "message", "status"))
    return agent_id, summary


def _first_string(payload: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def run_workflow(
    workflow: Workflow,
    context: dict[str, str],
    adapter: PaseoAdapter,
    *,
    dry_run: bool,
) -> WorkflowRunResult:
    result = WorkflowRunResult(workflow=workflow.name, dry_run=dry_run, status="ok")
    if not dry_run:
        adapter.check_daemon(Path(context["cwd"]))

    for step in workflow.steps:
        try:
            rendered_cwd = render_template(step.cwd, context)
            rendered_title = render_template(step.title, context)
            rendered_prompt = render_template(step.prompt, context)
            _check_required_artifacts(step, rendered_cwd, context)
            command = adapter.build_run_command(step, cwd=rendered_cwd, prompt=rendered_prompt, title=rendered_title)
            if dry_run:
                result.steps.append(
                    StepResult(
                        id=step.id,
                        title=rendered_title,
                        provider=step.provider,
                        cwd=rendered_cwd,
                        status="planned",
                        command=command,
                    )
                )
                continue
            command_result, agent_id, summary = adapter.run_step(
                step,
                cwd=rendered_cwd,
                prompt=rendered_prompt,
                title=rendered_title,
            )
            if not command_result.ok:
                error = WorkflowError("PASEO_STEP_FAILED", "Paseo step 执行失败。", step_id=step.id, details=_result_details(command_result))
                result.steps.append(
                    StepResult(
                        id=step.id,
                        title=rendered_title,
                        provider=step.provider,
                        cwd=rendered_cwd,
                        status="failed",
                        command=command,
                        error=error.to_dict(),
                    )
                )
                if step.stop_on_failure:
                    result.status = "failed"
                    result.error = error.to_dict()
                    return result
            else:
                result.steps.append(
                    StepResult(
                        id=step.id,
                        title=rendered_title,
                        provider=step.provider,
                        cwd=rendered_cwd,
                        status="completed" if step.wait else "started",
                        command=command,
                        agent_id=agent_id,
                        summary=summary,
                    )
                )
        except WorkflowError as error:
            result.steps.append(
                StepResult(
                    id=step.id,
                    title=step.title,
                    provider=step.provider,
                    cwd=step.cwd,
                    status="failed",
                    command=[],
                    error=error.to_dict(),
                )
            )
            if step.stop_on_failure:
                result.status = "failed"
                result.error = error.to_dict()
                return result
    return result


def _check_required_artifacts(step: WorkflowStep, cwd: str, context: dict[str, str]) -> None:
    base = Path(cwd)
    missing: list[str] = []
    for artifact in step.requires_artifacts:
        rendered = render_template(artifact, context)
        path = Path(rendered)
        if not path.is_absolute():
            path = base / path
        if not path.exists():
            missing.append(str(path))
    if missing:
        raise WorkflowError(
            "MISSING_ARTIFACT",
            f"步骤 `{step.id}` 缺少前置 artifact。",
            step_id=step.id,
            details="\n".join(missing),
        )


def _result_details(result: CommandResult) -> str:
    parts = [
        f"command: {' '.join(result.command)}",
        f"returncode: {result.returncode}",
    ]
    if result.error:
        parts.append(f"error: {result.error}")
    if result.stdout.strip():
        parts.append(f"stdout: {result.stdout.strip()[-1000:]}")
    if result.stderr.strip():
        parts.append(f"stderr: {result.stderr.strip()[-1000:]}")
    return "\n".join(parts)


def print_text_result(result: WorkflowRunResult) -> None:
    print(f"Workflow: {result.workflow}")
    print(f"Status: {result.status}")
    print(f"Dry run: {'yes' if result.dry_run else 'no'}")
    for step in result.steps:
        print(f"\n[{step.status}] {step.id} - {step.title}")
        print(f"Provider: {step.provider}")
        print(f"Cwd: {step.cwd}")
        if step.agent_id:
            print(f"Agent: {step.agent_id}")
        if step.summary:
            print(f"Summary: {step.summary}")
        if step.command:
            print(f"Command: {' '.join(step.command)}")
        if step.error:
            print(f"Error: {step.error.get('message')}")
            if step.error.get("details"):
                print(f"Details: {step.error.get('details')}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a project-local Paseo workflow.")
    parser.add_argument("workflow", help="Workflow name, e.g. prd-impl-review")
    parser.add_argument("--workflow-dir", default=".agents/workflows", help="Directory containing workflow JSON files")
    parser.add_argument("--cwd", default=".", help="Working directory passed to workflow steps")
    parser.add_argument("--task", help="Requirement text")
    parser.add_argument("--input", action="append", default=[], help="Extra workflow input as key=value")
    parser.add_argument("--paseo-bin", default="paseo", help="Paseo executable path")
    parser.add_argument("--dry-run", action="store_true", help="Print resolved steps without running Paseo")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    args = parser.parse_args(argv)

    try:
        workflow_dir = Path(args.workflow_dir).expanduser().resolve()
        cwd = Path(args.cwd).expanduser().resolve()
        cli_inputs = parse_key_value(args.input)
        cli_inputs.setdefault("cwd", str(cwd))
        if args.task is not None:
            cli_inputs["task"] = args.task
        workflow = load_workflow(workflow_dir, args.workflow)
        context = build_context(workflow, cli_inputs, cwd)
        adapter = PaseoAdapter(SubprocessRunner(), paseo_bin=args.paseo_bin)
        result = run_workflow(workflow, context, adapter, dry_run=args.dry_run)
    except WorkflowError as error:
        result = WorkflowRunResult(
            workflow=args.workflow,
            dry_run=args.dry_run,
            status="failed",
            error=error.to_dict(),
        )

    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print_text_result(result)
    return 0 if result.status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
