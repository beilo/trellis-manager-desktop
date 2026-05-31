from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

APP_NAME = "Trellis Manager"
OFFICIAL_REPO_URL = "https://github.com/beilo/Trellis.git"
ACCELERATED_REPO_URL = "https://xget.xi-xu.me/gh/beilo/Trellis.git"
DISTRIBUTION_BRANCH = "custom/beilo-v0.5-rc"

BASE_DIR = Path.home() / ".beilo-trellis"
DEFAULT_REPO_DIR = BASE_DIR / "Trellis"
DEFAULT_BIN_DIR = BASE_DIR / "bin"
CONFIG_DIR = BASE_DIR / "manager"
CONFIG_FILE = CONFIG_DIR / "config.json"
LOG_FILE = CONFIG_DIR / "operations.json"
MAX_OPERATION_LOGS = 80

PATH_EXPORT_LINE = 'export PATH="$HOME/.beilo-trellis/bin:$PATH"'

# 初始化平台合法 key 集合，供 config 与 ops 复用。
VALID_INIT_PLATFORMS = {"claude-code", "codex", "cursor"}


@dataclass(frozen=True)
class ManagerConfig:
    trellis_repo: Path = DEFAULT_REPO_DIR
    projects: list[Path] = field(default_factory=list)
    last_selected_project: Path | None = None
    recent_projects: list[Path] = field(default_factory=list)
    official_repo_url: str = OFFICIAL_REPO_URL
    accelerated_repo_url: str = ACCELERATED_REPO_URL
    distribution_branch: str = DISTRIBUTION_BRANCH
    # 初始化前置配置（全局单值，所有项目通用）
    developer_name: str = ""
    init_platforms: list[str] = field(default_factory=list)


def _path_from_json(value: object, fallback: Path) -> Path:
    if not isinstance(value, str) or not value.strip():
        return fallback
    return Path(value).expanduser()


# 统一把配置字符串做最小校验：空值回退到默认值，避免旧配置把运行时引到无效仓库或分支。
def _str_from_json(value: object, fallback: str) -> str:
    if not isinstance(value, str) or not value.strip():
        return fallback
    return value.strip()


