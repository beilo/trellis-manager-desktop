# Design

## Boundary

本任务只调整前端任务详情主界面：

- 删除 `TaskDetail` 中的 Context Tab trigger 和对应 panel。
- 删除仅供该 panel 使用的 `TaskContextPane` 前端实现与相关 import/helper。
- 将看板跳转到任务详情时的初始 Tab 从 `context` 改为 `detail`。

不改后端 API、不改文件读取服务、不删除 `.trellis` 任务上下文文件。

## Rationale

Context 展示的是 agent 内部执行记录、研究记录和检查记录，和 PRD / Design / Implement 不属于同一用户层级。放在主 Tab 会让普通任务阅读流程变复杂；底层能力暂时保留，未来如果需要调试入口，可以通过更弱的“更多/调试”入口重新挂接。

## Compatibility

- `TaskDetailTab` 收窄后，所有调用方必须只传入 `detail | prd | design | implement`。
- 归档任务禁用 Context 的逻辑会随入口删除一起移除。
- 后端 Context API 保留，不影响其它潜在消费者。
