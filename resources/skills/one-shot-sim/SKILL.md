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

简化版是完整 Trellis 一轮完成流程。核心差异：

- 不使用 Trellis channel runtime。
- 不调用、不启动、不委派任何子代理。
- 所有阶段由主会话按顺序直接执行。

稳定阶段 ID：

- `brainstorm`：使用 `trellis-brainstorm` 讨论需求、边界、约束、验收标准。
- `confirm`：确认是否进入执行链路。
- `plan`：基于成熟需求结论新建 task，并完成 Trellis Plan Flow。
- `execute`：主会话直接实现、检查和沉淀，不使用 channel，不使用子代理。
- `finish`：提交任务改动、适用时归档 task、记录 journal，并提交收尾变更。

## State Protocol

状态文件是阶段判断的主来源。不要只根据长上下文猜阶段。

- 每次进入本 skill，先运行本 skill 目录下的 `scripts/flow_state.py show --flow one-shot-sim`。
- 如果能识别 `CLAUDE_CODE_SESSION_ID`、`CLAUDE_SESSION_ID` 或 `CODEX_THREAD_ID`，把返回的 `state_path` 视为当前对话的唯一状态文件。
- 状态文件默认写入 `~/.one-shot/flow-state/<flow>/<conversation_id>.json`，不要在项目目录创建 `.one-flow-state` 或其他运行态记录目录。
- 状态目录优先级是 `--state-root` 参数 > `ONE_SHOT_STATE_DIR` 环境变量 > `~/.one-shot/flow-state`。
- 同一个对话连续使用同一个状态文件；不同对话必须使用不同状态文件。
- 状态文件不存在时，只能从用户明确指定的阶段、最近的 `<stage_complete id="...">`、或当前 Trellis task 状态恢复；恢复不了时一律进入 `brainstorm`，不要默认进入 `plan` 或 `execute`。
- 定位出阶段后，运行 `scripts/flow_state.py init --flow one-shot-sim --stage <stage> --allowed-next <next...> --blocked-next <blocked...>` 初始化。
- 无状态初始化默认使用 `--stage brainstorm --allowed-next confirm --blocked-next plan execute finish`。
- 每个阶段完成后，更新状态到下一阶段；如果停止等待用户，把 `status` 写成 `waiting_user`。
- 如果无法识别会话 ID，停止自动推进，说明缺少 `CLAUDE_CODE_SESSION_ID` / `CLAUDE_SESSION_ID` / `CODEX_THREAD_ID`，并让用户确认阶段。

## Stage Selection

默认使用自动挡。模式关键词：

- `法拉利`、`法拉利模式` 等同于 `自动挡` / `auto mode`。
- `拖拉机`、`拖拉机模式` 等同于 `手动挡` / `manual mode`。

如果用户只说 “one-shot-sim” 或 “继续 one-shot-sim”，按状态文件定位阶段：

- 无状态、状态文件不存在、状态无法恢复或缺少明确需求结论：进入 `brainstorm`。
- 已有 `brainstorm` 结论但还没有执行确认：进入 `confirm`。
- `confirm` 已完成且用户选择创建 task，但还没有 task：进入 `plan`。
- `confirm` 已完成且用户选择不创建 task：进入 no-task `execute`。
- task 已存在且规划文档完整：进入 `execute`。
- `execute` 已完成且需要提交、归档、记录 journal：进入 `finish`。
- 状态文件与上下文冲突时，停止并说明冲突，不要猜。

手动挡规则：

- 只有用户明确说 `拖拉机`、`拖拉机模式`、`手动挡`、`manual mode`、`只跑当前阶段`、`不要自动推进`、`不要自动跑到最后` 时，mode 才是 `manual`。
- 每次只执行用户指定或状态文件定位出的当前阶段。
- 阶段结束后输出阶段结论和下一阶段入口，然后停止等待用户继续。

自动挡规则：

