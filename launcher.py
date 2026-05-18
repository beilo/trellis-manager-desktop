from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parent
DATA_DIR = Path.home() / ".beilo-trellis" / "manager-app"
VENV_DIR = DATA_DIR / ".venv"
REQUIREMENTS = APP_ROOT / "requirements.txt"
MAIN = APP_ROOT / "main.py"
MIN_VERSION = (3, 11)
PYTHON_CANDIDATES = [
    "/opt/homebrew/bin/python3",
    "/usr/local/bin/python3",
    "python3.13",
    "python3.12",
    "python3.11",
    "python3",
    "python",
]


def main() -> int:
    if getattr(sys, "frozen", False):
        # 独立分发包已内置 Python 和依赖，冻结环境中不能再创建二级 venv。
        from main import main as run_app

        run_app()
        return 0

    python = ensure_compatible_python()
    if Path(python).resolve() != Path(sys.executable).resolve():
        os.execv(python, [python, str(Path(__file__).resolve())])
    venv_python = ensure_venv()
    env = os.environ.copy()
    env["TRELLIS_MANAGER_VENV"] = "1"
    return subprocess.run([str(venv_python), str(MAIN)], env=env, check=False).returncode


def ensure_compatible_python() -> str:
    if sys.version_info >= MIN_VERSION:
        return sys.executable
    for name in PYTHON_CANDIDATES:
        candidate = _resolve_python_candidate(name)
        if candidate and _is_compatible(candidate):
            return candidate
    raise SystemExit("需要 Python 3.11+ 才能启动 Trellis Manager。")


def _resolve_python_candidate(name: str) -> str | None:
    path = Path(name)
    if path.is_absolute():
        return str(path) if path.exists() else None
    return shutil.which(name)


def ensure_venv() -> Path:
    venv_python = VENV_DIR / "bin" / "python"
    if not venv_python.exists():
        # 使用当前兼容解释器创建本地虚拟环境，避免污染系统 Python。
        VENV_DIR.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([sys.executable, "-m", "venv", str(VENV_DIR)], check=True)
    marker = VENV_DIR / ".requirements-installed"
    if not marker.exists() or marker.stat().st_mtime < REQUIREMENTS.stat().st_mtime:
        subprocess.run([str(venv_python), "-m", "pip", "install", "-r", str(REQUIREMENTS)], check=True)
        marker.write_text("ok\n", encoding="utf-8")
    return venv_python


def _is_compatible(python: str) -> bool:
    script = "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)"
    return subprocess.run([python, "-c", script], check=False).returncode == 0


if __name__ == "__main__":
    raise SystemExit(main())
