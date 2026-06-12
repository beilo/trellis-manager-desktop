from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
import json

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.api import TrellisAPI  # noqa: E402
from app.config import ManagerConfig, save_config  # noqa: E402
from app.runner import CommandResult  # noqa: E402


class FakeDialogWindow:
    def __init__(self, result: list[str] | None) -> None:
        self.result = result

    def create_file_dialog(self, *_args: object, **_kwargs: object) -> list[str] | None:
        return self.result


class FakeGitPreviewRunner:
    def run(self, command: list[str | Path], cwd: Path | None = None, timeout: int = 60) -> CommandResult:
        normalized = [str(part) for part in command]
        if normalized[:3] == ["git", "rev-parse", "--is-inside-work-tree"]:
            return CommandResult(normalized, cwd, 0, "true\n", "", 1)
        if normalized[:3] == ["git", "status", "--short"]:
            return CommandResult(normalized, cwd, 0, " M app.py\n", "", 1)
        if normalized[:3] == ["git", "branch", "--show-current"]:
            return CommandResult(normalized, cwd, 0, "feature/git-summary\n", "", 1)
        if normalized[:4] == ["git", "fetch", "origin", "feature/git-summary"]:
            return CommandResult(normalized, cwd, 0, "", "", 1)
        if normalized[:4] == ["git", "rev-list", "--left-right", "--count"]:
            return CommandResult(normalized, cwd, 0, "0\t1\n", "", 1)
        if normalized[:5] == ["git", "log", "-5", "--date=short", "--pretty=format:%h%x1f%ad%x1f%s"]:
            return CommandResult(normalized, cwd, 0, "abc1234\x1f2026-05-24\x1fInitial commit\n", "", 1)
        if normalized[-3:] == ["update", "--force", "--dry-run"]:
            return CommandResult(normalized, cwd, 0, "[Dry run] No changes made.\n", "", 1)
        return CommandResult(normalized, cwd, 0, "", "", 1)


class FakeHelmRunner:
    def __init__(self, project: Path, task: Path) -> None:
        self.project = project
        self.task = task

    def run(self, command: list[str | Path], cwd: Path | None = None, timeout: int = 60) -> CommandResult:
        normalized = [str(part) for part in command]
        if normalized == ["helm", "--version"]:
            return CommandResult(normalized, cwd, 0, "helm 0.0.17\n", "", 1)
        if normalized == ["helm", "workspace", "ls", "--json"]:
            return CommandResult(
                normalized,
                cwd,
                0,
                json.dumps([{"name": "team", "projects": [str(self.project.resolve())]}]),
                "",
                1,
            )
        if normalized[:3] == ["helm", "issue", "new"]:
            return CommandResult(normalized, cwd, 0, '{"id":"ISS-1"}\n', "", 1)
        return CommandResult(normalized, cwd, 1, "", "unexpected command", 1)


class FakeBatchUpdateRunner:
    def __init__(self, behaviors: dict[str, dict[str, object]]) -> None:
        self.behaviors = behaviors
        self.calls: list[tuple[list[str], Path | None]] = []

    def run(self, command: list[str | Path], cwd: Path | None = None, timeout: int = 60) -> CommandResult:
        normalized = [str(part) for part in command]
        self.calls.append((normalized, cwd))
        behavior = self.behaviors.get(str(cwd.resolve()) if cwd else "", {})
        if normalized[:3] == ["git", "rev-parse", "--is-inside-work-tree"]:
            return CommandResult(normalized, cwd, 0, "true\n", "", 1)
        if normalized[:3] == ["git", "status", "--short"]:
            stdout = " M app.py\n" if behavior.get("dirty") else ""
            return CommandResult(normalized, cwd, 0, stdout, "", 1)
        if normalized[-2:] == ["update", "--force"]:
            return CommandResult(normalized, cwd, 0, "updated\n", "", 1)
        return CommandResult(normalized, cwd, 0, "", "", 1)


