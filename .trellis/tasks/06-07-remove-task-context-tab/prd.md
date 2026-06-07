# 移除任务详情 Context Tab

## Goal

从任务详情主 Tab 中移除 Context 入口，保留详情 / PRD / Design / Implement 核心文档展示。

## Requirements

- 任务详情主 Tab 只展示用户可理解的核心任务文档：详情、PRD、Design、Implement。
- 不再在主 Tab 中展示 `Context` 入口，避免把 agent 内部执行上下文和任务文档混在同一层级。
- 已归档任务、缺失文档禁用态等现有行为不能被破坏。
- 本次不删除后端 Context 文件读取 API，避免扩大变更面；仅移除主界面入口和不可达的前端面板代码。
- 不混入当前工作区已有的主题/布局未提交改动。

## Acceptance Criteria

- [ ] 任务详情 Tab 列表不再出现 `Context`。
- [ ] `TaskDetailTab` 类型不再包含 `context`。
- [ ] `highlightedTaskInitialTab` 不再默认跳转到 `context`。
- [ ] 前端构建和 lint 通过。
- [ ] 提交只包含 Context 移除相关 hunk、任务归档/记录等 Trellis 流程文件。

## Notes

- 用户明确判断 Context 对普通使用意义不大，主流程应更简洁。
