from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Literal

try:
    from watchdog.events import FileSystemEvent, FileSystemEventHandler
    from watchdog.observers import Observer
except ImportError:  # pragma: no cover - 单测环境可能不安装 watchdog。
    FileSystemEvent = object  # type: ignore[misc,assignment]
    FileSystemEventHandler = object  # type: ignore[misc,assignment]
    Observer = None  # type: ignore[assignment]

ChangeType = Literal["tasks", "version"]

_DEBOUNCE_SECONDS = 0.3
_logger = logging.getLogger(__name__)
_lock = threading.RLock()
_window: object | None = None
_observer: object | None = None
_debouncer: object | None = None


@dataclass(frozen=True)
class TrellisFileChange:
    """后端向前端推送的文件变化事件。"""

    type: ChangeType
    project_path: str


class ProjectChangeDebouncer:
    """按项目和事件类型合并短时间内的重复文件事件。"""

    def __init__(self, delay_seconds: float, callback: Callable[[TrellisFileChange], None]) -> None:
        self._delay_seconds = delay_seconds
        self._callback = callback
        self._timers: dict[tuple[str, ChangeType], threading.Timer] = {}
        self._lock = threading.RLock()

    def notify(self, change: TrellisFileChange) -> None:
        key = (change.project_path, change.type)
        with self._lock:
            previous = self._timers.pop(key, None)
            if previous is not None:
                previous.cancel()
            timer = threading.Timer(self._delay_seconds, self._fire, args=(key, change))
            timer.daemon = True
            self._timers[key] = timer
            timer.start()

    def flush(self) -> None:
        with self._lock:
            pending = list(self._timers.items())
            self._timers.clear()
        for _key, timer in pending:
            timer.cancel()

    def _fire(self, key: tuple[str, ChangeType], change: TrellisFileChange) -> None:
        with self._lock:
            current = self._timers.get(key)
            if current is not threading.current_thread():
                return
            self._timers.pop(key, None)
        self._callback(change)


class TrellisFileEventHandler(FileSystemEventHandler):  # type: ignore[misc,valid-type]
    """watchdog 事件处理器，只把目标 Trellis 路径转换为业务事件。"""

    def __init__(self, project_path: Path, debouncer: ProjectChangeDebouncer) -> None:
        self._project_path = project_path.expanduser().resolve()
        self._debouncer = debouncer

    def on_any_event(self, event: FileSystemEvent) -> None:  # type: ignore[override]
        for raw_path in _event_paths(event):
            change_type = classify_trellis_change(
                self._project_path,
                raw_path,
                bool(getattr(event, "is_directory", False)),
                str(getattr(event, "event_type", "")),
            )
            if change_type is None:
                continue
            change = TrellisFileChange(change_type, str(self._project_path))
            _logger.info("检测到 Trellis 文件变化：%s %s", change.type, change.project_path)
            self._debouncer.notify(change)


def set_notification_window(window: object | None) -> None:
    """设置用于通知前端的 pywebview window。"""

    global _window
    with _lock:
        _window = window


def start_project_watchers(projects: list[str]) -> None:
    """按当前项目列表启动文件监听；不可用时降级为 warning + no-op。"""

    global _observer, _debouncer
    stop_project_watchers()
    if Observer is None:
        _logger.warning("watchdog 不可用，文件监听后端已降级为 no-op")
        return

    observer = Observer()
    debouncer = ProjectChangeDebouncer(_DEBOUNCE_SECONDS, _dispatch_change)
    scheduled = 0

    for project in projects:
        project_path = Path(project).expanduser().resolve()
        trellis_dir = project_path / ".trellis"
        if not trellis_dir.exists():
            _logger.warning("项目缺少 .trellis 目录，跳过文件监听：%s", project_path)
            continue
        handler = TrellisFileEventHandler(project_path, debouncer)
        observer.schedule(handler, str(trellis_dir), recursive=True)
        scheduled += 1

    if scheduled == 0:
        debouncer.flush()
        _logger.warning("没有可监听的 Trellis 项目，文件监听后端未启动")
        return

    observer.daemon = True
    observer.start()
    with _lock:
        _observer = observer
        _debouncer = debouncer
    _logger.info("Trellis 文件监听后端已启动：%s 个项目", scheduled)


def stop_project_watchers() -> None:
    """停止所有文件监听并取消尚未派发的 debounce 事件。"""

    global _observer, _debouncer
    with _lock:
        observer = _observer
        debouncer = _debouncer
        _observer = None
        _debouncer = None

    if isinstance(debouncer, ProjectChangeDebouncer):
        debouncer.flush()
    if observer is None:
        return

    try:
        observer.stop()
        observer.join(timeout=2)
    except Exception as exc:  # noqa: BLE001 - 停止 watcher 不能影响应用退出。
        _logger.warning("停止 Trellis 文件监听失败：%s", exc)


def classify_trellis_change(
    project_path: Path,
    changed_path: str | Path,
    is_directory: bool,
    event_type: str = "",
) -> ChangeType | None:
    """将文件系统路径映射为前端事件类型；非目标路径返回 None。"""

    project = project_path.expanduser().resolve()
    path = Path(changed_path).expanduser()
    try:
        resolved = path.resolve()
        relative = resolved.relative_to(project / ".trellis")
    except (OSError, ValueError):
        return None

    parts = relative.parts
    if not parts or ".git" in parts:
        return None
    if parts == (".version",) and not is_directory:
        return "version"
    if parts[0] != "tasks":
        return None
    if is_directory:
        if event_type and event_type != "created":
            return None
        return "tasks" if len(parts) >= 2 else None
    if len(parts) >= 3 and parts[-1] == "task.json":
        return "tasks"
    return None


def _dispatch_change(change: TrellisFileChange) -> None:
    with _lock:
        window = _window
    if window is None:
        _logger.warning("pywebview window 不可用，跳过文件变化事件推送：%s", change.project_path)
        return

    evaluate_js = getattr(window, "evaluate_js", None)
    if not callable(evaluate_js):
        _logger.warning("pywebview window 缺少 evaluate_js，跳过文件变化事件推送：%s", change.project_path)
        return

    payload = {"type": change.type, "projectPath": change.project_path}
    script = f"window.onTrellisFileChange?.({json.dumps(payload, ensure_ascii=False)})"
    try:
        evaluate_js(script)
    except Exception as exc:  # noqa: BLE001 - 前端通知失败不能影响 watcher。
        _logger.warning("推送 Trellis 文件变化事件失败：%s", exc)


def _event_paths(event: FileSystemEvent) -> list[str]:  # type: ignore[valid-type]
    paths = [str(getattr(event, "src_path", ""))]
    dest_path = str(getattr(event, "dest_path", ""))
    if dest_path:
        paths.append(dest_path)
    return [path for path in paths if path]
