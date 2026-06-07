# Implement

## Steps

- [x] 读取前端 spec 与相关组件调用点。
- [x] 从 `TaskDetail` 删除 Context Tab、panel、`TaskContextPane` 和未使用依赖。
- [x] 将 `App` 里的任务跳转初始 Tab 从 `context` 改为 `detail`。
- [x] 更新 `CHANGELOG.md`。
- [x] 判断是否需要更新前端 code-spec。
- [x] 运行 `npm run build`、`npm run lint`、`git diff --check`。
- [x] 只暂存 Context 移除相关 hunk 并提交。
- [ ] finish-work 归档任务并记录 journal。

## Validation

```bash
npm run build
npm run lint
git diff --check
rg -n "context|TaskContextPane|listTaskContextFiles|readTaskContextFile" frontend/src/components/TaskDetail.tsx frontend/src/App.tsx
```
