from __future__ import annotations

import json
import platform
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, Any

import webview

from app.config import (
    ManagerConfig,
    load_config,
    load_operation_logs,
    remember_project,
    save_config,
)
from app.ops import (
    check_environment,
    check_tool_repo,
    check_wrapper_commands,
    dataclass_to_dict,
    ensure_wrappers_and_path,
    init_project,
    inspect_project,
    install_or_update_tool_repo,
    is_supported_macos,
    update_project,
)
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
            "recent_projects": [str(p) for p in self._config.recent_projects],
        }

    def save_repo_path(self, path: str) -> None:
        repo = Path(path).expanduser()
        self._config = ManagerConfig(
            trellis_repo=repo,
            recent_projects=self._config.recent_projects,
        )
        if self._config_file:
            save_config(self._config, self._config_file)
        else:
            save_config(self._config)

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

    # ── 安装/构建操作 ──

    def install_or_update_tool_repo(self, path: str) -> dict[str, Any]:
        report = install_or_update_tool_repo(Path(path).expanduser(), self._runner)
        return report.to_log_entry()

    def ensure_wrappers_and_path(self, path: str) -> dict[str, Any]:
        report = ensure_wrappers_and_path(repo_dir=Path(path).expanduser())
        return report.to_log_entry()

    # ── 业务项目操作 ──

    def inspect_project(self, path: str) -> dict[str, Any]:
        status = inspect_project(path, self._runner)
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
