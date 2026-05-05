"""Passikuva Pro entry point."""

import tkinter as tk

from app import PassportApp


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
