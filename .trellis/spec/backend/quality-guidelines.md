# Quality Guidelines

> Code quality standards for backend development.

---

## Overview

后端质量目标是：桌面 UI 输入不能变成任意 shell 或任意文件读取；Trellis 项目状态读取要兼容旧数据和损坏数据；外部命令必须可测试、可解释、可回滚。变更应保持模块边界小，优先补单元测试而不是依赖手工点击验证。

---

## Forbidden Patterns

- 禁止 `shell=True` 或把用户输入拼成 shell 字符串。命令必须是参数数组，并通过 `CommandRunner` 白名单。
- 禁止绕过 `SafeFileReader` 读取前端传入的业务项目文件路径。
- 禁止在 API 层复制 `task_snapshot.py`、`config.py`、`ops.py` 的业务规则。
- 禁止让批量写操作默认覆盖 dirty 项目。当前约定是默认跳过，只有显式 `allow_dirty=True` 才继续。
- 禁止测试真实用户目录、真实 Trellis 工具仓库、真实 `git/tl/helm` 环境。测试使用 `TemporaryDirectory`、临时 config/log 文件和 FakeRunner。
- 禁止无上限读取大文件或 JSONL。文本读取上限为 `MAX_TEXT_BYTES`，JSONL limit 上限为 `MAX_JSONL_LIMIT`。

---

## Required Patterns

- 命令执行：新增外部命令前先确认是否应加入 `ALLOWED_EXECUTABLES`，并在测试里断言命令数组。
- API 返回：dataclass 通过 `dataclass_to_dict()`、`to_log_entry()` 或模块内 `to_dict()` 转为普通 dict。
- 路径处理：用户输入路径先 `Path(...).expanduser()`，需要安全边界时再 `resolve()` 并断言位于允许根目录内。
- 配置修改：读写都经过 `app/config.py`，新增字段要同时更新 `ManagerConfig`、`_config_payload()`、`load_config()`、`get_settings()` 或相关 save 函数。
- 状态兼容：新增状态字段时保留 raw 值，未知状态映射到 `unknown`，不要让旧数据崩溃。
- 中文注释：代码中新增注释说明“为什么这样做”，不解释代码表面动作。

---

## Testing Requirements

- 后端测试使用 `unittest`，文件放在 `tests/test_*.py`。
- 命令型逻辑用 FakeRunner 断言调用序列和 cwd，例子见 `tests/test_ops.py`。
- 文件安全边界必须覆盖正常读取、路径穿越、符号链接逃逸、超大文件、缺失文件、非 UTF-8、JSONL 坏行分页，例子见 `tests/test_file_reader.py`。
- 任务快照要覆盖无 `.trellis`、空 tasks、各状态、unknown、损坏 task.json、children/subtasks 兼容、archive 月份分组，例子见 `tests/test_task_snapshot.py`。
- watcher 要覆盖路径分类、目录事件过滤、去抖和 JS 事件契约，例子见 `tests/test_watcher.py`。
- API 桥接测试应注入临时 config/log 文件或 fake runner，避免写真实 `~/.beilo-trellis`。

常用校验：

```bash
python3 -m unittest discover tests -v
python3 -m py_compile main.py launcher.py app/*.py scripts/*.py tests/*.py
git diff --check
```

---

## Code Review Checklist

- 新 API 是否只是桥接，业务规则是否放在正确模块？
- 是否存在 `shell=True`、字符串命令拼接、未白名单命令或未测试的外部命令？
- 是否可能读取 `.trellis/` 外部文件、跟随恶意符号链接或一次性读入大文件？
- 配置和操作日志是否保持 JSON 字段兼容、可序列化、有限增长？
- 批量操作是否逐项返回结果，dirty 项目是否默认保护？
- 新状态、字段或任务合同是否同时更新测试和前端消费方？
- 是否补了最接近风险点的单元测试，而不是只改实现？

## Scenario: 项目级 Paseo workflow 执行器

### 1. Scope / Trigger

- Trigger: 新增项目级命令入口，用本地配置驱动 `paseo run` 创建 agent。
- 适用范围：`scripts/run_paseo_workflow.py` 这类 repo-local workflow executor，以及 `.agents/workflows/*.json` 这类 agent 工作流配置。

### 2. Signatures

- CLI 签名：
  - `python3 scripts/run_paseo_workflow.py <workflow> --cwd <path> --task <text> [--input key=value] [--dry-run] [--json]`
