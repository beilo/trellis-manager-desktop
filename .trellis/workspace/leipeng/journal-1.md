# Journal - leipeng (Part 1)

> AI development session journal
> Started: 2026-06-06

---



## Session 1: Bootstrap backend guidelines

**Date**: 2026-06-06
**Task**: Bootstrap backend guidelines
**Branch**: `main`

### Summary

Filled backend Trellis spec from current app/tests patterns, updated bootstrap checklist, archived local bootstrap task.

### Main Changes

- Added bundled `resources/skills/one-shot-sim/` with `SKILL.md`, `CHANGELOG.md`, and `agents/openai.yaml`.
- Added post-build sync from bundled skill into `~/.codex/skills/one-shot-sim` and `~/.claude/skills/one-shot-sim`.
- Updated normal `.app` and standalone PyInstaller packaging to include `resources/`.
- Added unit coverage for directory/symlink replacement and temp-home skill sync.
- Documented the bundled global skill sync contract in backend code-spec.

### Git Commits

(No commits - planning session)

### Testing

- [OK] `python3 -m unittest discover -s tests -p 'test_*.py' -v`
- [OK] `python3 -m py_compile main.py launcher.py app/*.py scripts/*.py tests/*.py`
- [OK] `git diff --check`

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 2: 移除任务详情 Context Tab

**Date**: 2026-06-07
**Task**: 移除任务详情 Context Tab
**Branch**: `main`

### Summary

移除任务详情主 Tab 的 Context 入口，收窄 TaskDetailTab 类型，保留详情、PRD、Design、Implement 作为主任务文档视图，并同步前端 UI spec 与 changelog。

### Main Changes

- Replaced the one-shot-sim-only copy helper with `sync_bundled_public_skills`, which scans bundled skills and force-overwrites target entries.
- Made `~/.agents/skills/<skill>` the local source of truth and creates relative symlinks from `~/.codex/skills/<skill>` and `~/.claude/skills/<skill>`.
- Kept the bundled app resource scoped to `resources/skills/one-shot-sim` only.
- Updated backend code-spec and regression tests for the new distribution contract.

### Git Commits

| Hash | Message |
|------|---------|
| `9f6f0ff` | (see git log) |
| `85eb268` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 3: Paseo reusable workflow configuration

**Date**: 2026-06-07
**Task**: Paseo reusable workflow configuration
**Branch**: `main`

### Summary

Added project-local Paseo workflow config, executor, agent skill, tests, changelog, and backend spec contract for reusable PRD -> Implement -> Review orchestration.

### Main Changes

- Default Trellis tool distribution now follows `beilo/main`, while UI version semantics remain the Trellis CLI package version.
- Git tool-repo install/update now uses root `pnpm build`, matching zip install and letting the Trellis workspace own core/CLI build order.
- Project update preview detects the explicit `0.5.x -> 0.6.x` migrate case and the UI requires confirmation before running `tl update --force --migrate`.
- Wrapper checks now verify `tl mem help` / `trellis mem help` and expose `mem_help_ok`.
- Backend quality spec documents the Beilo distribution, migrate update, and MEM wrapper contracts.

### Git Commits

| Hash | Message |
|------|---------|
| `db0fabe` | (see git log) |

### Testing

- [OK] `python3 -m py_compile main.py launcher.py app/*.py scripts/*.py tests/*.py`
- [OK] `python3 -m unittest discover tests -v`
- [OK] `cd frontend && npm run build`
- [OK] `git diff --check`
- [OK] `~/.beilo-trellis/bin/tl mem help`
- [OK] `~/.beilo-trellis/bin/trellis mem help`

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 4: 内置 one-shot-sim 技能同步

**Date**: 2026-06-12
**Task**: 内置 one-shot-sim 技能同步
**Branch**: `main`

### Summary

桌面端内置 one-shot-sim 技能资源，并在工具仓库安装、更新、zip 重装构建成功后覆盖同步到 Codex 和 Claude Code 全局技能目录；补充打包资源、单元测试和 backend code-spec。

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `25a83be` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 5: 发包自动化

**Date**: 2026-06-12
**Task**: 发包自动化
**Branch**: `main`

### Summary

新增根 package.json 应用版本源、npm release:* 发包入口、Python release helper、版本化 macOS zip、GitHub Release dry-run/replace 门禁、README 流程和 release 单元测试；已归档 06-12-release-automation。

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `d506669` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 6: 公共技能全局分发

**Date**: 2026-06-16
**Task**: 公共技能全局分发
**Branch**: `main`

### Summary

将工具链安装后的技能同步改为桌面端内置公共技能分发：当前仅打包 one-shot-sim，安装后复制到 ~/.agents/skills，并为 ~/.codex/skills 与 ~/.claude/skills 创建相对 symlink；同步后端规范和测试。

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `53eb01d` | feat: distribute bundled one-shot-sim skill --leip |

### Testing

- [OK] `python3 -m unittest discover -s tests -p 'test_ops.py'`
- [OK] `python3 -m unittest discover -s tests`
- [OK] `python3 -m py_compile app/ops.py app/api.py scripts/build_app.py scripts/build_standalone_app.py`
- [OK] `git diff --check`

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 7: Adapt manager to Beilo Trellis 0.6

**Date**: 2026-06-17
**Task**: Adapt manager to Beilo Trellis 0.6
**Branch**: `main`

### Summary

Updated Trellis Manager defaults to Beilo distribution branch beilo/main, aligned Git builds to root pnpm build, added explicit 0.5.x to 0.6.x migrate update confirmation, verified wrapper mem help support, and documented the new backend contract.

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `ab94074` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 8: 添加使用说明入口

**Date**: 2026-06-19
**Task**: 添加使用说明入口
**Branch**: `main`

### Summary

为 Trellis Manager Desktop 增加 Header 使用说明入口，通过后端 get_help_url/open_in_browser 打开 resources/help.html，并补充 one-shot-sim 自动挡 finish 提交许可规则。

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `d16c7784103f6c7eee637000f62f47350ebda722` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete
