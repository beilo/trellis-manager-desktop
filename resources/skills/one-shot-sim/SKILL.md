---
name: one-shot-sim
description: >-
  当用户明确提到 one-shot-sim、one shot sim、oneshot sim、一轮完成、简化版
  one-shot、简化版一轮完成，或在 Trellis 一轮完成简化版语境里提到法拉利模式、
  拖拉机模式时触发。English draft: Trigger when the user explicitly says
  one-shot-sim, one shot sim, oneshot sim, simplified one-shot, Ferrari mode,
  tractor mode, or asks to use the current simplified Trellis one-shot workflow.
---

# Trellis 一轮完成

简化版 Trellis one-shot。核心差异：

- 不使用 Trellis channel runtime。
- 不调用、不启动、不委派任何子代理。
- 不包含 `grill-with-docs` 阶段。
- 所有阶段由主会话按顺序直接执行。
- 稳定阶段 ID 是协议主体：`brainstorm`、`plan`、`execute`、`finish`。

## Stage Selection

默认使用自动挡。按用户明确给出的稳定阶段执行：`brainstorm`、`plan`、`execute` 或 `finish`。

模式关键词：

- `法拉利`、`法拉利模式` 等同于 `自动挡` / `auto mode`。
- `拖拉机`、`拖拉机模式` 等同于 `手动挡` / `manual mode`。

如果用户只说 “one-shot-sim” 或 “继续 one-shot-sim”，先根据当前上下文定位阶段，并按默认自动挡推进：

- 没有 Brainstorming / 需求讨论结论：进入 `brainstorm`。
- 已有 `brainstorm` 结论但还没有 task：进入 `plan`，并在 `plan` 完成后自动推进到 `execute`。
- task 已存在且规划文档完整：进入 `execute`。
- 没有 active task、没有 task 文件，但用户给的是明确小改动或修复请求：进入 `execute` 的 no-task 路径。
- `execute` 已完成且需要提交、归档、记录 journal：进入 `finish`。
- 无法判断阶段时，停下并问用户当前要跑哪个阶段。

手动挡规则：

- 只有用户明确说 `拖拉机`、`拖拉机模式`、`手动挡`、`manual mode`、`只跑当前阶段`、`不要自动推进`、`不要自动跑到最后` 时，mode 才是 `manual`。
- 每次只执行用户指定或根据上下文定位出的当前阶段。
- 阶段结束后输出阶段结论和下一阶段入口，然后停止等待用户继续。
- 手动挡下，`brainstorm` 不自动进入 `plan`。

自动挡规则：

- 默认 mode 是 `auto`；用户明确说 `法拉利`、`法拉利模式`、`自动挡`、`自动推进`、`auto mode`、`自动跑到最后`、`自动跑完整流程` 时也视为 `auto`。
- `brainstorm` 必须完整遵循 `trellis-brainstorm`，不因为默认自动挡而合并、跳过或降低提问强度。
- 已有 `brainstorm` 结论后，自动进入 `plan`，新建 task 并完成 Trellis Plan Flow。
- `plan` 完成后，主会话直接进入 `execute`。
- `execute` 完成后，主会话直接进入 `finish`，完成 work commits、适用时 archive、journal 和收尾 commit。
- 自动挡目标是跑到 `finish` 完成；中途只有出现阻塞、失败、破坏性风险或需要用户确认的问题时才停止。

## Global Rules

- 以当前仓库为准，先运行 `python3 ./.trellis/scripts/get_context.py` 确认 Trellis 上下文、active task 和 git 状态。
- 禁止使用 Trellis channel runtime：不要运行 `trellis channel ...`，不要等待 channel message，不能把 channel 不可用当作阻塞。
- 禁止使用子代理：不要 spawn/启动/调用 explorer、implement、check、finish-work 或任何其他子代理。
- 主会话可以读取 task 规划文档、spec、代码和工具输出，并直接完成实现、检查、沉淀、提交、归档。
- 不要把 `.trellis/agents/*.md` 当作必须执行的 agent 流程；本 skill 已经定义主会话执行流程。
- 始终显式标注当前稳定阶段 ID：`brainstorm`、`plan`、`execute`、`finish`。不要只说“计划阶段”或“下一阶段”。
- 每个阶段结束时输出阶段结论和下一阶段入口，例如：`brainstorm 完成 -> plan`。手动挡阶段结束后停止；自动挡在 `plan -> execute -> finish` 之间连续推进。
- 阶段信息必须传递到后续阶段：`plan` 必须基于 `brainstorm` 的需求结论；`execute` 必须基于 `plan` 的规划产物。
- `brainstorm` 完全遵循 `trellis-brainstorm`；`one-shot-sim` 只负责阶段选择和阶段接续，不改写提问节奏、门禁、产物规则或用户确认规则。
- `brainstorm` 内如与本文件冲突，以 `trellis-brainstorm` 为准。
- 外部资料和当前信息优先用 smart-search；本地代码理解优先用 fast_context_search。
- 发现无关脏改时报告并保留，不清理、不回滚、不提交。
- 破坏性操作或无法判断文件归属时，立即停止并说明阻塞点。

