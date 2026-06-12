# Trellis Manager Desktop

面向 macOS 的独立 Trellis 管理客户端。它先维护团队分发版 Trellis 工具仓库，再保证本机 `tl` / `trellis` 可用，最后用这套命令给业务项目执行 `init` / `update`。

## 当前架构

- 桌面壳：Python 3.11+ + `pywebview`
- 前端 UI：`frontend/` 下的 React + Vite + shadcn 风格组件
- 后端桥接：`app/api.py` 通过 pywebview JS API 暴露操作
- 核心命令逻辑：`app/ops.py`
- 启动器：`launcher.py` 负责创建 `~/.beilo-trellis/manager-app/.venv` 并安装 `requirements.txt`

`main.py` 支持通过 `TRELLIS_USE_DEV_SERVER=1` 环境变量强制使用 Vite dev server；否则优先加载 `frontend/dist/index.html`（不存在时回退到 dev server）。

## 运行

### 开发模式（推荐）

前端改动后由 Vite HMR 即时生效：

```bash
cd apps/trellis-manager-desktop
./run.sh dev
```

或者手动分步操作：

```bash
cd apps/trellis-manager-desktop/frontend
pnpm install
pnpm dev
```

然后另开终端：

```bash
cd apps/trellis-manager-desktop
python3 launcher.py
```

### 构建模式（生产）

```bash
cd apps/trellis-manager-desktop
./run.sh build
```

或者手动分步操作：

```bash
cd apps/trellis-manager-desktop/frontend
pnpm install
pnpm build
```

然后启动：

```bash
cd apps/trellis-manager-desktop
python3 launcher.py
```

## 功能边界

- 默认团队仓库：`https://github.com/beilo/Trellis.git`
- 默认下载加速：`https://xget.xi-xu.me/gh/beilo/Trellis.git`，失败后回退 GitHub
- 默认分发分支：`sync/v0.6.0-rc`
- 默认安装目录：`~/.beilo-trellis/Trellis`
- 默认命令目录：`~/.beilo-trellis/bin`
- `tl` 和 `trellis` wrapper 都指向本地工具仓库的 `packages/cli/bin/trellis.js`
- 启动只检查状态，不自动下载或更新
- 检查类操作不锁住按钮；下载、更新、构建、init、update 这类写操作会锁住按钮
- 工具仓库 dirty 时阻止更新
- 业务项目必须是 git 仓库
- 已有 `.trellis` 的项目禁止 init，只允许 update
- 项目 init 会先执行 `tl init -y`，再执行 `tl update --force`
- 项目 update 使用 `tl update --force`
- 客户端不负责业务项目 `git add` / `commit` / `push`

## 本地源码 zip 安装

当用户机器无法可靠访问 GitHub 进行 `git clone` 时，可以通过本地源码 zip 安装 Trellis 工具仓库：

1. **维护者流程**：点击工具仓库卡片上的「打开分发分支」链接，在 GitHub 页面下载分支 zip（或通过 `https://codeload.github.com/beilo/Trellis/zip/refs/heads/sync/v0.6.0-rc` 获取）
2. **分享**：将 zip 通过内部渠道分享给团队成员
3. **安装**：在「本地源码 zip 安装」区域输入 zip 文件路径，点击「安装」
4. **更新**：zip 安装的工具仓库不能在线 `git pull`，如需更新请选择新的 zip 并点击「重装」

zip 安装的源码仍然是源码（不是预构建 CLI），因此仍然需要本地有可用的 `node` 和 `pnpm` 来执行依赖安装和构建。

## 打包轻量 `.app`

先构建前端：

```bash
cd apps/trellis-manager-desktop/frontend
pnpm install
pnpm build
```

再打包桌面 app：

```bash
cd apps/trellis-manager-desktop
python3 scripts/build_app.py
open "dist/Trellis Manager.app"
```

这个 `.app` 不是 PyInstaller 包，不内置 Python 运行时；它会把客户端源码和 `frontend/dist` 放进 app bundle，双击后用系统 Python 3.11+ 和 home 目录下的虚拟环境启动。

## 打包独立 `.app`

面向 macOS Apple 芯片分发时，使用独立包。它会把 Python 运行时、`pywebview` 依赖和前端静态资源一起打进 `.app`，用户不需要预装 Python 或联网安装 Python 依赖。

先构建前端：

```bash
cd apps/trellis-manager-desktop/frontend
pnpm install
pnpm build
```

再打包独立 app：

```bash
cd apps/trellis-manager-desktop
python3 scripts/build_standalone_app.py
open "dist/standalone/Trellis Manager.app"
```

可分发压缩包会生成在：

```bash
apps/trellis-manager-desktop/dist/standalone/Trellis Manager-<version>-macos-arm64.zip
```

## 维护者发包命令

应用版本以根目录 `package.json.version` 为唯一来源。`frontend/package.json.version` 只属于前端私有包，不代表 Trellis Manager Desktop 应用版本；工具仓库的 Trellis 版本和分发分支也不参与本应用发包。

### 1. 更新应用版本

```bash
npm run release:version -- 0.1.1
```

这个命令会：

- 校验工作区干净和版本格式
- 更新根 `package.json.version`
- 生成版本提交
- 创建本地 tag，例如 `v0.1.1`
- 输出下一步打包和 dry-run 发布命令

### 2. 打包应用发布包

```bash
npm run release:package
```

这个命令会复用现有 `frontend/node_modules`，执行：

```bash
cd frontend
npm install
npx vite build
```

然后生成独立 `.app` 和版本化 zip：

```bash
dist/standalone/Trellis Manager.app
dist/standalone/Trellis Manager-0.1.1-macos-arm64.zip
```

