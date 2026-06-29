from __future__ import annotations

import argparse
import json
import plistlib
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

APP_NAME = "Trellis Manager"
PLATFORM = "macos-arm64"
APP_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_JSON = APP_ROOT / "package.json"
FRONTEND_DIR = APP_ROOT / "frontend"
DIST_ROOT = APP_ROOT / "dist" / "standalone"
APP_BUNDLE = DIST_ROOT / f"{APP_NAME}.app"

SEMVER_PATTERN = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?$")


class ReleaseError(RuntimeError):
    pass


@dataclass(frozen=True)
class CommandResult:
    command: list[str]
    cwd: Path
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


class SubprocessRunner:
    def run(self, command: list[str], *, cwd: Path = APP_ROOT, timeout: int = 300) -> CommandResult:
        completed = subprocess.run(
            command,
            cwd=cwd,
            timeout=timeout,
            check=False,
            capture_output=True,
            text=True,
        )
        return CommandResult(command, cwd, completed.returncode, completed.stdout, completed.stderr)


def validate_semver(version: str) -> None:
    if not SEMVER_PATTERN.match(version):
        raise ReleaseError(f"应用版本必须是 semver，例如 0.1.1 或 0.1.1-rc.1：{version}")


def tag_for_version(version: str) -> str:
    validate_semver(version)
    return f"v{version}"


def expected_zip_path(version: str, root: Path = APP_ROOT) -> Path:
    validate_semver(version)
    return root / "dist" / "standalone" / f"{APP_NAME}-{version}-{PLATFORM}.zip"


def read_package_json(root: Path = APP_ROOT) -> dict[str, object]:
    path = root / "package.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ReleaseError(f"缺少根 package.json：{path}") from exc
    except json.JSONDecodeError as exc:
        raise ReleaseError(f"根 package.json 不是合法 JSON：{exc}") from exc
    if not isinstance(payload, dict):
        raise ReleaseError("根 package.json 必须是 JSON object。")
    return payload


def read_app_version(root: Path = APP_ROOT) -> str:
    payload = read_package_json(root)
    version = payload.get("version")
    if not isinstance(version, str):
        raise ReleaseError("根 package.json.version 缺失或不是字符串。")
    validate_semver(version)
    return version


def write_app_version(version: str, root: Path = APP_ROOT) -> None:
    validate_semver(version)
    path = root / "package.json"
    payload = read_package_json(root)
    payload["version"] = version
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_checked(
    runner: SubprocessRunner,
    command: list[str],
    *,
    cwd: Path = APP_ROOT,
    timeout: int = 300,
) -> CommandResult:
    result = runner.run(command, cwd=cwd, timeout=timeout)
    if not result.ok:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
        raise ReleaseError(f"命令失败：{format_command(command)}\n{detail}")
    return result


def format_command(command: list[str]) -> str:
    return " ".join(command)


def ensure_clean_worktree(runner: SubprocessRunner, root: Path = APP_ROOT) -> None:
    result = run_checked(runner, ["git", "status", "--short"], cwd=root, timeout=30)
    if result.stdout.strip():
        raise ReleaseError("工作区不干净，请先提交或暂存无关改动：\n" + result.stdout.strip())


def local_tag_exists(runner: SubprocessRunner, tag: str, root: Path = APP_ROOT) -> bool:
    result = runner.run(["git", "rev-parse", "-q", "--verify", f"refs/tags/{tag}"], cwd=root, timeout=30)
    return result.ok


def remote_tag_exists(runner: SubprocessRunner, tag: str, root: Path = APP_ROOT) -> bool:
    result = run_checked(runner, ["git", "ls-remote", "--tags", "origin", f"refs/tags/{tag}"], cwd=root, timeout=60)
    return bool(result.stdout.strip())


def current_branch(runner: SubprocessRunner, root: Path = APP_ROOT) -> str:
    result = run_checked(runner, ["git", "branch", "--show-current"], cwd=root, timeout=30)
    return result.stdout.strip()


def commit_suffix(runner: SubprocessRunner, root: Path = APP_ROOT) -> str:
    path = root / ".commit-suffix.json"
    if not path.exists():
        return ""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ReleaseError(f".commit-suffix.json 不是合法 JSON：{exc}") from exc
    branches = payload.get("branches") if isinstance(payload, dict) else None
    if not isinstance(branches, dict):
        return ""
    suffix = branches.get(current_branch(runner, root))
    return f" {suffix}" if isinstance(suffix, str) and suffix else ""


