# 添加使用说明入口实施计划

## Implementation Checklist

1. 新建 `resources/help.html`，编写 Trellis Manager Desktop 中文使用说明。
2. 修改 `app/api.py`：
   - 引入必要标准库。
   - 增加 `get_help_url()`。
   - 增加 `open_in_browser(url)` 并限制 scheme。
3. 修改 `frontend/src/api.ts`：
   - 扩展 `PywebviewAPI`。
   - 增加 `getHelpUrl()` / `openInBrowser()` 包装。
4. 修改 `frontend/src/components/Header.tsx`：
   - 引入帮助图标。
   - 增加 `onOpenHelp` prop。
   - 在设置按钮旁增加「使用说明」图标按钮。
5. 修改 `frontend/src/App.tsx`：
   - 实现 `handleOpenHelp`。
   - 将回调传给 `Header`。
6. README 增加帮助页维护说明。
7. 运行局部验证。

## Validation Commands

```bash
cd frontend && npm run build
python3 -m py_compile app/api.py
git diff --check
```

如果前端依赖缺失或环境问题导致构建无法运行，记录原始失败原因。

## Risky Files / Rollback Points

- `app/api.py`：pywebview 暴露 API，需保持兼容现有方法。
- `frontend/src/api.ts`：桥接类型错误会影响前端构建。
- `frontend/src/components/Header.tsx`：需遵守现有 Header hover 样式规范。
- `resources/help.html`：打包脚本已复制 `resources/`，但需保持文件在该目录下。
