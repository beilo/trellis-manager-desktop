from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
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