- Workflow 配置入口：
  - `.agents/workflows/<workflow>.json`
- Agent-facing 入口：
  - `.agents/skills/<skill-name>/SKILL.md`

### 3. Contracts

- `workflow`: 必须对应 `.agents/workflows/<workflow>.json`。
- `--cwd`: 作为 workflow step 的工作目录输入，执行前要解析为绝对路径。
- `--task`: 用户需求文本，作为必填 workflow input。
- `--input key=value`: 只补充 workflow input，不允许承载 secret。
- `--dry-run`: 只输出解析后的 step 和 command，不得启动 Paseo agent。
- `--json`: 输出结构化结果，供主 agent 或脚本消费。
- Workflow step 至少包含 `id`、`title`、`provider`、`cwd`、`prompt`。

### 4. Validation & Error Matrix

- workflow 文件不存在 -> `WORKFLOW_NOT_FOUND`。
- JSON 无法解析 -> `INVALID_JSON`。
- 缺少必填输入 -> `MISSING_INPUT`。
- 模板变量未解析 -> `UNRESOLVED_TEMPLATE`。
- 前置 artifact 缺失 -> `MISSING_ARTIFACT`。
- Paseo CLI 或 daemon 不可用 -> `PASEO_DAEMON_UNAVAILABLE`。
- step 命令非零退出 -> `PASEO_STEP_FAILED`。

### 5. Good/Base/Bad Cases

- Good: `--dry-run --json` 在没有 Paseo daemon 时仍能展示将要执行的三步计划。
- Base: fake runner 返回成功 JSON，executor 记录 agent id、provider、cwd 和 step 状态。
- Bad: 缺少 `--task` 或 artifact 时必须失败并停止后续步骤，不能继续启动 implement / review agent。

### 6. Tests Required

- 解析有效 workflow 配置并按顺序生成 step。
- 缺少必填 input 时不调用 runner。
- dry-run 时不调用 Paseo。
- fake runner 断言 `paseo run --json --provider ... --cwd ...` 参数数组。
- step 失败后 workflow 状态为 failed，后续步骤不执行。
- artifact 缺失时返回稳定错误码。

### 7. Wrong vs Correct

#### Wrong

```python
subprocess.run(f"paseo run {prompt}", shell=True)
```

#### Correct

```python
runner.run(["paseo", "run", "--json", "--provider", provider, "--cwd", cwd, prompt])
```

命令必须是参数数组，并通过 fake runner 覆盖命令构造，避免用户需求文本被拼进 shell。

## Scenario: 桌面端内置全局技能同步

### 1. Scope / Trigger

- Trigger: 工具仓库安装、更新或 zip 重装成功后，需要把桌面端内置公共技能覆盖到本机 AI 工具全局技能目录。
- 适用范围：`app/ops.py` 中安装/构建成功后的本地文件同步，以及 `scripts/build_app.py` / `scripts/build_standalone_app.py` 的资源打包。

### 2. Signatures

- `sync_bundled_public_skills(source_dir: Path = BUNDLED_SKILLS_DIR, home_dir: Path | None = None) -> dict[str, str]`
- 调用方：`install_or_update_tool_repo(...)`、`install_from_zip(...)`、`install_from_remote_zip(...)`
- 内置资源路径：`resources/skills/<skill>/`
- 本机权威源：`~/.agents/skills/<skill>`
- 工具入口：`~/.codex/skills/<skill>`、`~/.claude/skills/<skill>`

### 3. Contracts

- `source_dir` 必须是目录，且至少包含一个带 `SKILL.md` 的一级子目录。
- 只有包含 `SKILL.md` 的一级子目录视为可分发技能；无效子目录忽略。
- `home_dir` 仅用于测试注入；产品路径默认 `Path.home()`。
- 同步语义是强制覆盖：目标可以是旧目录、文件或历史 symlink；先移除目标入口，再写入新入口。
- 每个技能先复制到 `~/.agents/skills/<skill>`，这是本机唯一权威副本。
- `~/.codex/skills/<skill>` 和 `~/.claude/skills/<skill>` 必须创建为目录 symlink，目标为 `../../.agents/skills/<skill>`。
- `OperationReport.details` 必须包含 `synced_skills`、`synced_skill_count`、`skill_source`、`agents_skill_dir`、`codex_skill_dir`、`claude_skill_dir`，方便操作日志取证。
- 打包脚本必须把 `resources/` 放进应用根目录，保持运行时 `app/ops.py` 可通过 repo/app 根定位资源。

