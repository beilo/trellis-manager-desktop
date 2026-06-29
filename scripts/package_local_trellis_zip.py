#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = Path.home() / ".beilo-trellis" / "Trellis"
DEFAULT_OUTPUT_DIR = ROOT / "dist" / "trellis-source-zips"

# 内置 zip 是发布产物，固定文件名和输出目录，方便 release.py 和 PyInstaller --add-data 稳定引用。
EMBEDDED_ZIP_NAME = "trellis-source"
EMBEDDED_ZIP_FILENAME = f"{EMBEDDED_ZIP_NAME}.zip"
EMBEDDED_OUTPUT_DIR = ROOT / "resources"
# suite 布局：桌面端与 clean Trellis 源码树同级，故默认取 ../Trellis。
DEFAULT_EMBEDDED_SOURCE = ROOT.parent / "Trellis"

REQUIRED_MARKERS = [
    "package.json",
    "pnpm-lock.yaml",
    "packages/cli/package.json",
    "packages/cli/bin/trellis.js",
]

EXCLUDED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".manager-temp",
    ".next",
    ".nuxt",
    ".turbo",
    ".vite",
    ".cache",
    ".pytest_cache",
    "coverage",
    "dist",
    "node_modules",
    "__pycache__",
}

EXCLUDED_FILES = {
    ".DS_Store",
    # 子模块源码里的 .git 通常是文件而非目录，也不能进入发布 zip。
    ".git",
}


class EmbeddedZipError(RuntimeError):
    """内置 zip 生成或校验失败，供 release.py 统一转成 ReleaseError 阻断发布。"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Package a local Trellis CLI source tree into a zip that Manager can install.",
    )
    parser.add_argument(
        "legacy_source",
        nargs="?",
        default=str(DEFAULT_SOURCE),
        help=f"local Trellis source tree, default: {DEFAULT_SOURCE}",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help=f"zip output directory, default: {DEFAULT_OUTPUT_DIR}",
    )
    parser.add_argument(
        "--name",
        help="zip file name without .zip; default uses source name and timestamp",
    )
    parser.add_argument(
        "--exclude-assets",
        action="store_true",
        help="exclude top-level assets/ to create a smaller zip for local CLI validation",
    )
    # 内置模式：固定输出 resources/trellis-source.zip，供桌面端发布打包使用。
    parser.add_argument(
        "--embedded",
        action="store_true",
        help="生成内置 trellis-source.zip 到 resources/，供发布流程打进 .app",
    )
    parser.add_argument(
        "--source",
        dest="embedded_source",
        help="内置模式下的 Trellis 源码树路径，默认同级 ../Trellis",
    )
    return parser.parse_args()


def validate_source(source: Path) -> None:
    """校验源码树是合法 Trellis 源码；失败抛 EmbeddedZipError 供上层统一处理。"""
    if not source.is_dir():
        raise EmbeddedZipError(f"source is not a directory: {source}")
    missing = [marker for marker in REQUIRED_MARKERS if not (source / marker).exists()]
    if missing:
        joined = ", ".join(missing)
        raise EmbeddedZipError(f"source is not a valid Trellis source tree, missing: {joined}")


def should_exclude(path: Path) -> bool:
    name = path.name
    if path.is_dir() and name in EXCLUDED_DIRS:
        return True
    if path.is_file() and name in EXCLUDED_FILES:
        return True
    return False


def iter_files(source: Path, *, exclude_assets: bool = False) -> list[Path]:
    files: list[Path] = []
    for current, dirnames, filenames in os.walk(source):
        current_path = Path(current)
        dirnames[:] = [
            dirname
            for dirname in dirnames
            if not should_exclude(current_path / dirname)
            and not (exclude_assets and current_path == source and dirname == "assets")
        ]
        for filename in filenames:
            path = current_path / filename
            if should_exclude(path):
                continue
            files.append(path)
    return sorted(files)


def make_zip(
    source: Path,
    output_dir: Path,
    name: str | None = None,
    *,
    exclude_assets: bool = False,
    overwrite: bool = False,
) -> Path:
    """把源码树写入 zip。

    overwrite=False 时已存在产物直接报错，保留原有行为；内置模式用 overwrite=True
    安全覆盖固定产物，避免发布时残留旧 zip。
    """
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    root_name = name or f"{source.name}-local-{timestamp}"
    zip_path = output_dir / f"{root_name}.zip"
    output_dir.mkdir(parents=True, exist_ok=True)
    if zip_path.exists():
        if not overwrite:
            raise EmbeddedZipError(f"zip already exists: {zip_path}")
        # 仅内置固定产物允许安全覆盖，避免误删用户自定义 zip。
        zip_path.unlink()

    files = iter_files(source, exclude_assets=exclude_assets)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            relative = path.relative_to(source)
            archive.write(path, Path(root_name) / relative)
    return zip_path


def validate_zip_contents(
    zip_path: Path,
    *,
    root_name: str = EMBEDDED_ZIP_NAME,
    required_markers: list[str] | None = None,
    excluded_dirs: set[str] | None = None,
) -> None:
    """校验 zip 内含必需 marker 且不包含被排除目录，发布前 fail fast 用。"""
    if not zip_path.is_file():
        raise EmbeddedZipError(f"zip 不存在：{zip_path}")
    if not zipfile.is_zipfile(zip_path):
        raise EmbeddedZipError(f"不是有效 zip 文件：{zip_path}")
    markers = required_markers if required_markers is not None else REQUIRED_MARKERS
    excluded = excluded_dirs if excluded_dirs is not None else EXCLUDED_DIRS
    with zipfile.ZipFile(zip_path) as archive:
        names = archive.namelist()
    missing = [marker for marker in markers if f"{root_name}/{marker}" not in names]
    if missing:
        raise EmbeddedZipError(f"zip 缺少源码 marker：{', '.join(missing)}")
    found_excluded: set[str] = set()
    for name in names:
        for part in name.split("/"):
            if part in excluded:
                found_excluded.add(part)
    if found_excluded:
        raise EmbeddedZipError(f"zip 包含应排除目录：{', '.join(sorted(found_excluded))}")


def generate_embedded_zip(
    source: Path | str | None = None,
    *,
    output_dir: Path = EMBEDDED_OUTPUT_DIR,
) -> Path:
    """生成内置 trellis-source.zip 并校验内容，供发布流程调用。"""
    src = Path(source).expanduser().resolve() if source else DEFAULT_EMBEDDED_SOURCE.resolve()
    validate_source(src)
    output_dir.mkdir(parents=True, exist_ok=True)
    zip_path = make_zip(src, output_dir, EMBEDDED_ZIP_NAME, overwrite=True)
    validate_zip_contents(zip_path, root_name=EMBEDDED_ZIP_NAME)
    return zip_path


def validate_embedded_zip(zip_path: Path = EMBEDDED_OUTPUT_DIR / EMBEDDED_ZIP_FILENAME) -> None:
    """校验内置 zip 是否可用于离线安装；不可用则抛 EmbeddedZipError。"""
    validate_zip_contents(zip_path, root_name=EMBEDDED_ZIP_NAME)


def main() -> int:
    args = parse_args()
    try:
        if args.embedded:
            # 内置模式固定输出 resources/trellis-source.zip，并立即校验内容。
            zip_path = generate_embedded_zip(args.embedded_source)
        else:
            source = Path(args.legacy_source).expanduser().resolve()
            output_dir = Path(args.output_dir).expanduser().resolve()
            validate_source(source)
            zip_path = make_zip(source, output_dir, args.name, exclude_assets=args.exclude_assets)
    except EmbeddedZipError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1
    print(zip_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
