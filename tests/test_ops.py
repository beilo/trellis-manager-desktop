from __future__ import annotations

import json
import stat
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import launcher  # noqa: E402
from app.config import (  # noqa: E402
    ACCELERATED_REPO_URL,
    DISTRIBUTION_BRANCH,
    OFFICIAL_REPO_URL,
    PATH_EXPORT_LINE,
    ManagerConfig,
    add_project,
    get_settings,
    load_config,
    remove_project,
    save_config,
    save_projects,
    save_settings,
)
from app.ops import (  # noqa: E402
    OperationError,
    accelerated_clone_url,
    check_developer_config,
    check_helm_status,
    check_tool_repo,
    ensure_wrappers_and_path,
    ensure_zshrc_path,
    get_project_git_summary,
    github_branch_zip_url,
    inspect_project,
    init_project,
    install_from_zip,
    install_from_remote_zip,
    install_or_update_tool_repo,
    list_outdated_projects,
    batch_update_projects,
    preview_project_update,
    project_init_command,
    project_update_command,
    project_update_preview_command,
    push_task_to_helm,
    sync_bundled_public_skills,
    update_project,
)
from app.runner import CommandResult, CommandRunner  # noqa: E402
from app.runner import build_command_env  # noqa: E402


class FakeRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[list[str], Path | None]] = []

    def run(self, command: list[str | Path], cwd: Path | None = None, timeout: int = 60) -> CommandResult:
        normalized = [str(part) for part in command]
        self.calls.append((normalized, cwd))
        if normalized[:3] == ["git", "rev-parse", "--is-inside-work-tree"]:
            return self._result(normalized, cwd, "true\n")
        if normalized[:3] == ["git", "status", "--short"]:
            return self._result(normalized, cwd, " M app.py\n")
        if normalized[:3] == ["git", "branch", "--show-current"]:
            return self._result(normalized, cwd, f"{DISTRIBUTION_BRANCH}\n")
        if normalized[:4] == ["git", "remote", "get-url", "origin"]:
            return self._result(normalized, cwd, f"{OFFICIAL_REPO_URL}\n")
        if normalized[:5] == ["git", "log", "-5", "--date=short", "--pretty=format:%h%x1f%ad%x1f%s"]:
            return self._result(normalized, cwd, "abc1234\x1f2026-05-24\x1fInitial commit\ndef5678\x1f2026-05-23\x1fAdd feature\n")
        if normalized[:4] == ["git", "fetch", "origin", DISTRIBUTION_BRANCH]:
            return self._result(normalized, cwd, "")
        if normalized[:4] == ["git", "rev-list", "--left-right", "--count"]:
            return self._result(normalized, cwd, "1\t2\n")
        if normalized[-3:] == ["update", "--force", "--dry-run"]:
            return self._result(normalized, cwd, "Analyzing migrations...\n[Dry run] No changes made.\n")
        if normalized[-2:] == ["update", "--force"]:
            return self._result(normalized, cwd, "updated\n")
        if normalized[:3] == ["git", "diff", "--stat"]:
            return self._result(normalized, cwd, " .trellis/workflow.md | 2 +-\n")
        return self._result(normalized, cwd, "")

    def _result(self, command: list[str], cwd: Path | None, stdout: str) -> CommandResult:
        return CommandResult(command, cwd, 0, stdout, "", 1)


class CleanRunner(FakeRunner):
    def run(self, command: list[str | Path], cwd: Path | None = None, timeout: int = 60) -> CommandResult:
        normalized = [str(part) for part in command]
        self.calls.append((normalized, cwd))
        if normalized[:3] == ["git", "status", "--short"]:
            return self._result(normalized, cwd, "")
        if normalized[:4] == ["git", "fetch", "origin", DISTRIBUTION_BRANCH]:
            return self._result(normalized, cwd, "")
        if normalized[:4] == ["git", "rev-list", "--left-right", "--count"]:
            return self._result(normalized, cwd, "0\t2\n")
        return super().run(command, cwd, timeout)


class BatchUpdateRunner:
    def __init__(self, behaviors: dict[str, dict[str, object]]) -> None:
        self.behaviors = behaviors
        self.calls: list[tuple[list[str], Path | None]] = []

    def run(self, command: list[str | Path], cwd: Path | None = None, timeout: int = 60) -> CommandResult:
        normalized = [str(part) for part in command]
        self.calls.append((normalized, cwd))
        behavior = self.behaviors.get(str(cwd) if cwd else "", {})
        if normalized[:3] == ["git", "rev-parse", "--is-inside-work-tree"]:
            return self._result(normalized, cwd, "true\n")
        if normalized[:3] == ["git", "status", "--short"]:
            return self._result(normalized, cwd, " M app.py\n" if behavior.get("dirty") else "")
        if normalized[:3] == ["git", "diff", "--stat"]:
            return self._result(normalized, cwd, "")
        if normalized[-2:] == ["update", "--force"]:
            if behavior.get("update_fail"):
                return CommandResult(normalized, cwd, 1, "", "update failed", 1)
            return self._result(normalized, cwd, "updated\n")
        return self._result(normalized, cwd, "")

    def _result(self, command: list[str], cwd: Path | None, stdout: str) -> CommandResult:
        return CommandResult(command, cwd, 0, stdout, "", 1)


class ToolRepoInstallRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[list[str], Path | None]] = []

    def run(self, command: list[str | Path], cwd: Path | None = None, timeout: int = 60) -> CommandResult:
        normalized = [str(part) for part in command]
        self.calls.append((normalized, cwd))
        return CommandResult(normalized, cwd, 0, "", "", 1)


def write_bundled_skill(source_root: Path, name: str, skill_text: str = "skill\n") -> Path:
    skill_dir = source_root / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(skill_text, encoding="utf-8")
    return skill_dir


