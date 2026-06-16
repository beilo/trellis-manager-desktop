# 公共技能全局分发实施计划

## Checklist

1. 在 `app/ops.py` 中将 one-shot-sim 专用常量和函数改为公共技能 bundle root 与同步函数。
2. 更新 git 安装、本地 zip、远端 zip 的调用和返回 details 包装。
3. 更新 `tests/test_ops.py` 的导入、安装流程断言和同步函数测试。
4. 更新 `.trellis/spec/backend/quality-guidelines.md`，把旧 one-shot-sim 复制语义改为公共技能集合 + `.agents` 权威源 + symlink。
5. 运行后端相关测试与 Python 编译检查。

## Validation Commands

```bash
python3 -m unittest discover -s tests -p 'test_ops.py'
python3 -m py_compile app/ops.py app/api.py scripts/build_app.py scripts/build_standalone_app.py
```

## Risky Files

- `app/ops.py`: 安装成功路径上的后置同步逻辑，错误会阻断工具链安装。
- `tests/test_ops.py`: 旧测试假设 Codex/Claude 直接得到普通目录副本，需要同步更新。
- `.trellis/spec/backend/quality-guidelines.md`: 旧规范会与新实现冲突，必须更新。

## Rollback Point

如果公共技能集合同步引入阻断，可临时恢复为旧函数调用，但必须同时恢复 spec 和测试；不要只回滚代码。