def version_commit_time(runner: SubprocessRunner, root: Path = APP_ROOT) -> int:
    result = run_checked(runner, ["git", "log", "-1", "--format=%ct", "--", "package.json"], cwd=root, timeout=30)
    try:
        return int(result.stdout.strip())
    except ValueError as exc:
        raise ReleaseError("无法读取 package.json 最近提交时间。") from exc


def create_version(version: str, runner: SubprocessRunner, root: Path = APP_ROOT) -> int:
    validate_semver(version)
    tag = tag_for_version(version)
    ensure_clean_worktree(runner, root)
    if local_tag_exists(runner, tag, root):
        raise ReleaseError(f"本地 tag 已存在：{tag}")

    old_version = read_app_version(root)
    if old_version == version:
        raise ReleaseError(f"应用版本已经是 {version}。")

    write_app_version(version, root)
    created_tag = False
    try:
        run_checked(runner, ["git", "add", "package.json"], cwd=root, timeout=30)
        message = f"chore: release {tag}{commit_suffix(runner, root)}"
        run_checked(runner, ["git", "commit", "-m", message], cwd=root, timeout=60)
        run_checked(runner, ["git", "tag", tag], cwd=root, timeout=30)
        created_tag = True
    except Exception:
        if created_tag:
            runner.run(["git", "tag", "-d", tag], cwd=root, timeout=30)
        raise

    print(f"应用版本已更新：{old_version} -> {version}")
    print(f"已创建提交和 tag：{tag}")
    print("")
    print("下一步：")
    print("  npm run release:package")
    print(f"  npm run release:publish -- {version} --dry-run")
    return 0


def generate_embedded_zip_for_release(root: Path = APP_ROOT, *, source: Path | str | None = None) -> Path:
    # 发布前必须生成并校验内置 Trellis 源码 zip，确保 .app 离线安装链路可用。
    try:
        from package_local_trellis_zip import EmbeddedZipError, generate_embedded_zip, validate_embedded_zip
    except ModuleNotFoundError:  # pragma: no cover - 作为 scripts 包导入时回退
        from scripts.package_local_trellis_zip import (
            EmbeddedZipError,
            generate_embedded_zip,
            validate_embedded_zip,
        )
    output_dir = root / "resources"
    embedded_source = source if source is not None else root.parent / "Trellis"
    try:
        zip_path = generate_embedded_zip(embedded_source, output_dir=output_dir)
        validate_embedded_zip(zip_path)
    except EmbeddedZipError as exc:
        raise ReleaseError(f"内置 Trellis 源码 zip 生成或校验失败：{exc}") from exc
    return zip_path


def package_release(*, clean: bool, runner: SubprocessRunner, root: Path = APP_ROOT) -> int:
    version = read_app_version(root)
    node_modules = root / "frontend" / "node_modules"
    if clean and node_modules.exists():
        shutil.rmtree(node_modules)

    # 先生成并校验内置 zip，再构建前端和 .app，缺失/无效则 fail fast 阻断发布。
    generate_embedded_zip_for_release(root)

    run_checked(runner, ["npm", "install"], cwd=root / "frontend", timeout=600)
    run_checked(runner, ["npx", "vite", "build"], cwd=root / "frontend", timeout=600)
    run_checked(runner, [sys.executable, "scripts/build_standalone_app.py"], cwd=root, timeout=1800)
    verify_artifact(version, runner, root)

    print(f"应用发布包已生成：{expected_zip_path(version, root)}")
    return 0


def read_bundle_version(root: Path = APP_ROOT) -> str:
    plist_path = root / "dist" / "standalone" / f"{APP_NAME}.app" / "Contents" / "Info.plist"
    if not plist_path.exists():
        raise ReleaseError(f"缺少 app bundle Info.plist：{plist_path}")
    with plist_path.open("rb") as file:
        payload = plistlib.load(file)
    version = payload.get("CFBundleShortVersionString")
    if not isinstance(version, str):
        raise ReleaseError("Info.plist 缺少 CFBundleShortVersionString。")
    return version


def verify_artifact(version: str, runner: SubprocessRunner, root: Path = APP_ROOT) -> Path:
    validate_semver(version)
    zip_path = expected_zip_path(version, root)
    if not zip_path.exists():
        raise ReleaseError(f"缺少版本化 zip 产物：{zip_path}")
    bundle_version = read_bundle_version(root)
    if bundle_version != version:
        raise ReleaseError(f"app bundle 版本不匹配：Info.plist={bundle_version} package.json={version}")
    commit_time = version_commit_time(runner, root)
    if int(zip_path.stat().st_mtime) < commit_time:
        raise ReleaseError("zip 产物早于版本提交，请重新运行 release:package。")
    return zip_path


def gh_auth_ok(runner: SubprocessRunner, root: Path = APP_ROOT) -> None:
    run_checked(runner, ["gh", "auth", "status"], cwd=root, timeout=60)