只有明确需要修复前端依赖目录时，才使用清理模式：

```bash
npm run release:package -- --clean
```

### 3. 发布前检查

```bash
npm run release:publish -- 0.1.1 --dry-run
```

dry-run 只校验并打印将执行的 `git` / `gh` 命令，不 push、不创建 release、不上传 asset。

发布前会校验：

- 根 `package.json.version` 等于命令版本
- 工作区干净
- 本地 tag 存在
- `gh auth status` 可用
- zip 文件名包含版本
- app bundle `Info.plist` 版本匹配
- zip 产物晚于版本提交

### 4. 上传 GitHub Release

```bash
npm run release:publish -- 0.1.1
```

默认遇到同名远端 tag、release 或 asset 会失败退出。补发同版本 zip 时显式使用：

```bash
npm run release:publish -- 0.1.1 --replace
```

`--replace` 只覆盖同名 release asset，不删除 tag，也不删除整份 release。

### 失败恢复

发包命令不会在后续失败时自动回滚版本提交、tag 或 release。按实际情况手动恢复：

```bash
git tag -d v0.1.1
git reset --soft HEAD~1
gh release delete v0.1.1 --cleanup-tag
```

## 打包踩坑记录

本节记录实际打包过程中遇到的问题和解法，避免重复踩坑。

### 1. 前端依赖不在 pnpm workspace 内

`apps/trellis-manager-desktop/frontend` 未被 `pnpm-workspace.yaml` 包含（workspace 只声明了 `packages/*`），因此根目录的 `pnpm install` 不会安装前端依赖，`pnpm --filter frontend build` 也找不到项目。

**解法**：进入 `frontend/` 目录单独安装依赖。由于 pnpm hoist 链断裂，用 npm 更可靠：

```bash
cd apps/trellis-manager-desktop/frontend
npm install
```

### 2. tsc 版本不匹配

`package.json` 声明 `typescript: ~6.0.2`，但根 workspace 实际安装的是 `5.9.3`。pnpm hoist 导致前端 symlink 指向根目录的 5.9.3，而 6.0 的包根本不存在，`tsc -b` 会报 `MODULE_NOT_FOUND`。此外 `tsconfig.app.json` 中的 `ignoreDeprecations: "6.0"` 在 5.x 上也不被识别。

**解法**：跳过 tsc 类型检查，直接用 vite build（vite 不依赖 tsc 产线，noEmit 模式只做类型检查）：

```bash
cd apps/trellis-manager-desktop/frontend
npx vite build
```

### 3. vite 必须从 frontend 目录运行

vite 以 `index.html` 为入口，它相对于 cwd 查找。如果在项目根目录调用 `vite build`，会报 `UNRESOLVED_ENTRY: Cannot resolve entry module index.html`。

**解法**：始终先 `cd` 到 `frontend/` 再执行构建命令。

### 4. node_modules/.bin 内 symlink 可能断裂

pnpm 的 `.bin` symlink 指向全局 store 的硬链接路径，如果 store 中对应包版本被替换（比如 workspace 其他成员升级了 typescript），symlink 会悬空。`./node_modules/.bin/vite` 看起来存在但执行报 `Cannot find module`。

**解法**：删掉 `frontend/node_modules` 重新 `npm install`，npm 不用 symlink 机制，不会断裂。

### 底层手工打包命令

```bash
cd /Users/am/temp/Trellis/apps/trellis-manager-desktop

# 1. 构建前端
cd frontend
rm -rf node_modules
npm install
npx vite build
cd ..

# 2. 打包独立 .app（含 Python 运行时，用户无需预装 Python）
python3 scripts/build_standalone_app.py

# 3. 产出物
# .app → dist/standalone/Trellis Manager.app
# .zip → dist/standalone/Trellis Manager-<version>-macos-arm64.zip

# 4. 打包轻量 .app（不含 Python 运行时，需要系统 Python 3.11+）
# python3 scripts/build_app.py
# .app → dist/Trellis Manager.app
```

这个包未做 Apple Developer ID 签名和 notarize。正式公网分发还需要补签名、公证和 DMG 流程；内部小范围分发可以先用 zip。

下载或更新 Trellis 工具仓库有两种方式：
- **在线 Git 安装**：需要用户机器可访问 git 网络，使用「下载 / 更新并构建」按钮
- **本地 zip 安装**：不需要 GitHub 访问，使用「本地源码 zip 安装」区域，适合网络受限环境

无论哪种方式，都需要系统有可用的 `node` 和 `pnpm` 来执行依赖安装和构建。如果用户通过 nvm 安装 Node，客户端会按当前用户目录补充 `~/.nvm/versions/node/*/bin`，避免从 Finder 启动时拿不到终端 PATH。

## 验证

```bash
cd apps/trellis-manager-desktop/frontend
pnpm build

cd /Users/am/temp/Trellis
python3 -m unittest discover apps/trellis-manager-desktop/tests -v
python3 -m py_compile apps/trellis-manager-desktop/main.py apps/trellis-manager-desktop/launcher.py apps/trellis-manager-desktop/app/*.py apps/trellis-manager-desktop/scripts/*.py apps/trellis-manager-desktop/tests/*.py
python3 apps/trellis-manager-desktop/scripts/build_app.py
python3 apps/trellis-manager-desktop/scripts/build_standalone_app.py
git diff --check
```

验证结束后清理本目录生成的 Python 缓存：

```bash
find apps/trellis-manager-desktop -type d -name __pycache__ -prune -exec rm -rf {} +
find apps/trellis-manager-desktop -name '*.pyc' -delete
```
