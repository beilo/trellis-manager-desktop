from __future__ import annotations

import json
import platform
import shutil
import stat
import tempfile
import urllib.request
import zipfile
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
    append_operation_log,
)
from app.runner import CommandResult, CommandRunner
from app.task_snapshot import read_task_snapshot, TrellisTaskItem, TrellisTaskSnapshot

Status = Literal["ok", "warning", "error", "unknown", "info"]
SourceType = Literal["git", "zip_snapshot", "invalid", "missing"]
APP_ROOT = Path(__file__).resolve().parents[1]


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
    source_type: SourceType = "missing"


@dataclass(frozen=True)
class ProjectStatus:
    path: Path | None
    exists: bool
    is_git: bool
    has_trellis: bool
    dirty: bool
    status: Status
    message: str
    trellis_version: str | None = None
    latest_version: str | None = None
    version_outdated: bool = False


@dataclass(frozen=True)
class CommitEntry:
    short_hash: str
    date: str | None
    title: str
    oneline: str


@dataclass(frozen=True)
class GitSummary:
    branch: str | None
    dirty: bool
    dirty_files: list[str] = field(default_factory=list)
    ahead: int | None = None
    behind: int | None = None
    recent_commits: list[CommitEntry] = field(default_factory=list)


@dataclass(frozen=True)
class UpdatePreview:
    ok: bool
    message: str
    dry_run_output: str
    dirty_files_before: list[str] = field(default_factory=list)
    trellis_version_before: str | None = None
    latest_version: str | None = None
    would_run_migrations: bool = False
    requires_migrate: bool = False


@dataclass(frozen=True)
class ToolCommandStatus:
    name: str
    path: Path
    exists: bool
    executable: bool
    version_ok: bool
    help_ok: bool
    mem_help_ok: bool
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


@dataclass(frozen=True)
class ProjectUpdateResult:
    path: str
    ok: bool
    message: str
    report: dict[str, object] | None = None
    skipped: bool = False
    reason: str | None = None


