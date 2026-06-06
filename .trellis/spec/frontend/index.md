# Frontend Development Guidelines

> Trellis Manager Desktop 前端约定，基于当前 React、Tailwind、Base UI Button 和 Vite 代码结构。

---

## Overview

前端质量目标是：交互状态必须和视觉层级一致，组件默认样式不能意外覆盖业务态；重复 UI 状态分支应抽成局部常量，保持可读、可验证。

---

## Guidelines Index

| Guide | Description | Status |
|-------|-------------|--------|
| [UI Guidelines](./ui-guidelines.md) | 组件状态、Tailwind 覆盖和视觉交互约定 | Filled |

---

## Pre-Development Checklist

- 修改 `frontend/src/components/` 前，先确认被用到的基础组件默认 variant 是否自带 hover / active / aria 状态样式。
- 修改选中态、hover 态、展开态等交互样式时，同时检查基础组件类名和业务组件类名的合并结果。
- 新增或启用 Tailwind 语义色类名前，确认 `frontend/src/index.css` 的 `@theme inline` 已导出对应 `--color-*` token。
- 对固定格式控件，例如 Header segmented tabs，保持宽高稳定，避免 hover 或选中态改变布局尺寸。

---

**Language**: 代码中新增注释使用中文解释意图；公共标识符、CSS 类名、文件路径保持原样。
