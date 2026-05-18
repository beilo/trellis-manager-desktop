from __future__ import annotations

import plistlib
import shutil
import stat
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = APP_ROOT / "dist"
APP_DIR = DIST_DIR / "Trellis Manager.app"
CONTENTS = APP_DIR / "Contents"
MACOS = CONTENTS / "MacOS"
RESOURCES = CONTENTS / "Resources"
BUNDLE_ROOT = RESOURCES / "trellis-manager-desktop"
FRONTEND_DIST = APP_ROOT / "frontend" / "dist"


def main() -> int:
    if APP_DIR.exists():
        shutil.rmtree(APP_DIR)
    MACOS.mkdir(parents=True)
    RESOURCES.mkdir(parents=True)
    copy_resources()
    write_info_plist()
    write_launcher()
    print(f"已生成：{APP_DIR}")
    return 0


def copy_resources() -> None:
    BUNDLE_ROOT.mkdir(parents=True)
    for filename in ["launcher.py", "main.py", "requirements.txt"]:
        shutil.copy2(APP_ROOT / filename, BUNDLE_ROOT / filename)
    shutil.copytree(
        APP_ROOT / "app",
        BUNDLE_ROOT / "app",
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    if FRONTEND_DIST.exists():
        # 只把构建后的静态前端放进 .app，避免把 node_modules 打进交付包。
        shutil.copytree(FRONTEND_DIST, BUNDLE_ROOT / "frontend" / "dist")


def write_info_plist() -> None:
    payload = {
        "CFBundleDisplayName": "Trellis Manager",
        "CFBundleExecutable": "trellis-manager",
        "CFBundleIdentifier": "cc.beilo.trellis-manager",
        "CFBundleName": "Trellis Manager",
        "CFBundlePackageType": "APPL",
        "CFBundleShortVersionString": "0.1.0",
        "LSMinimumSystemVersion": "13.0",
    }
    with (CONTENTS / "Info.plist").open("wb") as file:
        plistlib.dump(payload, file)


def write_launcher() -> None:
    launcher = MACOS / "trellis-manager"
    # .app 只做轻量启动壳，真实依赖仍由 launcher.py 管理到本地 .venv。
    launcher.write_text(
        "#!/bin/sh\n"
        'export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"\n'
        'APP_ROOT="$(cd "$(dirname "$0")/../Resources/trellis-manager-desktop" && pwd)"\n'
        'cd "$APP_ROOT"\n'
        'exec /usr/bin/env python3 "launcher.py"\n',
        encoding="utf-8",
    )
    launcher.chmod(launcher.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


if __name__ == "__main__":
    raise SystemExit(main())
