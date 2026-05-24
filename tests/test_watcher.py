from __future__ import annotations

import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import watcher  # noqa: E402
from app.watcher import (  # noqa: E402
    ProjectChangeDebouncer,
    TrellisFileChange,
    classify_trellis_change,
)


class FakeWindow:
    def __init__(self) -> None:
        self.scripts: list[str] = []

    def evaluate_js(self, script: str) -> None:
        self.scripts.append(script)


class TestWatcherPathFiltering(unittest.TestCase):
    def test_accepts_task_json_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            task_json = project / ".trellis" / "tasks" / "05-24-demo" / "task.json"
            task_json.parent.mkdir(parents=True)
            task_json.write_text("{}", encoding="utf-8")

            self.assertEqual(
                classify_trellis_change(project, task_json, is_directory=False, event_type="modified"),
                "tasks",
            )

    def test_accepts_task_directory_creation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            task_dir = project / ".trellis" / "tasks" / "05-24-new"
            task_dir.mkdir(parents=True)

            self.assertEqual(
                classify_trellis_change(project, task_dir, is_directory=True, event_type="created"),
                "tasks",
            )

    def test_accepts_version_file_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            version = project / ".trellis" / ".version"
            version.parent.mkdir(parents=True)
            version.write_text("1", encoding="utf-8")

            self.assertEqual(
                classify_trellis_change(project, version, is_directory=False, event_type="modified"),
                "version",
            )

    def test_ignores_non_target_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            paths = [
                project / ".git" / "HEAD",
                project / "README.md",
                project / ".trellis" / "workspace" / "journal.md",
                project / ".trellis" / "tasks" / "05-24-demo" / "notes.md",
                project / ".trellis" / "tasks",
            ]
            for path in paths:
                path.parent.mkdir(parents=True, exist_ok=True)
                if path.suffix or path.name == "HEAD":
                    path.write_text("x", encoding="utf-8")
                else:
                    path.mkdir(exist_ok=True)

            self.assertIsNone(classify_trellis_change(project, paths[0], False, "modified"))
            self.assertIsNone(classify_trellis_change(project, paths[1], False, "modified"))
            self.assertIsNone(classify_trellis_change(project, paths[2], False, "modified"))
            self.assertIsNone(classify_trellis_change(project, paths[3], False, "modified"))
            self.assertIsNone(classify_trellis_change(project, paths[4], True, "created"))

    def test_ignores_task_directory_modification(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            task_dir = project / ".trellis" / "tasks" / "05-24-demo"
            task_dir.mkdir(parents=True)

            self.assertIsNone(
                classify_trellis_change(project, task_dir, is_directory=True, event_type="modified")
            )


class TestWatcherDebounce(unittest.TestCase):
    def test_debounce_merges_same_project_and_type(self) -> None:
        received: list[TrellisFileChange] = []
        debouncer = ProjectChangeDebouncer(0.05, received.append)

        change = TrellisFileChange("tasks", "/tmp/project")
        debouncer.notify(change)
        debouncer.notify(change)
        debouncer.notify(change)
        time.sleep(0.12)

        self.assertEqual(received, [change])

    def test_debounce_keeps_different_type_or_project(self) -> None:
        received: list[TrellisFileChange] = []
        debouncer = ProjectChangeDebouncer(0.05, received.append)

        first = TrellisFileChange("tasks", "/tmp/project-a")
        second = TrellisFileChange("version", "/tmp/project-a")
        third = TrellisFileChange("tasks", "/tmp/project-b")
        debouncer.notify(first)
        debouncer.notify(second)
        debouncer.notify(third)
        time.sleep(0.12)

        self.assertCountEqual(received, [first, second, third])

    def test_dispatch_uses_event_contract(self) -> None:
        window = FakeWindow()
        watcher.set_notification_window(window)
        watcher._dispatch_change(TrellisFileChange("tasks", "/tmp/project"))  # type: ignore[attr-defined]
        watcher.set_notification_window(None)

        self.assertEqual(len(window.scripts), 1)
        self.assertIn("window.onTrellisFileChange?.", window.scripts[0])
        self.assertIn('"type": "tasks"', window.scripts[0])
        self.assertIn('"projectPath": "/tmp/project"', window.scripts[0])

    def tearDown(self) -> None:
        watcher.stop_project_watchers()
        watcher.set_notification_window(None)


if __name__ == "__main__":
    unittest.main()
