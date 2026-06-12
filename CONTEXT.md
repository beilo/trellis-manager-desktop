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
