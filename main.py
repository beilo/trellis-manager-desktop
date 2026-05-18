from __future__ import annotations

from pathlib import Path

import webview

from app.api import TrellisAPI

_FRONTEND_DIST = Path(__file__).parent / "frontend" / "dist" / "index.html"
_FRONTEND_DEV = "http://localhost:5173"


def main() -> None:
    api = TrellisAPI()

    # 开发时若 dist 不存在则连接 Vite dev server
    if _FRONTEND_DIST.exists():
        url = str(_FRONTEND_DIST)
    else:
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
    webview.start(debug=not _FRONTEND_DIST.exists())


if __name__ == "__main__":
    main()
