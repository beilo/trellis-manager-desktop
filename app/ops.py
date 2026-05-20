from __future__ import annotations

import json
import platform
import shutil
import stat
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal

from app.config import (
    ACCELERATED_REPO_URL,
    DEFAULT_BIN_DIR,
    DEFAULT_REPO_DIR,
    DISTRIBUTION_BRANCH,
    OFFICIAL_REPO_URL,
    PATH_EXPORT_LINE,
)
from app.runner import CommandResult, CommandRunner

Status = Literal["ok", "warning", "error", "unknown"]


@dataclass(frozen=True)
class EnvironmentItem:
    name: str
    ok: bool
    status: Status
    message: str
    version: str | None = None


@dataclass(frozen=True)
class RepoStatus:
    path: Path
    exists: bool
    is_git: bool
    is_trellis_repo: bool
    dirty: bool
    branch: str | None
    origin: str | None
    version: str | None
    ahead: int | None
    behind: int | None
    status: Status
    message: str


@dataclass(frozen=True)
class ProjectStatus:
    path: Path | None
    exists: bool
    is_git: bool
    has_trellis: bool
    dirty: bool
    status: Status
    message: str


@dataclass(frozen=True)
class ToolCommandStatus:
    name: str
    path: Path
    exists: bool
    executable: bool
    version_ok: bool
    help_ok: bool
    status: Status
    message: str
    commands: list[CommandResult] = field(default_factory=list)


@dataclass(frozen=True)
class OperationReport:
    title: str
    ok: bool
    message: str
    commands: list[CommandResult] = field(default_factory=list)
    details: dict[str, str] = field(default_factory=dict)

    def to_log_entry(self) -> dict[str, object]:
        return {
            "title": self.title,
            "ok": self.ok,
            "message": self.message,
            "details": self.details,
            "commands": [command.to_dict() for command in self.commands],
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }


class OperationError(RuntimeError):
    def __init__(self, message: str, commands: list[CommandResult] | None = None) -> None:
        super().__init__(message)
        self.commands = commands or []


def is_supported_macos() -> bool:
    return platform.system() == "Darwin"


def expand_path(value: str | Path) -> Path:
    return Path(value).expanduser().resolve()


def accelerated_clone_url() -> str:
    return ACCELERATED_REPO_URL


def wrapper_path(name: str, bin_dir: Path = DEFAULT_BIN_DIR) -> Path:
    if name not in {"tl", "trellis"}:
        raise ValueError("wrapper 名称只能是 tl 或 trellis。")
    return bin_dir / name


def cli_entry_path(repo_dir: Path = DEFAULT_REPO_DIR) -> Path:
    return repo_dir / "packages" / "cli" / "bin" / "trellis.js"


def project_init_command(bin_dir: Path = DEFAULT_BIN_DIR) -> list[str]:
    return [str(wrapper_path("tl", bin_dir)), "init", "-y"]


def project_update_command(bin_dir: Path = DEFAULT_BIN_DIR) -> list[str]:
    return [str(wrapper_path("tl", bin_dir)), "update", "--force"]


def install_instruction(name: str) -> str:
    instructions = {
        "git": "请先安装 Xcode Command Line Tools 或 Homebrew git。",
        "node": "请安装 Node.js 18.17+，建议使用 nvm 或 Homebrew。",
        "pnpm": "请安装 pnpm，例如执行 npm install -g pnpm。",
    }
    return instructions.get(name, "请先安装缺失命令。")


def check_environment(runner: CommandRunner | None = None) -> list[EnvironmentItem]:
    runner = runner or CommandRunner()
    items: list[EnvironmentItem] = []
    for name in ["git", "node", "pnpm"]:
        result = runner.run([name, "--version"], timeout=10)
        output = (result.stdout or result.stderr).strip().splitlines()
        if result.ok:
            items.append(
                EnvironmentItem(
                    name=name,
                    ok=True,
                    status="ok",
                    version=output[0] if output else None,
                    message="已安装。",
                ),
            )
        else:
            items.append(
                EnvironmentItem(
                    name=name,
                    ok=False,
                    status="error",
                    message=install_instruction(name),
                ),
            )
    return items


def is_git_repo(path: Path, runner: CommandRunner | None = None) -> bool:
    runner = runner or CommandRunner()
    if not path.exists() or not path.is_dir():
        return False
    result = runner.run(["git", "rev-parse", "--is-inside-work-tree"], cwd=path, timeout=10)
    return result.ok and result.stdout.strip() == "true"


def git_status_short(path: Path, runner: CommandRunner | None = None) -> tuple[bool, str, CommandResult]:
    runner = runner or CommandRunner()
    result = runner.run(["git", "status", "--short"], cwd=path, timeout=20)
    output = result.stdout.strip()
    return bool(output), output, result


