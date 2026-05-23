"""
任务快照读取模块。

从业务项目的 .trellis/tasks/ 读取任务数据，生成快照供前端展示。
独立于 .trellis/scripts/ 避免循环依赖。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

import json

# 类型定义
TrellisTaskStatus = Literal["planning", "in_progress", "completed", "done", "unknown"]

VALID_STATUSES: set[str] = {"planning", "in_progress", "completed", "done"}


@dataclass(frozen=True)
class TrellisTaskItem:
    """单个任务快照，对应一个 task.json。"""
    dir_name: str
    path: str
    title: str
    status: TrellisTaskStatus
    raw_status: str
    assignee: str | None
    priority: str | None
    created_at: str | None
    completed_at: str | None
    parent: str | None
    children: list[str]
    child_done: int
    child_total: int
    branch: str | None
    base_branch: str | None
    has_prd: bool
    has_design: bool
    has_implement: bool
    archived: bool
    archive_month: str | None  # 归档月份 YYYY-MM，仅归档任务有值
    error: str | None


@dataclass(frozen=True)
class ArchiveMonthGroup:
    """归档任务按月份分组。"""
    month: str  # YYYY-MM
    tasks: list[TrellisTaskItem]
    error_count: int  # 损坏 task.json 数量


@dataclass(frozen=True)
class TrellisTaskSnapshot:
    """项目任务快照。"""
    project_path: str
    has_trellis: bool
    tasks_dir: str | None
    tasks: list[TrellisTaskItem]
    counts: dict[str, int]
    errors: list[str]
    archived_groups: list[ArchiveMonthGroup]  # 归档任务按月分组
    archive_counts: dict[str, int]  # 归档任务统计


def normalize_status(raw: str) -> TrellisTaskStatus:
    """将 raw_status 转换为规范状态。"""
    if raw in VALID_STATUSES:
        return raw  # type: ignore[return-value]
    return "unknown"


def check_documents(task_dir: Path) -> tuple[bool, bool, bool]:
    """检查任务目录是否有规划文档。"""
    has_prd = (task_dir / "prd.md").exists()
    has_design = (task_dir / "design.md").exists()
    has_implement = (task_dir / "implement.md").exists()
    return has_prd, has_design, has_implement


def load_task_item(task_dir: Path, archived: bool = False, archive_month: str | None = None) -> TrellisTaskItem | None:
    """加载单个任务，返回 None 如果 task.json 不存在或损坏。"""
    task_json = task_dir / "task.json"
    if not task_json.is_file():
        return None

    try:
        data = json.loads(task_json.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        return TrellisTaskItem(
            dir_name=task_dir.name,
            path=str(task_dir),
            title="[损坏的 task.json]",
            status="unknown",
            raw_status="invalid_json",
            assignee=None,
            priority=None,
            created_at=None,
            completed_at=None,
            parent=None,
            children=[],
            child_done=0,
            child_total=0,
            branch=None,
            base_branch=None,
            has_prd=False,
            has_design=False,
            has_implement=False,
            archived=archived,
            archive_month=archive_month,
            error=str(e),
        )

    raw_status = data.get("status", "unknown")
    # 兼容旧归档任务的 subtasks 字段和路径格式
    children = data.get("children", []) or data.get("subtasks", [])
    if isinstance(children, list):
        children = [c.split("/")[-1] if "/" in c else c for c in children]

    return TrellisTaskItem(
        dir_name=task_dir.name,
        path=str(task_dir),
        title=data.get("title") or data.get("name") or task_dir.name,
        status=normalize_status(raw_status),
        raw_status=raw_status,
        assignee=data.get("assignee") or None,
        priority=data.get("priority") or None,
        created_at=data.get("createdAt") or None,
        completed_at=data.get("completedAt") or None,
        parent=data.get("parent") or None,
        children=children if isinstance(children, list) else [],
        child_done=0,  # 后续 compute_children_progress 填充
        child_total=len(children) if isinstance(children, list) else 0,
        branch=data.get("branch") or None,
        base_branch=data.get("base_branch") or None,
        has_prd=False,  # 后续填充
        has_design=False,
        has_implement=False,
        archived=archived,
        archive_month=archive_month,
        error=None,
    )


def compute_children_progress(
    tasks: list[TrellisTaskItem],
    archived_tasks: list[TrellisTaskItem],
) -> list[TrellisTaskItem]:
    """
    计算子任务完成进度，语义与 tasks.py.children_progress 一致：
    - 子任务状态为 completed/done 视为已完成
    - 子任务不在 active 集合中（已归档）也视为已完成
    """
    all_statuses: dict[str, str] = {}
    for t in tasks:
        all_statuses[t.dir_name] = t.status

    # 归档任务的状态也加入（用于判断已归档子任务是否完成）
    for t in archived_tasks:
        all_statuses[t.dir_name] = t.status

    def child_done(child_list: list[str]) -> int:
        return sum(
            1 for c in child_list
            if c not in all_statuses or all_statuses.get(c) in ("completed", "done")
        )

    result = []
    for t in tasks:
        done = child_done(t.children) if t.children else 0
        item_dict = asdict(t)
        item_dict["child_done"] = done
        item_dict["child_total"] = len(t.children) if t.children else 0
        # 文档检查
        task_path = Path(t.path)
        has_prd, has_design, has_implement = check_documents(task_path)
        item_dict["has_prd"] = has_prd
        item_dict["has_design"] = has_design
        item_dict["has_implement"] = has_implement
        result.append(TrellisTaskItem(**item_dict))

    return result


def read_task_snapshot(project_path: str, include_archive: bool = False) -> TrellisTaskSnapshot:
    """读取项目任务快照。include_archive 控制是否扫描归档目录。"""
    path = Path(project_path).expanduser().resolve()
    trellis_dir = path / ".trellis"
    has_trellis = trellis_dir.exists()
    tasks_dir = trellis_dir / "tasks" if has_trellis else None
    errors: list[str] = []

    tasks: list[TrellisTaskItem] = []
    archived_tasks: list[TrellisTaskItem] = []
    archived_groups: list[ArchiveMonthGroup] = []
    archive_counts: dict[str, int] = {"total": 0}

    if tasks_dir and tasks_dir.is_dir():
        # 读取 active 任务（跳过 archive 目录）
        for d in sorted(tasks_dir.iterdir()):
            if not d.is_dir() or d.name == "archive":
                continue
            item = load_task_item(d, archived=False)
            if item:
                if item.error:
                    errors.append(f"{d.name}: {item.error}")
                tasks.append(item)

        # 读取归档任务（按月分组）
        if include_archive:
            archive_dir = tasks_dir / "archive"
            if archive_dir.is_dir():
                for year_month in sorted(archive_dir.iterdir(), reverse=True):
                    if not year_month.is_dir():
                        continue
                    month_tasks: list[TrellisTaskItem] = []
                    error_count = 0
                    for d in sorted(year_month.iterdir()):
                        if not d.is_dir():
                            continue
                        item = load_task_item(d, archived=True, archive_month=year_month.name)
                        if item:
                            if item.error:
                                error_count += 1
                                errors.append(f"archive/{year_month.name}/{d.name}: {item.error}")
                            month_tasks.append(item)
                            archived_tasks.append(item)
                    archived_groups.append(ArchiveMonthGroup(
                        month=year_month.name,
                        tasks=month_tasks,
                        error_count=error_count,
                    ))
                    archive_counts[year_month.name] = len(month_tasks)
                    archive_counts["total"] += len(month_tasks)

    # 计算子任务进度
    tasks = compute_children_progress(tasks, archived_tasks)

    # 统计 active 各状态数量
    counts: dict[str, int] = {
        "planning": 0,
        "in_progress": 0,
        "completed": 0,
        "done": 0,
        "unknown": 0,
    }
    for t in tasks:
        counts[t.status] = counts.get(t.status, 0) + 1

    return TrellisTaskSnapshot(
        project_path=str(path),
        has_trellis=has_trellis,
        tasks_dir=str(tasks_dir) if tasks_dir else None,
        tasks=tasks,
        counts=counts,
        errors=errors,
        archived_groups=archived_groups,
        archive_counts=archive_counts,
    )
