# 公共技能全局分发设计

## Architecture

后端仍由 `app/ops.py` 承载工具链安装后的本地文件同步。新的同步逻辑以应用内 `resources/skills` 为 bundle root：

```text
resources/skills/<skill>              # 应用打包源
~/.agents/skills/<skill>              # 本机权威源，普通目录副本
~/.codex/skills/<skill>               # symlink -> ../../.agents/skills/<skill>
~/.claude/skills/<skill>              # symlink -> ../../.agents/skills/<skill>
```

`scripts/build_app.py` 和 `scripts/build_standalone_app.py` 已经复制/打包整个 `resources/`，无需新增打包入口。运行时只依赖 bundle 内资源，不依赖开发机共享技能路径。

## Sync Contract

- 扫描 `resources/skills` 的一级子目录。
- 只有包含 `SKILL.md` 的子目录视为可分发技能。
- 没有有效技能时抛出 `OperationError`，提示内置公共技能不存在或不完整。
- 对每个技能，先强制删除目标入口：
  - symlink 或普通文件：`unlink()`
  - 普通目录：`shutil.rmtree()`
- 复制技能目录到 `~/.agents/skills/<skill>`。
- 为 Codex / Claude 创建相对 symlink：`../../.agents/skills/<skill>`。

## Compatibility

旧版本可能留下这些形态：

- `~/.codex/skills/one-shot-sim` 普通目录副本
- `~/.claude/skills/one-shot-sim` 普通目录副本
- Codex / Claude 下指向其他位置的旧 symlink
- `~/.agents/skills/<skill>` 旧目录、文件或 symlink

本任务按用户确认采用强制覆盖。删除 symlink 时只删除入口，不跟随目标，避免误删 shared source。

## Operation Details

返回 details 采用摘要字段，避免为多个技能生成不可控数量的动态 key：

- `synced_skills`: 逗号分隔技能名
- `synced_skill_count`: 技能数量字符串
- `skill_source`: 内置源根目录
- `agents_skill_dir`: `~/.agents/skills`
- `codex_skill_dir`: `~/.codex/skills`
- `claude_skill_dir`: `~/.claude/skills`

保留 `OperationReport.details: dict[str, str]` 的现有类型，降低 API 和前端类型改动。

## Risks

- 强制覆盖会删除用户同名技能。该行为是用户确认的产品选择，必须在 spec 和测试里固定。
- 如果运行环境不支持 symlink，安装会失败并返回 `OperationError`。当前目标是 macOS 桌面端，symlink 可用。
- 当前工作区已有 `resources/skills/one-shot-sim` 删除状态，执行时不应回滚；实现应支持新的公共技能资源布局由后续内容填充。
