# Changelog

## [Unreleased]

### Added

- **任务管理系统**：新增只读任务看板，支持查看 Trellis 项目的任务列表和详情

#### 后端

- `app/task_snapshot.py`：新增任务快照读取模块
  - `TrellisTaskItem`：单个任务快照数据结构
  - `TrellisTaskSnapshot`：项目任务快照数据结构
  - `read_task_snapshot()`：读取项目任务，支持 archive 可选扫描
  - `compute_children_progress()`：计算子任务完成进度
  - `check_documents()`：检查任务文档完整度（prd.md/design.md/implement.md）
  - `normalize_status()`：状态规范化
- `app/ops.py`：导入 task_snapshot 模块
- `app/api.py`：新增 `list_project_tasks` 和 `open_task_directory` API 方法

#### 前端

- `types.ts`：新增 `TrellisTaskStatus`、`TrellisTaskItem`、`TrellisTaskSnapshot` 类型
- `api.ts`：新增 `listProjectTasks` 和 `openTaskDirectory` API 包装
- `TaskStatusBadge.tsx`：任务状态 Badge 组件
- `TaskListItem.tsx`：任务列表行组件
- `TaskList.tsx`：任务列表组件，支持状态排序
- `TaskDetail.tsx`：任务详情组件，含元数据、文档、命令复制
- `TaskManagerPanel.tsx`：任务管理面板顶层容器
- `App.tsx`：集成 TaskManagerPanel

#### 测试

- `tests/test_task_snapshot.py`：14 个单元测试覆盖
  - 无 .trellis、空 tasks、损坏 JSON
  - 各种任务状态（planning/in_progress/completed/unknown）
  - 子任务进度计算、归档子任务处理
  - 文档完整度检查

### 暂未实现

- 直接执行 start/archive/create 命令（需 AI 会话上下文）
- 跨项目统一任务看板
- archive 任务默认展示