<skill_dependencies>
  - `trellis-brainstorm` 必须产出可识别的 `brainstorm` 需求结论：目标、边界、约束、验收标准、未决问题。
  - 如果 `trellis-brainstorm` 没有给出明确完成结论，不得假定 `brainstorm` 完成。
  - 如果 `trellis-brainstorm` 的输出格式变化，以其语义结论为准；无法判断时停止并说明需要同步 `one-shot-sim` 阶段判断。
</skill_dependencies>

## Output Contract

- 所有面向用户的输出必须使用中文，包括阶段结论、最终状态、提交清单、检查结果、错误说明、剩余脏改说明和下一步提示。
- 保留命令、文件路径、commit hash、分支名、工具名和工具原始输出的原文。
- 不要使用英文模板标题，例如 `Commits`、`Final state`、`Checks done`；改用 `提交记录`、`最终状态`、`检查结果`。
- 如果引用英文工具输出，先给中文结论，再贴必要原文片段。
- 每个阶段开始、阶段完成、阻塞或报错时，都输出流程进度块。进度块必须放在该次回复开头，使用固定 4 行格式：

```text
✓ brainstorm 需求讨论
→ plan 新建 task 和 Plan Flow
  execute Execute Flow
  finish Finish Flow
```

- 进度符号含义：`✓` 已完成，`→` 当前进行中或当前阻塞阶段，空格表示未开始。
- 若当前处于某阶段开始，该阶段用 `→`；若刚完成某阶段并即将进入下一阶段，已完成阶段用 `✓`，下一阶段用 `→`。自动挡连续推进时，每次对用户可见更新都展示最新进度。
- `finish` 完成时输出 4 行全 `✓`，并在下一行写：`一轮完成已完成。`

## Plan Flow

目标：按 `brainstorm -> plan` 的状态机推进。不要跳步，不要把两个阶段合并成一次普通计划。

### brainstorm

<stage id="brainstorm" name="Brainstorming / 需求讨论">
  <applies_only_to>brainstorm</applies_only_to>
  <do_not_apply_to>plan, execute, finish</do_not_apply_to>

  <rules>
    完整加载并执行 `trellis-brainstorm`。

    - 按 `trellis-brainstorm` 的提问、证据、产物和用户确认规则执行。
    - `one-shot-sim` 不降低 `trellis-brainstorm` 的提问强度，不替它判断“可以少问”。
    - 只有 `trellis-brainstorm` 自己判定 `brainstorm` 完成后，才能进入 `plan`。
  </rules>

  <completion>
    - `trellis-brainstorm` 的完成标准已满足。
    - 手动挡：输出 `brainstorm` 结论和 `plan` 入口，然后停止等待用户继续。
    - 自动挡：确认已有 `brainstorm` 结论后，进入 `plan`。
  </completion>
</stage>

### plan

<stage id="plan" name="新建 task 和 Plan Flow">
  <applies_only_to>plan</applies_only_to>
  <do_not_apply_to>brainstorm, execute, finish</do_not_apply_to>

  <rules>
    新建 task，进入 Trellis Plan Flow 阶段。

    - 只能基于 `brainstorm` 的需求结论创建 task。
    - 如果 Plan Flow 里出现需要用户确认的问题，返回 `brainstorm` 处理，不擅自继续。
    - 产出 task 规划文档后，明确当前处于 `plan`。手动挡停止等待用户继续；自动挡直接进入 `execute`。
  </rules>

  <completion>
    - 需求、约束、验收标准清楚。
    - task 已创建，并产出完整规划文档。
    - 有需要用户确认的问题时已停止等待。
    - 手动挡：输出 `plan` 结论、task 名称和规划产物路径，然后停止等待用户明确批准 `execute`。
    - 自动挡：输出 `plan` 结论、task 名称和规划产物路径，然后直接进入 `execute`。
  </completion>
</stage>

## execute

