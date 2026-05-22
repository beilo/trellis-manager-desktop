# Open in iTerm2 — 设计文档

## 概述

为 Trellis Manager 桌面端任务管理面板增加「在 iTerm2 中打开」功能：用户点击按钮后，macOS 原生 `open -a iTerm` 命令打开 iTerm2 并 `cd` 到任务所属的项目根目录。

## 约束

- **仅支持 macOS**（与已有的 `open_directory` 一致）
- iTerm2 必须已安装，否则 macOS 会弹出「应用不存在」的提示（系统默认行为，无需额外处理）
- 仅对非归档活跃任务（`planning` / `in_progress`）显示该按钮

## 改动清单

### 1. 后端 `app/api.py`

新增方法：

```python
def open_in_iterm(self, project_path: str) -> None:
    expanded = str(Path(project_path).expanduser())
    subprocess.Popen(["open", "-a", "iTerm", expanded])
```

与已有的 `open_directory`（Finder）和 `open_task_directory` 共用同模式。

### 2. 前端 `frontend/src/api.ts`

在 `PywebviewAPI` 接口和 `api` 对象中各加一个方法：

```typescript
// 接口
open_in_iterm(path: string): Promise<void>

// api 对象
async openInIterm(path: string): Promise<void> {
    return (await getApi()).open_in_iterm(path)
}
```

### 3. 组件 `TaskDetail.tsx`

- 新增 prop `projectPath: string`
- 新增 prop `onOpenIterm: (path: string) => void`
- 在「打开任务目录」按钮旁边增加新按钮，左侧用 `Terminal` 图标（`lucide-react`）

```tsx
{!task.archived && (task.status === 'planning' || task.status === 'in_progress') && (
  <Button variant="outline" onClick={() => onOpenIterm(projectPath)}>
    <Terminal className="size-4" />
    在 iTerm2 中打开
  </Button>
)}
```

### 4. 组件 `TaskManagerPanel.tsx`

将 `projectPath` 传给 `TaskDetail`，并绑定 `onOpenIterm` 回调：

```tsx
<TaskDetail
  task={selectedTask}
  projectPath={projectPath}
  onOpenDir={(path) => api.openTaskDirectory(path)}
  onOpenIterm={(path) => api.openInIterm(path)}
/>
```

## 不变的部分

- 已有的「打开任务目录」(Finder) 按钮保持不变
- TaskListItem 点击行为不变（仍只做选中）
- 布局、配色、数据流均不变
- 无需新增依赖