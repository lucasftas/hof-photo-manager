"""HOF Photo Manager — Entry point (pywebview)."""

import os
import sys
from pathlib import Path

import webview

from src.utils import setup_logging
from src.webview_api import Api

logger = setup_logging()


def main() -> None:
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except (ImportError, OSError):
        pass

    # Resolve caminho do HTML (funciona tanto em dev quanto empacotado)
    if getattr(sys, "frozen", False):
        base_dir = Path(sys._MEIPASS)  # type: ignore[attr-defined]
    else:
        base_dir = Path(__file__).parent

    html_path = base_dir / "src" / "ui.html"

    window_ref: list = [None]
    api = Api(window_ref)

    window = webview.create_window(
        "HOF Photo Manager",
        url=str(html_path),
        js_api=api,
        width=1400,
        height=750,
        min_size=(1024, 650),
    )
    window_ref[0] = window

    webview.start(debug=False)


if __name__ == "__main__":
    main()