### 4. Validation & Error Matrix

- 内置公共技能根目录不存在 -> `OperationError("内置公共技能目录不存在或不完整：...")`
- 内置公共技能根目录没有任何有效 `SKILL.md` -> 同上
- 目标是 symlink -> `unlink()` symlink 本身，禁止跟随并覆盖 shared source
- 目标是普通目录 -> `shutil.rmtree()` 后复制
- 目标是普通文件 -> `unlink()` 后写入新目录或 symlink
- 目标父目录不存在 -> 自动创建父目录

### 5. Good/Base/Bad Cases

- Good: 构建成功后，`.agents` 得到桌面端内置公共技能副本，Codex 和 Claude Code 全局目录得到指向 `.agents` 的 symlink。
- Base: 同名目标已存在旧目录、旧文件或旧 symlink，安装后被强制替换为新语义。
- Bad: 测试不注入 `home_dir`，导致单测写入真实 `~/.codex` 或 `~/.claude`。

### 6. Tests Required

- 单测覆盖 `sync_bundled_public_skills()` 扫描多个技能、忽略无效目录、覆盖旧目录/文件/symlink。
- 单测必须断言 `~/.agents/skills/<skill>/SKILL.md` 是普通目录副本。
- 单测必须断言 `~/.codex/skills/<skill>` 和 `~/.claude/skills/<skill>` 是 symlink，目标是 `../../.agents/skills/<skill>`。
- 安装/zip 构建测试必须传 `global_skill_home_dir=tmp/home` 和临时 `bundled_skill_source_dir`，避免依赖真实用户目录或当前仓库资源状态。
- 远端 zip 的 `replace=False` + 目标存在要前置阻断，避免先联网下载再失败。
- 打包脚本变更后至少运行 `python3 -m py_compile ... scripts/*.py`。

### 7. Wrong vs Correct

#### Wrong

```python
# 单测写真实 home，污染开发机全局技能目录。
install_from_zip(zip_path, repo_dir, runner=runner)
```

#### Correct

```python
install_from_zip(
    zip_path,
    repo_dir,
    runner=runner,
    global_skill_home_dir=temp_home,
    bundled_skill_source_dir=temp_bundled_skills,
)
```

同步逻辑必须从桌面端内置资源复制，不依赖 `/Users/am/ai-workspace/shared-skills/...` 这类开发机路径。

## Scenario: Trellis 工具分发线和项目迁移更新

### 1. Scope / Trigger

- Trigger: 修改工具仓库默认分发分支、工具仓库构建命令、wrapper 命令可用性检查、或项目 `update` 命令参数。
- 适用范围：`app/config.py` 默认值、`app/ops.py` 的安装/检查/update 逻辑、`app/api.py` 桥接参数、前端 `UpdatePreview` / `ToolCommandStatus` 消费方。
- 分发线身份和 Trellis CLI 兼容版本是两个概念：Manager 项目过期判断使用 CLI package version，不使用 Beilo release tag。

### 2. Signatures

- 默认分发分支：`DISTRIBUTION_BRANCH = "beilo/main"`
- Git 工具仓库构建：`pnpm install` 后执行根 `pnpm build`
- 预览：`preview_project_update(project_dir, runner=None, bin_dir=DEFAULT_BIN_DIR, tool_repo_dir=DEFAULT_REPO_DIR) -> UpdatePreview`
- 更新：`update_project(project_dir, allow_dirty=False, migrate=False, runner=None, bin_dir=DEFAULT_BIN_DIR, tool_repo_dir=DEFAULT_REPO_DIR) -> OperationReport`
- API：`TrellisAPI.update_project(path: str, allow_dirty: bool = False, migrate: bool = False) -> dict`
- 命令检查：`check_wrapper_commands(...) -> list[ToolCommandStatus]`

### 3. Contracts

