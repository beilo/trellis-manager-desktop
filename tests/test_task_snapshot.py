import shutil
import tempfile
import unittest
import json
from pathlib import Path

from app.task_snapshot import (
    read_all_task_snapshots,
    read_task_snapshot,
    normalize_status,
    compute_children_progress,
    TrellisTaskItem,
)


class TestNormalizeStatus(unittest.TestCase):
    def test_valid_statuses(self):
        for status in ["planning", "in_progress", "completed", "done"]:
            self.assertEqual(normalize_status(status), status)

    def test_invalid_status(self):
        self.assertEqual(normalize_status("invalid"), "unknown")
        self.assertEqual(normalize_status(""), "unknown")


class TestTaskSnapshot(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.project_dir = Path(self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def test_no_trellis(self):
        """无 .trellis 目录返回 has_trellis=False"""
        result = read_task_snapshot(str(self.project_dir))
        self.assertFalse(result.has_trellis)
        self.assertEqual(result.tasks, [])

    def test_empty_tasks(self):
        """有 .trellis 但无 tasks 目录"""
        (self.project_dir / ".trellis").mkdir()
        result = read_task_snapshot(str(self.project_dir))
        self.assertTrue(result.has_trellis)
        self.assertEqual(result.tasks, [])

    def test_planning_task(self):
        """读取 planning 状态任务"""
        task_dir = self.project_dir / ".trellis" / "tasks" / "01-01-test"
        task_dir.mkdir(parents=True)
        (task_dir / "task.json").write_text(json.dumps({
            "title": "Test Task",
            "status": "planning",
            "assignee": "user1",
        }))
        result = read_task_snapshot(str(self.project_dir))
        self.assertEqual(len(result.tasks), 1)
        self.assertEqual(result.tasks[0].status, "planning")
        self.assertEqual(result.tasks[0].title, "Test Task")
        self.assertEqual(result.tasks[0].assignee, "user1")

    def test_in_progress_task(self):
        """读取 in_progress 状态任务"""
        task_dir = self.project_dir / ".trellis" / "tasks" / "02-01-progress"
        task_dir.mkdir(parents=True)
        (task_dir / "task.json").write_text(json.dumps({
            "title": "In Progress Task",
            "status": "in_progress",
            "branch": "feature/test",
        }))
        result = read_task_snapshot(str(self.project_dir))
        self.assertEqual(len(result.tasks), 1)
        self.assertEqual(result.tasks[0].status, "in_progress")
        self.assertEqual(result.tasks[0].branch, "feature/test")

    def test_completed_task(self):
        """读取 completed 状态任务"""
        task_dir = self.project_dir / ".trellis" / "tasks" / "03-01-done"
        task_dir.mkdir(parents=True)
        (task_dir / "task.json").write_text(json.dumps({
            "title": "Done Task",
            "status": "completed",
            "completedAt": "2026-05-20",
        }))
        result = read_task_snapshot(str(self.project_dir))
        self.assertEqual(len(result.tasks), 1)
        self.assertEqual(result.tasks[0].status, "completed")

    def test_unknown_status(self):
        """未知状态映射为 unknown"""
        task_dir = self.project_dir / ".trellis" / "tasks" / "04-01-unknown"
        task_dir.mkdir(parents=True)
        (task_dir / "task.json").write_text(json.dumps({
            "title": "Unknown Task",
            "status": "some_weird_status",
        }))
        result = read_task_snapshot(str(self.project_dir))
        self.assertEqual(len(result.tasks), 1)
        self.assertEqual(result.tasks[0].status, "unknown")
        self.assertEqual(result.tasks[0].raw_status, "some_weird_status")

    def test_children_progress(self):
        """子任务完成进度计算"""
        tasks_dir = self.project_dir / ".trellis" / "tasks"
        tasks_dir.mkdir(parents=True)

        # 父任务
        parent = tasks_dir / "01-01-parent"
        parent.mkdir()
        (parent / "task.json").write_text(json.dumps({
            "title": "Parent",
            "status": "planning",
            "children": ["02-01-child1", "02-02-child2"],
        }))

        # 子任务1 - completed
        child1 = tasks_dir / "02-01-child1"
        child1.mkdir()
        (child1 / "task.json").write_text(json.dumps({
            "title": "Child 1",
            "status": "completed",
        }))

        # 子任务2 - in_progress
        child2 = tasks_dir / "02-02-child2"
        child2.mkdir()
        (child2 / "task.json").write_text(json.dumps({
            "title": "Child 2",
            "status": "in_progress",
        }))

        result = read_task_snapshot(str(self.project_dir))
        parent_task = next(t for t in result.tasks if t.dir_name == "01-01-parent")
        self.assertEqual(parent_task.child_total, 2)
        self.assertEqual(parent_task.child_done, 1)  # completed 计入

    def test_archived_child_done(self):
        """已归档子任务按完成计数"""
        tasks_dir = self.project_dir / ".trellis" / "tasks"
        tasks_dir.mkdir(parents=True)

        parent = tasks_dir / "01-01-parent"
        parent.mkdir()
        (parent / "task.json").write_text(json.dumps({
            "title": "Parent",
            "status": "planning",
            "children": ["02-01-child1"],
        }))

        # child1 已归档（不在 active 列表）
        archive_dir = tasks_dir / "archive" / "2026-05"
        archive_dir.mkdir(parents=True)
        child1 = archive_dir / "02-01-child1"
        child1.mkdir()
        (child1 / "task.json").write_text(json.dumps({
            "title": "Archived Child",
            "status": "completed",
        }))

        result = read_task_snapshot(str(self.project_dir), include_archive=True)
        parent_task = next(t for t in result.tasks if t.dir_name == "01-01-parent")
        self.assertEqual(parent_task.child_done, 1)  # 归档的也算完成

    def test_corrupted_task_json(self):
        """损坏的 task.json 不影响其他任务"""
        tasks_dir = self.project_dir / ".trellis" / "tasks"
        tasks_dir.mkdir(parents=True)

        good = tasks_dir / "01-01-good"
        good.mkdir()
        (good / "task.json").write_text(json.dumps({
            "title": "Good Task",
            "status": "planning",
        }))

        bad = tasks_dir / "02-02-bad"
        bad.mkdir()
        (bad / "task.json").write_text("not valid json")

        result = read_task_snapshot(str(self.project_dir))
        self.assertEqual(len(result.tasks), 2)  # 两个都返回
        good_task = next(t for t in result.tasks if t.dir_name == "01-01-good")
        self.assertIsNone(good_task.error)

    def test_documents_check(self):
        """文档完整度检查"""
        tasks_dir = self.project_dir / ".trellis" / "tasks"
        task_dir = tasks_dir / "01-01-docs"
        task_dir.mkdir(parents=True)
        (task_dir / "task.json").write_text(json.dumps({
            "title": "Task with docs",
            "status": "planning",
        }))
        (task_dir / "prd.md").write_text("# PRD")
        (task_dir / "implement.md").write_text("# Implement")

        result = read_task_snapshot(str(self.project_dir))
        task = result.tasks[0]
        self.assertTrue(task.has_prd)
        self.assertFalse(task.has_design)
        self.assertTrue(task.has_implement)

    def test_counts(self):
        """任务状态统计"""
        tasks_dir = self.project_dir / ".trellis" / "tasks"
        tasks_dir.mkdir(parents=True)

        for i, status in enumerate(["planning", "in_progress", "completed", "planning"]):
            task_dir = tasks_dir / f"0{i+1}-0{i+1}-{status}"
            task_dir.mkdir()
            (task_dir / "task.json").write_text(json.dumps({
                "title": f"Task {i}",
                "status": status,
            }))

        result = read_task_snapshot(str(self.project_dir))
        self.assertEqual(result.counts["planning"], 2)
        self.assertEqual(result.counts["in_progress"], 1)
        self.assertEqual(result.counts["completed"], 1)

    def test_read_all_task_snapshots(self):
        """跨项目聚合快照应汇总每个项目的任务与统计。"""
        first = self.project_dir / "first"
        second = self.project_dir / "second"
        for project, status in [(first, "planning"), (second, "in_progress")]:
            task_dir = project / ".trellis" / "tasks" / f"01-01-{project.name}"
            task_dir.mkdir(parents=True)
            (task_dir / "task.json").write_text(json.dumps({
                "title": f"{project.name} task",
                "status": status,
            }))

        result = read_all_task_snapshots([str(first), str(second)])

        self.assertEqual(result.project_count, 2)
        self.assertEqual(result.total_counts["planning"], 1)
        self.assertEqual(result.total_counts["in_progress"], 1)
        self.assertEqual(result.projects[0].project_name, "first")
        self.assertEqual(result.projects[1].tasks[0].title, "second task")

    def test_subtasks_alias(self):
        """支持 subtasks 别名字段"""
        task_dir = self.project_dir / ".trellis" / "tasks" / "01-01-subtasks"
        task_dir.mkdir(parents=True)
        (task_dir / "task.json").write_text(json.dumps({
            "title": "Subtasks Task",
            "status": "planning",
            "subtasks": ["02-01-sub1"],
        }))

        child = task_dir.parent / "02-01-sub1"
        child.mkdir()
        (child / "task.json").write_text(json.dumps({
            "title": "Sub 1",
            "status": "completed",
        }))

        result = read_task_snapshot(str(self.project_dir))
        parent = next(t for t in result.tasks if t.dir_name == "01-01-subtasks")
        self.assertEqual(parent.child_total, 1)
        self.assertEqual(parent.child_done, 1)

    def test_subtasks_path_stripping(self):
        """subtasks 中的路径格式兼容：只取最后一段作为 dir_name"""
        task_dir = self.project_dir / ".trellis" / "tasks" / "01-01-path"
        task_dir.mkdir(parents=True)
        (task_dir / "task.json").write_text(json.dumps({
            "title": "Path Subtasks",
            "status": "planning",
            "subtasks": [".trellis/tasks/02-01-deep"],
        }))

        child = task_dir.parent / "02-01-deep"
        child.mkdir()
        (child / "task.json").write_text(json.dumps({
            "title": "Deep Child",
            "status": "completed",
        }))

        result = read_task_snapshot(str(self.project_dir))
        parent = next(t for t in result.tasks if t.dir_name == "01-01-path")
        self.assertEqual(parent.children, ["02-01-deep"])  # 路径已剥离
        self.assertEqual(parent.child_done, 1)

    def test_archive_groups(self):
        """归档任务按月分组，archived_groups 结构正确"""
        tasks_dir = self.project_dir / ".trellis" / "tasks"
        tasks_dir.mkdir(parents=True)

        # 归档任务
        for month in ["2026-03", "2026-04"]:
            m_dir = tasks_dir / "archive" / month
            for i in range(2):
                t = m_dir / f"{month[5:]}-{i+1:02d}-task"
                t.mkdir(parents=True)
                (t / "task.json").write_text(json.dumps({
                    "title": f"Task {i}",
                    "status": "completed",
                }))

        result = read_task_snapshot(str(self.project_dir), include_archive=True)
        self.assertEqual(len(result.archived_groups), 2)
        # 月份倒序
        self.assertEqual(result.archived_groups[0].month, "2026-04")
        self.assertEqual(result.archived_groups[1].month, "2026-03")
        # 每月任务数
        self.assertEqual(len(result.archived_groups[0].tasks), 2)
        self.assertEqual(len(result.archived_groups[1].tasks), 2)
        # archive_counts
        self.assertEqual(result.archive_counts["2026-03"], 2)
        self.assertEqual(result.archive_counts["2026-04"], 2)
        self.assertEqual(result.archive_counts["total"], 4)

    def test_archive_month_field(self):
        """归档任务的 archive_month 字段正确"""
        tasks_dir = self.project_dir / ".trellis" / "tasks"
        tasks_dir.mkdir(parents=True)
        m_dir = tasks_dir / "archive" / "2026-05"
        t = m_dir / "05-01-archived"
        t.mkdir(parents=True)
        (t / "task.json").write_text(json.dumps({
            "title": "Archived",
            "status": "done",
        }))

        result = read_task_snapshot(str(self.project_dir), include_archive=True)
        archived = result.archived_groups[0].tasks[0]
        self.assertTrue(archived.archived)
        self.assertEqual(archived.archive_month, "2026-05")
        # active 任务的 archive_month 为 None
        self.assertIsNone(result.tasks[0].archive_month if result.tasks else None)

    def test_archive_error_count(self):
        """损坏归档 task.json 记入 error_count 而不阻塞"""
        tasks_dir = self.project_dir / ".trellis" / "tasks"
        tasks_dir.mkdir(parents=True)
        m_dir = tasks_dir / "archive" / "2026-01"
        good = m_dir / "01-01-ok"
        good.mkdir(parents=True)
        (good / "task.json").write_text(json.dumps({"title": "OK", "status": "completed"}))
        bad = m_dir / "01-02-bad"
        bad.mkdir(parents=True)
        (bad / "task.json").write_text("broken")

        result = read_task_snapshot(str(self.project_dir), include_archive=True)
        group = result.archived_groups[0]
        self.assertEqual(group.error_count, 1)
        self.assertEqual(len(group.tasks), 2)  # 好的+坏的都返回

    def test_no_archive_without_flag(self):
        """不开启归档时不扫描 archive 目录"""
        tasks_dir = self.project_dir / ".trellis" / "tasks"
        tasks_dir.mkdir(parents=True)
        m_dir = tasks_dir / "archive" / "2026-05"
        t = m_dir / "05-01-hidden"
        t.mkdir(parents=True)
        (t / "task.json").write_text(json.dumps({"title": "Hidden", "status": "done"}))

        result = read_task_snapshot(str(self.project_dir), include_archive=False)
        self.assertEqual(result.archived_groups, [])
        self.assertEqual(result.archive_counts, {"total": 0})
        self.assertEqual(len(result.tasks), 0)  # active 也没有


if __name__ == "__main__":
    unittest.main()
