"""Crop / rotate / zoom / offset panel."""

import tkinter as tk
from tkinter import ttk

from .base import Panel


class CropPanel(Panel):
    title = "Crop"

    def build_ui(self) -> None:
        row = 0
        ttk.Label(self, text="Rotation (°)").grid(row=row, column=0, sticky="w", padx=4, pady=2)
        row += 1
        self.angle_var = tk.DoubleVar(value=0.0)
        self.angle_scale = ttk.Scale(self, from_=-15.0, to=15.0, variable=self.angle_var,
                                      orient="horizontal", command=self._on_angle)
        self.angle_scale.grid(row=row, column=0, columnspan=3, sticky="ew", padx=4)
        row += 1

        # fine rotate
        ttk.Button(self, text="↺ -0.1°", command=lambda: self._nudge_angle(-0.1)).grid(row=row, column=0, sticky="ew", padx=2, pady=2)
        ttk.Button(self, text="↻ +0.1°", command=lambda: self._nudge_angle(0.1)).grid(row=row, column=1, sticky="ew", padx=2, pady=2)
        ttk.Button(self, text="Reset", command=self._reset_angle).grid(row=row, column=2, sticky="ew", padx=2, pady=2)
        row += 1

        ttk.Separator(self, orient="horizontal").grid(row=row, column=0, columnspan=3, sticky="ew", pady=6)
        row += 1

        ttk.Label(self, text="Zoom").grid(row=row, column=0, sticky="w", padx=4, pady=2)
        row += 1
        self.zoom_var = tk.DoubleVar(value=1.0)
        self.zoom_scale = ttk.Scale(self, from_=0.3, to=3.0, variable=self.zoom_var,
                                     orient="horizontal", command=self._on_zoom)
        self.zoom_scale.grid(row=row, column=0, columnspan=3, sticky="ew", padx=4)
        row += 1

        ttk.Separator(self, orient="horizontal").grid(row=row, column=0, columnspan=3, sticky="ew", pady=6)
        row += 1

        ttk.Label(self, text="Move").grid(row=row, column=0, columnspan=3, sticky="w", padx=4)
        row += 1
        ttk.Button(self, text="←", command=lambda: self._move(-5, 0)).grid(row=row, column=0, sticky="ew", padx=2, pady=2)
        ttk.Button(self, text="↑", command=lambda: self._move(0, -5)).grid(row=row, column=1, sticky="ew", padx=2, pady=2)
        ttk.Button(self, text="→", command=lambda: self._move(5, 0)).grid(row=row, column=2, sticky="ew", padx=2, pady=2)
        row += 1
        ttk.Button(self, text="↓", command=lambda: self._move(0, 5)).grid(row=row, column=1, sticky="ew", padx=2, pady=2)
        row += 1
        ttk.Button(self, text="Reset position", command=self._reset_offset).grid(row=row, column=0, columnspan=3, sticky="ew", padx=2, pady=4)
        row += 1

        ttk.Separator(self, orient="horizontal").grid(row=row, column=0, columnspan=3, sticky="ew", pady=6)
        row += 1
        ttk.Button(self, text="Reset all", command=self._reset_all).grid(row=row, column=0, columnspan=3, sticky="ew", padx=2, pady=2)

        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)
        self.columnconfigure(2, weight=1)

    def _on_angle(self, _val):
        self.app.pipeline.state.angle = round(float(self.angle_var.get()), 2)
        self.app.invalidate_mask_cache()
        self.app.request_render()

    def _nudge_angle(self, d):
        self.angle_var.set(round(self.angle_var.get() + d, 2))
        self._on_angle(None)

    def _reset_angle(self):
        self.angle_var.set(0.0)
        self._on_angle(None)

    def _on_zoom(self, _val):
        self.app.pipeline.state.zoom = float(self.zoom_var.get())
        self.app.request_render()

    def _move(self, dx, dy):
        self.app.pipeline.state.offset_x += dx
        self.app.pipeline.state.offset_y += dy
        self.app.request_render()

    def _reset_offset(self):
        self.app.pipeline.state.offset_x = 0
        self.app.pipeline.state.offset_y = 0
        self.app.request_render()

    def _reset_all(self):
        self.angle_var.set(0.0)
        self.zoom_var.set(1.0)
        self.app.pipeline.state.angle = 0.0
        self.app.pipeline.state.zoom = 1.0
        self.app.pipeline.state.offset_x = 0
        self.app.pipeline.state.offset_y = 0
        self.app.invalidate_mask_cache()
        self.app.request_render()

    def on_state_reset(self) -> None:
        self.angle_var.set(0.0)
        self.zoom_var.set(1.0)
