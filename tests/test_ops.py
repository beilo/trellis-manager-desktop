from __future__ import annotations

import json
import stat
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import launcher  # noqa: E402
from app.config import (  # noqa: E402
    OFFICIAL_REPO_URL,
    PATH_EXPORT_LINE,
    ManagerConfig,
    add_project,
    load_config,
    remove_project,
    save_config,
    save_projects,
)
from app.ops import (  # noqa: E402
    OperationError,
    accelerated_clone_url,
    check_helm_status,
    check_tool_repo,
    ensure_wrappers_and_path,
    ensure_zshrc_path,
    inspect_project,
    init_project,
    project_init_command,
    project_update_command,
    push_task_to_helm,
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
            return self._result(normalized, cwd, "custom/beilo-v0.5-rc\n")
        if normalized[:4] == ["git", "remote", "get-url", "origin"]:
            return self._result(normalized, cwd, f"{OFFICIAL_REPO_URL}\n")
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
        if normalized[:4] == ["git", "fetch", "origin", "custom/beilo-v0.5-rc"]:
            return self._result(normalized, cwd, "")
        if normalized[:4] == ["git", "rev-list", "--left-right", "--count"]:
            return self._result(normalized, cwd, "0\t2\n")
        return super().run(command, cwd, timeout)


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

            self.assertEqual(project_init_command(bin_dir), [str(bin_dir / "tl"), "init", "-y"])
            self.assertEqual(project_update_command(bin_dir), [str(bin_dir / "tl"), "update", "--force"])
            self.assertEqual(accelerated_clone_url(), "https://xget.xi-xu.me/gh/beilo/Trellis.git")

    def test_project_init_runs_init_then_force_update(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            bin_dir = Path(tmp) / "bin"
            project.mkdir()
            runner = FakeRunner()

            report = init_project(project, runner, bin_dir)  # type: ignore[arg-type]

            self.assertTrue(report.ok)
            self.assertIn("force update", report.message)
            self.assertEqual(
                [command.command for command in report.commands],
                [
                    [str(bin_dir / "tl"), "init", "-y"],
                    [str(bin_dir / "tl"), "update", "--force"],
                ],
            )
            self.assertEqual(
                [call[0] for call in runner.calls if call[0][:1] == [str(bin_dir / "tl")]],
                [
                    [str(bin_dir / "tl"), "init", "-y"],
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


if __name__ == "__main__":
    unittest.main()
