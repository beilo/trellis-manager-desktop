from __future__ import annotations

import shlex
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

ALLOWED_EXECUTABLES = {
    "git",
    "node",
    "pnpm",
    "tl",
    "trellis",
}


@dataclass(frozen=True)
class CommandResult:
    command: list[str]
    cwd: Path | None
    returncode: int | None
    stdout: str
    stderr: str
    duration_ms: int
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and self.error is None

    @property
    def command_line(self) -> str:
        return shlex.join(self.command)

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["cwd"] = str(self.cwd) if self.cwd is not None else None
        data["command_line"] = self.command_line
        return data


class CommandRunner:
    """只执行白名单命令，避免 UI 输入拼成任意 shell。"""

    def __init__(self, allowed: set[str] | None = None) -> None:
        self.allowed = allowed or ALLOWED_EXECUTABLES

    def run(
        self,
        command: Sequence[str | Path],
        cwd: Path | None = None,
        timeout: int = 60,
    ) -> CommandResult:
        normalized = [str(part) for part in command]
        self._validate_command(normalized)
        executed = self._prepare_command(normalized)
        started = time.monotonic()
        try:
            completed = subprocess.run(
                executed,
                cwd=str(cwd) if cwd is not None else None,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                shell=False,
                check=False,
            )
            return CommandResult(
                command=executed,
                cwd=cwd,
                returncode=completed.returncode,
                stdout=completed.stdout,
                stderr=completed.stderr,
                duration_ms=int((time.monotonic() - started) * 1000),
            )
        except subprocess.TimeoutExpired as error:
            return CommandResult(
                command=executed,
                cwd=cwd,
                returncode=None,
                stdout=error.stdout or "",
                stderr=error.stderr or "",
                duration_ms=int((time.monotonic() - started) * 1000),
                error=f"命令超时：{timeout} 秒内没有完成。",
            )
        except OSError as error:
            return CommandResult(
                command=executed,
                cwd=cwd,
                returncode=None,
                stdout="",
                stderr="",
                duration_ms=int((time.monotonic() - started) * 1000),
                error=f"命令无法执行：{error}",
            )

    def _validate_command(self, command: list[str]) -> None:
        if not command:
            raise ValueError("命令不能为空。")
        if any("\0" in part for part in command):
            raise ValueError("命令包含非法字符。")
        executable_name = Path(command[0]).name
        if executable_name not in self.allowed:
            raise ValueError(f"不允许执行命令：{executable_name}")

    def _prepare_command(self, command: list[str]) -> list[str]:
        executable_name = Path(command[0]).name
        if executable_name == "git":
            # 强制 git 输出 UTF-8，避免中文路径或日志在不同终端编码下乱码。
            return [command[0], "-c", "i18n.logOutputEncoding=UTF-8", *command[1:]]
        return command
