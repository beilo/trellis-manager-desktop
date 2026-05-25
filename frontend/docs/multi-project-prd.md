# Trellis Manager 多项目管理功能 PRD

## 1. 背景与目标

Trellis Manager Desktop 需要从单项目模式扩展为多项目管理。用户可在本地管理多个 Trellis 业务项目，共用同一套工具链。

## 2. 用户交互设计

### 2.1 Tab 切换

- Header 右侧添加 Tab：**[工具链]** / **[项目]**
- 两个 Tab 共享同一套 Summary Cards 和 LogPanel
- 默认进入上次所在的 Tab

### 2.2 工具链 Tab

**功能范围：**
- 环境检查（EnvironmentCard）
- 工具仓库管理（RepoCard）
- 命令入口检查（CommandCard）
- **无 Init/Update 按钮**

**Summary Cards：**
- 只显示 3 个工具链状态卡片（环境、仓库、命令）
- 项目状态卡片隐藏

**布局：**
```
┌─────────────────────────────────────────────────┐
│ Header: [工具链] [项目]                          │
├─────────────────────────────────────────────────┤
│ [环境] [仓库] [命令]   ← 项目卡片隐藏           │
├─────────────────────────────────────────────────┤
│                                                 │
│  EnvironmentCard                                 │
│  RepoCard                                       │
│  CommandCard                                   │
│                                                 │
├─────────────────────────────────────────────────┤
│ LogPanel                                        │
└─────────────────────────────────────────────────┘
```

### 2.3 项目 Tab

**功能范围：**
- 项目列表（侧边栏）
- 项目详情（主区域）
- Init / Update / 检查项目 / 打开目录

**Summary Cards：**
- 显示全部 4 个状态卡片
- "当前项目" 跟随选中项目变化

**布局：**
```
┌─────────────────────────────────────────────────┐
│ Header: [工具链] [项目]                          │
├─────────────────────────────────────────────────┤
│ [环境] [仓库] [命令] [project-a]               │
├──────────────┬──────────────────────────────────┤
│ 项目列表     │  ProjectCard (选中项目详情)      │
│ ──────────  │  - 检查项目 / Init / Update      │
│ project-a ✓ │  - 打开目录                      │
│ project-b ⚠ │  - dirty 选项                    │
│ project-c ✗ │                                  │
│ [+ 添加]     │                                  │
│              │                                  │
├──────────────┴──────────────────────────────────┤
│ LogPanel                                        │
└─────────────────────────────────────────────────┘
```

## 3. 数据模型

### 3.1 配置扩展 (config.toml)

```toml
[manager]
trellis_repo = "/path/to/trellis"
projects = ["/path/to/project-a", "/path/to/project-b"]
last_selected_project = "/path/to/project-a"
recent_projects = ["/path/to/project-a", "/path/to/project-b", "/path/to/project-c"]
```

### 3.2 类型定义

```typescript
interface ManagerConfig {
  trellis_repo: string
  projects: string[]           // 新增：项目路径列表
  last_selected_project: string | null  // 新增：上次选中的项目
  recent_projects: string[]
}

interface AppState {
  activeTab: 'toolchain' | 'projects'  // 新增
  // ... 其他现有字段
  // 项目相关
  projects: string[]           // 替换 single projectPath
  selectedProject: string | null
  projectStatuses: Record<string, ProjectStatus>  // 缓存各项目状态
}
```

## 4. 功能详细设计

### 4.1 添加项目

- 点击 "+ 添加项目" 按钮
- 弹出系统目录选择器
- 选择目录后自动调用 `inspect_project` 检查项目状态
- 将路径添加到 `projects` 列表并保存
- 自动选中新添加的项目

### 4.2 删除项目

- 项目列表项 hover 时显示 × 按钮
- 点击 × 只从 `projects` 列表移除，不删除实际目录
- 保存更新后的配置
- 如果删除的是选中项目，自动选中列表第一个（或无选中）

