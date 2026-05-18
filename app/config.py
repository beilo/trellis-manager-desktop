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


@dataclass(frozen=True)
class ManagerConfig:
    trellis_repo: Path = DEFAULT_REPO_DIR
    recent_projects: list[Path] = field(default_factory=list)


def _path_from_json(value: object, fallback: Path) -> Path:
    if not isinstance(value, str) or not value.strip():
        return fallback
    return Path(value).expanduser()


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
    repo = _path_from_json(
        data.get("trellis_repo") if isinstance(data, dict) else None,
        DEFAULT_REPO_DIR,
    )
    return ManagerConfig(trellis_repo=repo, recent_projects=_dedupe_paths(recent))


def save_config(config: ManagerConfig, config_file: Path = CONFIG_FILE) -> None:
    config_file.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "trellis_repo": str(config.trellis_repo.expanduser()),
        "recent_projects": [str(path.expanduser()) for path in _dedupe_paths(config.recent_projects)],
    }
    config_file.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def remember_project(project_dir: Path, config_file: Path = CONFIG_FILE) -> ManagerConfig:
    config = load_config(config_file)
    # 这里把最近项目去重后前置，避免 UI 下拉里出现重复路径。
    updated = ManagerConfig(
        trellis_repo=config.trellis_repo,
        recent_projects=_dedupe_paths([project_dir.expanduser(), *config.recent_projects])[:20],
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
