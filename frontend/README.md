# Trellis Manager Desktop Frontend

这是 Trellis Manager Desktop 的前端层，负责渲染桌面客户端的主界面。

- 技术栈：React + TypeScript + Vite
- UI 风格：shadcn 风格组件
- 通信方式：通过 `pywebview` 暴露的 JS API 调用 `app/api.py`

## 运行

```bash
cd apps/trellis-manager-desktop/frontend
pnpm install
pnpm dev
```

开发模式下，`apps/trellis-manager-desktop/main.py` 会在没有 `dist/` 时回退到 `http://localhost:5173`。

## 构建

```bash
cd apps/trellis-manager-desktop/frontend
pnpm build
```

构建产物会输出到 `frontend/dist/`，随后会被 `apps/trellis-manager-desktop/scripts/build_app.py` 打包进桌面 `.app`。

## 其他脚本

```bash
pnpm lint
pnpm preview
```

## 目录说明

- `src/App.tsx`：前端主入口，组织标题、摘要卡片、Tab 页面和日志面板
- `src/api.ts`：pywebview JS API 包装层
- `src/components/`：页面组件和 shadcn 风格基础组件
- `src/components/ui/`：按钮、卡片、表格、标签、Tabs、Tooltip 等基础 UI
- `src/types.ts`：前后端共享类型

## 与桌面壳的关系

桌面壳位于 `apps/trellis-manager-desktop/` 根目录：

- `main.py`：加载 `frontend/dist/index.html` 或 Vite dev server
- `launcher.py`：准备本地 `.venv` 并启动桌面壳
- `scripts/build_app.py`：把前端 `dist/` 和 Python 启动文件打进 `.app`
