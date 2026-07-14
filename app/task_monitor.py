from __future__ import annotations

import json
import logging
import platform
import re
import shutil
import sqlite3
import threading
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from app.runner import CommandRunner


LOGGER = logging.getLogger(__name__)
SCHEMA_VERSION = 1
CHANNEL_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
MAX_SOURCE_BYTES = 8 * 1024 * 1024
TERMINAL_EVENT_KINDS = {"done", "killed", "turn_finished"}
STATUS_LABELS = {
    "executing": "执行中",
    "waiting_worker": "等待 worker",
    "waiting_result": "等待结果",
    "done": "已完成",
    "blocked": "已阻塞",
    "failed": "失败",
    "partial": "部分完成",
    "sent": "已派发",
    "unknown": "未知",
}


class TaskMonitorError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code

    def to_dict(self) -> dict[str, Any]:
        return {"ok": False, "error": {"code": self.code, "message": str(self)}}


def default_database_path() -> Path:
    if platform.system() == "Darwin":
        root = Path.home() / "Library" / "Application Support"
    elif platform.system() == "Windows":
        root = Path.home() / "AppData" / "Local"
    else:
        root = Path.home() / ".local" / "share"
    return root / "Trellis Manager" / "task-monitor.db"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _parse_key_value_markdown(text: str) -> dict[str, str]:
    payload: dict[str, str] = {}
    for line in text.splitlines():
        if line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        if re.fullmatch(r"[a-z_]+", key):
            payload[key] = value.strip()
    return payload