- 默认 mode 是 `auto`；用户明确说 `法拉利`、`法拉利模式`、`自动挡`、`自动推进`、`auto mode`、`自动跑到最后`、`自动跑完整流程` 时也视为 `auto`。
- `brainstorm` 是交互阶段。没有对应 `<stage_complete>` 块时，禁止自动进入后续阶段。
- `confirm` 必须获得用户明确选择，才可进入 `plan` 或 no-task `execute`。
- 自动挡从 `plan` 或 no-task `execute` 开始连续推进。
- `plan` 完成后，主会话直接进入 `execute`。默认自动挡和用户明确选择 `法拉利` / `自动挡` 本身都视为已批准执行。
- `execute` 完成后，主会话直接进入 `finish`，完成 work commits、适用时 archive、journal 和收尾 commit。
- 自动挡目标是跑到 `finish` 完成；中途只有出现阻塞、失败、破坏性风险、需求冲突或真实未决问题时才停止。

## Global Rules

- 以当前仓库为准，先运行 `python3 ./.trellis/scripts/get_context.py` 确认 Trellis 上下文、active task 和 git 状态；`brainstorm` 阶段可在缺少 Trellis task 时先讨论需求。
- 禁止使用 Trellis channel runtime：不要运行 `trellis channel ...`，不要等待 channel message，不能把 channel 不可用当作阻塞。
- 禁止使用子代理：不要 spawn/启动/调用 explorer、implement、check、finish-work 或任何其他子代理。
- 主会话可以读取 task 规划文档、spec、代码和工具输出，并直接完成实现、检查、沉淀、提交、归档。
- 不要把 `.trellis/agents/*.md` 当作必须执行的 agent 流程；本 skill 已经定义主会话执行流程。
- 始终显式标注当前稳定阶段 ID：`brainstorm`、`confirm`、`plan`、`execute`、`finish`。
- 每个阶段结束时输出阶段结论和下一阶段入口，例如：`brainstorm 完成 -> confirm`。
- 外部资料和当前信息优先用 smart-search；本地代码理解优先用 fast_context_search。
- 发现无关脏改时报告并保留，不清理、不回滚、不提交。
- 破坏性操作或无法判断文件归属时，立即停止并说明阻塞点。

## Skill Execution Gate

- 任何阶段规则要求“使用”或“完整加载并执行”某个技能时，必须按该技能正文执行；读取技能说明只算加载，不算执行完成。
- 不得用 `one-shot-sim` 自己的阶段解释、需求摘要、代码取证、风险判断或个人判断替代该技能流程。
- 进入这类阶段后，先读取该技能全文；如果技能不存在、无法读取或名称无法解析，立即停止并说明，不得静默替换为相近技能。
- 如果该技能要求逐问逐答或等待用户反馈，必须按要求停下等待；只有问题可由代码、文档或工具输出直接回答时，才可以用取证结果代替用户回答，并写明对应问题和证据。
- 未满足该技能自己的完成标准前，禁止输出 `<stage_complete id="...">`，也禁止进入下一阶段。
- 输出阶段完成块时，必须写明技能执行证据：使用的技能名、完成的关键步骤、等待用户或代码取证情况、剩余未决问题。
- 禁止把“已读取技能”“已按规则处理”“技术边界明确”作为技能已完成的唯一证据。

## Stage Rule Files

- `plan` 阶段进入前必须读取并执行 `references/plan.md`。
- `execute` 阶段进入前必须读取并执行 `references/execute.md`。
- `finish` 阶段进入前必须读取并执行 `references/finish.md`。
- 这些引用文件是本 skill 的强制组成部分；无法读取对应文件时，停止并说明，不得凭记忆执行该阶段。

## Output Contract

