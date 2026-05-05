"""Passikuva Pro entry point."""

import os
import sys
import tkinter as tk

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "src"))

from app import PassportApp  # noqa: E402


def main():
    root = tk.Tk()
    app = PassportApp(root)

    def on_close():
        try:
            if app.cap is not None:
                app.cap.release()
        except Exception:
            pass
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()


if __name__ == "__main__":
    main()
