# 添加使用说明入口设计

## Architecture And Boundaries

- `resources/help.html` 作为用户使用说明的单文件静态页面，由项目维护。
- `app/api.py` 作为 pywebview 桥接层新增轻量方法：
  - `get_help_url()`：解析当前运行环境下的 `resources/help.html` 并返回 `file://` URL。
  - `open_in_browser(url)`：通用浏览器打开能力，限制允许的 URL scheme。
- `frontend/src/api.ts` 增加对应 TypeScript 桥接类型与包装方法。
- `frontend/src/components/Header.tsx` 增加可选 `onOpenHelp` 回调和帮助图标按钮。
- `frontend/src/App.tsx` 实现点击处理：获取帮助页 URL，调用 `openInBrowser`，失败写日志。

## Data Flow

1. 用户点击 Header 右侧「使用说明」。
2. 前端调用 `api.getHelpUrl()` 获取后端解析出的本地 HTML URL。
3. 前端调用 `api.openInBrowser(url)`。
4. 后端校验 scheme，只允许 `file` / `http` / `https`。
5. 后端通过系统默认浏览器打开 URL。
6. 异常返回给前端，前端写入日志。

## Compatibility

- `scripts/build_app.py` 已将 `resources/` 复制到轻量 `.app` bundle 内。
- `scripts/build_standalone_app.py` 已通过 PyInstaller `--add-data` 打包 `resources/`。
- 源码运行时，`resources/help.html` 位于项目根目录下。
- PyInstaller 独立包需要优先从 `sys._MEIPASS/resources/help.html` 定位资源，源码/轻量 `.app` 则从项目根目录定位。

## Trade-offs

- 通用 `open_in_browser(url)` 比专用 `open_help()` 灵活，但需要限制 scheme，避免打开危险协议。
- HTML 帮助页不走 React 路由，维护简单；代价是样式与应用 UI 不完全共享。

## Operational Notes

- 不新增外部依赖。
- 不引入前端路由或复杂文档系统。
- README 只补充帮助页维护位置，不复制完整用户说明。