def _parse_frontmatter(text: str) -> dict[str, str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return _parse_key_value_markdown(text)
    try:
        end = next(index for index, line in enumerate(lines[1:], 1) if line.strip() == "---")
    except StopIteration:
        return {}
    return _parse_key_value_markdown("\n".join(lines[1:end]))


def _fingerprint(path: Path) -> str:
    stat = path.stat()
    return f"{stat.st_mtime_ns}:{stat.st_size}"


def _read_limited(path: Path) -> str:
    with path.open("rb") as file:
        raw = file.read(MAX_SOURCE_BYTES + 1)
    if len(raw) > MAX_SOURCE_BYTES:
        raise ValueError(f"文件超过 {MAX_SOURCE_BYTES} 字节上限")
    return raw.decode("utf-8")


def _project_name(path: str) -> str:
    normalized = path.rstrip("/\\")
    return Path(normalized).name or normalized


def _fallback_task_name(task_path: str, channel: str) -> str:
    return Path(task_path.rstrip("/\\")).name or channel


def _task_name_from_json(text: str, fallback: str) -> str:
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise AttributeError("task.json 顶层必须是对象")
    return str(payload.get("name") or payload.get("title") or fallback)


def _status_group(status: str, archived_at: str | None) -> str:
    if archived_at:
        return "archived"
    return "ended" if status == "done" else "ongoing"


def _status_priority(status: str) -> int:
    if status in {"failed", "blocked"}:
        return 0
    if status == "partial":
        return 1
    if status == "executing":
        return 2
    if status == "waiting_result":
        return 3
    return 4


class TaskMonitorService:
    """Loop run 扫描、缓存、状态解析与全文查询。"""

    def __init__(
        self,
        db_path: Path | None = None,
        runs_root: Path | None = None,
        channels_root: Path | None = None,
        now: Callable[[], datetime] = _utc_now,
        scan_interval: float = 5.0,
        runner: CommandRunner | None = None,
    ) -> None:
        self.db_path = (db_path or default_database_path()).expanduser()
        self.runs_root = (runs_root or Path.home() / ".trellis-loop" / "runs").expanduser()
        self.channels_root = (channels_root or Path.home() / ".trellis" / "channels").expanduser()
        self._now = now
        self._scan_interval = scan_interval
        self._runner = runner or CommandRunner()
        self._scan_lock = threading.RLock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._initialized = False
        self._fts_enabled = False
        self._last_archive_check: date | None = None

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.db_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    @contextmanager
    def _connection(self) -> Any:
        connection = self._connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _ensure_schema(self) -> None:
        if self._initialized:
            return
        with self._connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS schema_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS run_sources (
                    source_path TEXT PRIMARY KEY,
                    channel TEXT,
                    payload_json TEXT,
                    mtime_ns INTEGER NOT NULL DEFAULT 0,
                    size INTEGER NOT NULL DEFAULT 0,
                    parse_error TEXT,
                    source_available INTEGER NOT NULL DEFAULT 1,
                    last_seen_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS run_sources_channel_idx ON run_sources(channel);
                CREATE TABLE IF NOT EXISTS monitor_runs (
                    channel TEXT PRIMARY KEY,
                    source_path TEXT NOT NULL,
                    record_conflict INTEGER NOT NULL DEFAULT 0,
                    project_path TEXT NOT NULL,
                    project_name TEXT NOT NULL,
                    task_path TEXT NOT NULL,
                    task_name TEXT NOT NULL,
                    worker TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    sent_at TEXT,
                    handoff_path TEXT,
                    display_status TEXT NOT NULL,
                    handoff_status TEXT,
                    completed_at TEXT,
                    source_available INTEGER NOT NULL DEFAULT 1,
                    channel_available INTEGER NOT NULL DEFAULT 0,
                    run_error TEXT,
                    task_error TEXT,
                    handoff_error TEXT,
                    channel_error TEXT,
                    task_fingerprint TEXT,
                    prd_fingerprint TEXT,
                    handoff_fingerprint TEXT,
                    events_fingerprint TEXT,
                    task_json TEXT NOT NULL DEFAULT '',
                    prd_text TEXT NOT NULL DEFAULT '',
                    handoff_text TEXT NOT NULL DEFAULT '',
                    messages_text TEXT NOT NULL DEFAULT '',
                    events_raw TEXT NOT NULL DEFAULT '',
                    recent_events_json TEXT NOT NULL DEFAULT '[]',
                    event_summary TEXT NOT NULL DEFAULT '',
                    worker_active INTEGER NOT NULL DEFAULT 0,
                    worker_stopped INTEGER NOT NULL DEFAULT 0,
                    last_event_at TEXT,
                    archived_at TEXT,
                    attention_started_on TEXT,
                    archive_due_on TEXT,
                    first_imported_on TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )
            connection.execute(
                "INSERT OR REPLACE INTO schema_meta(key, value) VALUES('version', ?)",
                (str(SCHEMA_VERSION),),
            )
            columns = {row[1] for row in connection.execute("PRAGMA table_info(monitor_runs)")}
            if "events_raw" not in columns:
                connection.execute("ALTER TABLE monitor_runs ADD COLUMN events_raw TEXT NOT NULL DEFAULT ''")
            if "worker_active" not in columns:
                connection.execute("ALTER TABLE monitor_runs ADD COLUMN worker_active INTEGER NOT NULL DEFAULT 0")
            if "worker_stopped" not in columns:
                connection.execute("ALTER TABLE monitor_runs ADD COLUMN worker_stopped INTEGER NOT NULL DEFAULT 0")
            if "last_event_at" not in columns:
                connection.execute("ALTER TABLE monitor_runs ADD COLUMN last_event_at TEXT")
            try:
                connection.execute(
                    """
                    CREATE VIRTUAL TABLE IF NOT EXISTS task_monitor_fts USING fts5(
                        channel UNINDEXED,
                        task_name,
                        project_name,
                        metadata,
                        prd,
                        handoff,
                        messages
                    )
                    """
                )
                self._fts_enabled = True
            except sqlite3.OperationalError:
                self._fts_enabled = False
        self._initialized = True

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        try:
            self.scan_once()
        except Exception:
            # 初次扫描失败不能阻止桌面窗口启动；后台循环会继续重试。
            LOGGER.exception("Initial Trellis Loop task monitor scan failed")
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._scan_loop, name="task-monitor", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=max(2.0, self._scan_interval + 1.0))
        self._thread = None

    def _scan_loop(self) -> None:
        while not self._stop_event.wait(self._scan_interval):
            try:
                self.scan_once()
            except Exception:
                LOGGER.exception("Trellis Loop task monitor scan failed")

    def scan_once(self) -> None:
        with self._scan_lock:
            self._ensure_schema()
            now = self._now()
            now_iso = _iso(now)
            discovered = set(self.runs_root.rglob("*.md")) if self.runs_root.exists() else set()
            with self._connection() as connection:
                known = {
                    row["source_path"]: row
                    for row in connection.execute("SELECT * FROM run_sources")
                }
                for path in discovered:
                    self._scan_run_source(connection, path, known.get(str(path)), now_iso)
                missing = set(known) - {str(path) for path in discovered}
                if missing:
                    connection.executemany(
                        "UPDATE run_sources SET source_available=0 WHERE source_path=?",
                        [(path,) for path in missing],
                    )

                channels = [
                    row[0]
                    for row in connection.execute(
                        "SELECT DISTINCT channel FROM run_sources WHERE channel IS NOT NULL"
                    )
                ]
                channel_files = self._channel_event_files()
                for channel in channels:
                    try:
                        self._refresh_channel(connection, channel, channel_files.get(channel), now)
                    except Exception as error:
                        LOGGER.warning("task monitor channel refresh failed for %s: %s", channel, error)
                        connection.execute(
                            "UPDATE monitor_runs SET run_error=?, updated_at=? WHERE channel=?",
                            (f"扫描失败：{error}", now_iso, channel),
                        )
                self._auto_archive(connection, now.date())

    def _scan_run_source(
        self,
        connection: sqlite3.Connection,
        path: Path,
        previous: sqlite3.Row | None,
        now_iso: str,
    ) -> None:
        try:
            stat = path.stat()
        except OSError as error:
            if previous:
                connection.execute(
                    "UPDATE run_sources SET source_available=0, parse_error=? WHERE source_path=?",
                    (f"源文件无法读取：{error}", str(path)),
                )
            return
        if previous and previous["mtime_ns"] == stat.st_mtime_ns and previous["size"] == stat.st_size:
            connection.execute(
                "UPDATE run_sources SET source_available=1, last_seen_at=? WHERE source_path=?",
                (now_iso, str(path)),
            )
            return
        payload_json = previous["payload_json"] if previous else None
        channel = previous["channel"] if previous else None
        parse_error: str | None = None
        try:
            payload = _parse_key_value_markdown(_read_limited(path))
            candidate = payload.get("channel", "")
            required = {"channel", "project", "task", "worker", "sent_at", "handoff"}
            if not required.issubset(payload):
                raise ValueError(f"缺少字段：{', '.join(sorted(required - set(payload)))}")
            if not CHANNEL_PATTERN.fullmatch(candidate):
                raise ValueError("channel 格式无效")
            channel = candidate
            payload_json = json.dumps(payload, ensure_ascii=False)
        except (OSError, UnicodeDecodeError, ValueError) as error:
            parse_error = f"run record 解析失败：{error}"
        connection.execute(
            """
            INSERT INTO run_sources(
                source_path, channel, payload_json, mtime_ns, size,
                parse_error, source_available, last_seen_at
            ) VALUES(?, ?, ?, ?, ?, ?, 1, ?)
            ON CONFLICT(source_path) DO UPDATE SET
                channel=excluded.channel,
                payload_json=excluded.payload_json,
                mtime_ns=excluded.mtime_ns,
                size=excluded.size,
                parse_error=excluded.parse_error,
                source_available=1,
                last_seen_at=excluded.last_seen_at
            """,
            (str(path), channel, payload_json, stat.st_mtime_ns, stat.st_size, parse_error, now_iso),
        )

    def _channel_event_files(self) -> dict[str, Path]:
        result: dict[str, Path] = {}
        if not self.channels_root.exists():
            return result
        for path in self.channels_root.glob("*/*/events.jsonl"):
            channel = path.parent.name
            current = result.get(channel)
            try:
                if current is None or path.stat().st_mtime_ns > current.stat().st_mtime_ns:
                    result[channel] = path
            except OSError:
                continue
        return result

    def _read_cached_text(
        self,
        path_value: str | None,
        old_fingerprint: str | None,
        old_text: str,
    ) -> tuple[str, str | None, str | None, bool]:
        if not path_value:
            return old_text, "missing", "未提供源文件路径", False
        path = Path(path_value).expanduser()
        if not path.exists():
            return old_text, "missing", "源文件缺失", False
        try:
            fingerprint = _fingerprint(path)
            if fingerprint == old_fingerprint:
                return old_text, fingerprint, None, True
            return _read_limited(path), fingerprint, None, True
        except (OSError, UnicodeDecodeError, ValueError) as error:
            return old_text, "error", f"源文件读取失败：{error}", True

    def _refresh_channel(
        self,
        connection: sqlite3.Connection,
        channel: str,
        events_path: Path | None,
        now: datetime,
    ) -> None:
        candidates = list(
            connection.execute(
                """
                SELECT * FROM run_sources
                WHERE channel=? AND payload_json IS NOT NULL
                ORDER BY CASE WHEN parse_error IS NULL THEN 0 ELSE 1 END, mtime_ns DESC
                """,
                (channel,),
            )
        )
        if not candidates:
            return
        canonical = candidates[0]
        payload = json.loads(canonical["payload_json"])
        old = connection.execute("SELECT * FROM monitor_runs WHERE channel=?", (channel,)).fetchone()
        old_value = (lambda key, fallback="": old[key] if old is not None else fallback)

        task_path = str(payload.get("task", ""))
        task_json_path = str(Path(task_path) / "task.json") if task_path else None
        prd_path = str(Path(task_path) / "prd.md") if task_path else None
        same_task_path = old is not None and old["task_path"] == task_path
        task_json, task_fp, task_error, _ = self._read_cached_text(
            task_json_path, old_value("task_fingerprint", None) if same_task_path else None, old_value("task_json")
        )
        prd_text, prd_fp, prd_error, _ = self._read_cached_text(
            prd_path, old_value("prd_fingerprint", None) if same_task_path else None, old_value("prd_text")
        )
        task_changed = old is None or not same_task_path or task_fp != old_value("task_fingerprint", None)
        prd_changed = old is None or not same_task_path or prd_fp != old_value("prd_fingerprint", None)
        task_name = old_value("task_name", "") or _fallback_task_name(task_path, channel)
        if task_changed and task_error is None:
            try:
                task_name = _task_name_from_json(task_json, task_name)
            except (json.JSONDecodeError, AttributeError) as error:
                task_error = f"task.json 解析失败：{error}"
        elif not task_changed:
            old_task_error = old_value("task_error", None)
            task_error = old_task_error if str(old_task_error or "").startswith("task.json") else None
        if prd_error and not task_error:
            task_error = f"prd.md：{prd_error}"
        elif not prd_changed and not task_error:
            old_task_error = old_value("task_error", None)
            task_error = old_task_error if str(old_task_error or "").startswith("prd.md") else None

        handoff_path = payload.get("handoff")
        same_handoff_path = old is not None and old["handoff_path"] == handoff_path
        handoff_text, handoff_fp, handoff_error, _ = self._read_cached_text(
            handoff_path, old_value("handoff_fingerprint", None) if same_handoff_path else None, old_value("handoff_text")
        )
        handoff_changed = old is None or not same_handoff_path or handoff_fp != old_value("handoff_fingerprint", None)
        if handoff_changed:
            handoff_payload = _parse_frontmatter(handoff_text)
            handoff_status = handoff_payload.get("status")
            if handoff_status not in {"done", "blocked", "failed", "partial"}:
                handoff_status = None
            handoff_created = _parse_datetime(handoff_payload.get("created_at"))
        else:
            handoff_status = old_value("handoff_status", None)
            handoff_created = None

        events_value = str(events_path) if events_path else None
        events_text, events_fp, channel_error, channel_available = self._read_cached_text(
            events_value, old_value("events_fingerprint", None), old_value("events_raw")
        )
        events_changed = old is None or events_fp != old_value("events_fingerprint", None)
        event_state = self._parse_events(events_text) if events_text and channel_available and events_changed else {
            "recent": json.loads(old_value("recent_events_json", "[]")),
            "messages": old_value("messages_text"),
            "summary": old_value("event_summary"),
            "last_timestamp": old_value("last_event_at", None),
            "active": bool(old_value("worker_active", 0)),
            "stopped": bool(old_value("worker_stopped", 0)),
        }
        if channel_error is None:
            messages_text = event_state["messages"]
            recent_events_json = json.dumps(event_state["recent"], ensure_ascii=False)
            event_summary = event_state["summary"]
        else:
            messages_text = old_value("messages_text")
            recent_events_json = old_value("recent_events_json", "[]")
            event_summary = old_value("event_summary")

        old_status = old_value("display_status", None)
        display_status = self._resolve_status(
            old_status=old_status,
            handoff_status=handoff_status,
            active=bool(event_state["active"]) if channel_available else False,
            stopped=bool(event_state["stopped"]) if channel_available else False,
            channel_available=channel_available,
            run_status=str(payload.get("status", "sent")),
        )
        sent_at = str(payload.get("sent_at") or "") or None
        source_time = _parse_datetime(sent_at)
        event_time = _parse_datetime(event_state.get("last_timestamp"))
        completed_at = old_value("completed_at", None)
        if display_status == "done" and not completed_at:
            completed_at = _iso(handoff_created or event_time or now)

        first_imported_on = old_value("first_imported_on", now.date().isoformat())
        attention_started_on = old_value("attention_started_on", None)
        archive_due_on = old_value("archive_due_on", None)
        if display_status == "done" and not attention_started_on:
            # 首次导入历史完成项以导入日开始；运行中项目转为完成时使用完成日。
            start_date = now.date() if old is None else (handoff_created or event_time or now).astimezone().date()
            attention_started_on = start_date.isoformat()
            archive_due_on = (start_date + timedelta(days=30)).isoformat()

        relevant_times = [value for value in (source_time, event_time, handoff_created) if value]
        updated_at = _iso(max(relevant_times)) if relevant_times else old_value("updated_at", _iso(now))
        run_errors = [row["parse_error"] for row in candidates if row["parse_error"]]
        if not canonical["source_available"]:
            run_errors.append("run record 源文件缺失，当前显示缓存快照")
        run_error = "；".join(dict.fromkeys(run_errors)) or None
        project_path = str(payload.get("project", ""))
        archived_at = old_value("archived_at", None)

        connection.execute(
            """
            INSERT INTO monitor_runs(
                channel, source_path, record_conflict, project_path, project_name,
                task_path, task_name, worker, provider, sent_at, handoff_path,
                display_status, handoff_status, completed_at, source_available,
                channel_available, run_error, task_error, handoff_error, channel_error,
                task_fingerprint, prd_fingerprint, handoff_fingerprint, events_fingerprint,
                task_json, prd_text, handoff_text, messages_text, events_raw, recent_events_json,
                event_summary, worker_active, worker_stopped, last_event_at,
                archived_at, attention_started_on, archive_due_on,
                first_imported_on, updated_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(channel) DO UPDATE SET
                source_path=excluded.source_path,
                record_conflict=excluded.record_conflict,
                project_path=excluded.project_path,
                project_name=excluded.project_name,
                task_path=excluded.task_path,
                task_name=excluded.task_name,
                worker=excluded.worker,
                provider=excluded.provider,
                sent_at=excluded.sent_at,
                handoff_path=excluded.handoff_path,
                display_status=excluded.display_status,
                handoff_status=excluded.handoff_status,
                completed_at=excluded.completed_at,
                source_available=excluded.source_available,
                channel_available=excluded.channel_available,
                run_error=excluded.run_error,
                task_error=excluded.task_error,
                handoff_error=excluded.handoff_error,
                channel_error=excluded.channel_error,
                task_fingerprint=excluded.task_fingerprint,
                prd_fingerprint=excluded.prd_fingerprint,
                handoff_fingerprint=excluded.handoff_fingerprint,
                events_fingerprint=excluded.events_fingerprint,
                task_json=excluded.task_json,
                prd_text=excluded.prd_text,
                handoff_text=excluded.handoff_text,
                messages_text=excluded.messages_text,
                events_raw=excluded.events_raw,
                recent_events_json=excluded.recent_events_json,
                event_summary=excluded.event_summary,
                worker_active=excluded.worker_active,
                worker_stopped=excluded.worker_stopped,
                last_event_at=excluded.last_event_at,
                attention_started_on=excluded.attention_started_on,
                archive_due_on=excluded.archive_due_on,
                updated_at=excluded.updated_at
            """,
            (
                channel,
                canonical["source_path"],
                1 if len(candidates) > 1 else 0,
                project_path,
                _project_name(project_path),
                task_path,
                task_name,
                str(payload.get("worker", "")),
                str(payload.get("provider", "")),
                sent_at,
                handoff_path,
                display_status,
                handoff_status,
                completed_at,
                int(any(row["source_available"] for row in candidates)),
                int(channel_available),
                run_error,
                task_error,
                handoff_error,
                channel_error,
                task_fp,
                prd_fp,
                handoff_fp,
                events_fp,
                task_json,
                prd_text,
                handoff_text,
                messages_text,
                events_text,
                recent_events_json,
                event_summary,
                int(bool(event_state["active"])),
                int(bool(event_state["stopped"])),
                event_state.get("last_timestamp"),
                archived_at,
                attention_started_on,
                archive_due_on,
                first_imported_on,
                updated_at,
            ),
        )
        search_changed = old is None or any(
            old_value(key, None) != value
            for key, value in (
                ("task_fingerprint", task_fp),
                ("prd_fingerprint", prd_fp),
                ("handoff_fingerprint", handoff_fp),
                ("events_fingerprint", events_fp),
                ("task_name", task_name),
                ("project_name", _project_name(project_path)),
                ("display_status", display_status),
                ("source_path", canonical["source_path"]),
            )
        )
        if search_changed:
            self._update_search_index(connection, channel)

    def _parse_events(self, text: str) -> dict[str, Any]:
        events: list[dict[str, Any]] = []
        commentary: dict[str, dict[str, Any]] = {}
        messages: list[tuple[int, str]] = []
        active_index = -1
        stopped_index = -1
        last_timestamp: str | None = None
        for index, line in enumerate(text.splitlines()):
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(event, dict):
                continue
            kind = str(event.get("kind", ""))
            timestamp = event.get("ts")
            if isinstance(timestamp, str):
                last_timestamp = timestamp
            if kind == "turn_started":
                active_index = index
            elif kind in TERMINAL_EVENT_KINDS:
                stopped_index = index
            detail = event.get("detail")
            compact_text = event.get("text") or event.get("reason") or ""
            if kind == "progress" and isinstance(detail, dict):
                if detail.get("kind") == "commentary":
                    stream = str(detail.get("stream_id") or f"seq:{event.get('seq', index)}")
                    entry = commentary.setdefault(
                        stream, {"text": "", "seq": 0}
                    )
                    entry["text"] += str(detail.get("text_delta", ""))
                    entry["seq"] = event.get("seq", index)
                    compact_text = detail.get("text_delta", "")
                elif detail.get("tool"):
                    compact_text = " · ".join(
                        str(value)
                        for value in (detail.get("tool"), detail.get("status"), detail.get("cmd"))
                        if value
                    )
                else:
                    compact_text = json.dumps(detail, ensure_ascii=False)[:500]
            compact = {
                "kind": kind,
                "by": event.get("by") or event.get("worker") or "system",
                "text": compact_text,
                "seq": event.get("seq"),
                "ts": timestamp,
            }
            events.append(compact)
            if kind == "message" and compact["by"] != "main" and compact["text"]:
                messages.append((int(compact["seq"] or index), str(compact["text"])))
        for entry in commentary.values():
            if entry["text"].strip():
                messages.append((int(entry["seq"] or 0), str(entry["text"])))
        messages.sort(key=lambda item: item[0])
        summary = re.sub(r"\s+", " ", messages[-1][1]).strip()[:240] if messages else ""
        return {
            "recent": [event for event in events if event["kind"] == "message"][-20:],
            "messages": "\n\n".join(message for _, message in messages),
            "summary": summary,
            "last_timestamp": last_timestamp,
            "active": active_index > stopped_index,
            "stopped": stopped_index >= active_index and stopped_index >= 0,
        }

    def _resolve_status(
        self,
        *,
        old_status: str | None,
        handoff_status: str | None,
        active: bool,
        stopped: bool,
        channel_available: bool,
        run_status: str,
    ) -> str:
        if old_status == "done" or handoff_status == "done":
            return "done"
        if active:
            return "executing"
        if stopped:
            return handoff_status or "waiting_result"
        if channel_available:
            return "waiting_worker"
        if handoff_status:
            return handoff_status
        return "sent" if run_status == "sent" else "unknown"

    def _update_search_index(self, connection: sqlite3.Connection, channel: str) -> None:
        if not self._fts_enabled:
            return
        row = connection.execute("SELECT * FROM monitor_runs WHERE channel=?", (channel,)).fetchone()
        if row is None:
            return
        metadata = " ".join(
            str(row[key] or "")
            for key in ("task_path", "channel", "display_status", "worker", "provider")
        )
        metadata = f"{metadata} {STATUS_LABELS.get(row['display_status'], '')}"
        connection.execute("DELETE FROM task_monitor_fts WHERE channel=?", (channel,))
        connection.execute(
            """
            INSERT INTO task_monitor_fts(channel, task_name, project_name, metadata, prd, handoff, messages)
            VALUES(?, ?, ?, ?, ?, ?, ?)
            """,
            (
                channel,
                row["task_name"],
                row["project_name"],
                metadata,
                row["prd_text"],
                row["handoff_text"],
                row["messages_text"],
            ),
        )

    def _auto_archive(self, connection: sqlite3.Connection, today: date) -> None:
        if self._last_archive_check == today:
            return
        now_iso = _iso(self._now())
        connection.execute(
            """
            UPDATE monitor_runs
            SET archived_at=?
            WHERE display_status='done'
              AND archived_at IS NULL
              AND archive_due_on IS NOT NULL
              AND archive_due_on <= ?
            """,
            (now_iso, today.isoformat()),
        )
        self._last_archive_check = today

    def _row_to_item(self, row: sqlite3.Row) -> dict[str, Any]:
        due = date.fromisoformat(row["archive_due_on"]) if row["archive_due_on"] else None
        days_remaining = max(0, (due - self._now().date()).days) if due and not row["archived_at"] else None
        errors = [
            value
            for value in (row["run_error"], row["task_error"], row["handoff_error"], row["channel_error"])
            if value
        ]
        return {
            "channel": row["channel"],
            "task_name": row["task_name"],
            "project_name": row["project_name"],
            "project_path": row["project_path"],
            "task_path": row["task_path"],
            "worker": row["worker"],
            "provider": row["provider"],
            "status": row["display_status"],
            "status_label": STATUS_LABELS.get(row["display_status"], row["display_status"]),
            "group": _status_group(row["display_status"], row["archived_at"]),
            "sent_at": row["sent_at"],
            "completed_at": row["completed_at"],
            "updated_at": row["updated_at"],
            "archived_at": row["archived_at"],
            "archive_due_on": row["archive_due_on"],
            "archive_days_remaining": days_remaining,
            "event_summary": row["event_summary"],
            "record_conflict": bool(row["record_conflict"]),
            "source_available": bool(row["source_available"]),
            "channel_available": bool(row["channel_available"]),
            "errors": errors,
        }

    def list_runs(self, group: str, limit: int = 20, offset: int = 0) -> dict[str, Any]:
        if group not in {"ongoing", "ended", "archived"}:
            raise TaskMonitorError("invalid_group", "group 必须是 ongoing、ended 或 archived")
        self._ensure_schema()
        limit = min(max(int(limit), 1), 10000)
        offset = max(int(offset), 0)
        with self._connection() as connection:
            rows = list(connection.execute("SELECT * FROM monitor_runs"))
        filtered = [row for row in rows if _status_group(row["display_status"], row["archived_at"]) == group]
        if group == "ongoing":
            filtered.sort(key=lambda row: (_status_priority(row["display_status"]), row["updated_at"]), reverse=False)
            # 同一状态内按更新时间倒序。
            grouped: list[sqlite3.Row] = []
            for priority in range(5):
                grouped.extend(sorted((row for row in filtered if _status_priority(row["display_status"]) == priority), key=lambda row: row["updated_at"], reverse=True))
            filtered = grouped
        else:
            filtered.sort(key=lambda row: row["updated_at"], reverse=True)
        page = filtered[offset : offset + limit]
        return {
            "items": [self._row_to_item(row) for row in page],
            "total": len(filtered),
            "next_offset": offset + limit if offset + limit < len(filtered) else None,
        }

    def get_detail(self, channel: str) -> dict[str, Any]:
        self._validate_channel(channel)
        self._ensure_schema()
        with self._connection() as connection:
            row = connection.execute("SELECT * FROM monitor_runs WHERE channel=?", (channel,)).fetchone()
        if row is None:
            raise TaskMonitorError("not_found", "任务监听记录不存在")
        result = self._row_to_item(row)
        result.update(
            {
                "source_path": row["source_path"],
                "handoff_path": row["handoff_path"],
                "recent_events": json.loads(row["recent_events_json"]),
            }
        )
        return result

    def archive(self, channel: str) -> dict[str, Any]:
        self._validate_channel(channel)
        self._ensure_schema()
        with self._connection() as connection:
            changed = connection.execute(
                "UPDATE monitor_runs SET archived_at=? WHERE channel=?",
                (_iso(self._now()), channel),
            ).rowcount
        if not changed:
            raise TaskMonitorError("not_found", "任务监听记录不存在")
        return self.get_detail(channel)

    def refollow(self, channel: str) -> dict[str, Any]:
        self._validate_channel(channel)
        self._ensure_schema()
        today = self._now().date()
        with self._connection() as connection:
            changed = connection.execute(
                """
                UPDATE monitor_runs
                SET archived_at=NULL, attention_started_on=?, archive_due_on=?
                WHERE channel=?
                """,
                (today.isoformat(), (today + timedelta(days=30)).isoformat(), channel),
            ).rowcount
        if not changed:
            raise TaskMonitorError("not_found", "任务监听记录不存在")
        return self.get_detail(channel)

    def search(self, query: str, limit: int = 20, offset: int = 0) -> dict[str, Any]:
        self._ensure_schema()
        query = query.strip()
        limit = min(max(int(limit), 1), 100)
        offset = max(int(offset), 0)
        with self._connection() as connection:
            if not query:
                rows = list(connection.execute("SELECT * FROM monitor_runs ORDER BY updated_at DESC"))
                ranked = [(row, 0.0) for row in rows]
            else:
                ranked = self._search_rows(connection, query)
        ranked.sort(key=lambda pair: pair[0]["updated_at"], reverse=True)
        if query:
            ranked.sort(
                key=lambda pair: (
                    0 if _status_group(pair[0]["display_status"], pair[0]["archived_at"]) == "ongoing" else 1,
                    pair[1],
                )
            )
        page = ranked[offset : offset + limit]
        items = []
        for row, rank in page:
            item = self._row_to_item(row)
            source, snippet = self._find_match(row, query)
            item.update({"hit_source": source, "snippet": snippet, "rank": rank})
            items.append(item)
        return {
            "items": items,
            "total": len(ranked),
            "next_offset": offset + limit if offset + limit < len(ranked) else None,
        }

    def _search_rows(self, connection: sqlite3.Connection, query: str) -> list[tuple[sqlite3.Row, float]]:
        tokens = re.findall(r"[\w\u4e00-\u9fff.-]+", query)
        if self._fts_enabled and tokens:
            expression = " AND ".join(f'"{token.replace(chr(34), chr(34) * 2)}"' for token in tokens)
            try:
                matches = list(
                    connection.execute(
                        "SELECT channel, bm25(task_monitor_fts) AS rank FROM task_monitor_fts WHERE task_monitor_fts MATCH ?",
                        (expression,),
                    )
                )
                result = []
                for match in matches:
                    row = connection.execute("SELECT * FROM monitor_runs WHERE channel=?", (match["channel"],)).fetchone()
                    if row is not None:
                        result.append((row, float(match["rank"])))
                if result:
                    return result
            except sqlite3.OperationalError:
                pass
        lowered_tokens = [token.casefold() for token in tokens] or [query.casefold()]
        result = []
        for row in connection.execute("SELECT * FROM monitor_runs"):
            haystack = "\n".join(
                str(row[key] or "")
                for key in (
                    "task_name",
                    "project_name",
                    "task_path",
                    "channel",
                    "display_status",
                    "prd_text",
                    "handoff_text",
                    "messages_text",
                )
            ).casefold() + f"\n{STATUS_LABELS.get(row['display_status'], '').casefold()}"
            positions = [haystack.find(token) for token in lowered_tokens]
            if all(position >= 0 for position in positions):
                result.append((row, float(min(positions) + 1)))
        return result

    def _find_match(self, row: sqlite3.Row, query: str) -> tuple[str, str]:
        if not query:
            return "最近更新", row["event_summary"] or row["task_path"]
        sources = [
            ("任务名", row["task_name"]),
            ("项目名", row["project_name"]),
            ("元数据", " ".join(str(row[key] or "") for key in ("task_path", "channel", "display_status")) + f" {STATUS_LABELS.get(row['display_status'], '')}"),
            ("PRD", row["prd_text"]),
            ("Handoff", row["handoff_text"]),
            ("Worker 消息", row["messages_text"]),
        ]
        tokens = [token.casefold() for token in re.findall(r"[\w\u4e00-\u9fff.-]+", query)] or [query.casefold()]
        for label, text in sources:
            lowered_text = str(text).casefold()
            positions = [(lowered_text.find(token), token) for token in tokens]
            matched = [(position, token) for position, token in positions if position >= 0]
            if matched:
                position, token = matched[0]
                start = max(0, position - 70)
                end = min(len(str(text)), position + len(token) + 110)
                snippet = re.sub(r"\s+", " ", str(text)[start:end]).strip()
                return label, snippet
        return "相关内容", row["event_summary"] or row["task_path"]

    def open_full_record(self, channel: str) -> dict[str, Any]:
        self._validate_channel(channel)
        detail = self.get_detail(channel)
        if not detail["channel_available"]:
            return {"ok": False, "message": "channel 当前不可用，无法打开完整记录。"}
        tl_path = shutil.which("tl") or shutil.which("trellis")
        if not tl_path:
            return {"ok": False, "message": "未找到 tl / trellis 命令。"}
        script = (
            "on run argv\n"
            "set projectDir to item 1 of argv\n"
            "set tlPath to item 2 of argv\n"
            "set channelName to item 3 of argv\n"
            "set commandText to \"cd \" & quoted form of projectDir & \" && \" & quoted form of tlPath & "
            "\" channel messages \" & quoted form of channelName & \" --raw --last 100\"\n"
            "tell application \"Terminal\"\n"
            "activate\n"
            "do script commandText\n"
            "end tell\n"
            "end run"
        )
        result = self._runner.run(
            ["osascript", "-e", script, detail["project_path"], tl_path, channel]
        )
        if not result.ok:
            return {
                "ok": False,
                "message": result.error or result.stderr.strip() or "终端窗口打开失败。",
            }
        return {"ok": True, "message": "已在新的终端窗口打开完整记录。"}

    def _validate_channel(self, channel: str) -> None:
        if not CHANNEL_PATTERN.fullmatch(channel):
            raise TaskMonitorError("invalid_channel", "channel 格式无效")
