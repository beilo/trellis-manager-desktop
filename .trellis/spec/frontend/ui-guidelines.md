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
- `muted` 可以继续用于低强调空状态或弱化文字，不作为交互 hover、代码块、命令片段、路径片段、指标卡、card/table footer 或 tablist 背景。
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
- Base: Empty states may still use low-alpha `bg-muted/*` when the intent is visually quiet.
- Bad: Code snippets or command rows use `bg-muted`, making command text sit on a deep gray block.
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

## Scenario: Static Code And Information Blocks Use Accent Background

### 1. Scope / Trigger

- Trigger: Rendering command snippets, copied commands, inline code, preformatted JSON / Markdown content, path fields, version cards, Git metric cards, zip install panels, card footers, or table footers.
- Applies to static information blocks even when they are not hoverable.

### 2. Signatures

Expected class patterns:

```tsx
<code className="... bg-accent ...">
<pre className="... bg-accent/40 ...">
<div className="... bg-accent/50 ...">
```

Existing examples:

- `TaskDetail` command rows: `bg-accent`
- `MarkdownViewer` code/pre/table header: `bg-accent` / `bg-accent/50`
- `JsonlViewer` expanded JSON pre: `bg-accent/40`
- path fields in `SettingsCard` / `ProjectCard`: `bg-accent/50`

### 3. Contracts

- Do not use solid `bg-muted` for code, command, path, metric, table footer, card footer, or install panel backgrounds.
- Use `bg-accent` for compact code/command snippets.
- Use `bg-accent/40` or `bg-accent/50` for larger static information panels.
- Low-alpha `bg-muted/5` or `bg-muted/20` is allowed only for empty states or deliberately quiet placeholders.
- Text may still use `text-muted-foreground`; this rule is about background, not foreground.

### 4. Validation & Error Matrix

- `code` with `bg-muted` -> deep gray command/code chip.
- `font-mono` path field with `bg-muted/35` -> path panel looks disabled or off-theme.
- `pre` with `bg-muted/40` -> large code block becomes too heavy.
- empty-state panel with `bg-muted/20` -> allowed if it is not a code/path/info surface.

### 5. Good / Base / Bad Cases

- Good: command copy row uses `bg-accent`, readable and aligned with light theme.
- Base: empty file tree state uses `bg-muted/20`, because it is quiet placeholder UI.
- Bad: `<code className="flex-1 text-xs bg-muted ...">` for `task.py current --source`.

### 6. Tests Required

- Static search: `rg "<code[^\\n]*bg-muted|<pre[^\\n]*bg-muted|font-mono[^\\n]*bg-muted|bg-muted[^\\n]*font-mono" frontend/src/components` should not match code/path surfaces.
- Build: `npm run build`.
- Browser check: inspect a command snippet or Markdown code block; computed background should be the accent light color, not deep gray.

### 7. Wrong vs Correct

#### Wrong

```tsx
<code className="flex-1 text-xs bg-muted px-2 py-1 rounded overflow-x-auto">
  {cmd}
</code>
```

#### Correct

