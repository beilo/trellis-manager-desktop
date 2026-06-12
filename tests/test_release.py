from __future__ import annotations

import json
import os
import plistlib
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.release import (
    APP_NAME,
    CommandResult,
    ReleaseError,
    create_version,
    expected_zip_path,
    publish_release,
    read_app_version,
    tag_for_version,
    validate_semver,
    write_app_version,
)


class FakeReleaseRunner:
    def __init__(
        self,
        *,
        local_tag_exists: bool = True,
        release_exists: bool = False,
        remote_tag_exists: bool = False,
    ) -> None:
        self.local_tag_exists = local_tag_exists
        self.release_exists = release_exists
        self.remote_tag_exists = remote_tag_exists
        self.calls: list[tuple[list[str], Path]] = []

    def run(self, command: list[str], *, cwd: Path, timeout: int = 300) -> CommandResult:
        self.calls.append((command, cwd))
        if command == ["git", "status", "--short"]:
            return self._result(command, cwd, "")
        if command[:4] == ["git", "rev-parse", "-q", "--verify"]:
            return self._result(command, cwd, "") if self.local_tag_exists else self._error(command, cwd)
        if command[:4] == ["git", "ls-remote", "--tags", "origin"]:
            stdout = "abc123\trefs/tags/v0.1.1\n" if self.remote_tag_exists else ""
            return self._result(command, cwd, stdout)
        if command == ["git", "log", "-1", "--format=%ct", "--", "package.json"]:
            return self._result(command, cwd, "1\n")
        if command == ["gh", "auth", "status"]:
            return self._result(command, cwd, "Logged in\n")
        if command[:3] == ["gh", "release", "view"]:
            if not self.release_exists:
                return self._error(command, cwd, "release not found")
            return self._result(command, cwd, json.dumps({"assets": [{"name": f"{APP_NAME}-0.1.1-macos-arm64.zip"}]}))
        if command == ["git", "branch", "--show-current"]:
            return self._result(command, cwd, "main\n")
        if command[:2] == ["git", "add"]:
            return self._result(command, cwd, "")
        if command[:2] == ["git", "commit"]:
            return self._result(command, cwd, "[main abc123] release\n")
        if command[:2] == ["git", "tag"]:
            return self._result(command, cwd, "")
        if command[:2] == ["git", "push"]:
            return self._result(command, cwd, "")
        if command[:3] == ["gh", "release", "create"]:
            return self._result(command, cwd, "")
        if command[:3] == ["gh", "release", "upload"]:
            return self._result(command, cwd, "")
        return self._error(command, cwd, "unexpected command")

    def _result(self, command: list[str], cwd: Path, stdout: str) -> CommandResult:
        return CommandResult(command, cwd, 0, stdout, "")

    def _error(self, command: list[str], cwd: Path, stderr: str = "") -> CommandResult:
        return CommandResult(command, cwd, 1, "", stderr)


def write_package(root: Path, version: str = "0.1.0") -> None:
    (root / "package.json").write_text(
        json.dumps({"private": True, "name": "trellis-manager-desktop", "version": version}, indent=2) + "\n",
        encoding="utf-8",
    )


def write_artifact(root: Path, version: str = "0.1.1") -> None:
    app = root / "dist" / "standalone" / f"{APP_NAME}.app" / "Contents"
    app.mkdir(parents=True)
    with (app / "Info.plist").open("wb") as file:
        plistlib.dump({"CFBundleShortVersionString": version}, file)
    zip_path = expected_zip_path(version, root)
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    zip_path.write_bytes(b"zip")
    now = time.time()
    os.utime(zip_path, (now, now))


class ReleaseScriptTest(unittest.TestCase):
    def test_validate_semver_accepts_plain_and_prerelease(self) -> None:
        validate_semver("0.1.1")
        validate_semver("1.2.3-rc.1")
        with self.assertRaises(ReleaseError):
            validate_semver("v1.2.3")

    def test_app_version_comes_from_root_package_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_package(root, "0.1.0")

            write_app_version("0.2.0", root)

            self.assertEqual(read_app_version(root), "0.2.0")
            self.assertEqual(json.loads((root / "package.json").read_text(encoding="utf-8"))["version"], "0.2.0")

    def test_create_version_commits_and_tags_with_branch_suffix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_package(root, "0.1.0")
            (root / ".commit-suffix.json").write_text(json.dumps({"branches": {"main": "--leip"}}), encoding="utf-8")
            runner = FakeReleaseRunner(local_tag_exists=False)

            create_version("0.1.1", runner, root)

            commands = [call[0] for call in runner.calls]
            self.assertIn(["git", "add", "package.json"], commands)
            self.assertIn(["git", "commit", "-m", "chore: release v0.1.1 --leip"], commands)
            self.assertIn(["git", "tag", "v0.1.1"], commands)
            self.assertEqual(read_app_version(root), "0.1.1")

    def test_publish_dry_run_does_not_push_or_create_release(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_package(root, "0.1.1")
            write_artifact(root, "0.1.1")
            runner = FakeReleaseRunner()

            publish_release("0.1.1", dry_run=True, replace=False, runner=runner, root=root)

            commands = [call[0] for call in runner.calls]
            self.assertNotIn(["git", "push", "origin", "HEAD"], commands)
            self.assertFalse(any(command[:3] == ["gh", "release", "create"] for command in commands))

    def test_publish_replace_only_uses_upload_clobber(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_package(root, "0.1.1")
            write_artifact(root, "0.1.1")
            runner = FakeReleaseRunner(release_exists=True, remote_tag_exists=True)

            publish_release("0.1.1", dry_run=False, replace=True, runner=runner, root=root)

            commands = [call[0] for call in runner.calls]
            self.assertIn(["gh", "release", "upload", "v0.1.1", str(expected_zip_path("0.1.1", root)), "--clobber"], commands)
            self.assertFalse(any(command[:3] == ["gh", "release", "delete"] for command in commands))

    def test_tag_for_version_adds_v_prefix(self) -> None:
        self.assertEqual(tag_for_version("0.1.1"), "v0.1.1")


if __name__ == "__main__":
    unittest.main()
