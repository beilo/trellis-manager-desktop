from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.api import TrellisAPI  # noqa: E402
from app.file_reader import MAX_TEXT_BYTES, SafeFileReader  # noqa: E402


class SafeFileReaderTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.project = self.tmp / "project"
        self.trellis = self.project / ".trellis"
        (self.trellis / "spec").mkdir(parents=True)
        (self.trellis / "workspace").mkdir()
        self.task_dir = self.trellis / "tasks" / "05-24-reader"
        self.task_dir.mkdir(parents=True)
        self.reader = SafeFileReader()

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp)

    def test_list_tree_and_read_text_stay_inside_trellis(self) -> None:
        """正常读取只返回相对 .trellis 的路径，避免前端拿到宿主机绝对路径。"""
        (self.trellis / "spec" / "prd.md").write_text("# Spec\n", encoding="utf-8")

        tree = self.reader.list_tree(str(self.project), "spec")
        text = self.reader.read_text(str(self.project), "spec/prd.md")

        self.assertTrue(tree.ok)
        self.assertEqual(tree.items[0].path, "spec/prd.md")
        self.assertTrue(text.ok)
        self.assertEqual(text.path, "spec/prd.md")
        self.assertEqual(text.content, "# Spec\n")

    def test_rejects_path_traversal(self) -> None:
        """用户输入中的 .. 必须直接拒绝，不能依赖后续文件是否存在。"""
        result = self.reader.read_text(str(self.project), "spec/../secret.md")

        self.assertFalse(result.ok)
        self.assertEqual(result.error.code if result.error else None, "path_traversal")

    def test_rejects_symlink_escape(self) -> None:
        """符号链接 resolve 后逃逸出 .trellis 时必须拒绝。"""
        outside = self.tmp / "outside.txt"
        outside.write_text("secret", encoding="utf-8")
        (self.trellis / "spec" / "escape.txt").symlink_to(outside)

        result = self.reader.read_text(str(self.project), "spec/escape.txt")

        self.assertFalse(result.ok)
        self.assertEqual(result.error.code if result.error else None, "symlink_escape")

    def test_rejects_too_large_file(self) -> None:
        """超出读取上限的文件应返回结构化错误，避免 UI 一次性吞大文件。"""
        large = self.trellis / "spec" / "large.md"
        large.write_text("x" * (MAX_TEXT_BYTES + 1), encoding="utf-8")

        result = self.reader.read_text(str(self.project), "spec/large.md")

        self.assertFalse(result.ok)
        self.assertEqual(result.error.code if result.error else None, "file_too_large")

    def test_returns_not_found_for_missing_file(self) -> None:
        result = self.reader.read_text(str(self.project), "spec/missing.md")

        self.assertFalse(result.ok)
        self.assertEqual(result.error.code if result.error else None, "not_found")

    def test_rejects_non_utf8_file(self) -> None:
        binary = self.trellis / "spec" / "binary.bin"
        binary.write_bytes(b"\xff\xfe\x00")

        result = self.reader.read_text(str(self.project), "spec/binary.bin")

        self.assertFalse(result.ok)
        self.assertEqual(result.error.code if result.error else None, "binary_file")

    def test_reads_jsonl_with_partial_errors_and_pagination(self) -> None:
        """JSONL 坏行不阻塞其它行，分页 offset 继续使用物理行号。"""
        context = self.task_dir / "research.jsonl"
        context.write_text('{"ok": 1}\nnot json\n{"ok": 2}\n{"ok": 3}\n', encoding="utf-8")

        first = self.reader.read_jsonl(str(self.project), "tasks/05-24-reader/research.jsonl", limit=2)
        second = self.reader.read_jsonl(str(self.project), "tasks/05-24-reader/research.jsonl", limit=2, offset=first.next_offset or 0)

        self.assertTrue(first.ok)
        self.assertEqual(first.items, [{"ok": 1}, {"ok": 2}])
        self.assertEqual(first.errors[0].line, 2)
        self.assertEqual(first.next_offset, 3)
        self.assertEqual(second.items, [{"ok": 3}])
        self.assertIsNone(second.next_offset)

    def test_api_reads_task_document_and_context(self) -> None:
        """API 层只做桥接，任务路径读取仍由 SafeFileReader 控制边界。"""
        (self.task_dir / "prd.md").write_text("# PRD\n", encoding="utf-8")
        (self.task_dir / "research.jsonl").write_text('{"note":"ok"}\n', encoding="utf-8")

        api = TrellisAPI()
        document = api.read_task_document(str(self.task_dir), "prd")
        context_tree = api.list_task_context_files(str(self.task_dir))
        context = api.read_task_context_file(str(self.task_dir), "research.jsonl")
        invalid = api.read_task_document(str(self.task_dir), "notes")

        self.assertTrue(document["ok"])
        self.assertEqual(document["content"], "# PRD\n")
        self.assertTrue(context_tree["ok"])
        self.assertEqual(context["items"], [{"note": "ok"}])
        self.assertFalse(invalid["ok"])
        self.assertEqual(invalid["error"]["code"], "invalid_document")


if __name__ == "__main__":
    unittest.main()
