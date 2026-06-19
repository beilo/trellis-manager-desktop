# 添加使用说明入口

## Goal

为 Trellis Manager Desktop 增加一个面向终端用户的「使用说明」入口。用户可在应用 Header 右侧点击入口，用系统浏览器打开项目维护的本地 HTML 使用说明页面，快速了解应用的基础使用流程。

## Requirements

- Header 右侧在「工具链设置」按钮旁新增「使用说明」入口。
- 点击入口后使用系统浏览器打开项目内维护的 `resources/help.html`。
- 帮助页面只覆盖 Trellis Manager Desktop 应用本身，不包含 one-shot-sim、Agent 流程或开发打包流程。
- 后端提供通用 `open_in_browser(url)` 桥接方法，用于打开受支持 URL。
- 为前端提供稳定的本地帮助页 URL，避免前端硬编码源码路径或打包路径。
- `open_in_browser(url)` 只允许安全可预期的 scheme，例如 `file`、`http`、`https`，拒绝其他协议。
- 源码运行、轻量 `.app` 和独立 `.app` 场景下，帮助页资源都应可被定位和打开。
- 打开失败时，前端应在日志中显示中文错误，不影响当前页面使用。

## Acceptance Criteria

- [x] Header 右侧显示「使用说明」图标按钮，并带有 `title` / `aria-label`。
- [x] 点击「使用说明」后，系统浏览器打开本地 `resources/help.html`。
- [x] 后端暴露 `open_in_browser(url)`，并限制 URL scheme 为 `file` / `http` / `https`。
- [x] 前端通过 API 获取帮助页 URL，不硬编码绝对文件路径。
- [x] `resources/help.html` 是单文件中文使用说明，包含首次使用、工具链、项目、看板和常见问题等章节。
- [x] 打包脚本已有或保持复制 `resources/` 的能力，帮助页在轻量 `.app` 和独立 `.app` 中可用。
- [x] 前端构建或局部验证通过；若无法执行，记录原因。

## Notes

- 用户明确选择创建 Trellis task 后执行。
- 用户明确要求后端使用通用 `open_in_browser(url)`，不是专用 `open_help()`。
- 验证已通过：`npm --prefix frontend run build`、`python3 -m py_compile app/api.py`、`git diff --check`。