class TrellisManagerUiTest(unittest.TestCase):
    def test_get_config_serializes_paths_for_frontend(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "config.json"
            repo = Path(tmp) / "Trellis"
            project = Path(tmp) / "crm-web-b2c"
            save_config(
                ManagerConfig(
                    trellis_repo=repo,
                    projects=[project],
                    last_selected_project=project,
                    recent_projects=[project],
                ),
                config_path,
            )

            api = TrellisAPI(config_file=config_path)

            self.assertEqual(
                api.get_config(),
                {
                    "trellis_repo": str(repo),
                    "projects": [str(project)],
                    "last_selected_project": str(project),
                    "recent_projects": [str(project)],
                    "official_repo_url": "https://github.com/beilo/Trellis.git",
                    "accelerated_repo_url": "https://xget.xi-xu.me/gh/beilo/Trellis.git",
                    "distribution_branch": "sync/v0.6.0-rc",
                },
            )

    def test_project_apis_persist_list_and_selection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "config.json"
            repo = Path(tmp) / "Trellis"
            first = Path(tmp) / "first"
            second = Path(tmp) / "second"
            save_config(ManagerConfig(trellis_repo=repo, projects=[first]), config_path)

            api = TrellisAPI(config_file=config_path)

            api.save_projects([str(first), str(second), str(first)], str(second))
            self.assertEqual(api.get_projects(), [str(first), str(second)])
            self.assertEqual(api.get_config()["last_selected_project"], str(second))

            api.remove_project(str(second))
            self.assertEqual(api.get_projects(), [str(first)])
            self.assertEqual(api.get_config()["last_selected_project"], str(first))

    def test_select_directory_handles_missing_and_present_window(self) -> None:
        api = TrellisAPI()

        self.assertIsNone(api.select_directory())

        api.set_window(FakeDialogWindow(["/tmp/project"]))  # type: ignore[arg-type]
        self.assertEqual(api.select_directory(), "/tmp/project")

        api.set_window(FakeDialogWindow(None))  # type: ignore[arg-type]
        self.assertIsNone(api.select_directory())

    def test_cursor_api_checks_common_location_and_opens_cursor(self) -> None:
        """Cursor 检查优先走本地常见路径，打开时只传参数数组。"""
        api = TrellisAPI()

        def fake_exists(self: Path) -> bool:
            return str(self) == "/Applications/Cursor.app"

        with (
            patch("app.api.Path.exists", new=fake_exists),
            patch("app.api.shutil.which", return_value=None),
            patch("app.api.subprocess.Popen") as popen,
        ):
            status = api.check_cursor_status()
            api.open_in_cursor("~/project")

        self.assertTrue(status["ok"])
        self.assertEqual(status["status"], "ok")
        self.assertIn("Cursor 已安装", status["message"])
        popen.assert_called_once_with(["open", "-a", "Cursor", str(Path("~/project").expanduser())])

    def test_cursor_api_prefers_cli_when_available(self) -> None:
        """Cursor CLI 可用时优先使用 CLI 打开路径。"""
        api = TrellisAPI()

        with patch("app.api.shutil.which", return_value="/usr/local/bin/cursor"), patch("app.api.subprocess.Popen") as popen:
            api.open_in_cursor("~/project")

        popen.assert_called_once_with(["/usr/local/bin/cursor", str(Path("~/project").expanduser())])

    def test_cursor_api_uses_mdfind_fallback_when_app_bundle_is_missing(self) -> None:
        """当常见安装路径不存在时，后端仍应通过 mdfind 兜底。"""
        api = TrellisAPI()
        mock_result = Mock(returncode=0, stdout="/Applications/Cursor.app\n")

        with patch("app.api.Path.exists", return_value=False), patch("app.api.subprocess.run", return_value=mock_result) as run:
            status = api.check_cursor_status()

        self.assertTrue(status["ok"])
        self.assertEqual(status["name"], "cursor")
        run.assert_called_once()

    def test_list_project_tasks_serializes_snapshot(self) -> None:
        """API 层应直接返回前端可消费的任务快照字典。"""
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            task_dir = project / ".trellis" / "tasks" / "05-22-api"
            task_dir.mkdir(parents=True)
            (task_dir / "task.json").write_text(
                '{"title": "API Task", "status": "planning"}',
                encoding="utf-8",
            )

            api = TrellisAPI()
            result = api.list_project_tasks(str(project))

            self.assertTrue(result["has_trellis"])
            self.assertEqual(result["tasks"][0]["title"], "API Task")
            self.assertEqual(result["counts"]["planning"], 1)

    def test_list_all_tasks_serializes_configured_projects(self) -> None:
        """看板 API 只聚合配置内项目，并返回前端可消费的字典。"""
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "config.json"
            repo = Path(tmp) / "Trellis"
            project = Path(tmp) / "project"
            task_dir = project / ".trellis" / "tasks" / "05-23-kanban"
            task_dir.mkdir(parents=True)
            (task_dir / "task.json").write_text(
                '{"title": "Kanban Task", "status": "in_progress"}',
                encoding="utf-8",
            )
            save_config(ManagerConfig(trellis_repo=repo, projects=[project]), config_path)

            api = TrellisAPI(config_file=config_path)
            result = api.list_all_tasks()

            self.assertEqual(result["project_count"], 1)
            self.assertEqual(result["total_counts"]["in_progress"], 1)
            self.assertEqual(result["projects"][0]["project_name"], "project")
            self.assertEqual(result["projects"][0]["tasks"][0]["title"], "Kanban Task")

    def test_batch_update_api_serializes_results_and_log(self) -> None:
        """批量更新 API 应返回前端字典，并只写一条聚合日志。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "first"
            second = root / "second"
            repo = root / "Trellis"
            package = repo / "packages" / "cli" / "package.json"
            for project in (first, second):
                project.mkdir()
                (project / ".trellis").mkdir()
                (project / ".trellis" / ".version").write_text("0.6.0-beta.9", encoding="utf-8")
            package.parent.mkdir(parents=True)
            package.write_text(json.dumps({"version": "0.6.0-beta.10"}), encoding="utf-8")
            config_path = root / "config.json"
            log_path = root / "logs.json"
            save_config(ManagerConfig(trellis_repo=repo, projects=[first, second]), config_path)
            api = TrellisAPI(config_file=config_path, log_file=log_path)
            api._runner = FakeBatchUpdateRunner({})  # type: ignore[assignment]  # 测试注入 runner，避免真实调用 git/tl。

            outdated = api.list_outdated_projects()
            report = api.batch_update_projects(None)
            logs = json.loads(log_path.read_text(encoding="utf-8"))

            self.assertEqual([item["path"] for item in outdated], [str(first.resolve()), str(second.resolve())])
            self.assertTrue(report["ok"])
            self.assertEqual(report["updated_count"], 2)
            self.assertEqual(report["failed_count"], 0)
            self.assertEqual(report["skipped_count"], 0)
            self.assertEqual(report["results"][0]["path"], str(first.resolve()))
            self.assertIsNotNone(report["results"][0]["report"])
            self.assertEqual(len(logs), 1)
            self.assertEqual(logs[0]["results"][1]["path"], str(second.resolve()))

    def test_batch_update_api_preserves_dirty_skip_reason(self) -> None:
        """批量更新桥接层应保留 dirty 跳过原因，方便前端展示。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            dirty = root / "dirty"
            repo = root / "Trellis"
            package = repo / "packages" / "cli" / "package.json"
            dirty.mkdir()
            (dirty / ".trellis").mkdir()
            (dirty / ".trellis" / ".version").write_text("0.6.0-beta.9", encoding="utf-8")
            package.parent.mkdir(parents=True)
            package.write_text(json.dumps({"version": "0.6.0-beta.10"}), encoding="utf-8")
            config_path = root / "config.json"
            save_config(ManagerConfig(trellis_repo=repo, projects=[dirty]), config_path)
            api = TrellisAPI(config_file=config_path, log_file=root / "logs.json")
            api._runner = FakeBatchUpdateRunner({str(dirty.resolve()): {"dirty": True}})  # type: ignore[assignment]

            report = api.batch_update_projects([str(dirty)])

            self.assertFalse(report["ok"])
            self.assertTrue(report["results"][0]["skipped"])
            self.assertIn("未提交变更", report["results"][0]["reason"])

    def test_git_summary_and_preview_api_serialize_for_frontend(self) -> None:
        """API 层应把 Git 摘要和 update 预览序列化为前端可消费字典。"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            repo = root / "Trellis"
            package = repo / "packages" / "cli" / "package.json"
            project.mkdir()
            (project / ".trellis").mkdir()
            (project / ".trellis" / ".version").write_text("0.6.0-beta.9", encoding="utf-8")
            package.parent.mkdir(parents=True)
            package.write_text(json.dumps({"version": "0.6.0-beta.10"}), encoding="utf-8")
            config_path = root / "config.json"
            save_config(ManagerConfig(trellis_repo=repo, projects=[project]), config_path)
            api = TrellisAPI(config_file=config_path)
            api._runner = FakeGitPreviewRunner()  # type: ignore[assignment]  # 测试注入 runner，避免真实调用 git/tl。

            summary = api.get_project_git_summary(str(project))
            preview = api.preview_project_update(str(project))

            self.assertEqual(summary["branch"], "feature/git-summary")
            self.assertEqual(summary["dirty_files"], [" M app.py"])
            self.assertEqual(summary["recent_commits"][0]["short_hash"], "abc1234")
            self.assertEqual(summary["recent_commits"][0]["date"], "2026-05-24")
            self.assertTrue(preview["ok"])
            self.assertEqual(preview["trellis_version_before"], "0.6.0-beta.9")
            self.assertEqual(preview["latest_version"], "0.6.0-beta.10")
            self.assertIn("[Dry run]", preview["dry_run_output"])

    def test_helm_api_serializes_status_and_push_report(self) -> None:
        """API 层应把 Helm 状态和推送结果序列化给前端。"""
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            task = project / ".trellis" / "tasks" / "05-23-helm"
            task.mkdir(parents=True)
            (task / "task.json").write_text('{"title":"Push Task"}', encoding="utf-8")
            (task / "prd.md").write_text("# PRD\n", encoding="utf-8")

            api = TrellisAPI()
            api._runner = FakeHelmRunner(project, task)  # type: ignore[assignment]  # 测试注入 runner，避免真实调用 Helm。

            status = api.check_helm_status()
            report = api.push_task_to_helm(str(project), str(task))

            self.assertTrue(status["ok"])
            self.assertEqual(report["details"]["workspace"], "team")
            self.assertIn("ISS-1", report["message"])


if __name__ == "__main__":
    unittest.main()