- `UpdatePreview.requires_migrate` 只表示 Manager 明确识别到 `.trellis/.version` 是 `0.5.x` 且工具仓库 CLI version 是 `0.6.x`。
- `UpdatePreview.would_run_migrations` 可以来自 dry-run migration 信号，也可以来自 `requires_migrate`。
- `update_project(..., migrate=True)` 只能在 `requires_migrate_update(installed, latest)` 为真时执行，否则抛 `OperationError`，不运行 `tl update`。
- 非迁移 update 继续执行 `tl update --force`；迁移 update 执行 `tl update --force --migrate`。
- `OperationReport.details["migrate"]` 必须记录 `"true"` 或 `"false"`，方便操作日志取证。
- `ToolCommandStatus.mem_help_ok` 必须反映 `<wrapper> mem help` 是否成功；`status="ok"` 需要 `--version`、`--help` 和 `mem help` 全部成功。
- 前端新增响应字段时，必须同步更新 `frontend/src/types.ts` 和所有对应组件/调用点，不能靠 `any` 隐式透传。

### 4. Validation & Error Matrix

- `.trellis/.version = 0.5.x` 且 CLI version `0.6.x` -> preview 标记 `requires_migrate=True`，真实执行前要求用户显式确认。
- `.trellis/.version = 0.6.0-beta.*` / `0.6.0-rc.0` / `0.6.x` 且 CLI version `0.6.x` -> 不强制 `--migrate`。
- 用户传 `migrate=True` 但版本不匹配 -> `OperationError("当前项目版本不需要 --migrate，请使用普通 update。")`，不执行 update 命令。
- wrapper `mem help` 失败 -> `ToolCommandStatus.status="error"`，提示用户检查 wrapper 或构建结果。
- Git 工具仓库构建仍使用 filtered CLI build -> 视为回归，因为 `@mindfoldhq/trellis-core` 可能未按根 workspace 顺序构建。

### 5. Good/Base/Bad Cases

- Good: `0.5.19 -> 0.6.0` 预览显示迁移确认，用户勾选后执行 `tl update --force --migrate`。
- Base: `0.6.0-rc.0 -> 0.6.0` 执行普通 `tl update --force`，不出现 migrate 强确认。
- Bad: 所有 update 都默认加 `--migrate`，导致普通模板刷新和版本迁移语义混在一起。
- Bad: wrapper 只检查 `--help`，没有检查 `mem help`，导致 0.6 MEM 子命令损坏时仍显示命令可用。

### 6. Tests Required

- 单测断言 `project_update_command(bin_dir, migrate=True)` 的命令数组包含 `--migrate`。
- 单测覆盖 `preview_project_update()` 对 `0.5.x -> 0.6.x` 设置 `requires_migrate=True`。
- 单测覆盖 `update_project(..., migrate=True)` 只在 `0.5.x -> 0.6.x` 运行 migrate 命令。
- 单测覆盖不需要迁移时传 `migrate=True` 会抛 `OperationError`。
- 单测覆盖 Git 安装/更新使用根 `["pnpm", "build"]`。
- 单测覆盖 `check_wrapper_commands()` 调用 `tl mem help` 和 `trellis mem help`，并序列化 `mem_help_ok`。
- 前端构建必须通过，证明 TS 类型、API 参数和弹窗/表格消费方一致。

### 7. Wrong vs Correct

#### Wrong

```python
# 普通 update 无条件加 migrate，破坏用户对迁移操作的显式确认。
runner.run([str(wrapper_path("tl", bin_dir)), "update", "--force", "--migrate"], cwd=project)
```

#### Correct

```python
requires_migrate = requires_migrate_update(
    read_project_trellis_version(project),
    read_cli_version(tool_repo_dir),
)
if migrate and not requires_migrate:
    raise OperationError("当前项目版本不需要 --migrate，请使用普通 update。")
runner.run(project_update_command(bin_dir, migrate=migrate), cwd=project)
```

迁移判断归后端命令层所有；前端只展示预览结果并收集用户确认，不重新实现版本比较。

## Scenario: 桌面项目动作和外部集成安装

### 1. Scope / Trigger

- Trigger: 修改业务项目卡上的 Init / Configure / Update / 外部集成按钮，或新增业务项目 pywebview 操作。
- 适用范围：`app/ops.py` 项目操作函数、`app/api.py` pywebview 桥接、`app/runner.py` 命令白名单、`frontend/src/api.ts` 包装、`frontend/src/components/ProjectCard.tsx` 状态矩阵、`frontend/src/App.tsx` 操作 handler。
- Trellis 项目生命周期动作和外部集成安装动作必须保持语义分离。

### 2. Signatures

