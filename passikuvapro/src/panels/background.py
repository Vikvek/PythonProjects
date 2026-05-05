"""Background removal panel."""

import tkinter as tk
from tkinter import colorchooser, messagebox, ttk

import bgremove
from .base import Panel


class BackgroundPanel(Panel):
    title = "Background"

    def build_ui(self) -> None:
        self.remove_var = tk.BooleanVar(value=False)
        chk = ttk.Checkbutton(self, text="Remove background", variable=self.remove_var,
                              command=self._on_toggle)
        chk.grid(row=0, column=0, columnspan=2, sticky="w", padx=4, pady=6)
        if not bgremove.is_available():
            chk.state(["disabled"])
            ttk.Label(self, text="rembg not installed", foreground="red").grid(
                row=1, column=0, columnspan=2, sticky="w", padx=4)
            return

        ttk.Label(self, text="Replacement color").grid(row=2, column=0, sticky="w", padx=4, pady=(8, 2))
        self.color_swatch = tk.Label(self, text="          ", bg="#ffffff", relief="solid", borderwidth=1)
        self.color_swatch.grid(row=2, column=1, sticky="ew", padx=4)
        ttk.Button(self, text="Pick color", command=self._pick_color).grid(
            row=3, column=0, columnspan=2, sticky="ew", padx=4, pady=2)

        ttk.Label(self, text="Edge feather (px)").grid(row=4, column=0, sticky="w", padx=4, pady=(8, 2))
        self.feather_var = tk.IntVar(value=2)
        ttk.Scale(self, from_=0, to=10, variable=self.feather_var, orient="horizontal",
                  command=self._on_feather).grid(row=5, column=0, columnspan=2, sticky="ew", padx=4)

        ttk.Label(self, text="First use downloads ~170 MB model.\nMight take a minute.",
                  foreground="#666").grid(row=6, column=0, columnspan=2, sticky="w", padx=4, pady=(10, 4))

        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)

    def _on_toggle(self):
        if self.remove_var.get() and not bgremove.is_available():
            messagebox.showerror("Error", "rembg is not installed.")
            self.remove_var.set(False)
            return
        self.app.pipeline.state.bg_remove = bool(self.remove_var.get())
        self.app.request_render()

    def _pick_color(self):
        rgb_hex = colorchooser.askcolor(title="Background color")
        if rgb_hex and rgb_hex[0]:
            r, g, b = (int(c) for c in rgb_hex[0])
            self.app.pipeline.state.bg_color = (r, g, b)
            self.color_swatch.configure(bg=rgb_hex[1])
            self.app.request_render()

    def _on_feather(self, _):
        self.app.pipeline.state.feather = int(self.feather_var.get())
        self.app.request_render()

    def on_state_reset(self) -> None:
        if hasattr(self, "remove_var"):
            self.remove_var.set(False)
        if hasattr(self, "feather_var"):
            self.feather_var.set(2)
