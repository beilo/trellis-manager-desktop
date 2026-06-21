from __future__ import annotations

import json
import platform
import shutil
import subprocess
import sys
import webbrowser
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

import webview

from app.config import (
    ManagerConfig,
    add_project as add_project_to_config,
    get_settings as load_settings_from_config,
    load_config,
    load_operation_logs,
    remember_project,
    remove_project as remove_project_from_config,
    save_config,
    save_projects as save_projects_to_config,
    save_selected_project as save_selected_project_to_config,
    save_settings as save_settings_to_config,
)
from app.file_reader import FileReadError, SafeFileReader, TextFileResult
from app import watcher as file_watcher
from app.ops import (
    check_developer_config,
    check_helm_status,
    check_environment,
    check_tool_repo,
    check_wrapper_commands,
    dataclass_to_dict,
    ensure_wrappers_and_path,
    get_project_git_summary as get_project_git_summary_op,
    github_branch_url,
    github_branch_zip_url,
    init_project,
    inspect_project,
    install_from_zip,
    install_from_remote_zip,
    install_or_update_tool_repo,
    is_supported_macos,
    preview_project_update as preview_project_update_op,
    push_task_to_helm,
    batch_update_projects as batch_update_projects_op,
    list_outdated_projects as list_outdated_projects_op,
    setup_gitnexus_project,
    update_project,
)
from app.task_snapshot import read_all_task_snapshots, read_task_snapshot
from app.runner import CommandRunner

if TYPE_CHECKING:
    pass