- `init_project(project_dir, platforms, developer_name, runner=None, bin_dir=DEFAULT_BIN_DIR) -> OperationReport`
- `configure_project(project_dir, platforms, developer_name, runner=None, bin_dir=DEFAULT_BIN_DIR) -> OperationReport`
- `update_project(project_dir, allow_dirty=False, migrate=False, runner=None, bin_dir=DEFAULT_BIN_DIR, tool_repo_dir=DEFAULT_REPO_DIR) -> OperationReport`
- `setup_gitnexus_project(project_dir, runner=None) -> OperationReport`
- `gitnexus_setup_command() -> ["npx", "--yes", "gitnexus", "setup"]`
- API bridge:
  - `TrellisAPI.configure_project(path: str) -> dict`
  - `TrellisAPI.setup_gitnexus_project(path: str) -> dict`
- Frontend wrappers:
  - `api.configureProject(path: string): Promise<OperationReport>`
  - `api.setupGitNexusProject(path: string): Promise<OperationReport>`

### 3. Contracts

- `Init` 只适用于 git 项目且项目内没有 `.trellis`；成功后必须继续执行 `tl update --force`。
- `Configure` 只适用于 git 项目且项目内已有 `.trellis`；它复用 Manager 设置里的 `developer_name` 和 `init_platforms`，只运行 `tl init -y ... -u ...`，不得自动运行 `tl update --force`。
- `Update` 只要求 git 项目且项目内已有 `.trellis`；手动按钮不得依赖 `version_outdated`，最新版项目也允许手动执行 `tl update --force`。
- `GitNexus Setup` 只要求 git 项目且项目内已有 `.trellis`；它属于外部集成安装动作，必须先由前端确认，再运行固定参数数组 `npx --yes gitnexus setup`。
- dirty 项目默认阻断 `Update`，除非用户显式允许；dirty 项目不得阻断 `GitNexus Setup`，但确认文案必须提醒可能产生额外 diff。
- `CommandRunner.ALLOWED_EXECUTABLES` 可以包含 `npx`，但 GitNexus 命令参数必须由后端固定构造，禁止从 UI 拼接 shell 字符串。

### 4. Validation & Error Matrix

- 非 git 项目执行任一项目写动作 -> `OperationError("目标项目必须是 git 仓库。")`
- 已有 `.trellis` 执行 `Init` -> `OperationError("目标项目已经存在 .trellis，请使用 update。")`
- 没有 `.trellis` 执行 `Configure` / `Update` / `GitNexus Setup` -> `OperationError("目标项目尚未安装 Trellis，请先 init。")`
- `developer_name` 为空执行 `Init` / `Configure` -> 中文 `OperationError` 提示先配置开发者名
- `init_platforms` 为空执行 `Init` / `Configure` -> 中文 `OperationError` 提示至少选择一个平台
- dirty 项目执行 `Update` 且 `allow_dirty=False` -> 阻断
- dirty 项目执行 `GitNexus Setup` -> 不阻断，日志记录 `dirty_before`

### 5. Good/Base/Bad Cases

- Good: 未初始化 git 项目只启用 `Init`；初始化后启用 `Configure`、`Update`、`GitNexus Setup`。
- Base: 已是最新版的 initialized 项目仍可点击 `Update`，然后走预览和确认弹窗。
- Bad: 把 GitNexus setup 塞进 `Init`，导致首次接入 Trellis 时隐式安装外部集成。
- Bad: `Configure` 运行后自动 `update --force`，让“修改开发者/平台配置”和“同步 Trellis 管理文件”重新混在一起。
- Bad: 前端自己拼 `npx gitnexus setup` 字符串或让用户输入 GitNexus 命令参数。

### 6. Tests Required

- `init_project` 仍拒绝已初始化项目，并断言 init 成功后命令序列包含 `tl update --force`。
- `configure_project` 覆盖配置校验、要求已初始化、只运行 `tl init -y ... -u ...`、不运行 update。
- `update_project` 覆盖 initialized 且 current-version 项目仍可运行普通 update。
- `setup_gitnexus_project` 覆盖要求已初始化、dirty 不阻断、命令数组等于 `["npx", "--yes", "gitnexus", "setup"]`。
- Frontend build 必须通过，证明 API wrapper、ProjectCard props 和 App handler 类型一致。
- UI 状态矩阵改动后至少静态检查 `ProjectCard` 不再用 `version_outdated` 决定手动 Update 是否可点。