@dataclass(frozen=True)
class BatchUpdateReport:
    ok: bool
    message: str
    results: list[ProjectUpdateResult] = field(default_factory=list)
    total: int = 0
    updated_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0

    def to_log_entry(self) -> dict[str, object]:
        return {
            "title": "批量更新业务项目",
            "ok": self.ok,
            "message": self.message,
            "details": {
                "total": str(self.total),
                "updated_count": str(self.updated_count),
                "failed_count": str(self.failed_count),
                "skipped_count": str(self.skipped_count),
            },
            "results": [dataclass_to_dict(result) for result in self.results],
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


def accelerated_clone_url(accelerated_repo_url: str = ACCELERATED_REPO_URL) -> str:
    return accelerated_repo_url


def wrapper_path(name: str, bin_dir: Path = DEFAULT_BIN_DIR) -> Path:
    if name not in {"tl", "trellis"}:
        raise ValueError("wrapper 名称只能是 tl 或 trellis。")
    return bin_dir / name


def cli_entry_path(repo_dir: Path = DEFAULT_REPO_DIR) -> Path:
    return repo_dir / "packages" / "cli" / "bin" / "trellis.js"


def project_init_command(
    platforms: list[str],
    developer_name: str,
    bin_dir: Path = DEFAULT_BIN_DIR,
) -> list[str]:
    # 平台 key → CLI flag 映射（固定三项，与 config.VALID_INIT_PLATFORMS 对齐）。
    _PLATFORM_FLAGS = {
        "claude-code": "--claude",
        "codex": "--codex",
        "cursor": "--cursor",
    }
    cmd = [str(wrapper_path("tl", bin_dir)), "init", "-y"]
    for key in platforms:
        cmd.append(_PLATFORM_FLAGS[key])
    cmd += ["-u", developer_name]
    return cmd


def project_update_command(bin_dir: Path = DEFAULT_BIN_DIR, migrate: bool = False) -> list[str]:
    cmd = [str(wrapper_path("tl", bin_dir)), "update", "--force"]
    if migrate:
        cmd.append("--migrate")
    return cmd


def project_update_preview_command(bin_dir: Path = DEFAULT_BIN_DIR) -> list[str]:
    return [*project_update_command(bin_dir), "--dry-run"]


def requires_migrate_update(installed: str | None, latest: str | None) -> bool:
    """0.5 -> 0.6 是 Trellis 官方要求的显式迁移路径。"""
    return _major_minor(installed) == (0, 5) and _major_minor(latest) == (0, 6)


def _parse_git_status_short(output: str) -> list[str]:
    files: list[str] = []
    for line in output.splitlines():
        preserved = line.rstrip("\r")
        if preserved:
            files.append(preserved)
    return files


def _parse_git_log_oneline(output: str) -> list[CommitEntry]:
    commits: list[CommitEntry] = []
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        # 用不可见分隔符承载日期，避免提交标题里的空格影响解析。
        if "\x1f" in stripped:
            parts = stripped.split("\x1f", 2)
            if len(parts) == 3:
                short_hash, date, title = parts
                clean_title = title.strip() or stripped
                commits.append(
                    CommitEntry(
                        short_hash=short_hash,
                        date=date.strip() or None,
                        title=clean_title,
                        oneline=f"{short_hash} {clean_title}",
                    ),
                )
                continue
        short_hash, _, title = stripped.partition(" ")
        commits.append(CommitEntry(short_hash=short_hash, date=None, title=title.strip() or stripped, oneline=stripped))
    return commits


def _detect_migration_signals(output: str) -> bool:
    keywords = [
        "Analyzing migrations",
        "Auto-migrate",
        "Requires confirmation",
        "Conflict",
        "MIGRATION REQUIRED",
    ]
    normalized = output.lower()
    return any(keyword.lower() in normalized for keyword in keywords)


def get_project_git_summary(project_path: Path | str, runner: CommandRunner | None = None) -> GitSummary:
    runner = runner or CommandRunner()
    path = expand_path(project_path)
    if not path.exists() or not path.is_dir():
        raise OperationError("业务项目目录不存在。")
    if not is_git_repo(path, runner):
        raise OperationError("目标项目不是 git 仓库。")

    branch_result = runner.run(["git", "branch", "--show-current"], cwd=path, timeout=10)
    branch = _successful_output(branch_result)

    dirty, _, dirty_result = git_status_short(path, runner)
    dirty_files = _parse_git_status_short(dirty_result.stdout)

    log_result = runner.run(["git", "log", "-5", "--date=short", "--pretty=format:%h%x1f%ad%x1f%s"], cwd=path, timeout=20)
    if not log_result.ok:
        raise OperationError("读取最近提交失败。")
    recent_commits = _parse_git_log_oneline(log_result.stdout)

    # 业务项目应跟随自身 upstream，而不是 Trellis 工具仓库的分发分支。
    ahead, behind = _read_ahead_behind(path, runner, None)
    return GitSummary(
        branch=branch,
        dirty=dirty,
        dirty_files=dirty_files,
        ahead=ahead,
        behind=behind,
        recent_commits=recent_commits,
    )


def preview_project_update(
    project_dir: Path | str,
    runner: CommandRunner | None = None,
    bin_dir: Path = DEFAULT_BIN_DIR,
    tool_repo_dir: Path = DEFAULT_REPO_DIR,
) -> UpdatePreview:
    runner = runner or CommandRunner()
    path = expand_path(project_dir)
    if not path.exists() or not path.is_dir():
        raise OperationError("业务项目目录不存在。")
    if not is_git_repo(path, runner):
        raise OperationError("目标项目必须是 git 仓库。")
    if not (path / ".trellis").exists():
        raise OperationError("目标项目尚未安装 Trellis，请先 init。")

    _, _, dirty_result = git_status_short(path, runner)
    dirty_files_before = _parse_git_status_short(dirty_result.stdout)
    trellis_version_before = read_project_trellis_version(path)
    latest_version = read_cli_version(tool_repo_dir.expanduser())
    requires_migrate = requires_migrate_update(trellis_version_before, latest_version)
    dry_run_result = runner.run(project_update_preview_command(bin_dir), cwd=path, timeout=300)
    dry_run_output = "\n".join(part for part in [dry_run_result.stdout.strip(), dry_run_result.stderr.strip()] if part)
    if not dry_run_output:
        dry_run_output = dry_run_result.stdout or dry_run_result.stderr or ""
    would_run_migrations = _detect_migration_signals(dry_run_output) or requires_migrate
    ok = dry_run_result.ok
    if ok:
        message = "已完成 update 预览。"
    else:
        detail = dry_run_result.error or dry_run_result.stderr.strip() or dry_run_result.stdout.strip() or "未知错误。"
        message = f"update 预览失败：{detail}"
    return UpdatePreview(
        ok=ok,
        message=message,
        dry_run_output=dry_run_output,
        dirty_files_before=dirty_files_before,
        trellis_version_before=trellis_version_before,
        latest_version=latest_version,
        would_run_migrations=would_run_migrations,
        requires_migrate=requires_migrate,
    )


def helm_workspace_new_command(workspace_name: str, project_dir: Path) -> list[str]:
    return ["helm", "workspace", "new", workspace_name, "--project", str(project_dir)]


def helm_issue_new_command(
    workspace_name: str,
    title: str,
    prd_file: Path,
    project_name: str,
) -> list[str]:
    return [
        "helm",
        "issue",
        "new",
        workspace_name,
        title,
        "--description-file",
        str(prd_file),
        "--project",
        project_name,
        "--status",
        "todo",
        "--json",
    ]


def install_instruction(name: str) -> str:
    instructions = {
        "git": "请先安装 Xcode Command Line Tools 或 Homebrew git。",
        "helm": "请先安装 Helm CLI。",
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


def check_helm_status(runner: CommandRunner | None = None) -> EnvironmentItem:
    """检查 Helm CLI 是否可执行，供前端决定按钮禁用态。"""
    runner = runner or CommandRunner()
    result = runner.run(["helm", "--version"], timeout=10)
    output = (result.stdout or result.stderr).strip().splitlines()
    if result.ok:
        return EnvironmentItem(
            name="helm",
            ok=True,
            status="ok",
            version=output[0] if output else None,
            message="Helm 已安装。",
        )
    return EnvironmentItem(
        name="helm",
        ok=False,
        status="error",
        message="未安装 Helm",
    )


def is_git_repo(path: Path, runner: CommandRunner | None = None) -> bool:
    runner = runner or CommandRunner()
    if not path.exists() or not path.is_dir():
        return False
    result = runner.run(["git", "rev-parse", "--is-inside-work-tree"], cwd=path, timeout=10)
    return result.ok and result.stdout.strip() == "true"


def git_status_short(path: Path, runner: CommandRunner | None = None) -> tuple[bool, str, CommandResult]:
    runner = runner or CommandRunner()
    result = runner.run(["git", "status", "--short"], cwd=path, timeout=20)
    # git status --short 的前两列是状态位，不能用 strip() 丢掉前导空格。
    output = result.stdout.rstrip("\r\n")
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


def read_project_trellis_version(project_dir: Path) -> str | None:
    version_file = project_dir / ".trellis" / ".version"
    if not version_file.exists():
        return None
    try:
        version = version_file.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return version or None


def is_version_outdated(installed: str | None, latest: str | None) -> bool:
    if latest is None:
        return False
    if installed is None:
        return True
    if installed == latest:
        return False
    installed_key = _semver_key(installed)
    latest_key = _semver_key(latest)
    if installed_key is None or latest_key is None:
        return installed != latest
    return installed_key < latest_key


def _major_minor(version: str | None) -> tuple[int, int] | None:
    if not version:
        return None
    release = version.partition("-")[0]
    parts = release.split(".")
    if len(parts) < 2:
        return None
    try:
        return int(parts[0]), int(parts[1])
    except ValueError:
        return None


def _semver_key(version: str) -> tuple[tuple[int, int, int], tuple[object, ...]] | None:
    release, separator, prerelease = version.partition("-")
    parts = release.split(".")
    if len(parts) != 3:
        return None
    try:
        release_key = tuple(int(part) for part in parts)
    except ValueError:
        return None
    if separator == "":
        return release_key, (1,)
    prerelease_key: list[object] = [0]
    for token in prerelease.split("."):
        prerelease_key.append((1, int(token)) if token.isdigit() else (0, token))
    return release_key, tuple(prerelease_key)


def is_trellis_repo(repo_dir: Path) -> bool:
    return cli_entry_path(repo_dir).exists() and (repo_dir / "packages" / "cli" / "package.json").exists()


def is_valid_source_tree(repo_dir: Path) -> bool:
    """验证目录是否为有效的 Trellis 源码树，不依赖 .git 目录。"""
    if not repo_dir.is_dir():
        return False
    # 检查核心标记文件，与 GitHub codeload zip 解压后的目录结构兼容
    markers = [
        repo_dir / "package.json",
        repo_dir / "pnpm-lock.yaml",
        repo_dir / "packages" / "cli" / "package.json",
        repo_dir / "packages" / "cli" / "bin" / "trellis.js",
    ]
    return all(marker.exists() for marker in markers)


def _safe_extract_zip(zip_path: Path, extract_to: Path) -> Path:
    """安全解压 zip 到临时目录，拒绝路径遍历攻击，返回检测到的源码根目录。"""
    extract_to.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        # 先校验所有条目，拒绝绝对路径和 .. 遍历
        for info in zf.infolist():
            target = extract_to / info.filename
            try:
                target.resolve().relative_to(extract_to.resolve())
            except ValueError:
                raise OperationError(f"zip 包含非法路径：{info.filename}")
        zf.extractall(extract_to)

    # GitHub codeload zip 解压后通常有一个顶层文件夹（如 Trellis-custom-beilo-v0.5-rc）
    # 先尝试直接找源码根
    if is_valid_source_tree(extract_to):
        return extract_to

    # 否则在子目录中查找有效的源码根
    for child in extract_to.iterdir():
        if child.is_dir() and is_valid_source_tree(child):
            return child

    raise OperationError("zip 中未找到有效的 Trellis 源码树。")


def install_from_zip(
    zip_path: Path,
    repo_dir: Path = DEFAULT_REPO_DIR,
    replace: bool = False,
    distribution_branch: str = DISTRIBUTION_BRANCH,
    runner: CommandRunner | None = None,
) -> OperationReport:
    """从本地 zip 安装或重装 Trellis 工具源码。"""
    runner = runner or CommandRunner()
    commands: list[CommandResult] = []
    zip_path = zip_path.expanduser().resolve()
    repo_dir = repo_dir.expanduser()

    if not zip_path.exists():
        raise OperationError(f"zip 文件不存在：{zip_path}")
    if not zip_path.is_file():
        raise OperationError(f"路径不是文件：{zip_path}")

    # 拒绝非 zip 文件（通过魔数判断，不依赖扩展名）
    try:
        with zip_path.open("rb") as f:
            magic = f.read(4)
        if magic not in (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"):
            raise OperationError("文件不是有效的 zip 格式。")
    except OSError as e:
        raise OperationError(f"读取 zip 文件失败：{e}")

    # 目标已存在且未要求替换时阻断
    if repo_dir.exists() and not replace:
        raise OperationError(
            "工具仓库已存在，如需替换请先确认重装。",
            commands,
        )

    # 在 manager 控制区域内创建临时目录
    temp_base = repo_dir.parent / ".manager-temp"
    temp_base.mkdir(parents=True, exist_ok=True)
    temp_extract = temp_base / f"extract-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    try:
        # 安全解压并定位源码根
        source_root = _safe_extract_zip(zip_path, temp_extract)

        # 验证源码根
        if not is_valid_source_tree(source_root):
            raise OperationError("zip 内容不是有效的 Trellis 源码树。")

        # 替换策略：备份旧目录 → 移动新目录 → 成功则删备份，失败则恢复
        backup_dir: Path | None = None
        if repo_dir.exists():
            backup_dir = repo_dir.parent / f"{repo_dir.name}.backup-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            repo_dir.rename(backup_dir)

        try:
            # 把验证通过的源码根移动到目标位置
            # 如果 source_root 就是 temp_extract，直接重命名；否则复制内容
            if source_root == temp_extract:
                temp_extract.rename(repo_dir)
            else:
                repo_dir.mkdir(parents=True, exist_ok=True)
                for item in source_root.iterdir():
                    dest = repo_dir / item.name
                    if dest.exists():
                        if dest.is_dir():
                            shutil.rmtree(dest)
                        else:
                            dest.unlink()
                    if item.is_dir():
                        shutil.copytree(item, dest)
                    else:
                        shutil.copy2(item, dest)
        except Exception:
            # 恢复备份
            if backup_dir and backup_dir.exists():
                if repo_dir.exists():
                    shutil.rmtree(repo_dir)
                backup_dir.rename(repo_dir)
            raise OperationError("安装源码到目标路径失败，已恢复原有目录。", commands)

        # clean 端已经把 core/cli 的顺序收敛进根 build，这里只认统一入口，避免重复维护构建顺序。
        for command, message, timeout in [
            (["pnpm", "install"], "安装依赖失败。", 600),
            (["pnpm", "build"], "构建 Trellis 失败。", 600),
        ]:
            result = runner.run(command, cwd=repo_dir, timeout=timeout)
            commands.append(result)
            _raise_if_failed(result, message, commands)

        # 成功：清理备份和临时目录
        if backup_dir and backup_dir.exists():
            shutil.rmtree(backup_dir)

        return OperationReport(
            title="从本地 zip 安装 Trellis 工具仓库",
            ok=True,
            message="工具仓库已从本地 zip 安装并构建完成。",
            commands=commands,
            details={
                "repo": str(repo_dir),
                "zip": str(zip_path),
                "source_type": "zip_snapshot",
                "branch": distribution_branch,
            },
        )
    finally:
        # 无论成功与否，清理临时解压目录
        if temp_extract.exists():
            shutil.rmtree(temp_extract)


def check_tool_repo(
    repo_dir: Path = DEFAULT_REPO_DIR,
    runner: CommandRunner | None = None,
    distribution_branch: str = DISTRIBUTION_BRANCH,
) -> RepoStatus:
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
            source_type="missing",
        )
    git_ok = is_git_repo(repo_dir, runner)
    if git_ok:
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
            fetch = runner.run(["git", "fetch", "origin", distribution_branch], cwd=repo_dir, timeout=120)
            if fetch.ok:
                ahead, behind = _read_ahead_behind(repo_dir, runner, distribution_branch)
                if branch != distribution_branch:
                    status = "warning"
                    message = f"当前分支不是团队分发分支，点击更新会切到 {distribution_branch}。"
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
            source_type="git" if valid else "invalid",
        )

    # 非 git 目录：检查是否为有效的源码快照
    valid_snapshot = is_valid_source_tree(repo_dir)
    version = read_cli_version(repo_dir) if valid_snapshot else None
    if valid_snapshot:
        return RepoStatus(
            path=repo_dir,
            exists=True,
            is_git=False,
            is_trellis_repo=True,
            dirty=False,
            branch=distribution_branch,
            origin=None,
            version=version,
            ahead=None,
            behind=None,
            status="ok",
            message="已检测本地源码快照有效；该安装方式不能在线 pull，如需更新请选择新的 zip。",
            source_type="zip_snapshot",
        )
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
        message="安装目录存在但不是 git 仓库，也不是有效的 Trellis 源码快照。",
        source_type="invalid",
    )


