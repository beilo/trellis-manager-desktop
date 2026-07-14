# 过滤任务详情工具消息

## Goal

任务监听详情的“最近 20 条”只展示最近 20 条可读 `message` 事件，不再被工具调用和流式进度事件淹没。

## Requirements

- 仅修改任务监听详情 DTO 的 `recent_events` 生成逻辑。
- 读取已缓存的 channel 事件后，先筛选 `kind == "message"`，再取最后 20 条。
- 排除 `progress`、工具调用、流式 delta、`done`、`error`、`killed` 等非 `message` 事件。
- 保持事件原有顺序和现有 `TaskMonitorEvent` 数据结构。
- 不改变任务列表、搜索、任务状态解析、归档或桌面端其他功能。
- 过滤应在后端完成；前端不得重新解释原始 channel 事件。

## Acceptance Criteria

- [ ] 当 channel 同时包含 `message`、`progress`、`done`、`error`、`killed` 事件时，详情 `recent_events` 只包含 `message`。
- [ ] 当可读消息超过 20 条时，返回按原顺序排列的最后 20 条消息。
- [ ] 非 `message` 事件不会占用 20 条额度；应先过滤，再截取。
- [ ] 当没有 `message` 事件时，`recent_events` 返回空列表，详情仍可正常打开。
- [ ] 现有任务状态、搜索、列表和详情其他字段行为不变。
- [ ] 增加或更新后端单元测试，覆盖混合事件、先过滤后截取和无消息场景。
- [ ] 对本次修改文件执行适用的定向测试，并运行 `git diff --check`；如项目规范要求更广验证，按规范执行并在 handoff 中记录结果。

## Notes

- `tl channel messages` 的等价操作口径是 `--last 20 --kind message --no-progress`。
- 当前唯一消费方是任务监听详情：`TaskMonitorPanel -> getTaskMonitorDetail -> get_task_monitor_detail -> TaskMonitorService`。
- 主要实现位置预计为 `app/task_monitor.py`，相关测试位于 `tests/test_task_monitor.py`；以 worker 阅读实际代码后的最小改动为准。
