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
