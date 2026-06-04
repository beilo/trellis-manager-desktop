# Changelog

## [Unreleased]

### Added

- **本地源码 zip 安装**：工具链页新增「本地源码 zip 安装」区域，支持从本地 zip 文件安装/重装 Trellis 工具源码，无需 GitHub 访问。
  - 后端新增 `is_valid_source_tree` 验证源码树（不依赖 `.git`）、`_safe_extract_zip` 安全解压（拒绝路径遍历）、`install_from_zip` 安装/重装（备份-交换-清理策略）
  - 后端新增 `github_branch_url` 从仓库 URL 推导 GitHub 分支页面链接
  - `check_tool_repo` 扩展 `source_type` 字段（git/zip_snapshot/invalid/missing），zip 快照显示独立状态文案，不执行 `git fetch`
  - 前端 `RepoCard` 新增「打开分发分支」外链、「本地源码 zip 安装」输入框与安装/重装按钮，zip 快照状态下禁用 Git 更新按钮
  - 前端 `App` 新增 `handleInstallFromZip` 处理 zip 安装流程
- **Manager P3 批量 Update 与配置页**：项目列表新增批量 Update 入口与结果对话框，工具链页新增设置齿轮，配置页复用现有 settings API 并支持 URL / 分支校验、恢复默认和保存持久化。
- **前端文件监听自动刷新**：接入 `window.onTrellisFileChange`，任务变更自动刷新当前项目任务管理与跨项目看板，版本变更自动刷新当前项目健康状态，并保留旧后端 no-op 降级。
- **Manager 批量项目更新 API**：新增落后项目筛选、批量更新聚合结果、dirty 默认跳过、单项失败继续执行、单条聚合 operation log、pywebview 桥接与前端类型/API 包装，并补充后端与桥接单元测试。
- **SafeFileReader 与 Trellis 文件读取 API**：新增受限只读文件读取后端、任务文档/Context JSONL 桥接 API、前端类型与 API 包装，并补充路径穿越、符号链接逃逸、超大文件、缺失文件、非 UTF-8 与 JSONL 部分成功单元测试。
- **Git 摘要与 Update 预览 API**：新增项目 Git 摘要读取、`tl update --force --dry-run` 预览、pywebview 桥接与前端类型包装，并补充对应单元测试。
- **Update 预览确认流**：单项目 Update 改为先 dry-run 预览再弹窗确认，预览失败禁用最终确认，dirty 且未显式允许时要求在弹窗内二次确认，并保留最终执行后的日志输出与状态刷新。
- **任务文档与 Context 预览**：任务详情新增详情 / PRD / Design / Implement / Context Tab，Markdown 使用安全只读渲染，JSONL 支持分页加载与 raw JSON 展开。
- **项目 Git 与知识库面板**：项目页新增只读 Git 快捷面板、任务 / 知识库切换、`.trellis/spec` 与 `.trellis/workspace` 文件树浏览，并复用 Markdown / JSONL viewer。
- **批量 Update 与工具链设置 UI**：项目列表新增批量 Update 入口，工具链页新增仓库 URL / 镜像 / 分发分支设置卡片，保存后供后续检查与下载更新使用。

### Changed

- **项目 Git 快捷面板**：改为项目卡片下方可折叠只读面板，并补充最近提交日期展示。

### Added

- **Manager P0 UI**：新增项目健康指示、三列跨项目看板与 Cursor 打开入口。

#### 后端

- `app/api.py`：新增 `check_cursor_status`，优先检查 `/Applications/Cursor.app` 和用户应用目录，缺失时用 `mdfind` 兜底检测 Cursor。
- `app/api.py`：新增 `open_in_cursor`，优先通过 Cursor CLI 打开项目根目录，缺失时回退 `open -a Cursor <path>`，避免 shell 拼接风险。

#### 前端

- `api.ts`：新增 `checkCursorStatus` 和 `openInCursor` 包装，并兼容旧 pywebview 后端缺少 Cursor API 的情况。
- `App.tsx`：启动检查中加入 Cursor 可用性检查，统一记录中文操作日志，并把 Cursor 状态传给项目和任务详情入口。
- `ProjectCard.tsx`：新增“在 Cursor 中打开”按钮，按 Cursor 检查结果显示禁用原因。
- `ProjectList.tsx`：新增 compact 健康 pill，可区分未初始化、版本过期、Dirty、正常和未检查状态。
- `KanbanPanel.tsx`：跨项目看板改为“规划中 / 进行中 / 已完成”三列布局，`completed` 与 `done` 合并展示，搜索、排序和刷新继续保留。
- `TaskDetail.tsx`：活跃任务新增 Cursor 入口，打开项目根目录，并以内联中文反馈展示失败原因。

#### 测试

- `tests/test_ui.py`：新增 Cursor 检查与打开桥接测试，覆盖常见安装路径和 `mdfind` 兜底路径。

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

### Added

- **文件监听后端**：新增 Trellis 项目文件变更监听事件源，支持 `task.json`、任务目录创建与 `.trellis/.version` 变化检测
- 后端事件契约文档：`docs/specs/2026-05-24-file-watcher-events.md`
- 规划阶段补充 watcher 事件契约、降级策略与去抖要求
