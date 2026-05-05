"""Auto-fit-to-spec panel."""

import threading
import tkinter as tk
from tkinter import messagebox, ttk

import bgremove
import detect
from pipeline import ImagePipeline
from .base import Panel


class AutoPanel(Panel):
    title = "Auto"

    def build_ui(self) -> None:
        if not detect.is_available():
            ttk.Label(self, text="mediapipe not installed", foreground="red").grid(
                row=0, column=0, padx=4, pady=4)
            return

        ttk.Label(self, text="Auto-fit photo to passport spec.\n"
                              "Levels eyes, sizes head (uses hair top, not\n"
                              "forehead), centers face. Uses background\n"
                              "segmentation for accurate head detection.",
                  justify="left").grid(row=0, column=0, sticky="w", padx=4, pady=6)

        ttk.Button(self, text="Auto-fit to spec", command=self._auto).grid(
            row=1, column=0, sticky="ew", padx=4, pady=4)

        ttk.Separator(self, orient="horizontal").grid(row=2, column=0, sticky="ew", pady=8)

        self.status_var = tk.StringVar(value="")
        ttk.Label(self, textvariable=self.status_var, justify="left",
                  foreground="#444").grid(row=3, column=0, sticky="w", padx=4)

        self.columnconfigure(0, weight=1)

    def _auto(self):
        if self.app.pipeline.source is None:
            messagebox.showerror("Error", "No image to fit.")
            return
        if not bgremove.is_available():
            messagebox.showwarning(
                "Auto-fit",
                "rembg not available — auto-fit will use forehead landmark instead\n"
                "of true hair top. Result may have head too high in frame.",
            )

        self.status_var.set("Computing… (this may take a few seconds)")
        self.update_idletasks()

        # Snapshot what to work with
        source = self.app.pipeline.source
        angle = self.app.pipeline.state.angle
        out_size = self.app.pipeline.output_size
        spec = self.app.spec
        rembg_model = self.app.settings["rembg_model"]

        def work():
            mask = self.app.pipeline.source_mask
            if mask is None and bgremove.is_available():
                mask = bgremove.alpha_mask(source, rembg_model)

            rotated_src = ImagePipeline._rotate(source, angle)
            rotated_mask = ImagePipeline._rotate(mask, angle) if mask is not None else None

            result = detect.compute_autofit(
                rotated_src, out_size,
                spec_target_head_ratio=spec.head_target_ratio(),
                spec_top_gap_ratio=spec.top_gap_target_ratio(),
                current_angle=angle,
                foreground_mask=rotated_mask,
            )

            def done():
                if result is None:
                    self.status_var.set("No face detected.")
                    messagebox.showwarning("Auto-fit", "No face detected in image.")
                    return

                if mask is not None and self.app.pipeline.source is source:
                    self.app.pipeline.set_source_mask(mask)

                new_angle = self.app.pipeline.state.angle + result.angle_delta
                self.app.pipeline.state.angle = round(new_angle, 2)
                self.app.pipeline.state.zoom = result.zoom
                self.app.pipeline.state.offset_x = result.offset_x
                self.app.pipeline.state.offset_y = result.offset_y
                self.app.sync_panels_to_state()
                self.app.request_render()
                self.status_var.set(
                    f"Applied. Tilt: {result.angle_delta:+.2f}°, "
                    f"Zoom: {result.zoom:.2f}×"
                )

            self.app.root.after(0, done)

        threading.Thread(target=work, daemon=True).start()

    def on_state_reset(self) -> None:
        if hasattr(self, "status_var"):
            self.status_var.set("")