- 所有面向用户的输出必须使用中文，包括阶段结论、最终状态、提交清单、检查结果、错误说明、剩余脏改说明和下一步提示。
- 保留命令、文件路径、commit hash、分支名、工具名和工具原始输出的原文。
- 不要使用英文模板标题，例如 `Commits`、`Final state`、`Checks done`；改用 `提交记录`、`最终状态`、`检查结果`。
- 如果引用英文工具输出，先给中文结论，再贴必要原文片段。
- 每个阶段开始、阶段完成、阻塞或报错时，都输出流程进度块。进度块必须放在该次回复开头，使用固定 5 行格式：

```text
→ brainstorm 需求讨论
  confirm 执行确认
  plan 新建 task 和 Plan Flow
  execute Execute Flow
  finish Finish Flow
```

- 进度符号含义：`✓` 已完成，`→` 当前进行中或当前阻塞阶段，空格表示未开始。
- 阶段完成时必须输出完成块。没有完成块，不得认为阶段完成。
- `finish` 完成时输出 5 行全 `✓`，并在下一行写：`一轮完成已完成。`

## brainstorm

<stage id="brainstorm" name="需求讨论">
  <applies_only_to>brainstorm</applies_only_to>
  <do_not_apply_to>confirm, plan, execute, finish</do_not_apply_to>

  <rules>
    使用并完整执行 `trellis-brainstorm`。读取 `trellis-brainstorm` 说明只算加载，不算完成。
  </rules>

  <completion>
    - `trellis-brainstorm` 的完成标准已满足。
    - 输出 `<stage_complete id="brainstorm">`。
    - 下一阶段只能是 `confirm`。
  </completion>
</stage>

## confirm

<stage id="confirm" name="执行确认">
  <applies_only_to>confirm</applies_only_to>
  <do_not_apply_to>brainstorm, plan, execute, finish</do_not_apply_to>

  <rules>
    询问用户选择哪条执行链路：

    1. 创建 task：进入 `plan -> execute -> finish`。
    2. 不创建 task：进入 no-task `execute -> finish`。

    - 只确认是否进入执行链路，不创建 task，不运行 Plan Flow，不执行代码。
    - 用户明确选择创建 task 后，进入 `plan`。
    - 用户明确选择不创建 task 后，进入 no-task `execute`；no-task 只表示确认执行后不创建 Trellis task，不表示跳过 `brainstorm`、`confirm`。
    - 用户拒绝或要求修改方案时，按用户要求回到 `brainstorm`。
  </rules>

  <completion>
    - 已向用户询问创建 task 还是 no-task 执行。
    - 获得用户明确选择后，输出 `<stage_complete id="confirm">`，并更新状态到 `plan` 或 no-task `execute`。
    - 未获用户明确选择时，状态保持 `waiting_user`，不要输出 `<stage_complete id="confirm">`。
  </completion>
</stage>

## plan

<stage id="plan" name="新建 task 和 Plan Flow">
  <applies_only_to>plan</applies_only_to>
  <do_not_apply_to>brainstorm, confirm, execute, finish</do_not_apply_to>

  <rules>
    读取并完整执行 `references/plan.md`。
  </rules>

  <completion>
    - `references/plan.md` 的完成标准已满足，或已按其规则停止等待。
  </completion>
</stage>

## execute

<stage id="execute" name="Execute Flow / 主会话直接执行">
  <applies_only_to>execute</applies_only_to>
  <do_not_apply_to>brainstorm, confirm, plan, finish</do_not_apply_to>

  <rules>
    读取并完整执行 `references/execute.md`。
  </rules>

  <completion>
    - `references/execute.md` 的完成标准已满足。
  </completion>

  <error_completion>
    - `references/execute.md` 的错误完成规则已执行。
  </error_completion>
</stage>

## finish

<stage id="finish" name="提交归档和 journal">
  <applies_only_to>finish</applies_only_to>
  <do_not_apply_to>brainstorm, confirm, plan, execute</do_not_apply_to>

  <rules>
    读取并完整执行 `references/finish.md`。
  </rules>

  <completion>
    - `references/finish.md` 的完成标准已满足。
  </completion>
</stage>
