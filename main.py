from __future__ import annotations

import sys
from pathlib import Path

import webview

from app.api import TrellisAPI

_FRONTEND_DEV = "http://localhost:5173"


def _find_frontend_dist() -> Path | None:
    candidates: list[Path] = []
    if getattr(sys, "frozen", False):
        # PyInstaller 独立包会把静态前端放到 bundle 资源目录，优先从冻结资源中查找。
        bundle_root = getattr(sys, "_MEIPASS", None)
        if bundle_root:
            candidates.append(Path(bundle_root) / "frontend" / "dist" / "index.html")
        executable = Path(sys.executable).resolve()
        candidates.append(executable.parent.parent / "Resources" / "frontend" / "dist" / "index.html")
    candidates.append(Path(__file__).parent / "frontend" / "dist" / "index.html")

    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def main() -> None:
    api = TrellisAPI()

    frontend_dist = _find_frontend_dist()
    if frontend_dist:
        url = str(frontend_dist)
    else:
        # 开发时若 dist 不存在则连接 Vite dev server。
        url = _FRONTEND_DEV

    window = webview.create_window(
        title="Trellis Manager",
        url=url,
        js_api=api,
        width=1220,
        height=920,
        min_size=(1060, 800),
        background_color="#f8fafc",
    )
    api.set_window(window)
    webview.start(debug=frontend_dist is None)


if __name__ == "__main__":
    main()