class TrellisAPI:
    """pywebview JS API 桥接层：把所有业务操作暴露给前端。"""

    def __init__(
        self,
        config_file: Path | None = None,
        log_file: Path | None = None,
    ) -> None:
        self._window: webview.Window | None = None
        self._config_file = config_file
        self._log_file = log_file
        # 测试可注入临时配置文件，避免读写真实用户目录。
        self._config = load_config(config_file) if config_file else load_config()
        self._settings = load_settings_from_config(config_file) if config_file else load_settings_from_config()
        self._runner = CommandRunner()
        # 文件读取集中交给 SafeFileReader，API 层只负责桥接和轻量参数约束。
        self._file_reader = SafeFileReader()

    def set_window(self, window: webview.Window) -> None:
        self._window = window
        file_watcher.set_notification_window(window)
        file_watcher.start_project_watchers(self.get_projects())

    def shutdown(self) -> None:
        """关闭后端资源，窗口退出时停止 watcher。"""

        file_watcher.stop_project_watchers()

    def _restart_project_watchers(self) -> None:
        file_watcher.start_project_watchers(self.get_projects())

    def _resource_file(self, relative_path: str) -> Path:
        candidates: list[Path] = []
        frozen_root = getattr(sys, "_MEIPASS", None)
        if frozen_root:
            candidates.append(Path(frozen_root) / relative_path)

        app_root = Path(__file__).resolve().parents[1]
        candidates.append(app_root / relative_path)

        for candidate in candidates:
            if candidate.exists():
                return candidate
        return candidates[0]

    # ── 配置 ──

    def get_config(self) -> dict[str, Any]:
        return {
            "trellis_repo": str(self._config.trellis_repo),
            "projects": [str(p) for p in self._config.projects],
            "last_selected_project": (
                str(self._config.last_selected_project)
                if self._config.last_selected_project
                else None
            ),
            "recent_projects": [str(p) for p in self._config.recent_projects],
            "official_repo_url": self._settings["official_repo_url"],
            "accelerated_repo_url": self._settings["accelerated_repo_url"],
            "distribution_branch": self._settings["distribution_branch"],
        }

    def get_settings(self) -> dict[str, str]:
        return dict(self._settings)

    def save_settings(self, settings: dict[str, object]) -> None:
        # 设置页只改仓库源和分支，保存后同步内存缓存，避免后续操作仍读旧值。
        self._config = save_settings_to_config(settings, self._config_file) if self._config_file else save_settings_to_config(settings)
        self._settings = load_settings_from_config(self._config_file) if self._config_file else load_settings_from_config()

    def save_repo_path(self, path: str) -> None:
        repo = Path(path).expanduser()
        self._config = ManagerConfig(
            trellis_repo=repo,
            projects=self._config.projects,
            last_selected_project=self._config.last_selected_project,
            recent_projects=self._config.recent_projects,
            official_repo_url=self._settings["official_repo_url"],
            accelerated_repo_url=self._settings["accelerated_repo_url"],
            distribution_branch=self._settings["distribution_branch"],
            developer_name=self._config.developer_name,
            init_platforms=self._config.init_platforms,
        )
        if self._config_file:
            save_config(self._config, self._config_file)
        else:
            save_config(self._config)

    def get_projects(self) -> list[str]:
        return [str(p) for p in self._config.projects]

    def save_projects(self, projects: list[str], last_selected_project: str | None = None) -> None:
        paths = [Path(path).expanduser() for path in projects]
        selected = Path(last_selected_project).expanduser() if last_selected_project else None
        self._config = (
            save_projects_to_config(paths, self._config_file, selected)
            if self._config_file
            else save_projects_to_config(paths, last_selected_project=selected)
        )
        self._restart_project_watchers()

    def add_project(self, path: str) -> dict[str, Any]:
        status = inspect_project(path, self._runner, self._config.trellis_repo)
        if status.path is None:
            return dataclass_to_dict(status)
        self._config = (
            add_project_to_config(status.path, self._config_file)
            if self._config_file
            else add_project_to_config(status.path)
        )
        self._restart_project_watchers()
        return dataclass_to_dict(status)

    def remove_project(self, path: str) -> None:
        self._config = (
            remove_project_from_config(Path(path).expanduser(), self._config_file)
            if self._config_file
            else remove_project_from_config(Path(path).expanduser())
        )
        self._restart_project_watchers()

    def save_selected_project(self, path: str | None) -> None:
        selected = Path(path).expanduser() if path else None
        self._config = (
            save_selected_project_to_config(selected, self._config_file)
            if self._config_file
            else save_selected_project_to_config(selected)
        )

    def get_recent_projects(self) -> list[str]:
        return [str(p) for p in self._config.recent_projects]

    def remember_project(self, path: str) -> None:
        updated = (
            remember_project(Path(path).expanduser(), self._config_file)
            if self._config_file
            else remember_project(Path(path).expanduser())
        )
        self._config = updated

    # ── 平台信息 ──

    def get_platform_info(self) -> dict[str, Any]:
        return {
            "is_macos": is_supported_macos(),
            "python_version": platform.python_version(),
        }

    # ── 检查操作 ──

    def check_environment(self) -> list[dict[str, Any]]:
        items = check_environment(self._runner)
        # 开发者配置检查项追加到系统依赖列表末尾。
        items.append(check_developer_config(self._config.developer_name, self._config.init_platforms))
        return [dataclass_to_dict(item) for item in items]

    def check_tool_repo(self, path: str) -> dict[str, Any]:
        status = check_tool_repo(
            Path(path).expanduser(),
            self._runner,
            self._settings["distribution_branch"],
        )
        return dataclass_to_dict(status)

    def check_wrapper_commands(self) -> list[dict[str, Any]]:
        items = check_wrapper_commands(runner=self._runner)
        result = []
        for item in items:
            d = dataclass_to_dict(item)
            # commands 列表内的 CommandResult 需要单独序列化
            d["commands"] = [c.to_dict() for c in item.commands]
            result.append(d)
        return result

    def check_helm_status(self) -> dict[str, Any]:
        """返回 Helm CLI 可用性，供任务详情按钮决定禁用原因。"""
        status = check_helm_status(self._runner)
        return dataclass_to_dict(status)

    def check_cursor_status(self) -> dict[str, Any]:
        """返回 Cursor 可用性，供前端决定按钮禁用原因。"""
        common_locations = [
            Path("/Applications/Cursor.app"),
            Path.home() / "Applications" / "Cursor.app",
        ]
        if any(path.exists() for path in common_locations):
            return {
                "name": "cursor",
                "ok": True,
                "status": "ok",
                "message": "Cursor 已安装。",
                "version": None,
            }

        queries = [
            'kMDItemCFBundleIdentifier == "com.todesktop.230313mzl4w4u92"',
            'kMDItemDisplayName == "Cursor.app"',
        ]
        for query in queries:
            try:
                result = subprocess.run(
                    ["mdfind", query],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=5,
                    shell=False,
                    check=False,
                )
            except (OSError, subprocess.TimeoutExpired):
                continue
            if result.returncode == 0 and result.stdout.strip():
                return {
                    "name": "cursor",
                    "ok": True,
                    "status": "ok",
                    "message": "Cursor 已安装。",
                    "version": None,
                }

        return {
            "name": "cursor",
            "ok": False,
            "status": "error",
            "message": "未检测到 Cursor，请先安装 Cursor。",
            "version": None,
        }

    # ── 安装/构建操作 ──

    def install_or_update_tool_repo(self, path: str) -> dict[str, Any]:
        report = install_or_update_tool_repo(
            Path(path).expanduser(),
            self._runner,
            self._settings["official_repo_url"],
            self._settings["accelerated_repo_url"],
            self._settings["distribution_branch"],
        )
        return report.to_log_entry()

    def install_from_zip(self, zip_path: str, repo_path: str, replace: bool = False) -> dict[str, Any]:
        """从本地 zip 安装或重装 Trellis 工具源码。"""
        report = install_from_zip(
            Path(zip_path).expanduser(),
            Path(repo_path).expanduser(),
            replace=replace,
            distribution_branch=self._settings["distribution_branch"],
            runner=self._runner,
        )
        return report.to_log_entry()

    def get_github_branch_url(self) -> str | None:
        """返回当前配置对应的 GitHub 分支页面链接。"""
        return github_branch_url(
            self._settings["official_repo_url"],
            self._settings["distribution_branch"],
        )

    def get_github_branch_zip_url(self) -> str | None:
        """返回当前配置对应的 GitHub codeload zip 下载地址。"""
        return github_branch_zip_url(
            self._settings["official_repo_url"],
            self._settings["distribution_branch"],
        )

    def install_from_remote_zip(self, repo_path: str, replace: bool = False) -> dict[str, Any]:
        """从远端 GitHub 下载源码 zip 并安装/重装 Trellis 工具仓库。"""
        report = install_from_remote_zip(
            Path(repo_path).expanduser(),
            replace=replace,
            official_repo_url=self._settings["official_repo_url"],
            distribution_branch=self._settings["distribution_branch"],
            runner=self._runner,
        )
        return report.to_log_entry()

    def ensure_wrappers_and_path(self, path: str) -> dict[str, Any]:
        report = ensure_wrappers_and_path(repo_dir=Path(path).expanduser())
        return report.to_log_entry()

    # ── 业务项目操作 ──

    def inspect_project(self, path: str) -> dict[str, Any]:
        status = inspect_project(path, self._runner, self._config.trellis_repo)
        return dataclass_to_dict(status)

    def init_project(self, path: str) -> dict[str, Any]:
        report = init_project(
            Path(path).expanduser(),
            self._config.init_platforms,
            self._config.developer_name,
            self._runner,
        )
        return report.to_log_entry()

    def update_project(self, path: str, allow_dirty: bool = False, migrate: bool = False) -> dict[str, Any]:
        report = update_project(
            Path(path).expanduser(),
            allow_dirty=allow_dirty,
            migrate=migrate,
            runner=self._runner,
            tool_repo_dir=self._config.trellis_repo,
        )
        return report.to_log_entry()

    def setup_gitnexus_project(self, path: str) -> dict[str, Any]:
        report = setup_gitnexus_project(Path(path).expanduser(), self._runner)
        return report.to_log_entry()

    def list_outdated_projects(self) -> list[dict[str, Any]]:
        statuses = list_outdated_projects_op(self._config.projects, self._runner, self._config.trellis_repo)
        return [dataclass_to_dict(status) for status in statuses]

    def batch_update_projects(self, paths: list[str] | None, allow_dirty: bool = False) -> dict[str, Any]:
        report = batch_update_projects_op(
            paths,
            self._config.projects,
            allow_dirty=allow_dirty,
            runner=self._runner,
            tool_repo_dir=self._config.trellis_repo,
            log_file=self._log_file,
        )
        return dataclass_to_dict(report)

    def get_project_git_summary(self, path: str) -> dict[str, Any]:
        """返回业务项目 Git 摘要，供下一版 Git 快捷面板消费。"""
        summary = get_project_git_summary_op(Path(path).expanduser(), self._runner)
        return dataclass_to_dict(summary)

    def preview_project_update(self, path: str) -> dict[str, Any]:
        """执行 update dry-run 预览，不改变现有真实 update 行为。"""
        preview = preview_project_update_op(
            Path(path).expanduser(),
            runner=self._runner,
            tool_repo_dir=self._config.trellis_repo,
        )
        return dataclass_to_dict(preview)

    # ── 日志 ──

    def get_logs(self) -> list[dict[str, Any]]:
        return load_operation_logs(self._log_file) if self._log_file else load_operation_logs()

    def get_all_logs(self) -> list[dict[str, Any]]:
        # 返回完整持久化日志，不截断，供前端"复制全部日志"使用。
        return load_operation_logs(self._log_file) if self._log_file else load_operation_logs()

    # ── 文件对话框 / 系统操作 ──

    def select_directory(self) -> str | None:
        if self._window is None:
            return None
        result = self._window.create_file_dialog(
            webview.FOLDER_DIALOG,
            directory=str(Path.home()),
        )
        if result and len(result) > 0:
            return str(result[0])
        return None

    def select_file(self, file_types: tuple[str, str] | None = None) -> str | None:
        """打开文件选择对话框，默认过滤 zip 文件。"""
        if self._window is None:
            return None
        filters = (file_types,) if file_types else (("Zip files", ".zip"),)
        result = self._window.create_file_dialog(
            webview.OPEN_DIALOG,
            directory=str(Path.home()),
            allow_multiple=False,
            file_types=filters,
        )
        if result and len(result) > 0:
            return str(result[0])
        return None

    def open_directory(self, path: str) -> None:
        expanded = str(Path(path).expanduser())
        subprocess.Popen(["open", expanded])  # noqa: S603,S607 - macOS only, safe path

    def get_help_url(self) -> str:
        """返回本地使用说明 HTML 的 file URL。"""
        help_path = self._resource_file("resources/help.html")
        if not help_path.exists():
            raise RuntimeError(f"未找到使用说明文件：{help_path}")
        return help_path.resolve().as_uri()

    def open_in_browser(self, url: str) -> None:
        """用系统默认浏览器打开受支持的 URL。"""
        parsed = urlparse(url)
        scheme = parsed.scheme.lower()
        if scheme not in {"file", "http", "https"}:
            raise RuntimeError(f"不支持打开此类链接：{scheme or '空协议'}")
        if not webbrowser.open(url, new=2):
            raise RuntimeError("系统浏览器打开失败。")

    def open_in_iterm(self, project_path: str) -> None:
        """在 iTerm2 中打开业务项目根目录。"""
        expanded = str(Path(project_path).expanduser())
        subprocess.Popen(["open", "-a", "iTerm", expanded])  # noqa: S603,S607 - macOS only, safe path

    def open_in_cursor(self, path: str) -> None:
        """在 Cursor 中打开业务项目根目录，优先使用 CLI，参数数组避免 shell 注入。"""
        expanded = str(Path(path).expanduser())
        cursor_cli = shutil.which("cursor")
        if cursor_cli:
            subprocess.Popen([cursor_cli, expanded])  # noqa: S603 - CLI 路径来自 PATH 查询结果
            return
        status = self.check_cursor_status()
        if not status["ok"]:
            raise RuntimeError(status["message"])
        subprocess.Popen(["open", "-a", "Cursor", expanded])  # noqa: S603,S607 - macOS only, safe path

    # ── 任务管理 ──

    def list_project_tasks(self, path: str, include_archive: bool = False) -> dict[str, Any]:
        """读取业务项目的 Trellis 任务快照。"""
        snapshot = read_task_snapshot(path, include_archive)
        # 统一复用桥接层已有序列化逻辑，避免 API 层漏导入 dataclasses.asdict。
        return dataclass_to_dict(snapshot)

    def list_all_tasks(self) -> dict[str, Any]:
        """聚合所有已配置项目的 active 任务快照。"""
        project_paths = [str(path) for path in self._config.projects]
        snapshot = read_all_task_snapshots(project_paths)
        # 看板只消费配置内项目，避免 API 层隐式扫描磁盘扩大范围。
        return dataclass_to_dict(snapshot)

    def open_task_directory(self, task_path: str) -> None:
        """打开指定任务目录（Finder）。"""
        expanded = str(Path(task_path).expanduser())
        subprocess.Popen(["open", expanded])  # noqa: S603,S607

    def list_project_files(self, project_path: str, subroot: str) -> dict[str, Any]:
        """列出项目 `.trellis/` 下受限子目录的文件树。"""
        result = self._file_reader.list_tree(project_path, subroot)
        return self._file_reader.to_dict(result)

    def read_project_file(self, project_path: str, relative_path: str) -> dict[str, Any]:
        """读取项目 `.trellis/` 下的 UTF-8 文本文件。"""
        result = self._file_reader.read_text(project_path, relative_path)
        return self._file_reader.to_dict(result)

    def read_project_jsonl(
        self,
        project_path: str,
        relative_path: str,
        limit: int = 200,
        offset: int = 0,
    ) -> dict[str, Any]:
        """分页读取项目 `.trellis/` 下的 JSONL 文件。"""
        result = self._file_reader.read_jsonl(project_path, relative_path, limit=limit, offset=offset)
        return self._file_reader.to_dict(result)

    def list_task_context_files(self, task_path: str) -> dict[str, Any]:
        """列出任务目录中可预览的 context 文件。"""
        relative, project = self._file_reader.task_directory_relative_path(task_path)
        return self.list_project_files(str(project), relative)

    def read_task_context_file(
        self,
        task_path: str,
        filename: str,
        limit: int = 200,
        offset: int = 0,
    ) -> dict[str, Any]:
        """读取任务目录中的上下文文件，JSONL 走分页解析。"""
        relative, project = self._file_reader.task_relative_path(task_path, filename)
        if relative.endswith(".jsonl"):
            result = self._file_reader.read_jsonl(str(project), relative, limit=limit, offset=offset)
        else:
            result = self._file_reader.read_text(str(project), relative)
        return self._file_reader.to_dict(result)

    def read_task_document(self, task_path: str, doc: str) -> dict[str, Any]:
        """读取任务文档，仅允许 prd、design、implement。"""
        if doc not in {"prd", "design", "implement"}:
            error = FileReadError("invalid_document", "文档类型必须是 prd、design 或 implement。")
            return self._file_reader.to_dict(
                TextFileResult(ok=False, path=None, content=None, size=None, truncated=False, error=error)
            )
        relative, project = self._file_reader.task_relative_path(task_path, f"{doc}.md")
        result = self._file_reader.read_text(str(project), relative)
        return self._file_reader.to_dict(result)

    def push_task_to_helm(self, project_path: str, task_path: str) -> dict[str, Any]:
        """将指定 Trellis 任务推送为 Helm issue。"""
        report = push_task_to_helm(
            Path(project_path).expanduser(),
            Path(task_path).expanduser(),
            self._runner,
        )
        return report.to_log_entry()
