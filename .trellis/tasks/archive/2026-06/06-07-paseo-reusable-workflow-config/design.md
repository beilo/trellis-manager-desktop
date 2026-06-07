# Design

## Boundary

本任务新增项目级 agent 工作流资产，不改桌面客户端业务功能。

首版边界：

- 新增一个可复用 workflow 配置，用来描述 PRD -> Implement -> Review 的线性多 agent 流程。
- 新增一个轻量执行入口，读取 workflow 配置并调用 Paseo CLI。
- 新增一个 agent-facing 入口，让主 agent 可以按名称调用 workflow。
- 增加针对配置解析、dry-run、命令构造和失败处理的测试。

明确不做：

- 不修改 `@getpaseo/cli`、Paseo daemon 或 upstream Paseo package。
- 不新增 Trellis Manager Desktop UI 页面。
- 不启动真实 agent 作为测试依赖。
- 不把该能力做成通用 DAG workflow engine。

## Grill 结论

文档压力测试后的关键结论：

- 项目 README 的产品边界是 Trellis Manager Desktop，但本需求属于 agent 工作流资产，不属于桌面 UI 功能。
- `.trellis/workflow.md` 已定义 `prd.md`、`design.md`、`implement.md` 的职责边界，工作流必须复用这些术语，不能发明新的规划文档层级。
- `.trellis/config.yaml` 中 Codex 默认是 inline 模式；因此首版不能假设 Codex 自带 Trellis sub-agent 上下文继承，必须通过 prompt 和显式 artifact 路径传递上下文。
- 项目没有 `CONTEXT.md` 或 ADR，因此不新增 glossary / ADR；本次设计记录在 Trellis task 文档中即可。
- `task.py validate <task-dir>` 是本任务规划阶段可用的 Trellis 校验入口。

## Architecture

采用三层结构：

1. Workflow 配置层
   - 保存可复用流程定义。
   - 描述输入、步骤、prompt 模板、provider、cwd / worktree、等待策略和失败策略。

2. Executor 层
   - 读取并校验配置。
   - 解析用户输入。
   - 做变量替换。
   - 在 dry-run 时只输出解析后的执行计划。
   - 在执行时通过 Paseo CLI adapter 创建 agent、等待结果、读取状态。

3. Agent skill / command 层
   - 给主 agent 一个稳定入口。
   - 负责把用户自然语言请求映射为 workflow 名称和输入。
   - 不直接实现 Paseo 调度细节。

## Workflow Contract

首版 workflow 配置应表达以下字段：

- `name`: workflow 名称。
- `description`: workflow 用途。
- `inputs`: 必填和可选输入定义。
- `steps`: 有序步骤列表。
- `step.id`: 步骤唯一标识。
- `step.title`: Paseo agent 标题。
- `step.provider`: Paseo provider 或 provider/model。
- `step.cwd`: 工作目录模板。
- `step.prompt`: prompt 模板。
- `step.wait`: 是否等待完成。
- `step.stopOnFailure`: 失败是否停止后续步骤。
- `step.requiresArtifacts`: 步骤开始前必须存在的 artifact。
- `outputs`: 执行结果字段约定。

首版只支持线性步骤。后续如果确实需要并行或分支，再新增 schema 版本。

## Default Workflow

默认工作流名称：`prd-impl-review`。

步骤：

1. `plan`
   - Provider: Codex。
   - 输入：需求文本、cwd。
   - 输出：Trellis `prd.md`、`design.md`、`implement.md`。
   - 失败条件：规划文档缺失、agent 失败、超时。

2. `implement`
   - Provider: Claude Code。
   - 输入：cwd、规划文档。
   - 输出：实现改动和实现摘要。
   - 前置条件：规划文档存在。
   - 失败条件：agent 失败、超时、未给出摘要。

3. `review`
   - Provider: Codex。
   - 输入：cwd、规划文档、实现改动。
   - 输出：review findings 或明确无问题。
   - 前置条件：implementation 步骤成功。
   - 失败条件：agent 失败、输出无法判断、配置要求 review 通过但存在阻断问题。

## Paseo Adapter

Executor 不直接依赖 Paseo 内部包，优先通过 CLI 调用。

Adapter 职责：

- 检查 Paseo daemon 是否可连接。
- 构造 `paseo run` 调用。
- 支持 provider、cwd、title、worktree、wait-timeout。
- 支持 dry-run 返回命令计划而不执行。
- 解析 JSON 输出。
- 在失败时保留原始 stderr / stdout 摘要，便于主 agent 判断。

不在 adapter 中实现业务流程判断。流程判断留在 executor。

## Trellis Integration

Workflow 不替代 Trellis task。

当在 Trellis repo 中执行时：

- 规划步骤必须围绕当前 task 的 `prd.md` / `design.md` / `implement.md`。
- 实施步骤必须读取这些 artifacts。
- Review 步骤必须对照这些 artifacts。
- 不自动 `task.py start`，除非后续明确把启动任务纳入 workflow 输入和用户确认流程。

## Failure Handling

失败统一按“失败即停”处理。

必须显式处理：

- workflow 文件不存在。
- workflow 名称不存在。
- 必填输入缺失。
- 模板变量未解析。
- Paseo CLI 不存在。
- Paseo daemon 不可连接。
- Paseo command 非零退出。
- agent 没有在等待时间内完成。
- 前置 artifact 缺失。
- review 步骤返回阻断问题。

失败报告至少包含：

- workflow 名称。
- step id。
- 失败类型。
- 可操作的下一步。
- 关联 agent id，如果已经创建。

## Testing Strategy

首版测试不启动真实 Paseo agent。

测试 seam：

- Workflow parser：配置解析、schema 校验、默认值。
- Template resolver：输入变量替换、未解析变量失败。
- Executor：步骤顺序、前置 artifact 检查、失败即停。
- Paseo adapter：用 fake command runner 验证命令构造和 JSON 解析。
- Dry-run：证明不会执行命令。

## Compatibility

- 该能力是新增项目级工具，不改变现有 Trellis Manager Desktop 行为。
- 如果用户没有安装 Paseo，dry-run 仍应可用；真实执行应明确提示安装或启动 Paseo。
- 如果 provider 名称后续变化，只需要修改 workflow 配置，不应修改 executor 核心逻辑。

## Rollback

回滚方式简单：删除 workflow 配置、执行入口、agent-facing 入口和对应测试。

由于不修改 Paseo、Trellis task 生命周期或桌面 UI，回滚不会影响现有产品功能。
