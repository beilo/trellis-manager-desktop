from __future__ import annotations

import os
import platform
import plistlib
import shutil
import subprocess
import sys
import venv
from pathlib import Path

try:
    from release import read_app_version
except ModuleNotFoundError:  # pragma: no cover - supports importing as scripts.build_standalone_app
    from scripts.release import read_app_version

APP_NAME = "Trellis Manager"
APP_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIST = APP_ROOT / "frontend" / "dist"
APP_RESOURCES = APP_ROOT / "resources"
BUILD_ROOT = APP_ROOT / ".build" / "standalone"
BUILD_VENV = BUILD_ROOT / ".venv"
PYINSTALLER_WORK = BUILD_ROOT / "pyinstaller-work"
PYINSTALLER_SPEC = BUILD_ROOT / "pyinstaller-spec"
DIST_ROOT = APP_ROOT / "dist" / "standalone"
APP_BUNDLE = DIST_ROOT / f"{APP_NAME}.app"
REQUIREMENTS = APP_ROOT / "requirements.txt"
ENTRYPOINT = APP_ROOT / "launcher.py"


def main() -> int:
    ensure_macos_arm64()
    ensure_frontend_dist()
    python = ensure_build_venv()
    install_build_dependencies(python)
    build_app(python)
    write_bundle_version(read_app_version(APP_ROOT))
    zip_path = create_zip()
    print(f"已生成独立应用：{APP_BUNDLE}")
    print(f"已生成分发压缩包：{zip_path}")
    return 0


def ensure_macos_arm64() -> None:
    if sys.platform != "darwin":
        raise SystemExit("独立 macOS .app 只能在 macOS 上构建。")
    if platform.machine() != "arm64":
        raise SystemExit("当前脚本目标是 macOS Apple 芯片，请在 arm64 Mac 上构建。")


def ensure_frontend_dist() -> None:
    index = FRONTEND_DIST / "index.html"
    if not index.exists():
        raise SystemExit(
            "缺少 frontend/dist/index.html。请先执行：\n"
            "  cd apps/trellis-manager-desktop/frontend && npm install && npx vite build"
        )


def ensure_build_venv() -> Path:
    python = BUILD_VENV / "bin" / "python"
    if not python.exists():
        # 打包依赖放在项目本地 .build，避免污染用户全局 Python 环境。
        BUILD_ROOT.mkdir(parents=True, exist_ok=True)
        venv.EnvBuilder(with_pip=True).create(BUILD_VENV)
    return python


def install_build_dependencies(python: Path) -> None:
    subprocess.run(
        [str(python), "-m", "pip", "install", "--upgrade", "pip"],
        check=True,
    )
    subprocess.run(
        [str(python), "-m", "pip", "install", "-r", str(REQUIREMENTS), "pyinstaller>=6.0"],
        check=True,
    )


def build_app(python: Path) -> None:
    if APP_BUNDLE.exists():
        shutil.rmtree(APP_BUNDLE)
    PYINSTALLER_WORK.mkdir(parents=True, exist_ok=True)
    PYINSTALLER_SPEC.mkdir(parents=True, exist_ok=True)
    DIST_ROOT.mkdir(parents=True, exist_ok=True)

    subprocess.run(
        [
            str(python),
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--windowed",
            "--name",
            APP_NAME,
            "--distpath",
            str(DIST_ROOT),
            "--workpath",
            str(PYINSTALLER_WORK),
            "--specpath",
            str(PYINSTALLER_SPEC),
            "--add-data",
            f"{FRONTEND_DIST}{os.pathsep}frontend/dist",
            "--add-data",
            f"{APP_RESOURCES}{os.pathsep}resources",
            "--hidden-import",
            "webview.platforms.cocoa",
            str(ENTRYPOINT),
        ],
        check=True,
    )
    collected_dir = DIST_ROOT / APP_NAME
    if collected_dir.exists():
        # PyInstaller 会先生成 onedir 中间目录，再生成 .app；分发只需要 .app。
        shutil.rmtree(collected_dir)


def write_bundle_version(version: str) -> None:
    plist_path = APP_BUNDLE / "Contents" / "Info.plist"
    if not plist_path.exists():
        raise SystemExit(f"未找到 Info.plist：{plist_path}")
    with plist_path.open("rb") as file:
        payload = plistlib.load(file)
    payload["CFBundleShortVersionString"] = version
    with plist_path.open("wb") as file:
        plistlib.dump(payload, file)


def versioned_zip_path(version: str) -> Path:
    return DIST_ROOT / f"{APP_NAME}-{version}-macos-arm64.zip"


def create_zip() -> Path:
    if not APP_BUNDLE.exists():
        raise SystemExit(f"未找到打包产物：{APP_BUNDLE}")
    zip_path = versioned_zip_path(read_app_version(APP_ROOT))
    if zip_path.exists():
        zip_path.unlink()
    subprocess.run(
        ["ditto", "-c", "-k", "--keepParent", str(APP_BUNDLE), str(zip_path)],
        check=True,
    )
    return zip_path


if __name__ == "__main__":
    raise SystemExit(main())
