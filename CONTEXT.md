# Trellis Manager Desktop

Trellis Manager Desktop is a macOS desktop client for maintaining a local Trellis tool repository and applying Trellis commands to business projects. This language keeps the desktop app release concepts separate from the Trellis tool repository distribution concepts.

## Language

**应用版本**:
The version of the Trellis Manager Desktop app itself.
_Avoid_: 工具版本, Trellis 版本

**应用发布包**:
The distributable Trellis Manager Desktop macOS app bundle and zip archive.
_Avoid_: 工具仓库 zip, 源码 zip

**工具仓库分发分支**:
The branch of the Trellis tool repository that the desktop app installs or updates for users.
_Avoid_: 应用版本, 应用发布分支

**工具仓库源码 zip**:
A zip snapshot of the Trellis tool repository source used when GitHub clone or pull is unavailable.
_Avoid_: 应用发布包

**项目首次接入动作**:
The desktop project action that runs Trellis `init` for a git project that does not yet have `.trellis`. In Manager this is `Init`, and it keeps the post-init forced update behavior.
_Avoid_: Configure, GitNexus Setup

**项目配置动作**:
The desktop project action that reapplies configured developer name and platforms to an already initialized Trellis project. In Manager this is `Configure`; it does not synchronize managed Trellis files.
_Avoid_: Init, Update, 外部集成安装动作

**项目手动同步动作**:
The desktop project action that runs Trellis `update --force` for an already initialized project, even when the project is already on the latest version.
_Avoid_: Init, Configure, GitNexus Setup

**外部集成安装动作**:
The desktop project action that installs or configures a non-Trellis integration inside a business project. `GitNexus Setup` belongs here and stays separate from Trellis Init/Configure/Update.
_Avoid_: Trellis 模板同步, 项目首次接入动作
