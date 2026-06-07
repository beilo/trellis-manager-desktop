# UI Guidelines

> 前端 UI 状态和 Tailwind 组合约定。

---

## Overview

业务组件可以复用 `Button`、`TabsTrigger` 等基础组件，但必须显式处理基础 variant 自带的交互态。尤其是选中态背景由独立视觉层承载，或按钮颜色本身代表“当前选择”时，hover 不能覆盖当前态。

---

## Pattern: Header Segmented Tabs

**Scope**: 适用于 `frontend/src/components/Header.tsx` 中的看板 / 工具链 / 项目胶囊 Tab，以及后续同类“独立滑块 + 多个 ghost 按钮”的 segmented control。

**Contract**:

- 选中态文字使用 `text-primary font-semibold`。
- 选中态背景由独立滑块元素承载，例如 `absolute ... bg-background`。
- 选中按钮必须覆盖 `Button variant="ghost"` 的默认 hover 背景：`hover:bg-transparent`。
- 选中按钮 hover 时文字保持 `text-primary`：`hover:text-primary`。
- 未选中按钮可以 hover 改文字，但背景保持透明，避免与滑块竞争。

**Why**: `muted` 在当前亮色主题里是深色 token。选中态如果只写 `text-primary font-semibold`，基础 hover 使用深色背景时会压住下层滑块，造成选中态闪暗。

### Wrong

```tsx
className={cn(
  'relative z-10 w-[76px] h-7 rounded-full text-xs transition-colors duration-150',
  activeTab === 'toolchain'
    ? 'text-primary font-semibold'
    : 'text-muted-foreground hover:text-foreground hover:bg-transparent',
)}
```

问题：选中分支没有覆盖基础 hover，实际 hover 可能得到深色背景。

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
- Bad: 选中项 hover 后出现深色底，说明基础组件默认 hover 泄漏到业务选中态。

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

---

## Pattern: Interactive Hover Uses Accent Background

**Scope**: 适用于 `Button` 的 `outline` / `ghost` variant、`TabsList` default 背景，以及列表项、文件树、JSONL 行、批量更新行、看板卡片等可点击元素。

**Contract**:

- 可点击元素的普通 hover 背景使用 `accent` 或 `accent/<alpha>`。
- 默认 Tab 容器背景使用 `accent`，不要使用深色 `muted`。
- `index.css` 的 `@theme inline` 必须导出 `--color-accent` 和 `--color-accent-foreground`，否则 `bg-accent` 只会出现在 class 字符串里，不会生成有效 CSS。
- 不要在 hover 背景里使用 `muted` 或 `muted/<alpha>`。
- `muted` 可以继续用于静态面板、代码块、空状态或弱化文字，不作为交互 hover 背景。
- 当前态可以使用 `accent`；如果当前态由滑块/下划线承载，hover 应透明或回到当前态。

**Why**: 当前主题的 `muted` 是深灰棕，适合弱化文本，不适合 hover 或 tablist 底色。用它做交互背景会让按钮经过或 Tab 区域突然变暗。

### Wrong

```tsx
default: "bg-muted"
outline: "border-border bg-background hover:bg-muted hover:text-foreground"
```

### Correct

```tsx
default: "bg-accent"
outline: "border-border bg-background hover:bg-accent hover:text-foreground"
```

### Tests Required

- 静态检查：`rg "hover:bg-muted|aria-expanded:bg-muted|has-aria-expanded:bg-muted" frontend/src` 必须无结果。
- 静态检查：`TabsList` default variant 必须使用 `bg-accent`。
- 静态检查：`frontend/src/index.css` 必须包含 `--color-accent: hsl(var(--accent));`。
- 浏览器检查：Tab 容器、批量更新、添加、刷新、文件树节点和任务列表项，背景应是浅色而不是深灰。

---

## Scenario: Theme Token Contract For Semantic UI Colors

### 1. Scope / Trigger

- Trigger: 使用新的 Tailwind 语义色类，例如 `bg-accent`、`text-accent-foreground`、`border-accent`。
- This applies even when the raw CSS variable already exists in `:root`.

### 2. Signatures

Required `frontend/src/index.css` shape:

```css
@theme inline {
  --color-accent: hsl(var(--accent));
  --color-accent-foreground: hsl(var(--accent-foreground));
}

:root {
  --accent: 38 33% 87%;
  --accent-foreground: 60 3% 8%;
}
```

### 3. Contracts

- `:root --accent` defines the HSL source value.
- `@theme inline --color-accent` exposes the value to Tailwind class generation.
- Components may use `bg-accent` only after both source and theme export exist.
- Static class strings are not sufficient evidence that CSS exists; browser computed style or generated CSS must prove it.

### 4. Validation & Error Matrix

- `:root --accent` missing -> token has no source value.
- `@theme inline --color-accent` missing -> `bg-accent` class may render transparent or not generate.
- `hover:bg-muted` present in interactive code -> hover may become deep gray.
- `default: "bg-muted"` in `TabsList` -> default tab container may become deep gray.

### 5. Good / Base / Bad Cases

- Good: `TabsList` default is `bg-accent`, and browser computed background is a light color.
- Base: Static code blocks or empty states may still use low-alpha `bg-muted/*`.
- Bad: DOM shows `bg-accent`, but computed background is transparent because `--color-accent` was not exported.

### 6. Tests Required

- `rg "hover:bg-muted|aria-expanded:bg-muted|has-aria-expanded:bg-muted|default: \"bg-muted\"" frontend/src` returns no matches.
- `rg "--color-accent: hsl\\(var\\(--accent\\)\\)" frontend/src/index.css` returns a match.
- `npm run build` passes so Tailwind generated classes are valid.
- Browser check: inspect `[data-slot="tabs-list"]`; class includes `bg-accent`, computed `backgroundColor` is not transparent.

### 7. Wrong vs Correct

#### Wrong

```css
:root {
  --accent: 38 33% 87%;
}
```

```tsx
default: "bg-accent"
```

#### Correct

```css
@theme inline {
  --color-accent: hsl(var(--accent));
}

:root {
  --accent: 38 33% 87%;
}
```

```tsx
default: "bg-accent"
```

---

## Scenario: Task Detail Tabs Show User-Facing Lifecycle Documents

### 1. Scope / Trigger

- Trigger: Adding or changing tabs in `TaskDetail`.
- Applies to the primary task detail tab row.

### 2. Contracts

- Primary task detail tabs should stay focused on user-facing task lifecycle views: `详情`、`PRD`、`Design`、`Implement`.
- Do not place agent-internal execution context, JSONL audit trails, or debug records in the primary tab row.
- If internal context viewing is needed later, expose it through a weaker debug/more entry instead of mixing it with lifecycle documents.

### 3. Good / Base / Bad Cases

- Good: Users see only `详情 / PRD / Design / Implement` in the main task detail tabs.
- Base: Missing PRD / Design / Implement tabs remain disabled with `文件不存在`.
- Bad: `Context` appears next to PRD / Design / Implement and suggests internal agent logs are first-class task documents.

### 4. Tests Required

- Static check: `TaskDetailTab` is `detail | prd | design | implement`.
- Static check: `TaskDetail` does not render a `TabsTrigger` with value `context`.
- Build and lint must pass after narrowing the tab union.
