from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from app.task_monitor import TaskMonitorError, TaskMonitorService, default_database_path
from app.runner import CommandResult


FIXED_NOW = datetime(2026, 7, 14, 16, 30, tzinfo=timezone.utc)


class FakeTerminalRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[list[str], Path | None]] = []

    def run(self, command: list[str], cwd: Path | None = None, timeout: int = 60) -> CommandResult:
        self.calls.append((command, cwd))
        return CommandResult(command, cwd, 0, "", "", 1)


class TaskMonitorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.runs = self.root / "runs"
        self.channels = self.root / "channels"
        self.db = self.root / "data" / "task-monitor.db"
        self.runner = FakeTerminalRunner()
        self.service = TaskMonitorService(
            db_path=self.db,
            runs_root=self.runs,
            channels_root=self.channels,
            now=lambda: FIXED_NOW,
            runner=self.runner,
        )

    def tearDown(self) -> None:
        self.service.stop()
        self.tmp.cleanup()

    def _fixture(self, channel: str = "trellis-test-20260714") -> tuple[Path, Path, Path]:
        project = self.root / "project"
        task = project / ".trellis" / "tasks" / "07-14-test"
        task.mkdir(parents=True)
        (task / "task.json").write_text(
            json.dumps({"name": "监听测试任务", "title": "备用名称"}), encoding="utf-8"
        )
        (task / "prd.md").write_text("# PRD\n\n可检索的验收关键词。", encoding="utf-8")
        handoff = self.root / "handoffs" / f"{channel}.md"
        handoff.parent.mkdir(parents=True)
        run = self.runs / "2026-07-14" / f"{channel}.md"
        run.parent.mkdir(parents=True)
        run.write_text(
            "\n".join(
                [
                    "# Trellis Loop Run",
                    "",
                    "status: sent",
                    f"channel: {channel}",
                    f"project: {project}",
                    f"task: {task}",
                    "worker: worker-1",
                    "provider: codex",
                    "sent_at: 2026-07-14T08:20:08Z",
                    f"record: {run}",
                    f"handoff: {handoff}",
                ]
            ),
            encoding="utf-8",
        )
        event_file = self.channels / "project-bucket" / channel / "events.jsonl"
        event_file.parent.mkdir(parents=True)
        self._write_events(
            event_file,
            [
                {"kind": "spawned", "by": "main", "as": "worker-1", "seq": 1, "ts": "2026-07-14T08:20:08Z"},
                {"kind": "turn_started", "by": "worker-1", "seq": 2, "ts": "2026-07-14T08:20:09Z"},
                {"kind": "message", "by": "worker-1", "text": "正在处理全文索引", "seq": 3, "ts": "2026-07-14T08:20:10Z"},
            ],
        )
        return run, handoff, event_file

    def _write_events(self, path: Path, events: list[dict[str, object]]) -> None:
        path.write_text("\n".join(json.dumps(event, ensure_ascii=False) for event in events) + "\n", encoding="utf-8")

    def test_default_database_path_uses_macos_application_support(self) -> None:
        with patch("app.task_monitor.platform.system", return_value="Darwin"):
            self.assertEqual(
                default_database_path(),
                Path.home() / "Library" / "Application Support" / "Trellis Manager" / "task-monitor.db",
            )

    def test_scan_resolves_active_then_done_and_preserves_cached_sources(self) -> None:
        run, handoff, events = self._fixture()
        self.service.scan_once()

        ongoing = self.service.list_runs("ongoing", limit=100)
        self.assertEqual(ongoing["total"], 1)
        self.assertEqual(ongoing["items"][0]["status"], "executing")
        self.assertEqual(ongoing["items"][0]["task_name"], "监听测试任务")
        self.assertEqual(ongoing["items"][0]["event_summary"], "正在处理全文索引")

        handoff.write_text(
            "---\nstatus: done\ncreated_at: 2026-07-14T08:25:00Z\n---\n\n完成全文索引。\n",
            encoding="utf-8",
        )
        self._write_events(
            events,
            [
                {"kind": "turn_started", "by": "worker-1", "seq": 2, "ts": "2026-07-14T08:20:09Z"},
                {"kind": "done", "by": "worker-1", "seq": 4, "ts": "2026-07-14T08:25:00Z"},
            ],
        )
        self.service.scan_once()

        ended = self.service.list_runs("ended")
        self.assertEqual(ended["total"], 1)
        self.assertEqual(ended["items"][0]["status"], "done")
        self.assertEqual(ended["items"][0]["archive_due_on"], "2026-08-13")

        run.write_text("corrupted after a successful scan", encoding="utf-8")
        self.service.scan_once()
        damaged = self.service.get_detail("trellis-test-20260714")
        self.assertEqual(damaged["status"], "done")
        self.assertIn("run record 解析失败", " ".join(damaged["errors"]))

        run.unlink()
        handoff.unlink()
        events.unlink()
        self.service.scan_once()
        cached = self.service.get_detail("trellis-test-20260714")
        self.assertEqual(cached["status"], "done")
        self.assertFalse(cached["source_available"])
        self.assertIn("run record 源文件缺失", " ".join(cached["errors"]))

    def test_duplicate_channel_and_single_file_failure_are_isolated(self) -> None:
        run, _, _ = self._fixture()
        duplicate = self.runs / "2026-07-15" / "duplicate.md"
        duplicate.parent.mkdir(parents=True)
        duplicate.write_text(run.read_text(encoding="utf-8"), encoding="utf-8")
        original_stat = run.stat()
        os.utime(duplicate, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns + 1_000_000))
        broken = self.runs / "2026-07-15" / "broken.md"
        broken.write_text("not a run record", encoding="utf-8")

        self.service.scan_once()

        detail = self.service.get_detail("trellis-test-20260714")
        self.assertTrue(detail["record_conflict"])
        self.assertEqual(detail["source_path"], str(duplicate))
        self.assertEqual(self.service.list_runs("ongoing")["total"], 1)

        duplicate.write_text("corrupted after a successful scan", encoding="utf-8")
        self.service.scan_once()
        fallback = self.service.get_detail("trellis-test-20260714")
        self.assertEqual(fallback["source_path"], str(run))
        self.assertIn("run record 解析失败", " ".join(fallback["errors"]))

        duplicate.write_text(run.read_text(encoding="utf-8"), encoding="utf-8")
        self.service.scan_once()
        duplicate.unlink()
        self.service.scan_once()
        self.assertEqual(self.service.get_detail("trellis-test-20260714")["source_path"], str(duplicate))

    def test_worker_state_precedes_non_done_handoff_until_worker_stops(self) -> None:
        _, handoff, events = self._fixture()
        handoff.write_text("---\nstatus: blocked\n---\n", encoding="utf-8")
        self.service.scan_once()
        self.assertEqual(self.service.get_detail("trellis-test-20260714")["status"], "executing")

        self._write_events(
            events,
            [
                {"kind": "turn_started", "by": "worker-1", "seq": 2, "ts": "2026-07-14T08:20:09Z"},
                {"kind": "killed", "by": "supervisor", "seq": 4, "ts": "2026-07-14T08:25:00Z"},
            ],
        )
        self.service.scan_once()
        self.assertEqual(self.service.get_detail("trellis-test-20260714")["status"], "blocked")

        handoff.unlink()
        self.service.scan_once()
        # handoff 删除后仍使用已缓存终态，避免任务从异常状态倒退。
        self.assertEqual(self.service.get_detail("trellis-test-20260714")["status"], "blocked")

    def test_unchanged_scan_does_not_reparse_events_or_rebuild_search_index(self) -> None:
        self._fixture()
        self.service.scan_once()

        with patch.object(self.service, "_parse_events") as parse_events, patch.object(
            self.service, "_update_search_index"
        ) as update_index, patch("app.task_monitor._parse_frontmatter") as parse_handoff, patch(
            "app.task_monitor._task_name_from_json"
        ) as parse_task:
            self.service.scan_once()

        parse_events.assert_not_called()
        update_index.assert_not_called()
        parse_handoff.assert_not_called()
        parse_task.assert_not_called()

    def test_recent_events_only_include_messages_from_mixed_events(self) -> None:
        _, _, events = self._fixture()
        rows = [
            {"kind": "turn_started", "by": "worker-1", "seq": 1, "ts": "2026-07-14T08:20:09Z"},
            {
                "kind": "progress",
                "by": "worker-1",
                "detail": {"tool": "shell", "status": "inProgress", "cmd": "command-1"},
                "seq": 2,
                "ts": "2026-07-14T08:20:10Z",
            },
            {"kind": "message", "by": "worker-1", "text": "第一条消息", "seq": 3, "ts": "2026-07-14T08:20:11Z"},
            {"kind": "done", "by": "worker-1", "seq": 4, "ts": "2026-07-14T08:20:12Z"},
            {"kind": "error", "by": "worker-1", "reason": "失败详情", "seq": 5, "ts": "2026-07-14T08:20:13Z"},
            {"kind": "killed", "by": "supervisor", "seq": 6, "ts": "2026-07-14T08:20:14Z"},
            {"kind": "message", "by": "main", "text": "第二条消息", "seq": 7, "ts": "2026-07-14T08:20:15Z"},
        ]
        self._write_events(events, rows)
        self.service.scan_once()

        recent = self.service.get_detail("trellis-test-20260714")["recent_events"]
        self.assertEqual([event["kind"] for event in recent], ["message", "message"])
        self.assertEqual([event["text"] for event in recent], ["第一条消息", "第二条消息"])
        self.assertEqual([event["seq"] for event in recent], [3, 7])

    def test_recent_events_filter_before_taking_last_twenty(self) -> None:
        _, _, events = self._fixture()
        rows: list[dict[str, object]] = []
        for index in range(25):
            rows.extend(
                [
                    {
                        "kind": "message",
                        "by": "worker-1",
                        "text": f"message-{index}",
                        "seq": index * 2 + 1,
                        "ts": "2026-07-14T08:20:10Z",
                    },
                    {
                        "kind": "progress",
                        "by": "worker-1",
                        "detail": {"tool": "shell", "status": "inProgress", "cmd": f"command-{index}"},
                        "seq": index * 2 + 2,
                        "ts": "2026-07-14T08:20:10Z",
                    },
                ]
            )
        self._write_events(events, rows)
        self.service.scan_once()

        recent = self.service.get_detail("trellis-test-20260714")["recent_events"]
        self.assertEqual(len(recent), 20)
        self.assertEqual(recent[0]["text"], "message-5")
        self.assertEqual(recent[-1]["text"], "message-24")
        self.assertTrue(all(event["kind"] == "message" for event in recent))

    def test_recent_events_are_empty_without_messages(self) -> None:
        _, _, events = self._fixture()
        self._write_events(
            events,
            [
                {"kind": "progress", "by": "worker-1", "seq": 1, "ts": "2026-07-14T08:20:09Z"},
                {"kind": "error", "by": "worker-1", "reason": "失败详情", "seq": 2, "ts": "2026-07-14T08:20:10Z"},
                {"kind": "killed", "by": "supervisor", "seq": 3, "ts": "2026-07-14T08:20:11Z"},
            ],
        )
        self.service.scan_once()

        detail = self.service.get_detail("trellis-test-20260714")
        self.assertEqual(detail["recent_events"], [])
        self.assertEqual(detail["status"], "waiting_result")

    def test_archive_refollow_and_search_include_archived_content(self) -> None:
        _, handoff, events = self._fixture()
        handoff.write_text("---\nstatus: done\ncreated_at: 2026-07-14T08:25:00Z\n---\n", encoding="utf-8")
        self._write_events(events, [{"kind": "done", "by": "worker-1", "seq": 4, "ts": "2026-07-14T08:25:00Z"}])
        self.service.scan_once()

        self.service.archive("trellis-test-20260714")
        self.assertEqual(self.service.list_runs("archived")["total"], 1)
        results = self.service.search("验收关键词")
        self.assertEqual(results["total"], 1)
        self.assertEqual(results["items"][0]["hit_source"], "PRD")

        refollowed = self.service.refollow("trellis-test-20260714")
        self.assertIsNone(refollowed["archived_at"])
        self.assertEqual(refollowed["archive_due_on"], "2026-08-13")
        self.assertEqual(self.service.list_runs("ended")["total"], 1)

        self.service._now = lambda: datetime(2026, 8, 13, 12, 0, tzinfo=timezone.utc)
        self.service.scan_once()
        self.assertEqual(self.service.list_runs("archived")["total"], 1)

    def test_search_fallback_and_terminal_launcher_use_validated_arguments(self) -> None:
        self._fixture()
        self.service.scan_once()
        self.service._fts_enabled = False
        results = self.service.search("全文索引")
        self.assertEqual(results["total"], 1)
        self.assertEqual(results["items"][0]["hit_source"], "Worker 消息")

        status_results = self.service.search("执行中")
        self.assertEqual(status_results["total"], 1)

        multi_source = self.service.search("监听 全文")
        self.assertEqual(multi_source["total"], 1)
        self.assertNotEqual(multi_source["items"][0]["hit_source"], "相关内容")

        with patch("app.task_monitor.shutil.which", return_value="/usr/local/bin/tl"):
            response = self.service.open_full_record("trellis-test-20260714")
        self.assertTrue(response["ok"])
        argv, cwd = self.runner.calls[0]
        self.assertIsNone(cwd)
        self.assertEqual(argv, ["osascript", "-e", argv[2], str(self.root / "project"), "/usr/local/bin/tl", "trellis-test-20260714"])
        self.assertEqual(argv[-1], "trellis-test-20260714")
        self.assertEqual(argv[-2], "/usr/local/bin/tl")
        self.assertNotIn("trellis-test-20260714", argv[2])
        with self.assertRaises(TaskMonitorError):
            self.service.open_full_record("bad channel; rm -rf")


if __name__ == "__main__":
    unittest.main()