def install_or_update_tool_repo(
    repo_dir: Path = DEFAULT_REPO_DIR,
    runner: CommandRunner | None = None,
    official_repo_url: str = OFFICIAL_REPO_URL,
    accelerated_repo_url: str = ACCELERATED_REPO_URL,
    distribution_branch: str = DISTRIBUTION_BRANCH,
) -> OperationReport:
    runner = runner or CommandRunner()
    repo_dir = repo_dir.expanduser()
    commands: list[CommandResult] = []
    repo_dir.parent.mkdir(parents=True, exist_ok=True)
    if not repo_dir.exists():
        clone = runner.run(
            ["git", "clone", "--branch", distribution_branch, accelerated_clone_url(accelerated_repo_url), str(repo_dir)],
            timeout=600,
        )
        commands.append(clone)
        if not clone.ok:
            fallback = runner.run(
                ["git", "clone", "--branch", distribution_branch, official_repo_url, str(repo_dir)],
                timeout=600,
            )
            commands.append(fallback)
            _raise_if_failed(fallback, "下载 Trellis 工具仓库失败。", commands)
        origin = runner.run(["git", "remote", "set-url", "origin", official_repo_url], cwd=repo_dir, timeout=30)
        commands.append(origin)
        _raise_if_failed(origin, "设置官方 origin 失败。", commands)
    else:
        status = check_tool_repo(repo_dir, runner, distribution_branch)
        if not status.is_git or not status.is_trellis_repo:
            raise OperationError(status.message, commands)
        # 使用 --autostash 自动暂存本地变更（如 lock 文件），更新后恢复
        pull = runner.run(
            ["git", "pull", "--autostash", "--ff-only", "origin", distribution_branch],
            cwd=repo_dir,
            timeout=120,
        )
        commands.append(pull)
        _raise_if_failed(pull, "更新工具仓库失败。", commands)
    for command, message, timeout in [
        (["pnpm", "install"], "安装依赖失败。", 600),
        (["pnpm", "build"], "构建 Trellis 失败。", 600),
    ]:
        result = runner.run(command, cwd=repo_dir, timeout=timeout)
        commands.append(result)
        _raise_if_failed(result, message, commands)
    return OperationReport(
        title="安装或更新 Trellis 工具仓库",
        ok=True,
        message="工具仓库已准备完成。",
        commands=commands,
        details={"repo": str(repo_dir), "branch": distribution_branch},
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
        mem_help_ok = False
        if executable:
            version = runner.run([path, "--version"], timeout=20)
            help_result = runner.run([path, "--help"], timeout=20)
            mem_help_result = runner.run([path, "mem", "help"], timeout=20)
            commands.extend([version, help_result, mem_help_result])
            version_ok = version.ok
            help_ok = help_result.ok
            mem_help_ok = mem_help_result.ok
        ok = exists and executable and version_ok and help_ok and mem_help_ok
        statuses.append(
            ToolCommandStatus(
                name=name,
                path=path,
                exists=exists,
                executable=executable,
                version_ok=version_ok,
                help_ok=help_ok,
                mem_help_ok=mem_help_ok,
                status="ok" if ok else "error",
                message="命令可用。" if ok else "命令不可用，请先创建 wrapper 或检查构建结果。",
                commands=commands,
            ),
        )
    return statuses


def inspect_project(
    path_text: str,
    runner: CommandRunner | None = None,
    tool_repo_dir: Path = DEFAULT_REPO_DIR,
) -> ProjectStatus:
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
    trellis_version = read_project_trellis_version(path) if has_trellis else None
    latest_version = read_cli_version(tool_repo_dir.expanduser()) if has_trellis else None
    version_outdated = has_trellis and is_version_outdated(trellis_version, latest_version)
    if not git_ok:
        status: Status = "error"
        message = "目标项目不是 git 仓库，不能 init 或 update。"
    elif has_trellis:
        status = "warning" if version_outdated else "ok"
        if version_outdated:
            current = trellis_version or "未知"
            message = f"项目 Trellis 版本 {current}，最新版本 {latest_version}，建议 update。"
        elif trellis_version:
            message = f"项目已安装 Trellis（{trellis_version}），可执行 update。"
        else:
            message = "项目已安装 Trellis，可执行 update。"
    else:
        status = "ok"
        message = "项目可执行 Trellis init。"
    return ProjectStatus(
        path,
        True,
        git_ok,
        has_trellis,
        dirty,
        status,
        message,
        trellis_version,
        latest_version,
        version_outdated,
    )


def check_developer_config(
    developer_name: str,
    platforms: list[str],
) -> EnvironmentItem:
    """检查初始化前置配置是否齐全，供环境面板展示。"""
    missing: list[str] = []
    if not developer_name.strip():
        missing.append("开发者名")
    if not platforms:
        missing.append("初始化平台")
    if missing:
        return EnvironmentItem(
            "开发者配置",
            False,
            "error",
            f"未配置：{'、'.join(missing)}。请在设置中填写并选择初始化平台。",
        )
    labels = "、".join(
        _PLATFORM_LABELS.get(k, k) for k in platforms
    )
    return EnvironmentItem(
        "开发者配置",
        True,
        "ok",
        f"开发者 {developer_name}，平台：{labels}。",
    )


# 平台 key → 中文标签（与 INIT_PLATFORMS 对齐，仅供检查项输出）。
_PLATFORM_LABELS = {
    "claude-code": "Claude Code",
    "codex": "Codex",
    "cursor": "Cursor",
}


def init_project(
    project_dir: Path,
    platforms: list[str],
    developer_name: str,
    runner: CommandRunner | None = None,
    bin_dir: Path = DEFAULT_BIN_DIR,
) -> OperationReport:
    runner = runner or CommandRunner()
    # 前置配置阻断：名字空或平台空时拒绝 init，避免生成无效配置。
    if not developer_name.strip():
        raise OperationError("未配置开发者名，请在设置中填写后再初始化。")
    if not platforms:
        raise OperationError("未选择初始化平台，请在设置中至少选择一个平台。")
    status = inspect_project(str(project_dir), runner)
    if not status.is_git:
        raise OperationError("目标项目必须是 git 仓库。")
    if status.has_trellis:
        raise OperationError("目标项目已经存在 .trellis，请使用 update。")
    commands: list[CommandResult] = []
    init_result = runner.run(project_init_command(platforms, developer_name.strip(), bin_dir), cwd=status.path, timeout=300)
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
    migrate: bool = False,
    runner: CommandRunner | None = None,
    bin_dir: Path = DEFAULT_BIN_DIR,
    tool_repo_dir: Path = DEFAULT_REPO_DIR,
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
    if migrate and not requires_migrate_update(read_project_trellis_version(status.path), read_cli_version(tool_repo_dir.expanduser())):
        raise OperationError("当前项目版本不需要 --migrate，请使用普通 update。", commands)
    update_result = runner.run(project_update_command(bin_dir, migrate=migrate), cwd=status.path, timeout=300)
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
            "migrate": "true" if migrate else "false",
            "status": status_result.stdout.strip(),
            "diff_stat": diff_result.stdout.strip(),
        },
    )