def read_cli_version(repo_dir: Path) -> str | None:
    package_file = repo_dir / "packages" / "cli" / "package.json"
    if not package_file.exists():
        return None
    try:
        data = json.loads(package_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    version = data.get("version") if isinstance(data, dict) else None
    return version if isinstance(version, str) else None


def is_trellis_repo(repo_dir: Path) -> bool:
    return cli_entry_path(repo_dir).exists() and (repo_dir / "packages" / "cli" / "package.json").exists()


def check_tool_repo(repo_dir: Path = DEFAULT_REPO_DIR, runner: CommandRunner | None = None) -> RepoStatus:
    runner = runner or CommandRunner()
    repo_dir = repo_dir.expanduser()
    if not repo_dir.exists():
        return RepoStatus(
            path=repo_dir,
            exists=False,
            is_git=False,
            is_trellis_repo=False,
            dirty=False,
            branch=None,
            origin=None,
            version=None,
            ahead=None,
            behind=None,
            status="unknown",
            message="尚未下载 Trellis 工具仓库。",
        )
    git_ok = is_git_repo(repo_dir, runner)
    if not git_ok:
        return RepoStatus(
            path=repo_dir,
            exists=True,
            is_git=False,
            is_trellis_repo=False,
            dirty=False,
            branch=None,
            origin=None,
            version=None,
            ahead=None,
            behind=None,
            status="error",
            message="安装目录存在但不是 git 仓库。",
        )
    dirty, _, _ = git_status_short(repo_dir, runner)
    branch = _successful_output(runner.run(["git", "branch", "--show-current"], cwd=repo_dir, timeout=10))
    origin = _successful_output(runner.run(["git", "remote", "get-url", "origin"], cwd=repo_dir, timeout=10))
    valid = is_trellis_repo(repo_dir)
    version = read_cli_version(repo_dir)
    ahead: int | None = None
    behind: int | None = None
    if dirty:
        status: Status = "info"
        message = "工具仓库有本地变更（如 lock 文件），更新时会自动暂存并恢复。"
    elif valid:
        fetch = runner.run(["git", "fetch", "origin", DISTRIBUTION_BRANCH], cwd=repo_dir, timeout=120)
        if fetch.ok:
            ahead, behind = _read_ahead_behind(repo_dir, runner)
            if branch != DISTRIBUTION_BRANCH:
                status = "warning"
                message = f"当前分支不是团队分发分支，点击更新会切到 {DISTRIBUTION_BRANCH}。"
            elif behind and behind > 0:
                status = "warning"
                message = f"远端有 {behind} 个新提交，可以更新。"
            elif ahead and ahead > 0:
                status = "warning"
                message = f"本地领先远端 {ahead} 个提交，更新前建议维护者确认。"
            else:
                status = "ok"
                message = "工具仓库已是最新。"
        else:
            status = "warning"
            message = "工具仓库可用，但检查远端更新失败。"
    else:
        status = "error"
        message = "目录不是有效的 Trellis 工具仓库。"
    return RepoStatus(
        path=repo_dir,
        exists=True,
        is_git=True,
        is_trellis_repo=valid,
        dirty=dirty,
        branch=branch,
        origin=origin,
        version=version,
        ahead=ahead,
        behind=behind,
        status=status,
        message=message,
    )


def install_or_update_tool_repo(
    repo_dir: Path = DEFAULT_REPO_DIR,
    runner: CommandRunner | None = None,
) -> OperationReport:
    runner = runner or CommandRunner()
    repo_dir = repo_dir.expanduser()
    commands: list[CommandResult] = []
    repo_dir.parent.mkdir(parents=True, exist_ok=True)
    if not repo_dir.exists():
        clone = runner.run(
            ["git", "clone", "--branch", DISTRIBUTION_BRANCH, accelerated_clone_url(), str(repo_dir)],
            timeout=600,
        )
        commands.append(clone)
        if not clone.ok:
            fallback = runner.run(
                ["git", "clone", "--branch", DISTRIBUTION_BRANCH, OFFICIAL_REPO_URL, str(repo_dir)],
                timeout=600,
            )
            commands.append(fallback)
            _raise_if_failed(fallback, "下载 Trellis 工具仓库失败。", commands)
        origin = runner.run(["git", "remote", "set-url", "origin", OFFICIAL_REPO_URL], cwd=repo_dir, timeout=30)
        commands.append(origin)
        _raise_if_failed(origin, "设置官方 origin 失败。", commands)
    else:
        status = check_tool_repo(repo_dir, runner)
        if not status.is_git or not status.is_trellis_repo:
            raise OperationError(status.message, commands)
        # 使用 --autostash 自动暂存本地变更（如 lock 文件），更新后恢复
        pull = runner.run(
            ["git", "pull", "--autostash", "--ff-only", "origin", DISTRIBUTION_BRANCH],
            cwd=repo_dir,
            timeout=120,
        )
        commands.append(pull)
        _raise_if_failed(pull, "更新工具仓库失败。", commands)
    for command, message, timeout in [
        (["pnpm", "install"], "安装依赖失败。", 600),
        (["pnpm", "--filter", "@mindfoldhq/trellis", "build"], "构建 Trellis CLI 失败。", 600),
    ]:
        result = runner.run(command, cwd=repo_dir, timeout=timeout)
        commands.append(result)
        _raise_if_failed(result, message, commands)
    return OperationReport(
        title="安装或更新 Trellis 工具仓库",
        ok=True,
        message="工具仓库已准备完成。",
        commands=commands,
        details={"repo": str(repo_dir), "branch": DISTRIBUTION_BRANCH},
    )


def ensure_wrappers_and_path(
    repo_dir: Path = DEFAULT_REPO_DIR,
    bin_dir: Path = DEFAULT_BIN_DIR,
    home_dir: Path | None = None,
) -> OperationReport:
    home_dir = home_dir or Path.home()
    repo_dir = repo_dir.expanduser()
    bin_dir = bin_dir.expanduser()
    entry = cli_entry_path(repo_dir)
    if not entry.exists():
        raise OperationError("Trellis CLI 入口不存在，请先安装并构建工具仓库。")
    bin_dir.mkdir(parents=True, exist_ok=True)
    for name in ["tl", "trellis"]:
        target = wrapper_path(name, bin_dir)
        # wrapper 固定调用工具仓库里的 CLI 入口，避免 npm link 改写全局环境。
        target.write_text(
            "#!/bin/sh\n"
            f'exec node "{entry}" "$@"\n',
            encoding="utf-8",
        )
        target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    path_message = ensure_zshrc_path(home_dir, bin_dir)
    return OperationReport(
        title="创建本机命令入口",
        ok=True,
        message="tl 和 trellis wrapper 已创建。",
        details={"bin": str(bin_dir), "path": path_message},
    )


def ensure_zshrc_path(home_dir: Path, bin_dir: Path = DEFAULT_BIN_DIR) -> str:
    zshrc = home_dir.expanduser() / ".zshrc"
    backup_message = "未备份，文件不存在。"
    existing = zshrc.read_text(encoding="utf-8") if zshrc.exists() else ""
    if PATH_EXPORT_LINE in existing:
        return "PATH 已存在，无需重复写入。"
    if zshrc.exists():
        backup = zshrc.with_name(f".zshrc.trellis-manager-backup-{datetime.now().strftime('%Y%m%d%H%M%S')}")
        shutil.copy2(zshrc, backup)
        backup_message = f"已备份到 {backup}"
    block = (
        "\n# Trellis Manager：将本机 Trellis wrapper 加入 PATH\n"
        f"{PATH_EXPORT_LINE}\n"
    )
    zshrc.write_text(existing.rstrip() + block, encoding="utf-8")
    return f"已写入 {zshrc}；{backup_message}"


def check_wrapper_commands(
    bin_dir: Path = DEFAULT_BIN_DIR,
    runner: CommandRunner | None = None,
) -> list[ToolCommandStatus]:
    runner = runner or CommandRunner()
    statuses: list[ToolCommandStatus] = []
    for name in ["tl", "trellis"]:
        path = wrapper_path(name, bin_dir)
        exists = path.exists()
        executable = exists and path.stat().st_mode & stat.S_IXUSR > 0
        commands: list[CommandResult] = []
        version_ok = False
        help_ok = False
        if executable:
            version = runner.run([path, "--version"], timeout=20)
            help_result = runner.run([path, "--help"], timeout=20)
            commands.extend([version, help_result])
            version_ok = version.ok
            help_ok = help_result.ok
        ok = exists and executable and version_ok and help_ok
        statuses.append(
            ToolCommandStatus(
                name=name,
                path=path,
                exists=exists,
                executable=executable,
                version_ok=version_ok,
                help_ok=help_ok,
                status="ok" if ok else "error",
                message="命令可用。" if ok else "命令不可用，请先创建 wrapper 或检查构建结果。",
                commands=commands,
            ),
        )
    return statuses


def inspect_project(path_text: str, runner: CommandRunner | None = None) -> ProjectStatus:
    runner = runner or CommandRunner()
    if not path_text.strip():
        return ProjectStatus(None, False, False, False, False, "unknown", "请先选择业务项目目录。")
    path = expand_path(path_text)
    if not path.exists() or not path.is_dir():
        return ProjectStatus(path, False, False, False, False, "error", "业务项目目录不存在。")
    git_ok = is_git_repo(path, runner)
    dirty = False
    if git_ok:
        dirty, _, _ = git_status_short(path, runner)
    has_trellis = (path / ".trellis").exists()
    if not git_ok:
        status: Status = "error"
        message = "目标项目不是 git 仓库，不能 init 或 update。"
    elif has_trellis:
        status = "warning" if dirty else "ok"
        message = "项目已安装 Trellis，可执行 update。"
    else:
        status = "warning" if dirty else "ok"
        message = "项目可执行 Trellis init。"
    return ProjectStatus(path, True, git_ok, has_trellis, dirty, status, message)


def init_project(
    project_dir: Path,
    runner: CommandRunner | None = None,
    bin_dir: Path = DEFAULT_BIN_DIR,
) -> OperationReport:
    runner = runner or CommandRunner()
    status = inspect_project(str(project_dir), runner)
    if not status.is_git:
        raise OperationError("目标项目必须是 git 仓库。")
    if status.has_trellis:
        raise OperationError("目标项目已经存在 .trellis，请使用 update。")
    commands: list[CommandResult] = []
    init_result = runner.run(project_init_command(bin_dir), cwd=status.path, timeout=300)
    commands.append(init_result)
    _raise_if_failed(init_result, "项目 init 失败。", commands)
    # init 遇到已有 AGENTS.md 会保留旧文件，随后强制 update 让团队模板覆盖到位。
    update_result = runner.run(project_update_command(bin_dir), cwd=status.path, timeout=300)
    commands.append(update_result)
    _raise_if_failed(update_result, "项目 force update 失败。", commands)
    return OperationReport(
        title="初始化业务项目",
        ok=True,
        message="业务项目已完成 Trellis init，并已执行 force update。",
        commands=commands,
        details={"project": str(status.path)},
    )


def update_project(
    project_dir: Path,
    allow_dirty: bool = False,
    runner: CommandRunner | None = None,
    bin_dir: Path = DEFAULT_BIN_DIR,
) -> OperationReport:
    runner = runner or CommandRunner()
    status = inspect_project(str(project_dir), runner)
    if not status.is_git:
        raise OperationError("目标项目必须是 git 仓库。")
    if not status.has_trellis:
        raise OperationError("目标项目尚未安装 Trellis，请先 init。")
    commands: list[CommandResult] = []
    dirty, dirty_output, dirty_result = git_status_short(status.path, runner)
    commands.append(dirty_result)
    if dirty and not allow_dirty:
        raise OperationError("项目工作区有未提交变更，请确认后再继续 update。", commands)
    update_result = runner.run(project_update_command(bin_dir), cwd=status.path, timeout=300)
    commands.append(update_result)
    _raise_if_failed(update_result, "项目 update 失败。", commands)
    status_result = runner.run(["git", "status", "--short"], cwd=status.path, timeout=20)
    diff_result = runner.run(["git", "diff", "--stat"], cwd=status.path, timeout=20)
    commands.extend([status_result, diff_result])
    return OperationReport(
        title="更新业务项目",
        ok=True,
        message="业务项目 Trellis 配置已更新。",
        commands=commands,
        details={
            "project": str(status.path),
            "dirty_before": dirty_output,
            "status": status_result.stdout.strip(),
            "diff_stat": diff_result.stdout.strip(),
        },
    )


def _successful_output(result: CommandResult) -> str | None:
    if not result.ok:
        return None
    value = result.stdout.strip()
    return value or None


def _read_ahead_behind(repo_dir: Path, runner: CommandRunner) -> tuple[int | None, int | None]:
    result = runner.run(
        ["git", "rev-list", "--left-right", "--count", f"HEAD...origin/{DISTRIBUTION_BRANCH}"],
        cwd=repo_dir,
        timeout=30,
    )
    if not result.ok:
        return None, None
    parts = result.stdout.strip().split()
    if len(parts) != 2:
        return None, None
    try:
        return int(parts[0]), int(parts[1])
    except ValueError:
        return None, None


def _raise_if_failed(result: CommandResult, message: str, commands: list[CommandResult]) -> None:
    if result.ok:
        return
    detail = result.error or result.stderr.strip() or result.stdout.strip()
    raise OperationError(f"{message} {detail}".strip(), commands)


def dataclass_to_dict(value: object) -> dict[str, object]:
    data = asdict(value)
    for key, item in list(data.items()):
        if isinstance(item, Path):
            data[key] = str(item)
    return data
