# Paseo 可复用工作流配置变更记录

## 背景

用户需要把“主 Agent 聊需求 -> Codex 生成 PRD / Design / Implement -> Claude Code 实施 -> Codex Review”的多 agent 流程沉淀成可复用配置，而不是每次临时手写 orchestration prompt。

## Changelog

- 新增项目级 workflow 配置 `prd-impl-review`，描述 Codex 规划、Claude Code 实施、Codex Review 的线性三步流程。
- 新增 `scripts/run_paseo_workflow.py`，支持按名称加载 workflow、校验输入、解析模板、dry-run、构造 `paseo run --json`、失败即停和结构化输出。
- 新增 `.agents/skills/paseo-workflow/SKILL.md`，给主 Agent 一个稳定入口，避免把 Paseo 调度细节散落在临时 prompt 中。
- 新增 `tests/test_paseo_workflow.py`，覆盖 dry-run、必填输入、daemon 预检、step 执行、失败即停和 artifact 缺失。
- 更新 Trellis task 规划文档，明确这是项目级 agent 工作流资产，不改桌面 UI、不改 Paseo upstream、不做通用 DAG workflow engine。
- 更新 backend quality spec，记录项目级 Paseo workflow 执行器的 CLI 签名、错误码、测试要求和禁止的 shell 拼接模式。

## 验证

- `python3 -m unittest discover tests -v`
- `python3 -m py_compile main.py launcher.py app/*.py scripts/*.py tests/*.py`
- `python3 scripts/run_paseo_workflow.py prd-impl-review --cwd . --task "验证 dry-run" --dry-run --json`
- `git diff --check -- scripts/run_paseo_workflow.py tests/test_paseo_workflow.py .agents/workflows/prd-impl-review.json .agents/skills/paseo-workflow/SKILL.md .trellis/tasks/06-07-paseo-reusable-workflow-config/prd.md .trellis/tasks/06-07-paseo-reusable-workflow-config/design.md .trellis/tasks/06-07-paseo-reusable-workflow-config/implement.md`