### 4.3 选中项目

- 点击列表项选中
- 选中后加载该项目的 `ProjectStatus`
- 选中的项目路径保存到 `last_selected_project`
- 项目详情区域显示选中项目信息

### 4.4 项目状态缓存

- 各项目状态缓存在 `projectStatuses` 中
- 每次操作后更新对应项目状态
- 切换选中项目时直接读取缓存
- 需要时调用 `inspect_project` 刷新

### 4.5 Init / Update

- 只在项目 Tab 可操作
- 执行前检查当前选中项目
- 操作完成后更新项目状态缓存
- 日志输出到 LogPanel

### 4.6 批量 Update 与工具链配置

- 批量 Update 入口只放在项目 Tab 的项目列表顶部
- 工具链 Tab 不展示批量 Update 卡片，避免工具链配置和业务项目操作混在一起
- 批量 Update 对话框调用 `list_outdated_projects()`，默认全选过期项目，dirty 项目默认由后端跳过
- 勾选“允许 dirty 项目更新”后调用 `batch_update_projects(paths, allow_dirty=true)`
- 结果表保留成功、失败、跳过状态和消息，并提供跳转底部日志的入口
- Header 齿轮打开工具链设置；工具链 Tab 内保留设置卡片
- 设置页只编辑官方仓库 URL、加速镜像 URL、分发分支，工具仓库路径仍由 RepoCard 管理

## 5. API 扩展

### 5.1 新增 API

```python
# 获取项目列表
def get_projects() -> List[str]:
    """返回已保存的项目路径列表"""

# 保存项目列表
def save_projects(projects: List[str]) -> None:
    """保存项目列表到配置"""

# 添加项目（带验证）
def add_project(path: str) -> ProjectStatus:
    """添加项目并返回检查状态"""

# 移除项目
def remove_project(path: str) -> None:
    """从项目列表移除项目"""
```

### 5.2 前端 API 扩展

```typescript
interface PywebviewAPI {
  // 现有 API...

  // 新增
  get_projects(): Promise<string[]>
  save_projects(projects: string[]): Promise<void>
  add_project(path: string): Promise<ProjectStatus>
  remove_project(path: string): Promise<void>
}
```

## 6. 组件变更

### 6.1 App.tsx

- 新增 `activeTab` 状态
- 新增 `projects` 状态（项目列表）
- 新增 `selectedProject` 状态（当前选中）
- 新增 `projectStatuses` 状态（状态缓存）
- Tab 切换逻辑
- 条件渲染工具链/项目内容

### 6.2 Header

- 添加 Tab 切换按钮
- 响应式显示当前 Tab

### 6.3 ProjectList（新组件）

- 项目列表侧边栏
- 显示项目名称 + 状态指示器
- hover 显示删除按钮
- "+ 添加项目" 按钮

### 6.4 ProjectCard

- 复用现有逻辑
- props 改为接收选中项目信息

### 6.5 SummaryCards

- 根据 Tab 动态显示/隐藏项目状态卡片

## 7. 非功能性要求

### 7.1 性能

- 项目状态缓存避免重复 API 调用
- 批量操作暂不考虑

### 7.2 兼容性

- 现有单项目用户的数据需平滑迁移
- `recent_projects` 保留作为补充

### 7.3 边界情况

- 项目路径不存在：显示 error 状态
- 选中的项目被删除：自动切换到列表第一个
- 空项目列表：显示引导添加项目的提示

## 8. 测试要点

1. Tab 切换状态保持
2. 添加/删除项目后配置正确持久化
3. 选中项目状态正确显示
4. Init/Update 操作正确更新项目状态
5. 应用重启后恢复上次状态
6. 工具链 Tab 不显示项目相关内容
7. 批量 Update 单项失败不阻断后续项目，完成后刷新项目状态
8. 设置保存后重启仍生效，URL/分支校验阻止无效输入
