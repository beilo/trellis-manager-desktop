"""
Trellis 安全文件读取模块。

所有入口都把读取范围限制在业务项目的 `.trellis/` 下，避免 Manager UI 预览能力变成任意文件读取。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

import json

MAX_TEXT_BYTES = 2 * 1024 * 1024
DEFAULT_JSONL_LIMIT = 200
MAX_JSONL_LIMIT = 1000

FileKind = Literal["file", "directory"]


@dataclass(frozen=True)
class FileReadError:
    """结构化读取错误，供 pywebview 前端稳定展示。"""
    code: str
    message: str


@dataclass(frozen=True)
class FileTreeItem:
    """文件树节点，路径始终相对 `.trellis/`。"""
    path: str
    name: str
    type: FileKind
    size: int
    mtime: float
    children: list["FileTreeItem"] | None = None


@dataclass(frozen=True)
class TextFileResult:
    """文本读取结果。"""
    ok: bool
    path: str | None
    content: str | None
    size: int | None
    truncated: bool
    error: FileReadError | None = None


@dataclass(frozen=True)
class JsonlLineError:
    """JSONL 单行解析错误，允许前端展示部分成功结果。"""
    line: int
    message: str


@dataclass(frozen=True)
class JsonlFileResult:
    """JSONL 分页读取结果。"""
    ok: bool
    path: str | None
    items: list[Any]
    offset: int
    limit: int
    next_offset: int | None
    errors: list[JsonlLineError]
    error: FileReadError | None = None


@dataclass(frozen=True)
class FileTreeResult:
    """文件树读取结果。"""
    ok: bool
    root: str | None
    items: list[FileTreeItem]
    error: FileReadError | None = None


class SafeFileReader:
    """只读 `.trellis/` 文件访问器。"""

    def list_tree(self, project_path: str, subroot: str) -> FileTreeResult:
        """列出允许 subroot 下的文件树。"""
        trellis_root = self._trellis_root(project_path)
        try:
            relative = self._normalize_subroot(subroot)
            target = self._resolve_inside(trellis_root, relative)
            if not target.exists():
                return self._tree_error("not_found", "目录不存在。", relative)
            if not target.is_dir():
                return self._tree_error("not_directory", "目标不是目录。", relative)
            items = [self._tree_item(child, trellis_root) for child in sorted(target.iterdir(), key=self._sort_key)]
            return FileTreeResult(ok=True, root=relative, items=items)
        except SafeFileReaderError as error:
            return self._tree_error(error.code, error.message)
        except OSError as error:
            return self._tree_error("io_error", f"读取目录失败：{error}")

    def read_text(self, project_path: str, relative_path: str, max_bytes: int = MAX_TEXT_BYTES) -> TextFileResult:
        """读取 UTF-8 文本文件。"""
        trellis_root = self._trellis_root(project_path)
        try:
            relative = self._normalize_relative_path(relative_path)
            target = self._resolve_inside(trellis_root, relative)
            self._ensure_readable_file(target, max_bytes)
            content = target.read_text(encoding="utf-8")
            return TextFileResult(
                ok=True,
                path=relative,
                content=content,
                size=target.stat().st_size,
                truncated=False,
            )
        except SafeFileReaderError as error:
            return self._text_error(error.code, error.message, relative_path)
        except UnicodeDecodeError:
            return self._text_error("binary_file", "文件不是 UTF-8 文本，已拒绝读取。", relative_path)
        except OSError as error:
            return self._text_error("io_error", f"读取文件失败：{error}", relative_path)

    def read_jsonl(
        self,
        project_path: str,
        relative_path: str,
        limit: int = DEFAULT_JSONL_LIMIT,
        offset: int = 0,
    ) -> JsonlFileResult:
        """分页读取 JSONL，坏行以 errors 返回，不阻塞其它行。"""
        normalized_limit = self._normalize_limit(limit)
        normalized_offset = max(0, offset)
        trellis_root = self._trellis_root(project_path)
        try:
            relative = self._normalize_relative_path(relative_path)
            target = self._resolve_inside(trellis_root, relative)
            self._ensure_readable_file(target, MAX_TEXT_BYTES)
            items: list[Any] = []
            errors: list[JsonlLineError] = []
            next_offset: int | None = None
            with target.open("r", encoding="utf-8") as file:
                for line_number, line in enumerate(file):
                    if line_number < normalized_offset:
                        continue
                    if len(items) >= normalized_limit:
                        next_offset = line_number
                        break
                    stripped = line.strip()
                    if not stripped:
                        continue
                    try:
                        items.append(json.loads(stripped))
                    except json.JSONDecodeError as error:
                        errors.append(JsonlLineError(line=line_number + 1, message=str(error)))
            return JsonlFileResult(
                ok=True,
                path=relative,
                items=items,
                offset=normalized_offset,
                limit=normalized_limit,
                next_offset=next_offset,
                errors=errors,
            )
        except SafeFileReaderError as error:
            return self._jsonl_error(error.code, error.message, relative_path, normalized_limit, normalized_offset)
        except UnicodeDecodeError:
            return self._jsonl_error(
                "binary_file",
                "文件不是 UTF-8 文本，已拒绝读取。",
                relative_path,
                normalized_limit,
                normalized_offset,
            )
        except OSError as error:
            return self._jsonl_error("io_error", f"读取 JSONL 失败：{error}", relative_path, normalized_limit, normalized_offset)

    def task_project_path(self, task_path: str) -> Path:
        """从 `.trellis/tasks/<task>` 任务目录反推业务项目根。"""
        task_dir = Path(task_path).expanduser().resolve()
        parts = task_dir.parts
        for index in range(len(parts) - 2):
            if parts[index] == ".trellis" and parts[index + 1] == "tasks":
                return Path(*parts[:index])
        raise SafeFileReaderError("invalid_task_path", "任务路径必须位于 `.trellis/tasks/` 下。")

    def task_directory_relative_path(self, task_path: str) -> tuple[str, Path]:
        """把任务目录转换为相对 `.trellis/` 路径和项目路径。"""
        project = self.task_project_path(task_path)
        trellis_root = project / ".trellis"
        task_dir = Path(task_path).expanduser().resolve()
        self._assert_inside(task_dir, trellis_root.resolve())
        # 任务目录本身用于 list_tree，不能复用文件名归一化，否则空文件名会被误判为非法。
        relative = task_dir.relative_to(trellis_root.resolve()).as_posix()
        return relative, project

    def task_relative_path(self, task_path: str, filename: str) -> tuple[str, Path]:
        """把任务内文件名转换为相对 `.trellis/` 路径和项目路径。"""
        project = self.task_project_path(task_path)
        trellis_root = project / ".trellis"
        task_dir = Path(task_path).expanduser().resolve()
        self._assert_inside(task_dir, trellis_root.resolve())
        name = self._normalize_relative_path(filename)
        target = self._resolve_inside(task_dir, name)
        relative = target.relative_to(trellis_root.resolve()).as_posix()
        return relative, project

    def to_dict(self, value: object) -> dict[str, Any]:
        """递归 dataclass 序列化，保持 API 层简单。"""
        return asdict(value)

    def _tree_item(self, path: Path, trellis_root: Path) -> FileTreeItem:
        resolved = path.resolve()
        self._assert_inside(resolved, trellis_root.resolve())
        stat = resolved.stat()
        if resolved.is_dir():
            children = [self._tree_item(child, trellis_root) for child in sorted(resolved.iterdir(), key=self._sort_key)]
            return FileTreeItem(
                path=resolved.relative_to(trellis_root.resolve()).as_posix(),
                name=resolved.name,
                type="directory",
                size=0,
                mtime=stat.st_mtime,
                children=children,
            )
        return FileTreeItem(
            path=resolved.relative_to(trellis_root.resolve()).as_posix(),
            name=resolved.name,
            type="file",
            size=stat.st_size,
            mtime=stat.st_mtime,
        )

    def _trellis_root(self, project_path: str) -> Path:
        return Path(project_path).expanduser().resolve() / ".trellis"

    def _normalize_subroot(self, subroot: str) -> str:
        relative = self._normalize_relative_path(subroot)
        if relative in {"spec", "workspace"} or relative.startswith("spec/") or relative.startswith("workspace/"):
            return relative
        if relative.startswith("tasks/") and len(relative.split("/")) >= 2:
            return relative
        raise SafeFileReaderError("subroot_denied", "只允许读取 spec/、workspace/ 或 tasks/{task}/。")

    def _normalize_relative_path(self, value: str) -> str:
        if not value or value.strip() == "":
            raise SafeFileReaderError("invalid_path", "路径不能为空。")
        raw = value.replace("\\", "/").strip("/")
        path = Path(raw)
        if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
            raise SafeFileReaderError("path_traversal", "路径必须是安全的相对路径。")
        return path.as_posix()

    def _resolve_inside(self, root: Path, relative: str) -> Path:
        root_resolved = root.resolve()
        target = (root_resolved / relative).resolve()
        self._assert_inside(target, root_resolved)
        return target

    def _assert_inside(self, target: Path, root: Path) -> None:
        if target != root and root not in target.parents:
            raise SafeFileReaderError("symlink_escape", "路径解析后逃逸出允许读取范围。")

    def _ensure_readable_file(self, target: Path, max_bytes: int) -> None:
        if not target.exists():
            raise SafeFileReaderError("not_found", "文件不存在。")
        if not target.is_file():
            raise SafeFileReaderError("not_file", "目标不是文件。")
        size = target.stat().st_size
        if size > max_bytes:
            raise SafeFileReaderError("file_too_large", f"文件超过读取上限 {max_bytes} 字节。")

    def _normalize_limit(self, limit: int) -> int:
        if limit <= 0:
            return DEFAULT_JSONL_LIMIT
        return min(limit, MAX_JSONL_LIMIT)

    def _sort_key(self, path: Path) -> tuple[int, str]:
        return (0 if path.is_dir() else 1, path.name.lower())

    def _tree_error(self, code: str, message: str, root: str | None = None) -> FileTreeResult:
        return FileTreeResult(ok=False, root=root, items=[], error=FileReadError(code, message))

    def _text_error(self, code: str, message: str, path: str | None = None) -> TextFileResult:
        return TextFileResult(ok=False, path=path, content=None, size=None, truncated=False, error=FileReadError(code, message))

    def _jsonl_error(self, code: str, message: str, path: str | None, limit: int, offset: int) -> JsonlFileResult:
        return JsonlFileResult(
            ok=False,
            path=path,
            items=[],
            offset=offset,
            limit=limit,
            next_offset=None,
            errors=[],
            error=FileReadError(code, message),
        )


class SafeFileReaderError(ValueError):
    """SafeFileReader 内部可预期错误。"""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