class HelmRunner:
    def __init__(
        self,
        workspaces_json: str = "[]",
        *,
        helm_installed: bool = True,
        fail_workspace_once: bool = False,
    ) -> None:
        self.workspaces_json = workspaces_json
        self.helm_installed = helm_installed
        self.fail_workspace_once = fail_workspace_once
        self.workspace_calls = 0
        self.calls: list[tuple[list[str], Path | None]] = []

    def run(self, command: list[str | Path], cwd: Path | None = None, timeout: int = 60) -> CommandResult:
        normalized = [str(part) for part in command]
        self.calls.append((normalized, cwd))
        if normalized == ["helm", "--version"]:
            if self.helm_installed:
                return self._result(normalized, cwd, "helm 0.0.17\n")
            return CommandResult(normalized, cwd, 1, "", "helm: command not found", 1)
        if normalized == ["helm", "workspace", "ls", "--json"]:
            self.workspace_calls += 1
            if self.fail_workspace_once and self.workspace_calls == 1:
                return CommandResult(normalized, cwd, 1, "", "daemon not running", 1)
            return self._result(normalized, cwd, self.workspaces_json)
        if normalized == ["helm", "daemon", "start"]:
            return self._result(normalized, cwd, "started\n")
        if normalized[:3] == ["helm", "workspace", "new"]:
            return self._result(normalized, cwd, '{"name":"created"}\n')
        if normalized[:3] == ["helm", "issue", "new"]:
            return self._result(normalized, cwd, '{"id":"ISS-1"}\n')
        return CommandResult(normalized, cwd, 1, "", "unexpected command", 1)

    def _result(self, command: list[str], cwd: Path | None, stdout: str) -> CommandResult:
        return CommandResult(command, cwd, 0, stdout, "", 1)