def list_outdated_projects(
    project_paths: list[Path | str],
    runner: CommandRunner | None = None,
    tool_repo_dir: Path = DEFAULT_REPO_DIR,
) -> list[ProjectStatus]:
    runner = runner or CommandRunner()
    outdated: list[ProjectStatus] = []
    for project_path in project_paths:
        status = inspect_project(str(project_path), runner, tool_repo_dir)
        if status.version_outdated:
            outdated.append(status)
    return outdated


def batch_update_projects(
    project_paths: list[Path | str] | None,
    configured_projects: list[Path | str],
    allow_dirty: bool = False,
    runner: CommandRunner | None = None,
    bin_dir: Path = DEFAULT_BIN_DIR,
    tool_repo_dir: Path = DEFAULT_REPO_DIR,
    log_file: Path | None = None,
) -> BatchUpdateReport:
    runner = runner or CommandRunner()
    candidates: list[Path | str]
    if project_paths is None:
        # 未显式指定路径时只处理已落后项目，避免批量按钮误更新全部仓库。
        candidates = [status.path for status in list_outdated_projects(configured_projects, runner, tool_repo_dir) if status.path is not None]
    else:
        candidates = project_paths

    results: list[ProjectUpdateResult] = []
    for candidate in _dedupe_project_candidates(candidates):
        path = expand_path(candidate)
        try:
            status = inspect_project(str(path), runner, tool_repo_dir)
            if status.path is None:
                results.append(ProjectUpdateResult(str(path), False, status.message, skipped=True, reason=status.message))
                continue
            if status.dirty and not allow_dirty:
                message = "项目工作区有未提交变更，批量更新已跳过。"
                results.append(ProjectUpdateResult(str(status.path), False, message, skipped=True, reason=message))
                continue
            report = update_project(status.path, allow_dirty=allow_dirty, runner=runner, bin_dir=bin_dir, tool_repo_dir=tool_repo_dir)
            results.append(ProjectUpdateResult(str(status.path), True, report.message, report=report.to_log_entry()))
        except OperationError as error:
            results.append(
                ProjectUpdateResult(
                    str(path),
                    False,
                    str(error),
                    report=_operation_error_report("更新业务项目", str(error), error.commands),
                ),
            )

    updated_count = sum(1 for result in results if result.ok)
    skipped_count = sum(1 for result in results if result.skipped)
    failed_count = len(results) - updated_count - skipped_count
    ok = len(results) > 0 and failed_count == 0 and skipped_count == 0
    if not results:
        message = "没有需要批量更新的项目。"
    elif ok:
        message = f"批量更新完成：成功 {updated_count} 个项目。"
    else:
        message = f"批量更新完成：成功 {updated_count} 个，失败 {failed_count} 个，跳过 {skipped_count} 个。"
    report = BatchUpdateReport(
        ok=ok,
        message=message,
        results=results,
        total=len(results),
        updated_count=updated_count,
        failed_count=failed_count,
        skipped_count=skipped_count,
    )
    entry = report.to_log_entry()
    append_operation_log(entry, log_file) if log_file else append_operation_log(entry)
    return report


