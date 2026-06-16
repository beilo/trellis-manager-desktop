# 公共技能全局分发

## Goal

将桌面端内置技能同步从 one-shot-sim 专用复制升级为公共技能集合分发：~/.agents/skills 为权威源，~/.codex/skills 与 ~/.claude/skills 软链接过去，并强制覆盖同名入口。

## Confirmed Facts

- 当前实现只同步 `resources/skills/one-shot-sim`，并复制到 `~/.codex/skills/one-shot-sim` 和 `~/.claude/skills/one-shot-sim`。
- 同步发生在工具仓库 git 安装/更新成功后、本地 zip 安装成功后；远端 zip 复用本地 zip 安装流程。
- 打包脚本已经把 `resources/` 放进应用包，运行时可以从桌面端内置资源读取技能。
- 旧 backend spec 记录的是 one-shot-sim 专用复制语义，需要随本任务同步更新。
- 用户确认同名技能冲突时强制覆盖。
- 用户确认 `~/.agents/skills` 必须作为本机权威源，Codex 和 Claude 的技能入口由桌面端创建软链接。

## Requirements

- 桌面端应扫描应用内 `resources/skills/<skill>` 下的所有有效技能目录，不能再硬编码只处理 `one-shot-sim`。
- 有效技能目录至少包含 `SKILL.md`；无有效技能时应返回可解释错误，避免安装流程静默成功但技能未分发。
- 对每个技能，桌面端应强制覆盖写入 `~/.agents/skills/<skill>`。
- 对每个技能，桌面端应强制覆盖 `~/.codex/skills/<skill>` 和 `~/.claude/skills/<skill>`，并创建指向 `../../.agents/skills/<skill>` 的目录 symlink。
- 强制覆盖范围包括普通目录、文件和历史 symlink；覆盖 symlink 时只能删除 symlink 入口本身，不能跟随 symlink 删除目标。
- 工具仓库 git 安装/更新、本地 zip 安装、远端 zip 安装成功后都应触发公共技能同步。
- `OperationReport.details` 应保留足够信息用于日志取证，包括同步技能数量、技能名列表、公共源目录和三个工具目录。
- 单元测试必须使用临时 home 注入，不得写入真实用户目录。
- 后端规范必须更新为公共技能集合语义，替换旧 one-shot-sim 专用复制说明。

## Acceptance Criteria

- [x] `sync_bundled_public_skills` 承载公共技能集合同步逻辑。
- [x] 给定两个内置技能目录时，同步后 `home/.agents/skills/<skill>/SKILL.md` 存在且内容来自内置资源。
- [x] 同步后 `home/.codex/skills/<skill>` 和 `home/.claude/skills/<skill>` 都是 symlink，目标为 `../../.agents/skills/<skill>`。
- [x] 同名普通目录、普通文件、历史 symlink 都会被强制覆盖为新语义。
- [x] 安装/zip 流程返回的 details 包含公共技能同步摘要，远端 zip 包装返回不丢失该摘要。
- [x] 旧的 one-shot-sim 专用测试更新为公共技能集合测试，并补充 `~/.agents/skills` 断言。
- [x] `.trellis/spec/backend/quality-guidelines.md` 记录新的公共技能分发契约。
- [x] 后端单元测试和 Python 编译检查通过。

## Notes

- 本任务不设计前端新按钮。工具链现有安装/更新动作成功后自动执行同步。
- 本任务不从 `/Users/am/ai-workspace/shared-skills` 读取运行时技能；运行时只使用桌面端打包进来的 `resources/skills`。
- 当前应用发布资源只内置 `one-shot-sim`。同步逻辑保留公共目录扫描能力，但不把 Trellis 项目技能整套打包分发。