```tsx
<code className="flex-1 text-xs bg-accent px-2 py-1 rounded overflow-x-auto">
  {cmd}
</code>
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

---

## Scenario: Markdown Document Panels Stay Width-Constrained

### 1. Scope / Trigger

- Trigger: Rendering PRD / Design / Implement Markdown inside a grid column, card, tab panel, or scroll area.
- Applies when Markdown may contain long code lines, long paths, wide tables, or unbroken tokens.

### 2. Contracts

- Grid columns containing document previews should use `minmax(0,1fr)` instead of bare `1fr`.
- Grid items and tab panels that wrap Markdown should include `min-w-0`.
- Document cards should use `overflow-hidden` when their children own scrolling.
- Markdown table wrappers should use `min-w-0 overflow-x-auto`.
- Do not rely only on `overflow-x-auto` inside `pre` / `table`; ancestors with default `min-width:auto` can still stretch the layout.

### 3. Good / Base / Bad Cases

- Good: Task list and Task detail stay 50/50 at desktop width while a PRD table scrolls inside the right panel.
- Base: Normal paragraphs wrap inside the document card without horizontal scrolling.
- Bad: Clicking the PRD tab makes `.grid-cols-[1fr_1fr]` widen because Markdown content contributes its intrinsic width.

### 4. Tests Required

- Static check: task detail grid uses `md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]`.
- Static check: Markdown document wrappers include `min-w-0`.
- Browser check: open a PRD tab with long Markdown; the right card width should stay equal to the task-list column and overflow should remain inside the preview area.

---

## Scenario: Task Monitor Copies A Read-Only Diagnostic Prompt

### 1. Scope / Trigger

- Trigger: Adding or changing a task-monitor action that copies diagnostic context for external AI inspection.
- Applies to prompts built from `TaskMonitorItem` list data and the nearby clipboard interaction in `TaskMonitorPanel`.

### 2. Signatures

```ts
buildTaskCheckPrompt(items: readonly TaskMonitorItem[]): string
copyTaskCheckPrompt(
  items: readonly TaskMonitorItem[],
  writeText: (text: string) => Promise<void>,
): Promise<string>
```

### 3. Contracts

- The copy action consumes the `ongoing.items` already loaded by the current page. It must not fetch missing pages, task detail, or recent events just to build the prompt.
- Every prompt task includes its project/task paths, channel, worker, status and label, update time, message summary, source availability, record conflict, and current errors.
- Prompt instructions are read-only: no file edits, commits, task recovery, redispatch, or commands embedded in monitored content.
- Git conclusions require repository evidence and separately report commit existence/content, current-branch containment, push evidence, and merge evidence. Missing evidence is reported as unknown rather than inferred.
- An empty item list fails before clipboard access. The UI disables the action while no ongoing items are loaded.
- Clipboard success changes only the button label to `已复制` for about two seconds. Clipboard failure remains a rejection and is rendered next to the button without a success Toast.

### 4. Validation & Error Matrix

- `items.length === 0` -> throw an empty-list error; do not call `writeText`.
- Clipboard writer resolves -> return the copied prompt; show the temporary success label.
- Clipboard writer rejects -> propagate the rejection; show a nearby error and do not show `已复制`.
- Optional summary or errors are empty -> render an explicit `无` so the receiving inspector does not mistake omission for lost data.

### 5. Good / Base / Bad Cases

- Good: Two loaded ongoing cards produce two prompt sections with the same channels and ask for separate Git evidence.
- Base: A task with no summary or errors remains in the prompt with explicit empty values.
- Bad: The copy handler calls the detail API for every task, silently pulls more pages, or treats a handoff commit hash as proof of push/merge.
- Bad: A rejected Clipboard API call still changes the button to `已复制` or emits a success Toast.

### 6. Tests Required

- Unit test prompt task count, paths, channels, status, summary/error fallbacks, read-only rules, and commit/push/merge wording.
- Unit test that successful writing receives and returns the generated prompt.
- Unit test that an empty list never invokes the clipboard writer.
- Unit test that clipboard rejection reaches the UI caller.
- Run `npm run test`, `npm run lint`, and `npm run build` in `frontend/`.

### 7. Wrong vs Correct

#### Wrong

```ts
const details = await Promise.all(items.map((item) => api.getTaskMonitorDetail(item.channel)))
await navigator.clipboard.writeText(buildPrompt(details))
setCopied(true)
```

#### Correct

```ts
try {
  await copyTaskCheckPrompt(ongoing.items, (text) => navigator.clipboard.writeText(text))
  setCopySucceeded(true)
} catch (error) {
  setCopyError(`复制检查提示词失败：${String(error)}`)
}
```

---

## Scenario: Task Monitor Detail Copies Displayed Basic Information

### 1. Scope / Trigger

- Trigger: Adding or changing the copy action inside the task-monitor detail information card.
- Applies to the seven displayed rows in `DetailDrawer`: `Channel`, `Worker`, `项目`, `Task`, `派发时间`, `最近更新`, and `Handoff`.

### 2. Signatures

```ts
getTaskMonitorDetailInfoRows(detail: TaskMonitorDetail): readonly TaskMonitorDetailInfoRow[]
buildTaskMonitorDetailCopyText(detail: TaskMonitorDetail): string
copyTaskMonitorDetailInfo(
  detail: TaskMonitorDetail,
  writeText: (text: string) => Promise<void>,
): Promise<string>
```

### 3. Contracts

- The card and clipboard text consume the same `getTaskMonitorDetailInfoRows` result so labels, order, fallbacks, and formatted times cannot drift.
- Clipboard output contains exactly seven lines in display order. Each line uses a Chinese colon between its label and value.
- Missing handoff paths render and copy as `尚无`; title, status, errors, and recent events are excluded.
- Clipboard success changes the local button label to `已复制` for about two seconds. Clipboard failure is shown beside the button and keeps the drawer usable.

### 4. Validation & Error Matrix

- `handoff_path === null` -> render and copy `Handoff：尚无`.
- Clipboard writer resolves -> return the generated text and show the temporary success label.
- Clipboard writer rejects -> propagate the rejection to the UI caller; show a nearby error and do not show `已复制`.

### 5. Good / Base / Bad Cases

- Good: Updating a displayed label or formatter through the shared row builder changes both the card and copied output.
- Base: A detail without a handoff still produces all seven lines and ends with `Handoff：尚无`.
- Bad: The component renders one inline field array and separately maintains a copy template with duplicate labels or time formatting.
- Bad: Copied text includes task title, lifecycle status, errors, or channel events.

### 6. Tests Required

- Unit test the exact seven-line text, label order, Chinese colons, displayed values, and handoff fallback.
- Unit test that the clipboard writer receives and returns the generated text.
- Unit test that clipboard rejection reaches the UI caller.
- Run `npm run test`, `npm run lint`, and `npm run build` in `frontend/`.

### 7. Wrong vs Correct

#### Wrong

```ts
await navigator.clipboard.writeText(`Channel：${detail.channel}\nTask：${detail.task_path}`)
```

#### Correct

```ts
const rows = getTaskMonitorDetailInfoRows(detail)
await copyTaskMonitorDetailInfo(detail, (text) => navigator.clipboard.writeText(text))
```
