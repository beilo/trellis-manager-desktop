# Paseo 可复用工作流配置

## Goal

把“主 Agent 聊需求 -> Codex 生成 PRD / Design / Implement -> Claude Code 实施 -> Codex Review”的多 agent 流程沉淀为项目级可复用工作流配置，后续通过固定入口调用，不再依赖每次临时手写长 prompt。

## Problem Statement

用户已经理解 Paseo 是本地 agent 调度层，可以创建 Codex、Claude Code 等子 agent，并在子 agent 完成后通知主 agent。当前缺口是：Paseo CLI 自身没有内置 `workflow run <name>` 这类声明式工作流入口，导致多 agent 流程仍然靠主 agent 临时组织。

如果继续靠临时 prompt，PRD / Design / Implement 的生成顺序、实施 agent 的上下文读取、review agent 的检查口径、失败后的停止条件都会随会话漂移。用户需要一个项目内可读、可版本化、可重复调用的工作流配置，把固定流程和可变输入分开。

## Solution

提供一个项目级 Paseo 工作流配置机制，由配置文件描述流程，由轻量执行入口读取配置并调用 Paseo CLI。

首版工作流固定为线性三步：

1. 规划：Codex 根据用户需求生成或补齐 Trellis `prd.md`、`design.md`、`implement.md`。
2. 实施：Claude Code 读取规划文档后实施。
3. 审查：Codex 对照规划文档和实际改动做 review，只输出问题、风险和缺失测试。

Paseo 继续只负责 agent 生命周期、日志、状态、通知和 worktree / cwd 调度。工作流配置和执行器负责步骤顺序、prompt 模板、变量替换、等待策略和失败停止条件。

## Confirmed Decisions

- 这不是桌面 UI 功能，不新增 Trellis Manager 前端页面。
- 这不是修改 Paseo 源码，不 fork `@getpaseo/cli`。
- 这不是完整 workflow engine，首版只支持线性步骤。
- 这不是替代 Trellis。Trellis 的 `prd.md` / `design.md` / `implement.md` 仍是规划事实来源。
- 首版不做并行分支、复杂条件表达式、审批节点或自动修复 review 结果。
- 工作流配置必须能被主 agent 调用，也应能被人通过命令行预览或执行。
- 工作流执行必须支持 dry-run，避免用户没看清步骤就启动 agent。
- 没有未澄清的产品问题；剩余工作是技术设计和实现取舍。

## Requirements

- 提供一个命名工作流配置，用于描述 `prd-impl-review` 这类多 agent 流程。
- 工作流配置必须包含输入定义、步骤定义、provider / model、cwd / worktree 策略、prompt 模板、等待策略和失败策略。
- 执行入口必须支持按名称加载工作流。
- 执行入口必须支持传入需求文本和工作目录。
- 执行入口必须支持 dry-run，输出解析后的步骤和将要调用的 Paseo 行为，不启动 agent。
- 执行入口必须在缺少必填输入时失败并给出明确原因。
- 执行入口必须在 Paseo daemon 不可用时失败并提示需要启动 Paseo。
- 执行入口必须按配置顺序执行步骤，默认前一步未成功不得进入下一步。
- 执行入口必须记录每个步骤的 agent id、provider、cwd、状态和摘要。
- 规划步骤必须明确产出 Trellis `prd.md`、`design.md`、`implement.md`。
- 实施步骤必须明确读取 Trellis 规划文档后再改动。
- Review 步骤必须明确对照规划文档和实际改动，只关注 bug、需求偏移、回归风险和缺失测试。
- 工作流配置不得包含 API key、token、provider secret 或本地私密凭据。
- 工作流不得绕过 Trellis 任务生命周期；进入实施前仍应由 Trellis task 处于可实施状态。
- 工作流应保留未来扩展到 `paseo loop run` 的空间，但首版不要求使用 loop。

## User Stories

1. As a主 agent user, I want to invoke a named workflow, so that I do not need to repeat the same orchestration prompt every time.
2. As a主 agent user, I want to pass a requirement into the workflow, so that the same workflow can be reused for different features.
3. As a主 agent user, I want the workflow to generate PRD, Design, and Implement artifacts first, so that implementation starts from explicit requirements.
4. As a主 agent user, I want the implementation agent to read the generated planning artifacts, so that implementation follows the agreed scope.
5. As a主 agent user, I want the review agent to compare code changes against the planning artifacts, so that review catches requirement drift.
6. As a主 agent user, I want provider and model choices to live in configuration, so that I can tune model roles without rewriting the executor.
7. As a主 agent user, I want every spawned agent id reported, so that I can inspect logs or send follow-up prompts through Paseo.
8. As a主 agent user, I want dry-run output, so that I can confirm the workflow before starting agents.
9. As a主 agent user, I want failed steps to stop the workflow, so that incomplete planning or implementation does not cascade.
10. As a workflow maintainer, I want workflow files to be plain text, so that they can be reviewed and versioned.
11. As a workflow maintainer, I want prompt templates near the step definitions, so that orchestration behavior is visible without reading executor internals.
12. As an implementation agent, I want explicit task and artifact context in my prompt, so that I do not infer scope from chat history.
13. As a review agent, I want a focused review prompt, so that I prioritize actionable defects over summaries.

## Acceptance Criteria

- [ ] A reusable workflow configuration exists for the PRD -> Implement -> Review flow.
- [ ] The workflow can be invoked by name with requirement text and cwd inputs.
- [ ] Dry-run prints resolved steps without calling Paseo.
- [ ] Missing workflow name, missing input, invalid config, and unavailable Paseo daemon produce explicit failures.
- [ ] The planner step is configured to use Codex and generate Trellis planning artifacts.
- [ ] The implement step is configured to use Claude Code and read Trellis planning artifacts.
- [ ] The review step is configured to use Codex and compare implementation against planning artifacts.
- [ ] Each completed step reports agent id, status, provider, cwd, and summary.
- [ ] The workflow stops before implementation if planning artifacts are missing or the planner step fails.
- [ ] The workflow stops before review if implementation fails.
- [ ] The implementation does not modify Paseo packages or Trellis Manager desktop UI.
- [ ] Tests validate config parsing, dry-run, command construction, step ordering, and failure handling with fake Paseo command execution.

## Out of Scope

- 修改 Paseo CLI / daemon 源码。
- 新增 Trellis Manager 桌面 UI。
- 全局安装、卸载或重配置 Paseo。
- 并行 DAG、审批节点、复杂条件表达式、自动 retry。
- 自动判断和修复 review 发现的问题。
- 替换 Trellis task、PRD、Design、Implement 或质量检查流程。
- 把 provider credentials 写进 workflow 配置。

## Further Notes

- 核心边界：Paseo 负责派 agent；工作流执行器负责读配置、套模板、串步骤、等待和失败处理。
- 当前规划没有未澄清问题。后续实现应先按 `design.md` / `implement.md` 执行，不需要再回到需求澄清。
