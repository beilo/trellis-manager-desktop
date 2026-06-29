# Changelog

## [Unreleased]

### Added

- **内置 Trellis 源码 zip 安装**：发布流程会从同级 `../Trellis` 生成 `resources/trellis-source.zip` 并打入 `.app`，工具链页新增弱网推荐的内置 zip 安装/重装入口；本地外部 zip 和远端 zip 入口保留，操作日志用 `embedded_zip_snapshot` / `local_zip_snapshot` / `remote_zip_snapshot` 区分来源。
- **前端 UI 规范**：新增 `.trellis/spec/frontend/`，记录 Header segmented tabs 的选中态 hover 覆盖约定，避免 `Button ghost` 默认 hover 背景覆盖滑块选中态。

### Changed

- **ProjectCard 按钮统一 variant**：Init / Update 按钮移除条件 `className` 颜色覆盖，统一使用 `variant="default"`，不需要时通过 `disabled` 表达状态，与其他按钮规范一致。
- **默认分发分支**：工具仓库默认分发分支从 `sync/v0.6.0-rc` 调整为 `beilo/main`，新配置和前端恢复默认会跟随 Beilo 自有发布线；工具版本展示仍使用 Trellis CLI 兼容版本。
- **0.6 迁移更新**：业务项目从 `0.5.x` 升级到 `0.6.x` 时，Update 预览会要求显式确认后执行 `tl update --force --migrate`；其他更新保持普通 `tl update --force`。
- **Header Tab 选中 hover 态**：选中的看板 / 工具链 / 项目入口 hover 时保持透明背景和主色文字，避免 Button ghost 默认深色 `muted` 背景覆盖滑块选中态。
- **按钮式当前态 hover**：Tabs 当前项、工具链设置平台多选按钮和表格选中行 hover 时保持当前态颜色，避免基础组件默认 hover 覆盖选中反馈。
- **前端交互浅色底**：基础 Button / Badge、默认 Tabs 容器，以及项目列表、任务列表、文件树、JSONL 行、批量更新行和看板卡片的交互背景从深色 `muted` 改为浅色 `accent`。
- **Accent 主题 token**：`index.css` 的 Tailwind theme 导出 `--color-accent` / `--color-accent-foreground`，确保 `bg-accent` 等类实际生成浅色样式。
- **前端 UI code-spec**：补充 Tailwind 语义色 token 契约，明确 `:root` 源变量和 `@theme inline --color-*` 导出必须同时存在，并记录对应静态/浏览器检查。
- **代码与信息块浅色底**：命令复制行、Markdown code/pre、JSONL 预览、工具仓库路径、项目路径、Git 指标卡、zip 安装区和卡片 / 表格 footer 等静态信息背景改用浅色 `accent` 系列，避免实色 `muted` 深灰块破坏亮色主题。
- **任务 Markdown 详情布局**：任务管理双栏、任务详情卡片、Tab 内容和 Markdown 表格容器补充 `min-w-0` / 内部滚动约束，避免点击 PRD / Design / Implement 后长 Markdown 内容撑大右侧面板。
- **任务详情主 Tab 精简**：移除 Context 入口，任务详情主 Tab 只保留详情、PRD、Design、Implement，避免 agent 内部上下文记录干扰核心任务文档阅读。
- **移除暗色主题，固定亮色主题**：删除系统主题自动同步、`.dark` CSS 变量块和所有 `dark:` Tailwind 类名，应用不再随系统 `prefers-color-scheme` 切换主题。

### Added

- **Trellis 后端规范初始化**：填充 `.trellis/spec/backend/` 的目录结构、持久化、错误处理、日志和质量规范，基于当前 `app/` 与 `tests/` 的真实模块边界、JSON 持久化、CommandRunner 白名单、安全文件读取、watcher 降级和 unittest/FakeRunner 测试模式记录约定。
- **远端源码 zip 下载安装**：工具链页新增「远端源码 zip 安装」区域，Manager 根据当前配置的官方 Git 仓库地址和分发分支自动推导 GitHub codeload zip 下载地址，一键下载并复用现有 zip 安装安全流程完成安装或重装。
  - 后端新增 `github_branch_zip_url` 推导 codeload zip 下载地址（支持 HTTPS/SSH GitHub URL，非 GitHub 返回 None）
  - 后端新增 `_download_zip` 使用标准库下载 zip 到临时目录，120s 超时
  - 后端新增 `install_from_remote_zip` 下载远端 zip 后复用 `install_from_zip` 安全安装流程（解压校验 / 备份替换 / pnpm install & build），返回 `source_type=zip_snapshot` 和 `download_url`
  - 后端 API 新增 `get_github_branch_zip_url` 和 `install_from_remote_zip` 桥接方法
  - 前端 `RepoCard` 新增「远端源码 zip 安装」区域，按钮文案随仓库状态变化（下载 zip 并安装 / 下载 zip 并重装 / 下载并安装中…），非 GitHub 仓库显示不可用提示
  - 前端 `api.ts` 新增 `getGithubBranchZipUrl` 和 `installFromRemoteZip`，旧后端兼容降级
  - 前端 `App` 新增 `githubBranchZipUrl` 状态和 `handleInstallFromRemoteZip` 处理流程
  - 测试新增 8 个用例：URL 推导（HTTPS/SSH/非 GitHub/畸形/无.git 后缀）、远程安装（非 GitHub 阻断、下载失败清理、replace=False 阻断）
  - PRD：`docs/specs/2026-06-05-remote-source-zip-install-prd.md`
  - 实施计划：`docs/specs/2026-06-05-remote-source-zip-install-implement.md`
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

- **远端源码 zip 重装**：zip 快照安装改为走根 `pnpm build` 统一入口，保持与 clean 端构建顺序一致，避免 `@mindfoldhq/trellis-core/channel` 等 workspace 二级导出缺少 dist/types 时导致重装失败。
- **开发模式启动**：`run.sh dev` 固定使用 Vite 5173 端口，启动后等待 `http://localhost:5173/` 可访问再打开 pywebview 桌面壳，避免桌面窗口抢先加载 dev server 或端口漂移导致白屏。
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