def _dedupe_project_candidates(project_paths: list[Path | str]) -> list[Path | str]:
    seen: set[str] = set()
    deduped: list[Path | str] = []
    for project_path in project_paths:
        key = str(Path(project_path).expanduser())
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(project_path)
    return deduped


def _operation_error_report(title: str, message: str, commands: list[CommandResult]) -> dict[str, object]:
    return {
        "title": title,
        "ok": False,
        "message": message,
        "details": {},
        "commands": [command.to_dict() for command in commands],
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }


def push_task_to_helm(
    project_dir: Path,
    task_dir: Path,
    runner: CommandRunner | None = None,
) -> OperationReport:
    """将 Trellis 任务 PRD 推送为 Helm issue。"""
    runner = runner or CommandRunner()
    project_dir = expand_path(project_dir)
    task_dir = expand_path(task_dir)
    prd_file = task_dir / "prd.md"
    if not prd_file.is_file():
        raise OperationError("需要 PRD 文档。")

    commands: list[CommandResult] = []
    helm_status = runner.run(["helm", "--version"], timeout=10)
    commands.append(helm_status)
    _raise_if_failed(helm_status, "未安装 Helm。", commands)

    workspace_name = _find_or_create_helm_workspace(project_dir, runner, commands)
    title = _read_task_title(task_dir)
    issue_result = runner.run(
        helm_issue_new_command(workspace_name, title, prd_file, project_dir.name),
        cwd=project_dir,
        timeout=60,
    )
    commands.append(issue_result)
    _raise_if_failed(issue_result, "推送 Helm issue 失败。", commands)

    issue_id = _extract_helm_issue_id(issue_result.stdout)
    message = f"已推送到 Helm issue {issue_id}。" if issue_id else "已推送到 Helm issue。"
    details = {
        "workspace": workspace_name,
        "project": str(project_dir),
        "task": str(task_dir),
        "prd": str(prd_file),
    }
    if issue_id:
        details["issue_id"] = issue_id
    return OperationReport(
        title="推送任务到 Helm",
        ok=True,
        message=message,
        commands=commands,
        details=details,
    )


