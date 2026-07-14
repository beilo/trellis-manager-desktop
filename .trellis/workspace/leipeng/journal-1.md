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

- Changed the zip snapshot success message from a pull-focused warning to an explicit local validation success message.
- Added a regression test that builds a non-git Trellis source snapshot, verifies `source_type="zip_snapshot"`, and asserts no `git fetch` is attempted.

### Git Commits

| Hash | Message |
|------|---------|
| `25a83be` | (see git log) |

### Testing

- [OK] `python3 -m py_compile main.py launcher.py app/*.py scripts/*.py tests/*.py`
- [OK] `git diff --check`
- [OK] `python3 -m unittest discover -s tests -p 'test_ops.py' -v`
- [OK] `python3 -m unittest discover tests -v`

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

- Added desktop backend operations for initialized-project Configure and explicit GitNexus setup.
- Exposed new pywebview and frontend API wrappers, then wired ProjectCard buttons and App handlers.
- Made manual Update available for any initialized project while preserving the preview/confirm flow.
- Documented action terminology in CONTEXT, added a GitNexus ADR, and captured the cross-layer contract in backend code-spec.

### Git Commits

| Hash | Message |
|------|---------|
| `d506669` | (see git log) |

### Testing

- [OK] `python3 tests/test_ops.py`
- [OK] `python3 tests/test_ui.py`
- [OK] `npm run build`
- [OK] `npm run lint`
- [OK] `python3 -m py_compile main.py launcher.py app/*.py scripts/*.py tests/*.py`
- [OK] `python3 -m unittest discover tests -v`
- [OK] `git diff --check`

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


## Session 9: Clarify zip snapshot repo check status

**Date**: 2026-06-19
**Task**: Clarify zip snapshot repo check status
**Branch**: `main`

### Summary

Clarified zip snapshot tool repository check copy to state that local source snapshot validation succeeded, and added regression coverage proving zip snapshots are validated locally without git fetch.

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `88240d8` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 10: Desktop project action split

**Date**: 2026-06-19
**Task**: Desktop project action split
**Branch**: `main`

### Summary

Split desktop project actions into Init, Configure, manual Update, and explicit GitNexus Setup. Added backend operations, frontend buttons/API wiring, regression tests, ADR, CONTEXT terminology, and backend code-spec contract.

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `970d279` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 11: 删除 Configure 项目动作

**Date**: 2026-06-21
**Task**: 删除 Configure 项目动作
**Branch**: `main`

### Summary

彻底移除 Configure 项目动作：删除前端按钮和 API wrapper、后端 pywebview/ops 入口、相关单测，并同步 CONTEXT、GitNexus ADR 和 backend quality spec；验证通过 frontend build/lint、python3 tests/test_ops.py、git diff --check。

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `2ee0941` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 12: Trellis Loop 任务监听

**Date**: 2026-07-14
**Task**: Trellis Loop 任务监听
**Branch**: `main`

### Summary

实现桌面端任务监听、搜索、详情、归档与终端定位；新增后端契约及完整回归验证。

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `01039ba` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 13: Copy task check prompt

**Date**: 2026-07-14
**Task**: Copy task check prompt
**Branch**: `main`

### Summary

Added a task monitor action that copies a read-only diagnostic prompt from loaded ongoing tasks, with clipboard state handling, tests, and frontend spec coverage.

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `701f453` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete


## Session 14: 任务详情复制基础信息

**Date**: 2026-07-14
**Task**: 任务详情复制基础信息
**Branch**: `main`

### Summary

在任务监听详情卡片增加 7 行基础信息复制，复用界面格式化结果；补齐剪贴板成功/失败处理、单元测试和前端 code-spec。

### Main Changes

(Add details)

### Git Commits

| Hash | Message |
|------|---------|
| `ad8e61b` | (see git log) |

### Testing

- [OK] (Add test results)

### Status

[OK] **Completed**

### Next Steps

- None - task complete
