# 移除暗色主题，固定亮色主题

## Goal

系统当前会根据 OS `prefers-color-scheme` 自动切换亮/暗主题，暗色主题存在样式问题。目标是完全移除暗色主题支持，固定使用当前的亮色主题，不再随系统变化。

## Requirements

- 删除 `App.tsx` 中监听系统主题的 `useEffect`（自动同步 `prefers-color-scheme: dark` → `.dark` class）
- 删除 `index.css` 中的 `.dark` CSS 变量块和 `@custom-variant dark` 声明
- 清理所有组件中 `dark:` 前缀的 Tailwind 类名（约 12 个文件）
- 不改变任何业务逻辑和亮色主题下的视觉效果

## Constraints

- 仅做删除操作，不引入新的主题切换机制
- 不改动组件结构和功能逻辑
- 亮色主题的视觉表现应与当前完全一致

## Acceptance Criteria

- [ ] `App.tsx` 中无 `prefers-color-scheme` 相关代码
- [ ] `index.css` 中无 `.dark` 变量块和 `@custom-variant dark`
- [ ] 代码库中无 `dark:` 前缀的 Tailwind 类名残留
- [ ] 应用在系统为暗色模式时仍显示亮色主题
- [ ] 亮色主题视觉效果无变化

## Files to modify

- `frontend/src/App.tsx` — 删除主题同步 useEffect
- `frontend/src/index.css` — 删除 `.dark` 变量块和 `@custom-variant dark`
- `frontend/src/components/StatusBadge.tsx` — 清理 `dark:` 类
- `frontend/src/components/KanbanTaskCard.tsx` — 清理 `dark:` 类
- `frontend/src/components/StepBadge.tsx` — 清理 `dark:` 类
- `frontend/src/components/ProjectCard.tsx` — 清理 `dark:` 类
- `frontend/src/components/BatchUpdateDialog.tsx` — 清理 `dark:` 类
- `frontend/src/components/UpdatePreviewDialog.tsx` — 清理 `dark:` 类
- `frontend/src/components/SettingsCard.tsx` — 清理 `dark:` 类
- `frontend/src/components/JsonlViewer.tsx` — 清理 `dark:` 类
- `frontend/src/components/ProjectList.tsx` — 清理 `dark:` 类
- `frontend/src/components/Header.tsx` — 清理 `dark:` 类
- `frontend/src/components/ui/button.tsx` — 清理 `dark:` 类
- `frontend/src/components/ui/badge.tsx` — 清理 `dark:` 类
- `frontend/src/components/ui/tabs.tsx` — 清理 `dark:` 类
