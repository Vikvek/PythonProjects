"""Brightness / contrast / saturation / greyscale panel."""

import tkinter as tk
from tkinter import ttk

from .base import Panel


class AdjustPanel(Panel):
    title = "Adjust"

    def build_ui(self) -> None:
        self.brightness_var = tk.DoubleVar(value=1.0)
        self.contrast_var = tk.DoubleVar(value=1.0)
        self.saturation_var = tk.DoubleVar(value=1.0)
        self.grey_var = tk.BooleanVar(value=False)

        sliders = [
            ("Brightness", self.brightness_var, 0.3, 2.0, self._on_brightness),
            ("Contrast",   self.contrast_var,   0.3, 2.0, self._on_contrast),
            ("Saturation", self.saturation_var, 0.0, 2.0, self._on_saturation),
        ]
        for r, (label, var, lo, hi, cb) in enumerate(sliders):
            ttk.Label(self, text=label).grid(row=r * 2, column=0, sticky="w", padx=4, pady=(6, 0))
            scale = ttk.Scale(self, from_=lo, to=hi, variable=var, orient="horizontal", command=cb)
            scale.grid(row=r * 2 + 1, column=0, columnspan=2, sticky="ew", padx=4)

        ttk.Checkbutton(self, text="Greyscale", variable=self.grey_var,
                        command=self._on_grey).grid(row=6, column=0, sticky="w", padx=4, pady=8)
        ttk.Button(self, text="Reset", command=self._reset).grid(row=6, column=1, sticky="ew", padx=4, pady=8)

        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)

    def _on_brightness(self, _):
        self.app.pipeline.state.brightness = float(self.brightness_var.get())
        self.app.request_render()

    def _on_contrast(self, _):
        self.app.pipeline.state.contrast = float(self.contrast_var.get())
        self.app.request_render()

    def _on_saturation(self, _):
        self.app.pipeline.state.saturation = float(self.saturation_var.get())
        self.app.request_render()

    def _on_grey(self):
        self.app.pipeline.state.greyscale = bool(self.grey_var.get())
        self.app.request_render()

    def _reset(self):
        self.brightness_var.set(1.0)
        self.contrast_var.set(1.0)
        self.saturation_var.set(1.0)
        self.grey_var.set(False)
        self.app.pipeline.state.brightness = 1.0
        self.app.pipeline.state.contrast = 1.0
        self.app.pipeline.state.saturation = 1.0
        self.app.pipeline.state.greyscale = False
        self.app.request_render()

    def on_state_reset(self) -> None:
        self.brightness_var.set(1.0)
        self.contrast_var.set(1.0)
        self.saturation_var.set(1.0)
        self.grey_var.set(False)