# 开发者名清理：strip 后允许空，由阻断逻辑决定是否合法。
def _clean_name(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()


# 平台列表清理：仅保留合法 key、去重、保持顺序。
def _clean_platforms(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    seen: set[str] = set()
    result: list[str] = []
    for item in value:
        if isinstance(item, str) and item in VALID_INIT_PLATFORMS and item not in seen:
            seen.add(item)
            result.append(item)
    return result


# 只序列化已知配置字段，避免以后迁移时丢失语义或把内部结构写进 JSON。
def _config_payload(config: ManagerConfig) -> dict[str, object]:
    return {
        "trellis_repo": str(config.trellis_repo.expanduser()),
        "projects": [str(path.expanduser()) for path in _dedupe_paths(config.projects)],
        "last_selected_project": (
            str(config.last_selected_project.expanduser())
            if config.last_selected_project
            else None
        ),
        "recent_projects": [str(path.expanduser()) for path in _dedupe_paths(config.recent_projects)],
        "official_repo_url": config.official_repo_url,
        "accelerated_repo_url": config.accelerated_repo_url,
        "distribution_branch": config.distribution_branch,
        "developer_name": config.developer_name,
        "init_platforms": config.init_platforms,
    }


def _dedupe_paths(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    result: list[Path] = []
    for path in paths:
        key = str(path.expanduser())
        if key in seen:
            continue
        seen.add(key)
        result.append(path)
    return result


def load_config(config_file: Path = CONFIG_FILE) -> ManagerConfig:
    if not config_file.exists():
        return ManagerConfig()
    try:
        data = json.loads(config_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ManagerConfig()
    recent_raw = data.get("recent_projects") if isinstance(data, dict) else None
    if isinstance(recent_raw, list):
        recent = [
            Path(item).expanduser()
            for item in recent_raw
            if isinstance(item, str) and item.strip()
        ]
    else:
        recent = []
    projects_raw = data.get("projects") if isinstance(data, dict) else None
    if isinstance(projects_raw, list):
        projects = [
            Path(item).expanduser()
            for item in projects_raw
            if isinstance(item, str) and item.strip()
        ]
    else:
        # 旧配置只有最近项目列表，首次加载时直接迁移成项目列表。
        projects = recent
    last_selected_raw = data.get("last_selected_project") if isinstance(data, dict) else None
    last_selected = (
        Path(last_selected_raw).expanduser()
        if isinstance(last_selected_raw, str) and last_selected_raw.strip()
        else None
    )
    repo = _path_from_json(
        data.get("trellis_repo") if isinstance(data, dict) else None,
        DEFAULT_REPO_DIR,
    )
    official_repo_url = _str_from_json(
        data.get("official_repo_url") if isinstance(data, dict) else None,
        OFFICIAL_REPO_URL,
    )
    accelerated_repo_url = _str_from_json(
        data.get("accelerated_repo_url") if isinstance(data, dict) else None,
        ACCELERATED_REPO_URL,
    )
    distribution_branch = _str_from_json(
        data.get("distribution_branch") if isinstance(data, dict) else None,
        DISTRIBUTION_BRANCH,
    )
    developer_name = _clean_name(
        data.get("developer_name") if isinstance(data, dict) else None,
    )
    init_platforms = _clean_platforms(
        data.get("init_platforms") if isinstance(data, dict) else None,
    )
    deduped_projects = _dedupe_paths(projects)
    project_keys = {str(path.expanduser()) for path in deduped_projects}
    if last_selected and str(last_selected.expanduser()) not in project_keys:
        last_selected = deduped_projects[0] if deduped_projects else None
    return ManagerConfig(
        trellis_repo=repo,
        projects=deduped_projects,
        last_selected_project=last_selected,
        recent_projects=_dedupe_paths(recent),
        official_repo_url=official_repo_url,
        accelerated_repo_url=accelerated_repo_url,
        distribution_branch=distribution_branch,
        developer_name=developer_name,
        init_platforms=init_platforms,
    )


def save_config(config: ManagerConfig, config_file: Path = CONFIG_FILE) -> None:
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text(
        json.dumps(_config_payload(config), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def remember_project(project_dir: Path, config_file: Path = CONFIG_FILE) -> ManagerConfig:
    config = load_config(config_file)
    # 这里把最近项目去重后前置，避免 UI 下拉里出现重复路径。
    updated = ManagerConfig(
        trellis_repo=config.trellis_repo,
        projects=config.projects,
        last_selected_project=config.last_selected_project,
        recent_projects=_dedupe_paths([project_dir.expanduser(), *config.recent_projects])[:20],
        official_repo_url=config.official_repo_url,
        accelerated_repo_url=config.accelerated_repo_url,
        distribution_branch=config.distribution_branch,
        developer_name=config.developer_name,
        init_platforms=config.init_platforms,
    )
    save_config(updated, config_file)
    return updated


def save_projects(
    projects: list[Path],
    config_file: Path = CONFIG_FILE,
    last_selected_project: Path | None = None,
) -> ManagerConfig:
    config = load_config(config_file)
    deduped_projects = _dedupe_paths([path.expanduser() for path in projects])
    selected = last_selected_project.expanduser() if last_selected_project else config.last_selected_project
    project_keys = {str(path.expanduser()) for path in deduped_projects}
    if selected and str(selected.expanduser()) not in project_keys:
        selected = deduped_projects[0] if deduped_projects else None
    updated = ManagerConfig(
        trellis_repo=config.trellis_repo,
        projects=deduped_projects,
        last_selected_project=selected,
        recent_projects=config.recent_projects,
        official_repo_url=config.official_repo_url,
        accelerated_repo_url=config.accelerated_repo_url,
        distribution_branch=config.distribution_branch,
        developer_name=config.developer_name,
        init_platforms=config.init_platforms,
    )
    save_config(updated, config_file)
    return updated


def add_project(project_dir: Path, config_file: Path = CONFIG_FILE) -> ManagerConfig:
    config = load_config(config_file)
    project = project_dir.expanduser()
    updated = ManagerConfig(
        trellis_repo=config.trellis_repo,
        projects=_dedupe_paths([*config.projects, project]),
        last_selected_project=project,
        recent_projects=_dedupe_paths([project, *config.recent_projects])[:20],
        official_repo_url=config.official_repo_url,
        accelerated_repo_url=config.accelerated_repo_url,
        distribution_branch=config.distribution_branch,
        developer_name=config.developer_name,
        init_platforms=config.init_platforms,
    )
    save_config(updated, config_file)
    return updated


def remove_project(project_dir: Path, config_file: Path = CONFIG_FILE) -> ManagerConfig:
    config = load_config(config_file)
    target = str(project_dir.expanduser())
    projects = [path for path in config.projects if str(path.expanduser()) != target]
    selected = config.last_selected_project
    if selected and str(selected.expanduser()) == target:
        selected = projects[0] if projects else None
    updated = ManagerConfig(
        trellis_repo=config.trellis_repo,
        projects=projects,
        last_selected_project=selected,
        recent_projects=config.recent_projects,
        official_repo_url=config.official_repo_url,
        accelerated_repo_url=config.accelerated_repo_url,
        distribution_branch=config.distribution_branch,
        developer_name=config.developer_name,
        init_platforms=config.init_platforms,
    )
    save_config(updated, config_file)
    return updated


def save_selected_project(project_dir: Path | None, config_file: Path = CONFIG_FILE) -> ManagerConfig:
    config = load_config(config_file)
    selected = project_dir.expanduser() if project_dir else None
    project_keys = {str(path.expanduser()) for path in config.projects}
    if selected and str(selected.expanduser()) not in project_keys:
        selected = config.projects[0] if config.projects else None
    updated = ManagerConfig(
        trellis_repo=config.trellis_repo,
        projects=config.projects,
        last_selected_project=selected,
        recent_projects=config.recent_projects,
        official_repo_url=config.official_repo_url,
        accelerated_repo_url=config.accelerated_repo_url,
        distribution_branch=config.distribution_branch,
        developer_name=config.developer_name,
        init_platforms=config.init_platforms,
    )
    save_config(updated, config_file)
    return updated


def get_settings(config_file: Path = CONFIG_FILE) -> dict[str, object]:
    config = load_config(config_file)
    return {
        "official_repo_url": config.official_repo_url,
        "accelerated_repo_url": config.accelerated_repo_url,
        "distribution_branch": config.distribution_branch,
        "developer_name": config.developer_name,
        "init_platforms": config.init_platforms,
    }


def save_settings(partial: dict[str, object], config_file: Path = CONFIG_FILE) -> ManagerConfig:
    config = load_config(config_file)
    # 只接受设置页允许修改的字段，缺失项保留当前值，空字符串回退默认值。
    updated = ManagerConfig(
        trellis_repo=config.trellis_repo,
        projects=config.projects,
        last_selected_project=config.last_selected_project,
        recent_projects=config.recent_projects,
        official_repo_url=_str_from_json(partial.get("official_repo_url"), config.official_repo_url),
        accelerated_repo_url=_str_from_json(partial.get("accelerated_repo_url"), config.accelerated_repo_url),
        distribution_branch=_str_from_json(partial.get("distribution_branch"), config.distribution_branch),
        developer_name=_clean_name(partial.get("developer_name")) if "developer_name" in partial else config.developer_name,
        init_platforms=_clean_platforms(partial.get("init_platforms")) if "init_platforms" in partial else config.init_platforms,
    )
    save_config(updated, config_file)
    return updated


def append_operation_log(entry: dict[str, Any], log_file: Path = LOG_FILE) -> None:
    existing = load_operation_logs(log_file)
    existing.insert(0, entry)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    log_file.write_text(
        json.dumps(existing[:MAX_OPERATION_LOGS], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load_operation_logs(log_file: Path = LOG_FILE) -> list[dict[str, Any]]:
    if not log_file.exists():
        return []
    try:
        data = json.loads(log_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]