def release_assets(runner: SubprocessRunner, tag: str, root: Path = APP_ROOT) -> list[str] | None:
    result = runner.run(["gh", "release", "view", tag, "--json", "assets"], cwd=root, timeout=60)
    if not result.ok:
        combined = f"{result.stdout}\n{result.stderr}".lower()
        if "not found" not in combined and "not exist" not in combined:
            detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
            raise ReleaseError(f"无法确认 GitHub Release 是否存在：{tag}\n{detail}")
        return None
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ReleaseError(f"无法解析 gh release view 输出：{exc}") from exc
    assets = payload.get("assets") if isinstance(payload, dict) else None
    if not isinstance(assets, list):
        return []
    names: list[str] = []
    for asset in assets:
        if isinstance(asset, dict) and isinstance(asset.get("name"), str):
            names.append(asset["name"])
    return names


def publish_release(
    version: str,
    *,
    dry_run: bool,
    replace: bool,
    runner: SubprocessRunner,
    root: Path = APP_ROOT,
) -> int:
    validate_semver(version)
    current_version = read_app_version(root)
    if current_version != version:
        raise ReleaseError(f"命令版本和根 package.json.version 不一致：{version} != {current_version}")

    tag = tag_for_version(version)
    zip_path = verify_artifact(version, runner, root)
    ensure_clean_worktree(runner, root)
    gh_auth_ok(runner, root)

    if not local_tag_exists(runner, tag, root):
        raise ReleaseError(f"缺少本地 tag：{tag}。请先运行 npm run release:version -- {version}")

    has_remote_tag = remote_tag_exists(runner, tag, root)
    assets = release_assets(runner, tag, root)
    has_release = assets is not None
    asset_name = zip_path.name

    if not replace and has_remote_tag:
        raise ReleaseError(f"远端 tag 已存在：{tag}。如需补发同版本 asset，请显式传入 --replace。")
    if not replace and has_release:
        raise ReleaseError(f"GitHub Release 已存在：{tag}。如需补发同版本 asset，请显式传入 --replace。")
    if not replace and assets and asset_name in assets:
        raise ReleaseError(f"Release asset 已存在：{asset_name}。如需覆盖，请显式传入 --replace。")

    commands: list[list[str]] = [["git", "push", "origin", "HEAD"]]
    if not has_remote_tag:
        commands.append(["git", "push", "origin", tag])
    if has_release:
        upload = ["gh", "release", "upload", tag, str(zip_path)]
        if replace:
            upload.append("--clobber")
        commands.append(upload)
    else:
        commands.append(
            [
                "gh",
                "release",
                "create",
                tag,
                str(zip_path),
                "--title",
                f"{APP_NAME} {version}",
                "--generate-notes",
                "--verify-tag",
            ]
        )

    if dry_run:
        print("dry-run：不会 push、创建 release 或上传 asset。")
        for command in commands:
            print("  " + format_command(command))
        return 0

    for command in commands:
        run_checked(runner, command, cwd=root, timeout=600)

    print(f"GitHub Release 已发布：{tag}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Trellis Manager Desktop release helper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    version_parser = subparsers.add_parser("version", help="update app version, commit, and tag")
    version_parser.add_argument("version")

    package_parser = subparsers.add_parser("package", help="build versioned macOS app zip")
    package_parser.add_argument("--clean", action="store_true", help="remove frontend/node_modules before npm install")

    publish_parser = subparsers.add_parser("publish", help="publish versioned zip to GitHub Release")
    publish_parser.add_argument("version")
    publish_parser.add_argument("--dry-run", action="store_true")
    publish_parser.add_argument("--replace", action="store_true", help="replace same-name release asset")

    return parser


def main(argv: list[str] | None = None, *, runner: SubprocessRunner | None = None, root: Path = APP_ROOT) -> int:
    args = build_parser().parse_args(argv)
    command_runner = runner or SubprocessRunner()
    try:
        if args.command == "version":
            return create_version(args.version, command_runner, root)
        if args.command == "package":
            return package_release(clean=args.clean, runner=command_runner, root=root)
        if args.command == "publish":
            return publish_release(args.version, dry_run=args.dry_run, replace=args.replace, runner=command_runner, root=root)
    except ReleaseError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        print("", file=sys.stderr)
        print("常用恢复命令：", file=sys.stderr)
        print("  git tag -d vX.Y.Z", file=sys.stderr)
        print("  git reset --soft HEAD~1", file=sys.stderr)
        print("  gh release delete vX.Y.Z --cleanup-tag", file=sys.stderr)
        return 1
    raise AssertionError(f"unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