### 7. Wrong vs Correct

#### Wrong

```python
# 外部集成被隐式塞进 Trellis Init，用户无法区分副作用来源。
runner.run(project_init_command(platforms, developer_name, bin_dir), cwd=project)
runner.run(["npx", "--yes", "gitnexus", "setup"], cwd=project)
runner.run(project_update_command(bin_dir), cwd=project)
```

#### Correct

```python
def setup_gitnexus_project(project_dir: Path, runner: CommandRunner | None = None) -> OperationReport:
    status = inspect_project(str(project_dir), runner)
    if not status.has_trellis:
        raise OperationError("目标项目尚未安装 Trellis，请先 init。")
    setup_result = runner.run(gitnexus_setup_command(), cwd=status.path, timeout=300)
```

外部集成安装必须是单独按钮、单独确认、单独日志；Trellis Init / Configure / Update 只处理 Trellis 生命周期语义。

## Scenario: 应用发包命令

### 1. Scope / Trigger

- Trigger: 新增或修改 Trellis Manager Desktop 应用版本、打包、GitHub Release 上传命令。
- 适用范围：根 `package.json` 的 `release:*` scripts、`scripts/release.py`、`scripts/build_app.py`、`scripts/build_standalone_app.py`。
- 只发布桌面应用本身；不要把 Trellis 工具仓库分发分支或工具仓库源码 zip 混入应用发包语义。

### 2. Signatures

- `npm run release:version -- <semver>`
- `npm run release:package`
- `npm run release:package -- --clean`
- `npm run release:publish -- <semver> [--dry-run] [--replace]`
- 内部入口：`python3 scripts/release.py <version|package|publish> ...`

### 3. Contracts

- 根 `package.json.version` 是唯一应用版本源。
- `frontend/package.json.version` 只属于前端私有包，不代表应用版本。
- `release:version` 自动更新根版本、创建版本提交、创建本地 `v<semver>` tag；提交消息必须遵守 `.commit-suffix.json` 的分支后缀。
- `release:package` 默认复用 `frontend/node_modules`，执行 `npm install` 和 `npx vite build`；只有显式 `--clean` 才删除前端依赖目录。
- `release:publish --dry-run` 不得 push、创建 release 或上传 asset。
- `--replace` 只允许覆盖同名 release asset，不得删除 tag 或整份 release。

### 4. Validation & Error Matrix

- semver 不合法 -> 失败并提示合法格式。
- 工作区不干净 -> 失败并列出 `git status --short`。
- 本地 tag 已存在 -> `release:version` 失败。
- 根版本和命令版本不一致 -> `release:publish` 失败。
- 缺少版本化 zip -> `release:publish` 失败，不触发远端命令。
- app bundle `Info.plist` 版本和根版本不一致 -> 失败。
- zip 产物早于版本提交 -> 失败，要求重新打包。
- 远端 tag/release/asset 已存在且没有 `--replace` -> 失败。
- `gh release view` 因非 not-found 原因失败 -> 失败；不要当作 release 不存在。

### 5. Good/Base/Bad Cases

- Good: `release:publish --dry-run` 只打印将执行的 `git` / `gh` 命令，FakeRunner 中不出现 `git push` 或 `gh release create` 调用。
- Base: `release:package` 生成 `dist/standalone/Trellis Manager-<version>-macos-arm64.zip`，并写入匹配的 `CFBundleShortVersionString`。
- Bad: 默认发布路径直接使用 `gh release upload --clobber` 覆盖线上 asset，没有显式 `--replace`。

### 6. Tests Required

- semver 校验和 `v` tag 前缀。
- 根 `package.json.version` 读写。
- `release:version` 的 `git add` / `git commit` / `git tag` 命令数组和 commit suffix。
- `release:publish --dry-run` 不调用 push/create/upload。
- `release:publish --replace` 只使用 `gh release upload ... --clobber`，不调用 `gh release delete`。
- 构建脚本版本化 zip 路径和 plist 版本写入。

### 7. Wrong vs Correct

#### Wrong

```python
subprocess.run(f"gh release upload {tag} {zip_path} --clobber", shell=True)
```

#### Correct

```python
runner.run(["gh", "release", "upload", tag, str(zip_path), "--clobber"], cwd=root)
```

发布命令必须用参数数组和 fake runner 覆盖；`--clobber` 只能在显式 `--replace` 时出现。