def _find_or_create_helm_workspace(
    project_dir: Path,
    runner: CommandRunner,
    commands: list[CommandResult],
) -> str:
    list_result = runner.run(["helm", "workspace", "ls", "--json"], timeout=30)
    commands.append(list_result)
    if not list_result.ok:
        # Helm daemon 未运行时先尝试启动，再重试 workspace 列表。
        daemon_result = runner.run(["helm", "daemon", "start"], timeout=30)
        commands.append(daemon_result)
        _raise_if_failed(daemon_result, "Helm daemon 启动失败。", commands)
        list_result = runner.run(["helm", "workspace", "ls", "--json"], timeout=30)
        commands.append(list_result)
        _raise_if_failed(list_result, "读取 Helm workspace 失败。", commands)

    workspace = _find_matching_workspace(list_result.stdout, project_dir, commands)
    if workspace:
        return workspace

    create_result = runner.run(helm_workspace_new_command(project_dir.name, project_dir), timeout=60)
    commands.append(create_result)
    _raise_if_failed(create_result, "创建 Helm workspace 失败。", commands)
    return project_dir.name


def _find_matching_workspace(
    workspaces_json: str,
    project_dir: Path,
    commands: list[CommandResult],
) -> str | None:
    try:
        payload = json.loads(workspaces_json or "[]")
    except json.JSONDecodeError as error:
        raise OperationError(f"读取 Helm workspace 失败：JSON 格式无效。{error}", commands) from error
    workspaces = _workspace_items(payload)
    for workspace in workspaces:
        if not isinstance(workspace, dict):
            continue
        name = workspace.get("name")
        projects = workspace.get("projects")
        if isinstance(name, str) and _workspace_projects_include(projects, project_dir):
            return name
    return None


