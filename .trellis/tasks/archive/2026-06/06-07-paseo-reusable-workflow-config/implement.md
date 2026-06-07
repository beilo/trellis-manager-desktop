# Implementation Plan

## Scope

只实现项目级 Paseo workflow 配置和执行入口。

不写桌面 UI，不改 Paseo upstream，不启动真实 agent 测试。

## Ordered Checklist

1. 选择并固定 workflow 文件位置。
   - 推荐：项目级 agent 资产目录。
   - 验收点：能按 workflow 名称找到配置。

2. 定义首版 workflow schema。
   - 支持 `name`、`description`、`inputs`、`steps`、`outputs`。
   - 支持 step 的 `id`、`title`、`provider`、`cwd`、`prompt`、`wait`、`stopOnFailure`、`requiresArtifacts`。
   - 验收点：无效字段或缺少必填字段能给出明确错误。

3. 新增默认 `prd-impl-review` workflow。
   - `plan` 使用 Codex。
   - `implement` 使用 Claude Code。
   - `review` 使用 Codex。
   - 验收点：dry-run 能展示三个解析后的步骤。

4. 实现 workflow executor。
   - 加载 workflow。
   - 合并输入。
   - 解析模板变量。
   - 按顺序执行步骤。
   - 失败即停。
   - 验收点：fake runner 下可复现成功和失败流程。

5. 实现 Paseo CLI adapter。
   - 检查 CLI / daemon。
   - 构造 `paseo run` 参数。
   - 支持 JSON 输出解析。
   - 支持 dry-run。
   - 验收点：不依赖真实 Paseo 也能测试命令构造。

6. 实现 agent-facing 入口。
   - 主 agent 可以通过固定 skill / command 调用 workflow。
   - 入口只负责参数收集和调用 executor，不复制 executor 逻辑。
   - 验收点：入口文档说明如何调用 `prd-impl-review`。

7. 增加测试。
   - parser tests。
   - template resolver tests。
   - executor success / failure tests。
   - adapter command-construction tests。
   - dry-run no-execute tests。

8. 更新任务文档或使用说明。
   - 记录如何 dry-run。
   - 记录如何真实执行。
   - 记录失败时怎么看 agent id / Paseo logs。

## Validation Commands

规划阶段验证：

```bash
python3 ./.trellis/scripts/task.py validate .trellis/tasks/06-07-paseo-reusable-workflow-config
```

实现阶段建议验证：

```bash
python3 -m py_compile <executor-python-files>
python3 -m unittest <workflow-tests> -v
```

如果执行器使用 TypeScript，则改用项目实际测试命令：

```bash
npm test -- <workflow-tests>
```

真实 Paseo agent 不作为自动测试依赖；最多作为手动验收。

## Review Gates

进入实施前必须确认：

- `prd.md`、`design.md`、`implement.md` 都存在。
- PRD 没有 Open Questions。
- workflow 首版只做线性三步。
- 不修改 Paseo upstream。
- 不新增桌面 UI。

实施完成后 review 必须确认：

- dry-run 不启动 agent。
- 失败场景不会继续后续步骤。
- prompt 模板不依赖隐藏会话上下文。
- secret 不进入 workflow 配置。
- 对 Trellis artifacts 的读取要求写在 step prompt 或前置检查中。

## Rollback Points

- 如果 workflow schema 设计过宽，回滚到只支持 `prd-impl-review` 所需字段。
- 如果 agent-facing 入口变复杂，保留 CLI executor，删除入口包装。
- 如果 Paseo CLI 输出不稳定，adapter 限定只依赖明确的 JSON 输出模式。
- 如果真实执行不稳定，保留 dry-run 和 fake-runner 测试，推迟真实执行集成。

## Non-Goals During Implementation

- 不做并行工作流。
- 不做审批系统。
- 不做 UI 配置编辑器。
- 不自动安装 Paseo。
- 不自动启动或停止 Paseo daemon，除非用户明确要求。
- 不替代 Trellis task lifecycle。
