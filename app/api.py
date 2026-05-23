from __future__ import annotations

import json
import platform
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any

import webview

from app.config import (
    ManagerConfig,
    add_project as add_project_to_config,
    load_config,
    load_operation_logs,
    remember_project,
    remove_project as remove_project_from_config,
    save_config,
    save_projects as save_projects_to_config,
    save_selected_project as save_selected_project_to_config,
)
from app.ops import (
    check_helm_status,
    check_environment,
    check_tool_repo,
    check_wrapper_commands,
    dataclass_to_dict,
    ensure_wrappers_and_path,
    init_project,
    inspect_project,
    install_or_update_tool_repo,
    is_supported_macos,
    push_task_to_helm,
    update_project,
)
from app.task_snapshot import read_task_snapshot
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
        self._runner = CommandRunner()

    def set_window(self, window: webview.Window) -> None:
        self._window = window

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
        }

    def save_repo_path(self, path: str) -> None:
        repo = Path(path).expanduser()
        self._config = ManagerConfig(
            trellis_repo=repo,
            projects=self._config.projects,
            last_selected_project=self._config.last_selected_project,
            recent_projects=self._config.recent_projects,
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

    def add_project(self, path: str) -> dict[str, Any]:
        status = inspect_project(path, self._runner, self._config.trellis_repo)
        if status.path is None:
            return dataclass_to_dict(status)
        self._config = (
            add_project_to_config(status.path, self._config_file)
            if self._config_file
            else add_project_to_config(status.path)
        )
        return dataclass_to_dict(status)

    def remove_project(self, path: str) -> None:
        self._config = (
            remove_project_from_config(Path(path).expanduser(), self._config_file)
            if self._config_file
            else remove_project_from_config(Path(path).expanduser())
        )

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
        return [dataclass_to_dict(item) for item in items]

    def check_tool_repo(self, path: str) -> dict[str, Any]:
        status = check_tool_repo(Path(path).expanduser(), self._runner)
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

    # ── 安装/构建操作 ──

    def install_or_update_tool_repo(self, path: str) -> dict[str, Any]:
        report = install_or_update_tool_repo(Path(path).expanduser(), self._runner)
        return report.to_log_entry()

    def ensure_wrappers_and_path(self, path: str) -> dict[str, Any]:
        report = ensure_wrappers_and_path(repo_dir=Path(path).expanduser())
        return report.to_log_entry()

    # ── 业务项目操作 ──

    def inspect_project(self, path: str) -> dict[str, Any]:
        status = inspect_project(path, self._runner, self._config.trellis_repo)
        return dataclass_to_dict(status)

    def init_project(self, path: str) -> dict[str, Any]:
        report = init_project(Path(path).expanduser(), self._runner)
        return report.to_log_entry()

    def update_project(self, path: str, allow_dirty: bool = False) -> dict[str, Any]:
        report = update_project(
            Path(path).expanduser(),
            allow_dirty=allow_dirty,
            runner=self._runner,
        )
        return report.to_log_entry()

    # ── 日志 ──

    def get_logs(self) -> list[dict[str, Any]]:
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

    def open_directory(self, path: str) -> None:
        expanded = str(Path(path).expanduser())
        subprocess.Popen(["open", expanded])  # noqa: S603,S607 - macOS only, safe path

    def open_in_iterm(self, project_path: str) -> None:
        """在 iTerm2 中打开业务项目根目录。"""
        expanded = str(Path(project_path).expanduser())
        subprocess.Popen(["open", "-a", "iTerm", expanded])  # noqa: S603,S607 - macOS only, safe path

    # ── 任务管理 ──

    def list_project_tasks(self, path: str, include_archive: bool = False) -> dict[str, Any]:
        """读取业务项目的 Trellis 任务快照。"""
        snapshot = read_task_snapshot(path, include_archive)
        # 统一复用桥接层已有序列化逻辑，避免 API 层漏导入 dataclasses.asdict。
        return dataclass_to_dict(snapshot)

    def open_task_directory(self, task_path: str) -> None:
        """打开指定任务目录（Finder）。"""
        expanded = str(Path(task_path).expanduser())
        subprocess.Popen(["open", expanded])  # noqa: S603,S607

    def push_task_to_helm(self, project_path: str, task_path: str) -> dict[str, Any]:
        """将指定 Trellis 任务推送为 Helm issue。"""
        report = push_task_to_helm(
            Path(project_path).expanduser(),
            Path(task_path).expanduser(),
            self._runner,
        )
        return report.to_log_entry()
