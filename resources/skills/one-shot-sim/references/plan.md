# plan 阶段规则

## 适用阶段

仅适用于 `plan` 阶段。不要在 `brainstorm`、`confirm`、`execute`、`finish` 阶段套用本文件。

## 规则

新建 task，进入 Trellis Plan Flow 阶段。

- 只能基于 `brainstorm` 需求结论或用户明确给出的可执行方案创建 task。
- 如果缺少目标、边界、约束、验收标准或关键取舍，回到 `brainstorm`，不要进入 `plan`。
- 如果 Plan Flow 里出现真实未决问题、破坏性风险或需求冲突，停止并说明阻塞点；不要擅自继续。
- Plan Flow 的“执行前确认”只在手动挡生效；自动挡 / 法拉利下，完整规划材料加无未决问题即视为已批准执行。
- 产出 task 规划文档后，明确当前处于 `plan`。手动挡停止等待用户继续；自动挡运行 `task.py start` 后直接进入 `execute`。

## 完成标准

- 需求、约束、验收标准清楚。
- task 已创建，并产出完整规划文档。
- 有真实未决问题、破坏性风险或需求冲突时已停止等待。
- 手动挡：输出 `plan` 结论、task 名称和规划产物路径，然后停止等待用户明确批准 `execute`。
- 自动挡：输出 `plan` 结论、task 名称和规划产物路径，运行 `task.py start`，然后直接进入 `execute`。