class TrellisManagerOpsTest(unittest.TestCase):
    def _make_task(self, root: Path, *, with_prd: bool = True) -> tuple[Path, Path]:
        project = root / "project"
        task = project / ".trellis" / "tasks" / "05-23-helm"
        task.mkdir(parents=True)
        (task / "task.json").write_text(
            json.dumps({"title": "Push Task", "status": "planning"}),
            encoding="utf-8",
        )
        if with_prd:
            (task / "prd.md").write_text("# PRD\n", encoding="utf-8")
        return project, task

    def test_project_commands_use_local_wrapper_and_force_update(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir = Path(tmp) / "bin"

            self.assertEqual(project_init_command(["claude-code", "cursor"], "alice", bin_dir), [str(bin_dir / "tl"), "init", "-y", "--claude", "--cursor", "-u", "alice"])
            self.assertEqual(project_update_command(bin_dir), [str(bin_dir / "tl"), "update", "--force"])
            self.assertEqual(project_update_preview_command(bin_dir), [str(bin_dir / "tl"), "update", "--force", "--dry-run"])
            self.assertEqual(accelerated_clone_url(), "https://xget.xi-xu.me/gh/beilo/Trellis.git")

    def test_project_git_summary_returns_dirty_files_and_commits(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            runner = FakeRunner()

            summary = get_project_git_summary(project, runner)  # type: ignore[arg-type]

            self.assertEqual(summary.branch, DISTRIBUTION_BRANCH)
            self.assertTrue(summary.dirty)
            self.assertEqual(summary.dirty_files, [" M app.py"])
            self.assertEqual(summary.ahead, 1)
            self.assertEqual(summary.behind, 2)
            self.assertIn(["git", "rev-list", "--left-right", "--count", "HEAD...@{upstream}"], [call[0] for call in runner.calls])
            self.assertEqual(summary.recent_commits[0].short_hash, "abc1234")
            self.assertEqual(summary.recent_commits[0].date, "2026-05-24")
            self.assertEqual(summary.recent_commits[0].title, "Initial commit")
            self.assertEqual(summary.recent_commits[0].oneline, "abc1234 Initial commit")

    def test_project_git_summary_clean_project_has_empty_dirty_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            runner = CleanRunner()

            summary = get_project_git_summary(project, runner)  # type: ignore[arg-type]

            self.assertFalse(summary.dirty)
            self.assertEqual(summary.dirty_files, [])
            self.assertEqual(summary.behind, 2)
            self.assertIn(["git", "rev-list", "--left-right", "--count", "HEAD...@{upstream}"], [call[0] for call in runner.calls])

    def test_project_git_summary_rejects_non_git_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            runner = FakeRunner()
            runner.run = lambda command, cwd=None, timeout=60: CommandResult(  # type: ignore[method-assign]
                [str(part) for part in command],
                cwd,
                1,
                "",
                "not git",
                1,
            )

            with self.assertRaises(OperationError) as error:
                get_project_git_summary(project, runner)  # type: ignore[arg-type]

            self.assertIn("不是 git 仓库", str(error.exception))

    def test_preview_project_update_runs_dry_run_without_real_update(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            tool_repo = root / "tool"
            bin_dir = root / "bin"
            project.mkdir()
            (project / ".trellis").mkdir()
            (project / ".trellis" / ".version").write_text("0.6.0-beta.9", encoding="utf-8")
            package = tool_repo / "packages" / "cli" / "package.json"
            package.parent.mkdir(parents=True)
            package.write_text(json.dumps({"version": "0.6.0-beta.10"}), encoding="utf-8")
            runner = FakeRunner()

            preview = preview_project_update(project, runner, bin_dir, tool_repo)  # type: ignore[arg-type]

            self.assertTrue(preview.ok)
            self.assertEqual(preview.dirty_files_before, [" M app.py"])
            self.assertEqual(preview.trellis_version_before, "0.6.0-beta.9")
            self.assertEqual(preview.latest_version, "0.6.0-beta.10")
            self.assertTrue(preview.would_run_migrations)
            self.assertIn("[Dry run] No changes made.", preview.dry_run_output)
            calls = [call[0] for call in runner.calls]
            self.assertIn([str(bin_dir / "tl"), "update", "--force", "--dry-run"], calls)
            self.assertNotIn([str(bin_dir / "tl"), "update", "--force"], calls)

    def test_preview_project_update_failure_preserves_output(self) -> None:
        class FailingPreviewRunner(FakeRunner):
            def run(self, command: list[str | Path], cwd: Path | None = None, timeout: int = 60) -> CommandResult:
                normalized = [str(part) for part in command]
                self.calls.append((normalized, cwd))
                if normalized[-3:] == ["update", "--force", "--dry-run"]:
                    return CommandResult(normalized, cwd, 1, "Cannot update\n", "version is older\n", 1)
                return super().run(command, cwd, timeout)

        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            tool_repo = Path(tmp) / "tool"
            project.mkdir()
            (project / ".trellis").mkdir()
            runner = FailingPreviewRunner()

            preview = preview_project_update(project, runner, Path(tmp) / "bin", tool_repo)  # type: ignore[arg-type]

            self.assertFalse(preview.ok)
            self.assertIn("update 预览失败", preview.message)
            self.assertIn("Cannot update", preview.dry_run_output)
            self.assertIn("version is older", preview.dry_run_output)

    def test_preview_project_update_rejects_non_git_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            runner = FakeRunner()
            runner.run = lambda command, cwd=None, timeout=60: CommandResult(  # type: ignore[method-assign]
                [str(part) for part in command],
                cwd,
                1,
                "",
                "not git",
                1,
            )

            with self.assertRaises(OperationError) as error:
                preview_project_update(project, runner)  # type: ignore[arg-type]

            self.assertIn("必须是 git 仓库", str(error.exception))

    def test_preview_project_update_rejects_missing_trellis(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)

            with self.assertRaises(OperationError) as error:
                preview_project_update(project, FakeRunner())  # type: ignore[arg-type]

            self.assertIn("尚未安装 Trellis", str(error.exception))

    def test_project_init_runs_init_then_force_update(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            bin_dir = Path(tmp) / "bin"
            project.mkdir()
            runner = FakeRunner()

            report = init_project(project, ["claude-code"], "alice", runner, bin_dir)  # type: ignore[arg-type]

            self.assertTrue(report.ok)
            self.assertIn("force update", report.message)
            self.assertEqual(
                [command.command for command in report.commands],
                [
                    [str(bin_dir / "tl"), "init", "-y", "--claude", "-u", "alice"],
                    [str(bin_dir / "tl"), "update", "--force"],
                ],
            )
            self.assertEqual(
                [call[0] for call in runner.calls if call[0][:1] == [str(bin_dir / "tl")]],
                [
                    [str(bin_dir / "tl"), "init", "-y", "--claude", "-u", "alice"],
                    [str(bin_dir / "tl"), "update", "--force"],
                ],
            )

    def test_command_runner_rejects_non_whitelisted_executables(self) -> None:
        runner = CommandRunner()

        with self.assertRaises(ValueError):
            runner.run(["rm", "-rf", "/tmp/anything"])

    def test_command_runner_allows_helm(self) -> None:
        runner = CommandRunner(allowed={"helm"})

        result = runner._prepare_command(["helm", "--version"])  # noqa: SLF001

        self.assertEqual(result, ["helm", "--version"])

    def test_check_helm_status_reports_missing_cli(self) -> None:
        status = check_helm_status(HelmRunner(helm_installed=False))  # type: ignore[arg-type]

        self.assertFalse(status.ok)
        self.assertEqual(status.status, "error")
        self.assertEqual(status.message, "未安装 Helm")

    def test_command_runner_forces_git_utf8_output(self) -> None:
        runner = CommandRunner()

        self.assertEqual(
            runner._prepare_command(["git", "status", "--short"]),  # noqa: SLF001
            ["git", "-c", "i18n.logOutputEncoding=UTF-8", "status", "--short"],
        )

    def test_command_runner_env_includes_gui_app_tool_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            node_bin = home / ".nvm" / "versions" / "node" / "v22.13.0" / "bin"
            node_bin.mkdir(parents=True)
            (home / ".beilo-trellis" / "bin").mkdir(parents=True)
            (home / ".local" / "bin").mkdir(parents=True)

            env = build_command_env(home)
            path_parts = env["PATH"].split(":")

            self.assertEqual(path_parts[:3], [
                str(home / ".beilo-trellis" / "bin"),
                str(home / ".local" / "bin"),
                str(node_bin),
            ])

    def test_zshrc_path_write_is_backed_up_and_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            zshrc = home / ".zshrc"
            zshrc.write_text("# existing\n", encoding="utf-8")

            first = ensure_zshrc_path(home)
            second = ensure_zshrc_path(home)

            self.assertIn("已写入", first)
            self.assertIn("无需重复写入", second)
            self.assertEqual(zshrc.read_text(encoding="utf-8").count(PATH_EXPORT_LINE), 1)
            self.assertEqual(len(list(home.glob(".zshrc.trellis-manager-backup-*"))), 1)

    def test_wrapper_files_point_to_repo_cli_entry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "Trellis"
            bin_dir = root / "bin"
            entry = repo / "packages" / "cli" / "bin" / "trellis.js"
            entry.parent.mkdir(parents=True)
            entry.write_text("#!/usr/bin/env node\n", encoding="utf-8")

            report = ensure_wrappers_and_path(repo, bin_dir, root)

            self.assertTrue(report.ok)
            for name in ["tl", "trellis"]:
                wrapper = bin_dir / name
                self.assertTrue(wrapper.exists())
                self.assertIn(str(entry), wrapper.read_text(encoding="utf-8"))
                self.assertTrue(wrapper.stat().st_mode & stat.S_IXUSR)

    def test_tool_repo_dirty_reports_info(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            entry = repo / "packages" / "cli" / "bin" / "trellis.js"
            entry.parent.mkdir(parents=True)
            entry.write_text("#!/usr/bin/env node\n", encoding="utf-8")
            package = repo / "packages" / "cli" / "package.json"
            package.write_text(json.dumps({"version": "0.1.0"}), encoding="utf-8")

            status = check_tool_repo(repo, FakeRunner())  # type: ignore[arg-type]

            self.assertTrue(status.dirty)
            self.assertEqual(status.status, "info")
            self.assertIn("本地变更", status.message)

    def test_tool_repo_check_reports_remote_updates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            entry = repo / "packages" / "cli" / "bin" / "trellis.js"
            entry.parent.mkdir(parents=True)
            entry.write_text("#!/usr/bin/env node\n", encoding="utf-8")
            package = repo / "packages" / "cli" / "package.json"
            package.write_text(json.dumps({"version": "0.1.0"}), encoding="utf-8")

            status = check_tool_repo(repo, CleanRunner())  # type: ignore[arg-type]

            self.assertEqual(status.behind, 2)
            self.assertIn("可以更新", status.message)

    def test_project_update_requires_confirmation_when_dirty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / ".trellis").mkdir()
            runner = FakeRunner()

            with self.assertRaises(OperationError):
                update_project(project, allow_dirty=False, runner=runner)  # type: ignore[arg-type]

            report = update_project(project, allow_dirty=True, runner=runner)  # type: ignore[arg-type]

            self.assertTrue(report.ok)
            self.assertIn([str(Path.home() / ".beilo-trellis" / "bin" / "tl"), "update", "--force"], [call[0] for call in runner.calls])

    def test_project_inspection_dirty_current_version_is_ok(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            (project / ".trellis").mkdir()
            (project / ".trellis" / ".version").write_text("0.6.0-beta.10", encoding="utf-8")
            tool_repo = root / "tool"
            package = tool_repo / "packages" / "cli" / "package.json"
            package.parent.mkdir(parents=True)
            package.write_text(json.dumps({"version": "0.6.0-beta.10"}), encoding="utf-8")

            status = inspect_project(str(project), FakeRunner(), tool_repo)  # type: ignore[arg-type]

            self.assertTrue(status.dirty)
            self.assertEqual(status.status, "ok")
            self.assertFalse(status.version_outdated)
            self.assertEqual(status.trellis_version, "0.6.0-beta.10")
            self.assertEqual(status.latest_version, "0.6.0-beta.10")

    def test_project_inspection_warns_when_version_outdated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            (project / ".trellis").mkdir()
            (project / ".trellis" / ".version").write_text("0.6.0-beta.9", encoding="utf-8")
            tool_repo = root / "tool"
            package = tool_repo / "packages" / "cli" / "package.json"
            package.parent.mkdir(parents=True)
            package.write_text(json.dumps({"version": "0.6.0-beta.10"}), encoding="utf-8")

            status = inspect_project(str(project), CleanRunner(), tool_repo)  # type: ignore[arg-type]

            self.assertEqual(status.status, "warning")
            self.assertTrue(status.version_outdated)
            self.assertIn("0.6.0-beta.9", status.message)
            self.assertIn("0.6.0-beta.10", status.message)

    def test_project_inspection_rejects_non_git_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            runner = FakeRunner()
            runner.run = lambda command, cwd=None, timeout=60: CommandResult(  # type: ignore[method-assign]
                [str(part) for part in command],
                cwd,
                1,
                "",
                "not git",
                1,
            )

            status = inspect_project(str(project), runner)  # type: ignore[arg-type]

            self.assertFalse(status.is_git)
            self.assertEqual(status.status, "error")

    def test_list_outdated_projects_filters_configured_projects(self) -> None:
        """未指定 paths 时，批量入口只应选择版本落后的已配置项目。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            outdated = root / "outdated"
            current = root / "current"
            tool_repo = root / "tool"
            for project, version in [(outdated, "0.6.0-beta.9"), (current, "0.6.0-beta.10")]:
                project.mkdir()
                (project / ".trellis").mkdir()
                (project / ".trellis" / ".version").write_text(version, encoding="utf-8")
            package = tool_repo / "packages" / "cli" / "package.json"
            package.parent.mkdir(parents=True)
            package.write_text(json.dumps({"version": "0.6.0-beta.10"}), encoding="utf-8")

            statuses = list_outdated_projects([outdated, current], BatchUpdateRunner({}), tool_repo)  # type: ignore[arg-type]

            self.assertEqual([status.path for status in statuses], [outdated.resolve()])

    def test_batch_update_projects_collects_results_and_writes_one_log(self) -> None:
        """批量更新应逐项目返回结果，并只写一条聚合操作日志。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "first"
            second = root / "second"
            tool_repo = root / "tool"
            log_file = root / "logs.json"
            bin_dir = root / "bin"
            for project in [first, second]:
                project.mkdir()
                (project / ".trellis").mkdir()
                (project / ".trellis" / ".version").write_text("0.6.0-beta.9", encoding="utf-8")
            package = tool_repo / "packages" / "cli" / "package.json"
            package.parent.mkdir(parents=True)
            package.write_text(json.dumps({"version": "0.6.0-beta.10"}), encoding="utf-8")
            runner = BatchUpdateRunner({})

            report = batch_update_projects([str(first), str(second), str(first)], [], runner=runner, bin_dir=bin_dir, tool_repo_dir=tool_repo, log_file=log_file)  # type: ignore[arg-type]

            self.assertTrue(report.ok)
            self.assertEqual(report.total, 2)
            self.assertEqual(report.updated_count, 2)
            self.assertEqual([result.path for result in report.results], [str(first.resolve()), str(second.resolve())])
            self.assertEqual(
                [call[0] for call in runner.calls if call[0][:1] == [str(bin_dir / "tl")]],
                [[str(bin_dir / "tl"), "update", "--force"], [str(bin_dir / "tl"), "update", "--force"]],
            )
            logs = json.loads(log_file.read_text(encoding="utf-8"))
            self.assertEqual(len(logs), 1)
            self.assertEqual(logs[0]["details"]["updated_count"], "2")
            self.assertEqual(len(logs[0]["results"]), 2)

    def test_batch_update_projects_defaults_to_outdated_projects_only(self) -> None:
        """paths 为 None 时只更新落后项目，避免批量按钮误触当前项目。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            outdated = root / "outdated"
            current = root / "current"
            tool_repo = root / "tool"
            bin_dir = root / "bin"
            for project, version in [(outdated, "0.6.0-beta.9"), (current, "0.6.0-beta.10")]:
                project.mkdir()
                (project / ".trellis").mkdir()
                (project / ".trellis" / ".version").write_text(version, encoding="utf-8")
            package = tool_repo / "packages" / "cli" / "package.json"
            package.parent.mkdir(parents=True)
            package.write_text(json.dumps({"version": "0.6.0-beta.10"}), encoding="utf-8")
            runner = BatchUpdateRunner({})

            report = batch_update_projects(None, [outdated, current], runner=runner, bin_dir=bin_dir, tool_repo_dir=tool_repo, log_file=root / "logs.json")  # type: ignore[arg-type]

            self.assertEqual(report.total, 1)
            self.assertEqual(report.results[0].path, str(outdated.resolve()))
            self.assertEqual(
                [call[1] for call in runner.calls if call[0][:1] == [str(bin_dir / "tl")]],
                [outdated.resolve()],
            )

    def test_batch_update_projects_skips_dirty_by_default(self) -> None:
        """dirty 项目默认转成跳过结果，避免批量更新覆盖未提交工作。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dirty = root / "dirty"
            tool_repo = root / "tool"
            dirty.mkdir()
            (dirty / ".trellis").mkdir()
            (dirty / ".trellis" / ".version").write_text("0.6.0-beta.9", encoding="utf-8")
            package = tool_repo / "packages" / "cli" / "package.json"
            package.parent.mkdir(parents=True)
            package.write_text(json.dumps({"version": "0.6.0-beta.10"}), encoding="utf-8")
            runner = BatchUpdateRunner({str(dirty.resolve()): {"dirty": True}})

            report = batch_update_projects([dirty], [], runner=runner, tool_repo_dir=tool_repo, log_file=root / "logs.json")  # type: ignore[arg-type]

            self.assertFalse(report.ok)
            self.assertEqual(report.skipped_count, 1)
            self.assertTrue(report.results[0].skipped)
            self.assertIn("未提交变更", report.results[0].reason or "")
            self.assertNotIn([str(Path.home() / ".beilo-trellis" / "bin" / "tl"), "update", "--force"], [call[0] for call in runner.calls])

    def test_batch_update_projects_continues_after_single_failure(self) -> None:
        """单个项目 update 失败不应阻断后续项目。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            failing = root / "failing"
            ok_project = root / "ok"
            tool_repo = root / "tool"
            bin_dir = root / "bin"
            for project in [failing, ok_project]:
                project.mkdir()
                (project / ".trellis").mkdir()
                (project / ".trellis" / ".version").write_text("0.6.0-beta.9", encoding="utf-8")
            package = tool_repo / "packages" / "cli" / "package.json"
            package.parent.mkdir(parents=True)
            package.write_text(json.dumps({"version": "0.6.0-beta.10"}), encoding="utf-8")
            runner = BatchUpdateRunner({str(failing.resolve()): {"update_fail": True}})

            report = batch_update_projects([failing, ok_project], [], runner=runner, bin_dir=bin_dir, tool_repo_dir=tool_repo, log_file=root / "logs.json")  # type: ignore[arg-type]

            self.assertFalse(report.ok)
            self.assertEqual(report.failed_count, 1)
            self.assertEqual(report.updated_count, 1)
            self.assertIn("项目 update 失败", report.results[0].message)
            self.assertTrue(report.results[1].ok)
            self.assertEqual(
                [call[1] for call in runner.calls if call[0][:1] == [str(bin_dir / "tl")]],
                [failing.resolve(), ok_project.resolve()],
            )

    def test_push_task_to_helm_requires_prd(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project, task = self._make_task(Path(tmp), with_prd=False)

            with self.assertRaises(OperationError) as error:
                push_task_to_helm(project, task, HelmRunner())  # type: ignore[arg-type]

            self.assertIn("需要 PRD 文档", str(error.exception))

    def test_push_task_to_helm_uses_matching_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project, task = self._make_task(Path(tmp))
            runner = HelmRunner(json.dumps([{"name": "team", "projects": [str(project.resolve())]}]))

            report = push_task_to_helm(project, task, runner)  # type: ignore[arg-type]

            self.assertTrue(report.ok)
            self.assertEqual(report.details["workspace"], "team")
            self.assertIn("ISS-1", report.message)
            self.assertIn(
                [
                    "helm",
                    "issue",
                    "new",
                    "team",
                    "Push Task",
                    "--description-file",
                    str(task.resolve() / "prd.md"),
                    "--project",
                    project.name,
                    "--status",
                    "todo",
                    "--json",
                ],
                [call[0] for call in runner.calls],
            )

    def test_push_task_to_helm_creates_workspace_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project, task = self._make_task(Path(tmp))
            runner = HelmRunner("[]")

            report = push_task_to_helm(project, task, runner)  # type: ignore[arg-type]

            self.assertTrue(report.ok)
            self.assertEqual(report.details["workspace"], project.name)
            self.assertIn(
                ["helm", "workspace", "new", project.name, "--project", str(project.resolve())],
                [call[0] for call in runner.calls],
            )

    def test_push_task_to_helm_starts_daemon_then_retries_workspace_list(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project, task = self._make_task(Path(tmp))
            runner = HelmRunner(
                json.dumps([{"name": "team", "projects": [str(project.resolve())]}]),
                fail_workspace_once=True,
            )

            report = push_task_to_helm(project, task, runner)  # type: ignore[arg-type]

            self.assertTrue(report.ok)
            self.assertEqual(runner.workspace_calls, 2)
            self.assertIn(["helm", "daemon", "start"], [call[0] for call in runner.calls])

    def test_tool_repo_check_uses_custom_distribution_branch(self) -> None:
        """工具仓库检查应使用配置里的分发分支而不是硬编码值。"""
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / "packages" / "cli" / "bin").mkdir(parents=True)
            (repo / "packages" / "cli" / "bin" / "trellis.js").write_text("#!/usr/bin/env node\n", encoding="utf-8")
            (repo / "packages" / "cli" / "package.json").write_text(json.dumps({"version": "0.1.0"}), encoding="utf-8")
            runner = CleanRunner()

            status = check_tool_repo(repo, runner, "release/custom")

            self.assertIn(["git", "fetch", "origin", "release/custom"], [call[0] for call in runner.calls])
            self.assertEqual(status.behind, 2)
            self.assertEqual(status.status, "warning")

    def test_tool_repo_install_uses_configured_sources(self) -> None:
        """安装工具仓库时应透传设置页里的仓库源与分发分支。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo = root / "Trellis"
            bundled_skills = root / "bundled-skills"
            write_bundled_skill(bundled_skills, "trellis-start")
            runner = ToolRepoInstallRunner()

            report = install_or_update_tool_repo(
                repo,
                runner,
                official_repo_url="https://example.com/official.git",
                accelerated_repo_url="https://example.com/mirror.git",
                distribution_branch="release/custom",
                global_skill_home_dir=root / "home",
                bundled_skill_source_dir=bundled_skills,
            )

            self.assertTrue(report.ok)
            self.assertEqual(report.details["branch"], "release/custom")
            self.assertEqual(report.details["synced_skills"], "trellis-start")
            self.assertIn(
                ["git", "clone", "--branch", "release/custom", "https://example.com/mirror.git", str(repo)],
                [call[0] for call in runner.calls],
            )
            self.assertIn(
                ["git", "remote", "set-url", "origin", "https://example.com/official.git"],
                [call[0] for call in runner.calls],
            )
            self.assertIn(["pnpm", "install"], [call[0] for call in runner.calls])

    def test_settings_roundtrip_persists_repo_sources_and_branch(self) -> None:
        """设置读写应保留新字段，并允许局部更新不丢失现有值。"""
        with tempfile.TemporaryDirectory() as tmp:
            config_file = Path(tmp) / "config.json"
            repo = Path(tmp) / "Trellis"
            first = Path(tmp) / "a"
            save_config(
                ManagerConfig(
                    trellis_repo=repo,
                    projects=[first],
                    official_repo_url="https://example.com/official.git",
                    accelerated_repo_url="https://example.com/mirror.git",
                    distribution_branch="release/one",
                ),
                config_file,
            )

            self.assertEqual(
                get_settings(config_file),
                {
                    "official_repo_url": "https://example.com/official.git",
                    "accelerated_repo_url": "https://example.com/mirror.git",
                    "distribution_branch": "release/one",
                    "developer_name": "",
                    "init_platforms": [],
                },
            )

            updated = save_settings(
                {
                    "official_repo_url": "https://example.com/official-2.git",
                    "accelerated_repo_url": "",
                    "distribution_branch": "release/two",
                },
                config_file,
            )

            self.assertEqual(updated.official_repo_url, "https://example.com/official-2.git")
            self.assertEqual(updated.accelerated_repo_url, "https://example.com/mirror.git")
            self.assertEqual(updated.distribution_branch, "release/two")
            self.assertEqual(load_config(config_file).official_repo_url, "https://example.com/official-2.git")

    def test_config_persistence_dedupes_recent_projects(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_file = Path(tmp) / "config.json"
            first = Path(tmp) / "a"
            second = Path(tmp) / "b"

            save_config(
                ManagerConfig(
                    trellis_repo=Path(tmp),
                    projects=[first, second, first],
                    last_selected_project=second,
                    recent_projects=[first, second, first],
                ),
                config_file,
            )
            loaded = load_config(config_file)

            self.assertEqual(loaded.projects, [first, second])
            self.assertEqual(loaded.last_selected_project, second)
            self.assertEqual(loaded.recent_projects, [first, second])

    def test_config_migrates_recent_projects_to_projects(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_file = Path(tmp) / "config.json"
            first = Path(tmp) / "a"
            second = Path(tmp) / "b"
            config_file.write_text(
                json.dumps(
                    {
                        "trellis_repo": str(Path(tmp) / "Trellis"),
                        "recent_projects": [str(first), str(second), str(first)],
                    },
                ),
                encoding="utf-8",
            )

            loaded = load_config(config_file)

            self.assertEqual(loaded.projects, [first, second])
            self.assertIsNone(loaded.last_selected_project)

    def test_project_list_helpers_persist_selection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_file = Path(tmp) / "config.json"
            first = Path(tmp) / "a"
            second = Path(tmp) / "b"

            add_project(first, config_file)
            add_project(second, config_file)
            loaded = save_projects([first, second, first], config_file, last_selected_project=second)

            self.assertEqual(loaded.projects, [first, second])
            self.assertEqual(loaded.last_selected_project, second)

            loaded = remove_project(second, config_file)

            self.assertEqual(loaded.projects, [first])
            self.assertEqual(loaded.last_selected_project, first)

    def test_launcher_checks_homebrew_python_candidates(self) -> None:
        self.assertIn("/opt/homebrew/bin/python3", launcher.PYTHON_CANDIDATES)
        self.assertIn("/usr/local/bin/python3", launcher.PYTHON_CANDIDATES)

    # ── 初始化前置配置校验测试 ──

    def test_init_project_blocks_on_empty_developer_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            runner = FakeRunner()
            # git 仓库条件满足（FakeRunner 默认 git ok）
            with self.assertRaises(OperationError) as error:
                init_project(project, ["claude-code"], "", runner)  # type: ignore[arg-type]
            self.assertIn("开发者名", str(error.exception))
            # runner 不应被调用
            self.assertEqual(
                [c for c in runner.calls if c[0][0:1] == [str(project)]],
                [],
            )

    def test_init_project_blocks_on_empty_platforms(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            runner = FakeRunner()
            with self.assertRaises(OperationError) as error:
                init_project(project, [], "alice", runner)  # type: ignore[arg-type]
            self.assertIn("平台", str(error.exception))
            self.assertEqual(
                [c for c in runner.calls if c[0][0:1] == [str(project)]],
                [],
            )

    def test_check_developer_config_ok_when_both_set(self) -> None:
        item = check_developer_config("alice", ["claude-code", "cursor"])
        self.assertTrue(item.ok)
        self.assertEqual(item.status, "ok")
        self.assertIn("alice", item.message)
        self.assertIn("Claude Code", item.message)
        self.assertIn("Cursor", item.message)

    def test_check_developer_config_error_when_missing_name(self) -> None:
        item = check_developer_config("", ["claude-code"])
        self.assertFalse(item.ok)
        self.assertEqual(item.status, "error")
        self.assertIn("开发者名", item.message)

    def test_check_developer_config_error_when_missing_platforms(self) -> None:
        item = check_developer_config("alice", [])
        self.assertFalse(item.ok)
        self.assertEqual(item.status, "error")
        self.assertIn("平台", item.message)

    def test_check_developer_config_error_when_both_missing(self) -> None:
        item = check_developer_config("", [])
        self.assertFalse(item.ok)
        self.assertIn("开发者名", item.message)
        self.assertIn("平台", item.message)

    def test_config_roundtrip_with_new_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_file = Path(tmp) / "config.json"
            config = ManagerConfig(
                trellis_repo=Path(tmp),
                projects=[],
                developer_name="alice",
                init_platforms=["claude-code", "cursor"],
            )
            save_config(config, config_file)
            loaded = load_config(config_file)
            self.assertEqual(loaded.developer_name, "alice")
            self.assertEqual(loaded.init_platforms, ["claude-code", "cursor"])

    def test_config_loads_old_format_without_new_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_file = Path(tmp) / "config.json"
            config_file.write_text(
                json.dumps({"trellis_repo": str(Path(tmp) / "Trellis")}),
                encoding="utf-8",
            )
            loaded = load_config(config_file)
            self.assertEqual(loaded.developer_name, "")
            self.assertEqual(loaded.init_platforms, [])

    def test_config_filters_invalid_platform_keys(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_file = Path(tmp) / "config.json"
            config_file.write_text(
                json.dumps({
                    "trellis_repo": str(Path(tmp) / "Trellis"),
                    "init_platforms": ["claude-code", "invalid", "codex"],
                }),
                encoding="utf-8",
            )
            loaded = load_config(config_file)
            self.assertEqual(loaded.init_platforms, ["claude-code", "codex"])

    def test_save_settings_preserves_new_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_file = Path(tmp) / "config.json"
            save_config(
                ManagerConfig(trellis_repo=Path(tmp), developer_name="alice", init_platforms=["codex"]),
                config_file,
            )
            updated = save_settings(
                {"official_repo_url": "https://example.com/repo.git",
                 "accelerated_repo_url": "https://mirror.example.com/repo.git",
                 "distribution_branch": "main",
                 "developer_name": "bob",
                 "init_platforms": ["claude-code", "cursor"]},
                config_file,
            )
            self.assertEqual(updated.developer_name, "bob")
            self.assertEqual(updated.init_platforms, ["claude-code", "cursor"])
            loaded = load_config(config_file)
            self.assertEqual(loaded.developer_name, "bob")
            self.assertEqual(loaded.init_platforms, ["claude-code", "cursor"])

    # ── github_branch_zip_url 测试 ──

    def test_github_branch_zip_url_https(self) -> None:
        """HTTPS GitHub URL 推导 codeload zip 地址。"""
        url = github_branch_zip_url(
            "https://github.com/beilo/Trellis.git",
            "sync/v0.6.0-rc",
        )
        self.assertEqual(
            url,
            "https://codeload.github.com/beilo/Trellis/zip/refs/heads/sync/v0.6.0-rc",
        )

    def test_github_branch_zip_url_ssh(self) -> None:
        """SSH GitHub URL 推导 codeload zip 地址。"""
        url = github_branch_zip_url(
            "git@github.com:beilo/Trellis.git",
            "sync/v0.6.0-rc",
        )
        self.assertEqual(
            url,
            "https://codeload.github.com/beilo/Trellis/zip/refs/heads/sync/v0.6.0-rc",
        )

    def test_github_branch_zip_url_non_github(self) -> None:
        """非 GitHub URL 返回 None。"""
        self.assertIsNone(github_branch_zip_url("https://gitlab.com/foo/bar.git", "main"))

    def test_github_branch_zip_url_invalid_base(self) -> None:
        """畸形 GitHub URL 返回 None。"""
        self.assertIsNone(github_branch_zip_url("https://github.com/onlyowner", "main"))

    def test_github_branch_zip_url_https_no_git_suffix(self) -> None:
        """HTTPS URL 不带 .git 后缀也能推导。"""
        url = github_branch_zip_url(
            "https://github.com/beilo/Trellis",
            "main",
        )
        self.assertEqual(
            url,
            "https://codeload.github.com/beilo/Trellis/zip/refs/heads/main",
        )

    def test_install_from_zip_builds_core_before_cli(self) -> None:
        """zip 快照安装会使用根 build 统一构建 core 和 CLI。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            (source / "packages" / "cli" / "bin").mkdir(parents=True)
            (source / "packages" / "cli" / "bin" / "trellis.js").write_text("#!/usr/bin/env node\n", encoding="utf-8")
            (source / "packages" / "cli" / "package.json").write_text(json.dumps({"name": "@mindfoldhq/trellis"}), encoding="utf-8")
            (source / "packages" / "core").mkdir(parents=True)
            (source / "packages" / "core" / "package.json").write_text(json.dumps({"name": "@mindfoldhq/trellis-core"}), encoding="utf-8")
            (source / "package.json").write_text(json.dumps({"name": "trellis-root"}), encoding="utf-8")
            (source / "pnpm-lock.yaml").write_text("", encoding="utf-8")

            zip_path = root / "trellis.zip"
            with zipfile.ZipFile(zip_path, "w") as archive:
                for path in source.rglob("*"):
                    archive.write(path, path.relative_to(root))

            bundled_skills = root / "bundled-skills"
            write_bundled_skill(bundled_skills, "trellis-start")
            runner = FakeRunner()
            report = install_from_zip(
                zip_path,
                root / "Trellis",
                runner=runner,  # type: ignore[arg-type]
                global_skill_home_dir=root / "home",
                bundled_skill_source_dir=bundled_skills,
            )

            self.assertTrue(report.ok)
            self.assertEqual(
                [command.command for command in report.commands],
                [
                    ["pnpm", "install"],
                    ["pnpm", "build"],
                ],
            )
            self.assertEqual(report.details["synced_skills"], "trellis-start")
            self.assertEqual(report.details["synced_skill_count"], "1")
            agents_target = root / "home" / ".agents" / "skills" / "trellis-start"
            codex_target = root / "home" / ".codex" / "skills" / "trellis-start"
            claude_target = root / "home" / ".claude" / "skills" / "trellis-start"
            self.assertTrue((agents_target / "SKILL.md").exists())
            self.assertTrue(codex_target.is_symlink())
            self.assertTrue(claude_target.is_symlink())
            self.assertEqual(codex_target.readlink(), Path("..") / ".." / ".agents" / "skills" / "trellis-start")
            self.assertEqual(claude_target.readlink(), Path("..") / ".." / ".agents" / "skills" / "trellis-start")

    def test_sync_bundled_public_skills_replaces_targets_with_shared_symlinks(self) -> None:
        """内置公共技能同步应强制覆盖旧入口，并让 Codex/Claude 指向 .agents 权威源。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "bundled"
            alpha_source = write_bundled_skill(source, "alpha", "alpha skill\n")
            (alpha_source / "agents").mkdir()
            (alpha_source / "agents" / "openai.yaml").write_text("agent\n", encoding="utf-8")
            write_bundled_skill(source, "beta", "beta skill\n")
            (source / "invalid").mkdir()

            home = root / "home"
            agents_alpha = home / ".agents" / "skills" / "alpha"
            agents_alpha.mkdir(parents=True)
            (agents_alpha / "SKILL.md").write_text("old skill\n", encoding="utf-8")
            agents_beta = home / ".agents" / "skills" / "beta"
            agents_beta.parent.mkdir(parents=True, exist_ok=True)
            agents_beta.write_text("old file\n", encoding="utf-8")
            codex_target = home / ".codex" / "skills" / "alpha"
            codex_target.parent.mkdir(parents=True)
            codex_target.write_text("old file\n", encoding="utf-8")
            claude_target = home / ".claude" / "skills" / "alpha"
            shared = root / "shared"
            shared.mkdir()
            claude_target.parent.mkdir(parents=True)
            claude_target.symlink_to(shared, target_is_directory=True)

            details = sync_bundled_public_skills(source, home)

            self.assertEqual(details["synced_skills"], "alpha,beta")
            self.assertEqual(details["synced_skill_count"], "2")
            self.assertEqual((agents_alpha / "SKILL.md").read_text(encoding="utf-8"), "alpha skill\n")
            self.assertEqual((agents_alpha / "agents" / "openai.yaml").read_text(encoding="utf-8"), "agent\n")
            self.assertEqual((agents_beta / "SKILL.md").read_text(encoding="utf-8"), "beta skill\n")
            self.assertTrue(shared.exists())
            for tool_name in [".codex", ".claude"]:
                target = home / tool_name / "skills" / "alpha"
                self.assertTrue(target.is_symlink())
                self.assertEqual(target.readlink(), Path("..") / ".." / ".agents" / "skills" / "alpha")
                self.assertEqual((target / "SKILL.md").read_text(encoding="utf-8"), "alpha skill\n")

    def test_sync_bundled_public_skills_rejects_empty_source(self) -> None:
        """内置公共技能为空时应阻断安装，避免静默漏装技能。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "bundled"
            source.mkdir()

            with self.assertRaises(OperationError) as error:
                sync_bundled_public_skills(source, root / "home")

            self.assertIn("内置公共技能目录不存在或不完整", str(error.exception))

    # ── install_from_remote_zip 测试 ──

    def test_install_from_remote_zip_non_github_rejects(self) -> None:
        """非 GitHub 仓库 URL 时抛中文错误。"""
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "Trellis"

            with self.assertRaises(OperationError) as error:
                install_from_remote_zip(
                    repo,
                    official_repo_url="https://gitlab.com/foo/bar.git",
                    distribution_branch="main",
                )

            self.assertIn("不是 GitHub 仓库", str(error.exception))

    def test_install_from_remote_zip_download_failure_cleans_temp(self) -> None:
        """下载失败时不创建或污染目标工具仓库。"""
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "Trellis"

            with self.assertRaises(OperationError):
                # 使用一个无法访问的 GitHub URL 来模拟下载失败
                install_from_remote_zip(
                    repo,
                    official_repo_url="https://github.com/beilo/nonexistent-repo-xyz.git",
                    distribution_branch="nonexistent-branch",
                )

            # 目标目录不应被创建
            self.assertFalse(repo.exists())
            # 临时目录应被清理（manager-temp 目录可能存在但不应有残留文件）
            temp_base = repo.parent / ".manager-temp"
            temp_zip_files = list(temp_base.glob("remote-*.zip")) if temp_base.exists() else []
            self.assertEqual(len(temp_zip_files), 0)

    def test_install_from_remote_zip_replace_false_blocks_when_exists(self) -> None:
        """目标已存在且 replace=False 时阻断。"""
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "Trellis"
            repo.mkdir()
            # 创建有效的 Trellis 源码树结构
            (repo / "packages" / "cli" / "bin").mkdir(parents=True)
            (repo / "packages" / "cli" / "bin" / "trellis.js").write_text("#!/usr/bin/env node\n", encoding="utf-8")
            (repo / "packages" / "cli" / "package.json").write_text(json.dumps({"version": "0.1.0"}), encoding="utf-8")
            (repo / "package.json").write_text("{}", encoding="utf-8")
            (repo / "pnpm-lock.yaml").write_text("", encoding="utf-8")

            with self.assertRaises(OperationError) as error:
                install_from_remote_zip(
                    repo,
                    replace=False,
                    official_repo_url="https://github.com/beilo/Trellis.git",
                    distribution_branch="sync/v0.6.0-rc",
                )

            self.assertIn("已存在", str(error.exception))


if __name__ == "__main__":
    unittest.main()