def _workspace_items(payload: object) -> list[object]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("workspaces", "items", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
    return []


def _workspace_projects_include(projects: object, project_dir: Path) -> bool:
    if not isinstance(projects, list):
        return False
    project_path = project_dir.resolve()
    for item in projects:
        if isinstance(item, str) and Path(item).expanduser().resolve() == project_path:
            return True
        if isinstance(item, dict):
            path = item.get("path") or item.get("project")
            if isinstance(path, str) and Path(path).expanduser().resolve() == project_path:
                return True
    return False


def _read_task_title(task_dir: Path) -> str:
    task_json = task_dir / "task.json"
    try:
        data = json.loads(task_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return task_dir.name
    if not isinstance(data, dict):
        return task_dir.name
    title = data.get("title") or data.get("name")
    return title if isinstance(title, str) and title.strip() else task_dir.name


def _extract_helm_issue_id(stdout: str) -> str | None:
    try:
        payload = json.loads(stdout or "{}")
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    for source in (payload, payload.get("issue")):
        if not isinstance(source, dict):
            continue
        for key in ("id", "number"):
            value = source.get(key)
            if isinstance(value, str) and value.strip():
                return value
            if isinstance(value, int):
                return str(value)
    return None


def _successful_output(result: CommandResult) -> str | None:
    if not result.ok:
        return None
    value = result.stdout.strip()
    return value or None


def _read_ahead_behind(
    repo_dir: Path,
    runner: CommandRunner,
    distribution_branch: str | None = DISTRIBUTION_BRANCH,
) -> tuple[int | None, int | None]:
    # 工具仓库比较固定分发分支；业务项目传 None 时比较当前分支配置的 upstream。
    target = f"origin/{distribution_branch}" if distribution_branch else "@{upstream}"
    result = runner.run(
        ["git", "rev-list", "--left-right", "--count", f"HEAD...{target}"],
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


def github_branch_url(official_repo_url: str, distribution_branch: str) -> str | None:
    """从官方仓库 URL 和分发分支推导 GitHub 分支页面链接。"""
    url = official_repo_url.strip()
    # 支持 HTTPS 和 SSH 格式的 GitHub URL
    if url.startswith("https://github.com/"):
        # https://github.com/owner/repo.git → https://github.com/owner/repo/tree/branch
        base = url.removeprefix("https://github.com/").removesuffix(".git")
        return f"https://github.com/{base}/tree/{distribution_branch}"
    if url.startswith("git@github.com:"):
        # git@github.com:owner/repo.git → https://github.com/owner/repo/tree/branch
        base = url.removeprefix("git@github.com:").removesuffix(".git")
        return f"https://github.com/{base}/tree/{distribution_branch}"
    return None


def github_branch_zip_url(official_repo_url: str, distribution_branch: str) -> str | None:
    """从官方仓库 URL 和分发分支推导 GitHub codeload zip 下载地址。"""
    url = official_repo_url.strip()
    if url.startswith("https://github.com/"):
        # https://github.com/owner/repo.git → owner/repo
        base = url.removeprefix("https://github.com/").removesuffix(".git")
    elif url.startswith("git@github.com:"):
        # git@github.com:owner/repo.git → owner/repo
        base = url.removeprefix("git@github.com:").removesuffix(".git")
    else:
        return None
    # 验证 base 格式为 owner/repo，拒绝空或畸形输入
    parts = base.strip("/").split("/")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        return None
    return f"https://codeload.github.com/{parts[0]}/{parts[1]}/zip/refs/heads/{distribution_branch}"


def install_from_remote_zip(
    repo_dir: Path = DEFAULT_REPO_DIR,
    replace: bool = False,
    official_repo_url: str = OFFICIAL_REPO_URL,
    distribution_branch: str = DISTRIBUTION_BRANCH,
    runner: CommandRunner | None = None,
) -> OperationReport:
    """从远端 GitHub 下载源码 zip 并安装/重装 Trellis 工具仓库。"""
    runner = runner or CommandRunner()
    repo_dir = repo_dir.expanduser()
    if repo_dir.exists() and not replace:
        raise OperationError("工具仓库已存在，如需替换请先确认重装。")

    # 1. 推导下载 URL
    download_url = github_branch_zip_url(official_repo_url, distribution_branch)
    if download_url is None:
        raise OperationError("当前官方仓库 URL 不是 GitHub 仓库，无法下载源码 zip。")

    # 2. 下载 zip 到临时目录
    temp_base = repo_dir.parent / ".manager-temp"
    temp_base.mkdir(parents=True, exist_ok=True)
    zip_path = temp_base / f"remote-{datetime.now().strftime('%Y%m%d%H%M%S')}.zip"

    try:
        _download_zip(download_url, zip_path)
    except Exception:
        # 清理可能的不完整文件
        if zip_path.exists():
            zip_path.unlink()
        raise OperationError("下载源码 zip 失败，请检查网络连接或分发分支配置。")

    try:
        # 3. 复用现有本地 zip 安装流程
        report = install_from_zip(
            zip_path,
            repo_dir,
            replace=replace,
            distribution_branch=distribution_branch,
            runner=runner,
        )
        # 4. 包装返回结果，语义改为远端 zip
        return OperationReport(
            title="从远端 zip 安装 Trellis 工具仓库",
            ok=report.ok,
            message=report.message,
            commands=report.commands,
            details={
                **report.details,
                "repo": str(repo_dir),
                "source_type": "zip_snapshot",
                "branch": distribution_branch,
                "download_url": download_url,
                "zip": str(zip_path),
            },
        )
    finally:
        # 5. 清理下载的临时 zip（无论成功失败）
        if zip_path.exists():
            zip_path.unlink()


def _download_zip(url: str, dest: Path) -> None:
    """下载 URL 到本地文件，仅用于 Manager 内部推导的 codeload URL。"""
    try:
        with urllib.request.urlopen(url, timeout=120) as response:  # noqa: S310 — URL 由内部推导，非用户输入
            dest.write_bytes(response.read())
    except urllib.error.URLError as error:
        raise OperationError(f"下载源码 zip 失败：{error}") from error
    except OSError as error:
        raise OperationError(f"写入 zip 文件失败：{error}") from error


def _raise_if_failed(result: CommandResult, message: str, commands: list[CommandResult]) -> None:
    if result.ok:
        return
    detail = result.error or result.stderr.strip() or result.stdout.strip()
    raise OperationError(f"{message} {detail}".strip(), commands)


def dataclass_to_dict(value: object) -> dict[str, object]:
    data = asdict(value)
    return _json_safe(data)  # type: ignore[return-value]


def _json_safe(value: object) -> object:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    return value