<stage id="execute" name="Execute Flow / 主会话直接执行">
  <applies_only_to>execute</applies_only_to>
  <do_not_apply_to>brainstorm, plan, finish</do_not_apply_to>

  <rules>
    目标：由主会话直接实现、检查和沉淀，不使用 channel，不使用子代理。支持 task-backed 路径，也支持没有 task 文件的 no-task 路径。

    <preconditions>
      - task-backed 路径：task 已存在且有完整规划文档。用户未提供 task 时，默认当前 active task。
      - no-task 路径：没有 active task、没有 task 文件，但用户请求已经足够明确，可以直接实现；此时以当前对话作为需求来源。
      - 已确认不使用 Trellis channel runtime。
      - 已确认不使用任何子代理。
    </preconditions>

    <required_order>
      1. task-backed 路径读取当前 task 的 PRD、design、implement 计划材料和相关 spec；no-task 路径读取当前对话、相关 spec 和必要代码上下文。
      2. 只修改本任务相关文件；发现无关脏改时报告并保留。
      3. task-backed 路径按计划材料实现；no-task 路径按用户当前明确请求实现。有疑问按推荐方案继续，除非遇到破坏性风险、无法判断文件归属或缺少关键上下文。
      4. 主会话执行 `trellis-check`；检查逻辑只围绕本任务 diff、task artifacts 和相关 spec。
      5. 主会话执行 `trellis-update-spec`；有沉淀内容就更新 spec，没有则明确说明。
    </required_order>

    <check_scope>
      - 只检查本任务改过的文件。
      - 不做全量 lint/typecheck，除非 task 规划明确要求或局部验证无法覆盖风险。
      - 不 review 无关 diff。
      - 不要求 channel done/error 证据。
      - no-task 路径没有 task artifacts 时，只围绕本次对话请求、实际 diff、相关 spec 和局部验证检查。
    </check_scope>
  </rules>

  <completion>
    - 主会话已完成任务实现。
    - 主会话已完成 `trellis-check`，或明确报告局部检查无法执行的原因。
    - 主会话已完成 `trellis-update-spec`，或明确说明没有可沉淀内容。
    - 手动挡：输出 `execute` 结论和 `finish` 入口，然后停止等待用户继续。
    - 自动挡：输出 `execute` 结论，并直接进入 `finish`。
  </completion>

  <error_completion>
    - 主会话无法继续执行时，输出 `execute` 错误结论。
    - 不进入 `finish`。
  </error_completion>
</stage>

## finish

<stage id="finish" name="提交归档和 journal">
  <applies_only_to>finish</applies_only_to>
  <do_not_apply_to>brainstorm, plan, execute</do_not_apply_to>

  <rules>
    目标：在 `execute` 完成后收尾。只处理本任务相关代码、计划材料、spec、archive 和 journal，不处理无关脏改。

    <preconditions>
      - `execute` 结论明确显示计划验收标准已满足；no-task 路径则显示用户当前请求已满足。
      - `execute` 结论明确显示检查已通过，或明确说明无法执行的检查及原因。
      - `execute` 结论明确显示 `trellis-update-spec` 已完成，或明确说明没有可沉淀内容。
      - 如果存在 task，使用 task-backed 收尾；如果没有 active task、没有 task 文件，使用 no-task 收尾，不把缺少 task 当作阻塞。
    </preconditions>

    <work_commits>
      - 做 work commits：只提交任务相关代码、计划材料和 spec 变更。
      - 如有 `.commit-suffix.json`，必须通过 `lp-commit-suffix` 完成提交。
      - 无关脏改只报告并保留，不提交、不清理、不回滚。
    </work_commits>

    <parameter_sources>
      - `<task-name>`：仅 task-backed 路径需要。优先使用用户提供的 task；未提供时使用当前 active task。no-task 路径不需要 task 名。
      - `<work-commit-hashes>`：使用本阶段刚创建的 work commit hash；多个 hash 用逗号或空格分隔，保持命令可读。
      - `<title>`：task-backed 路径使用 task 名称或本次 work commit 的主题；no-task 路径使用本次用户请求的短标题。
      - `<summary>`：概括 `execute` 结果、已提交范围、archive/journal 变更；不要包含无关脏改。
      - 任一参数无法确定时，停止并说明缺失项，不用占位符执行命令。
    </parameter_sources>

    <archive_and_journal>
      task-backed 路径先无提交归档 task：

      ```bash
      python3 ./.trellis/scripts/task.py archive <task-name> --no-commit
      ```

      no-task 路径没有 task 可归档时，跳过 `task.py archive`，不要编造 task 名。

      两种路径都要无提交记录 journal：

      ```bash
      python3 ./.trellis/scripts/add_session.py --title "<title>" --commit "<work-commit-hashes>" --summary "<summary>" --no-commit
      ```

      task-backed 路径提交 archive + journal 变更；no-task 路径只提交 journal 变更。仍遵守 `.commit-suffix.json` / `lp-commit-suffix`。
    </archive_and_journal>
  </rules>

  <completion>
    - work commits 和收尾 commit 分开；task-backed 路径的收尾 commit 包含 archive + journal，no-task 路径的收尾 commit 只包含 journal。
    - task-backed 路径：`task.py archive <task-name> --no-commit` 返回成功，并产生预期 archive 变更。
    - no-task 路径：明确说明没有 task 文件，已跳过 archive。
    - `add_session.py --title "<title>" --commit "<work-commit-hashes>" --summary "<summary>" --no-commit` 返回成功，并产生预期 journal 变更。
    - 只留下用户已知的无关脏改。
  </completion>
</stage>
