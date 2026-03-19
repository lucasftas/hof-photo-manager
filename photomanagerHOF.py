"""HOF Photo Manager — Entry point."""

import tkinter as tk
from tkinter import ttk

from src.app import AppOrganizador
from src.utils import setup_logging

logger = setup_logging()


def main() -> None:
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except (ImportError, OSError):
        pass

    root = tk.Tk()
    style = ttk.Style()
    style.theme_use("clam")

    AppOrganizador(root)
    root.mainloop()


if __name__ == "__main__":
    main()
