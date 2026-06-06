# UI Guidelines

> 前端 UI 状态和 Tailwind 组合约定。

---

## Overview

业务组件可以复用 `Button` 等基础组件，但必须显式处理基础 variant 自带的交互态。尤其是选中态背景由独立视觉层承载时，按钮本身不能在 hover 时再绘制背景，否则会覆盖选中态。

---

## Pattern: Header Segmented Tabs

**Scope**: 适用于 `frontend/src/components/Header.tsx` 中的看板 / 工具链 / 项目胶囊 Tab，以及后续同类“独立滑块 + 多个 ghost 按钮”的 segmented control。

**Contract**:

- 选中态文字使用 `text-primary font-semibold`。
- 选中态背景由独立滑块元素承载，例如 `absolute ... bg-background`。
- 选中按钮必须覆盖 `Button variant="ghost"` 的默认 hover 背景：`hover:bg-transparent`。
- 选中按钮 hover 时文字保持 `text-primary`：`hover:text-primary`。
- 未选中按钮可以 hover 改文字，但背景保持透明，避免与滑块竞争。

**Why**: `Button` 的 `ghost` variant 默认包含 `hover:bg-muted hover:text-foreground`。如果选中态只写 `text-primary font-semibold`，hover 会落到深色 `muted` 背景，压住下层滑块，造成选中态闪暗。

### Wrong

```tsx
className={cn(
  'relative z-10 w-[76px] h-7 rounded-full text-xs transition-colors duration-150',
  activeTab === 'toolchain'
    ? 'text-primary font-semibold'
    : 'text-muted-foreground hover:text-foreground hover:bg-transparent',
)}
```

问题：选中分支没有覆盖 `ghost` 的默认 hover，实际 hover 会得到 `hover:bg-muted hover:text-foreground`。

### Correct

```tsx
// 选中项背景由滑块承载，hover 需要保持透明，避免 ghost 默认深色底压住选中态。
const activeTabClass = 'text-primary font-semibold hover:bg-transparent hover:text-primary'
const inactiveTabClass = 'text-muted-foreground hover:text-foreground hover:bg-transparent'

className={cn(
  'relative z-10 w-[76px] h-7 rounded-full text-xs transition-colors duration-150',
  activeTab === 'toolchain' ? activeTabClass : inactiveTabClass,
)}
```

### Good / Base / Bad Cases

- Good: 选中 `工具链` 后 hover，按钮背景透明，下层滑块仍是 `bg-background`，文字保持 `primary`。
- Base: 未选中 `项目` hover，文字从 `muted-foreground` 变为 `foreground`，背景透明。
- Bad: 选中项 hover 后出现 `muted` 深色底，说明基础组件默认 hover 泄漏到业务选中态。

### Tests Required

- 静态检查：确认选中分支包含 `hover:bg-transparent hover:text-primary`。
- 构建检查：运行 `npm run build`，确认 Tailwind 类和 TypeScript 无错误。
- Lint 检查：运行 `npm run lint`，确认局部 class 常量不违反前端规则。
- 视觉检查：通过浏览器 hover 当前选中 Tab，确认没有深色背景覆盖滑块。

---

## Common Mistakes

### 只给未选中态写 hover 覆盖

**Symptom**: 未选中项 hover 正常，选中项 hover 闪成深色背景。

**Cause**: `Button variant="ghost"` 的默认 hover 是基础类，业务组件只在未选中分支写了 `hover:bg-transparent`。

**Fix**: 选中分支也必须显式覆盖 hover 背景和文字色。

**Prevention**: 写条件 class 时同时检查 active / inactive 两个分支，不要默认基础组件会替业务态让路。
