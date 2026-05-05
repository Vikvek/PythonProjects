"""Main app window."""

from __future__ import annotations

import os
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Optional

import cv2
import numpy as np
from PIL import Image, ImageTk

import bgremove
import detect
import settings as settings_mod
import spec as spec_mod
from overlay import build_overlay
from pipeline import ImagePipeline
from panels.adjust import AdjustPanel
from panels.auto import AutoPanel
from panels.background import BackgroundPanel
from panels.crop import CropPanel


class SourceDialog(tk.Toplevel):
    """Modal: pick webcam or upload."""

    def __init__(self, parent):
        super().__init__(parent)
        self.title("Choose source")
        self.transient(parent)
        self.grab_set()
        self.resizable(False, False)
        self.choice: Optional[str] = None
        self.upload_path: Optional[str] = None

        ttk.Label(self, text="How do you want to provide the photo?",
                  font=("", 11)).pack(padx=20, pady=(20, 12))

        btn_frame = ttk.Frame(self)
        btn_frame.pack(padx=20, pady=(0, 20))

        ttk.Button(btn_frame, text="📷 Use Webcam", width=20,
                   command=self._pick_webcam).grid(row=0, column=0, padx=4)
        ttk.Button(btn_frame, text="🖼  Upload Image", width=20,
                   command=self._pick_upload).grid(row=0, column=1, padx=4)

        self.update_idletasks()
        self._center_on_parent(parent)

    def _center_on_parent(self, parent):
        parent.update_idletasks()
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        w = self.winfo_width()
        h = self.winfo_height()
        x = px + (pw - w) // 2
        y = py + (ph - h) // 2
        self.geometry(f"+{x}+{y}")

    def _pick_webcam(self):
        self.choice = "webcam"
        self.destroy()

    def _pick_upload(self):
        path = filedialog.askopenfilename(
            parent=self,
            title="Select photo",
            filetypes=[("Images", "*.jpg *.jpeg *.png *.bmp *.webp"), ("All files", "*.*")],
        )
        if path:
            self.upload_path = path
            self.choice = "upload"
            self.destroy()


class PassportApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Passikuva Pro")

        self.settings = settings_mod.load()
        self.spec = spec_mod.SPECS.get(self.settings["spec"], spec_mod.FINNISH)
        self.pipeline = ImagePipeline(tuple(self.settings["output_size"]))
        self.pipeline.state.bg_color = tuple(self.settings["default_bg_color"])

        self.cap: Optional[cv2.VideoCapture] = None
        self.is_frozen = False
        self.live_frame: Optional[np.ndarray] = None  # BGR live webcam frame
        self.mode: Optional[str] = None  # "webcam" or "upload"

        self.overlay_rgba: Optional[np.ndarray] = None
        self._render_pending = False
        self._heavy_render_in_progress = False

        self._build_ui()
        self._load_overlay()

        # Show source dialog after the root is mapped
        self.root.after(50, self._choose_source)

    # --- UI ---

    def _build_ui(self):
        root = self.root
        root.geometry("980x740")

        # Menu
        menubar = tk.Menu(root)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="New from Webcam", command=lambda: self._reset_to("webcam"))
        file_menu.add_command(label="Upload Image…", command=lambda: self._reset_to("upload"))
        file_menu.add_separator()
        file_menu.add_command(label="Save", command=self._save)
        file_menu.add_separator()
        file_menu.add_command(label="Settings…", command=self._open_settings)
        file_menu.add_separator()
        file_menu.add_command(label="Quit", command=root.quit)
        menubar.add_cascade(label="File", menu=file_menu)
        root.config(menu=menubar)

        # Layout: left canvas, right panel
        main = ttk.Frame(root, padding=8)
        main.pack(fill="both", expand=True)
        main.columnconfigure(0, weight=0)
        main.columnconfigure(1, weight=1)
        main.rowconfigure(0, weight=1)

        # Left side: canvas + button row
        left = ttk.Frame(main)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        out_w, out_h = self.pipeline.output_size
        self.canvas = tk.Canvas(left, width=out_w, height=out_h, bg="#222",
                                 highlightthickness=1, highlightbackground="#888")
        self.canvas.pack()

        btn_row = ttk.Frame(left)
        btn_row.pack(pady=8, fill="x")
        self.capture_btn = ttk.Button(btn_row, text="Capture", command=self._capture)
        self.capture_btn.pack(side="left", padx=2)
        self.retake_btn = ttk.Button(btn_row, text="Re-take", command=self._retake)
        self.retake_btn.pack(side="left", padx=2)
        self.save_btn = ttk.Button(btn_row, text="Save", command=self._save)
        self.save_btn.pack(side="left", padx=2)

        self.busy_var = tk.StringVar(value="")
        ttk.Label(btn_row, textvariable=self.busy_var, foreground="#0a7").pack(side="left", padx=8)

        # Right side: notebook + validation footer
        right = ttk.Frame(main)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)

        self.notebook = ttk.Notebook(right)
        self.notebook.grid(row=0, column=0, sticky="nsew")

        self.panels = []
        for cls in (CropPanel, AdjustPanel, BackgroundPanel, AutoPanel):
            panel = cls(self.notebook, self)
            self.notebook.add(panel, text=cls.title)
            self.panels.append(panel)

        validation = ttk.LabelFrame(right, text="Validation (Finnish spec)", padding=6)
        validation.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        self.validation_var = tk.StringVar(value="Capture or upload an image to validate.")
        ttk.Label(validation, textvariable=self.validation_var, justify="left",
                  foreground="#333").pack(anchor="w")

    def _load_overlay(self):
        if self.settings.get("use_generated_overlay", True):
            self.overlay_rgba = build_overlay(self.spec, self.pipeline.output_size)
            return
        path = self.settings["overlay_path"]
        try:
            img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
        except Exception:
            img = None
        if img is None:
            self.overlay_rgba = build_overlay(self.spec, self.pipeline.output_size)
            return
        if img.shape[2] == 4:
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2RGBA)
        else:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            img = np.dstack([img, np.full(img.shape[:2], 255, dtype=np.uint8)])
        self.overlay_rgba = img

    # --- Source flow ---

    def _choose_source(self):
        dlg = SourceDialog(self.root)
        self.root.wait_window(dlg)
        if dlg.choice == "webcam":
            self._start_webcam()
        elif dlg.choice == "upload" and dlg.upload_path:
            self._load_upload(dlg.upload_path)
        else:
            self.root.quit()

    def _reset_to(self, mode: str):
        self._stop_webcam()
        self.is_frozen = False
        if mode == "webcam":
            self._start_webcam()
        else:
            path = filedialog.askopenfilename(
                title="Select photo",
                filetypes=[("Images", "*.jpg *.jpeg *.png *.bmp *.webp"), ("All files", "*.*")],
            )
            if path:
                self._load_upload(path)

    def _start_webcam(self):
        self.mode = "webcam"
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            self.cap = None
            messagebox.showerror("Webcam", "Could not open webcam. Use upload instead.")
            self._reset_to("upload")
            return
        self.is_frozen = False
        self.capture_btn.state(["!disabled"])
        self.retake_btn.state(["disabled"])
        for p in self.panels:
            p.on_state_reset()
        self._tick_webcam()

    def _stop_webcam(self):
        if self.cap is not None:
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None

    def _tick_webcam(self):
        if self.cap is None:
            return
        if not self.is_frozen:
            ret, frame = self.cap.read()
            if ret:
                self.live_frame = frame
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                preview = self._fit_to_canvas(rgb)
                with_overlay = self._blit_overlay(preview)
                self._show(with_overlay)
        self.root.after(33, self._tick_webcam)

    def _fit_to_canvas(self, rgb: np.ndarray) -> np.ndarray:
        out_w, out_h = self.pipeline.output_size
        h, w = rgb.shape[:2]
        scale = min(out_w / w, out_h / h)
        nw, nh = int(w * scale), int(h * scale)
        resized = cv2.resize(rgb, (nw, nh), interpolation=cv2.INTER_AREA)
        canvas_img = np.full((out_h, out_w, 3), 32, dtype=np.uint8)
        x = (out_w - nw) // 2
        y = (out_h - nh) // 2
        canvas_img[y:y + nh, x:x + nw] = resized
        # center-crop to output_size for consistent overlay alignment
        # actually full canvas already matches output_size
        return canvas_img

    def _blit_overlay(self, rgb: np.ndarray) -> np.ndarray:
        if self.overlay_rgba is None:
            return rgb
        ov = cv2.resize(self.overlay_rgba, (rgb.shape[1], rgb.shape[0]),
                        interpolation=cv2.INTER_LINEAR)
        opacity = self.settings["opacity"] / 100.0
        ov_rgb = ov[:, :, :3]
        ov_a = (ov[:, :, 3].astype(np.float32) / 255.0) * opacity
        out = rgb.astype(np.float32) * (1 - ov_a[..., None]) + ov_rgb.astype(np.float32) * ov_a[..., None]
        return out.clip(0, 255).astype(np.uint8)

    def _capture(self):
        if self.live_frame is None:
            messagebox.showerror("Capture", "No frame available.")
            return
        rgb = cv2.cvtColor(self.live_frame, cv2.COLOR_BGR2RGB)
        self.pipeline.set_source(rgb)
        self.is_frozen = True
        self.capture_btn.state(["disabled"])
        self.retake_btn.state(["!disabled"])
        for p in self.panels:
            p.on_state_reset()
        self.request_render()
        self._precompute_mask_async()

    def _retake(self):
        if self.mode != "webcam":
            self._reset_to("upload")
            return
        self.is_frozen = False
        self.pipeline.source = None
        self.pipeline.source_mask = None
        self.capture_btn.state(["!disabled"])
        self.retake_btn.state(["disabled"])

    def _load_upload(self, path: str):
        self.mode = "upload"
        try:
            pil = Image.open(path).convert("RGB")
        except Exception as e:
            messagebox.showerror("Upload", f"Could not open image: {e}")
            return
        self._stop_webcam()
        rgb = np.array(pil)
        self.pipeline.set_source(rgb)
        self.is_frozen = True
        self.capture_btn.state(["disabled"])
        self.retake_btn.state(["!disabled"])
        for p in self.panels:
            p.on_state_reset()
        self.request_render()
        self._precompute_mask_async()

    # --- Rendering ---

    def request_render(self, heavy: bool = False):
        """Queue a render. heavy is unused now (mask is precomputed); kept for API compat."""
        if self._render_pending:
            return
        self._render_pending = True
        self.root.after_idle(self._do_render)

    def _do_render(self):
        self._render_pending = False
        if self.pipeline.source is None:
            return

        if self.pipeline.state.bg_remove and not self.pipeline.has_mask():
            # User toggled bg-remove before mask finished. Kick off precompute
            # if not already running; once it's ready we'll re-render.
            self._precompute_mask_async()
            self.busy_var.set("Removing background…")

        img = self.pipeline.render_with_overlay(
            self.overlay_rgba,
            self.settings["opacity"] / 100.0,
        )
        if img is not None:
            self._show(img)
            self._update_validation()

    def _precompute_mask_async(self):
        """Run rembg in a background thread, store the mask on the pipeline."""
        if self.pipeline.source is None or not bgremove.is_available():
            return
        if self.pipeline.has_mask() or self._heavy_render_in_progress:
            return
        self._heavy_render_in_progress = True
        if not self.busy_var.get():
            self.busy_var.set("Analyzing image…")

        source = self.pipeline.source
        model = self.settings["rembg_model"]

        def work():
            mask = bgremove.alpha_mask(source, model)

            def done():
                self._heavy_render_in_progress = False
                self.busy_var.set("")
                if mask is None:
                    return
                # Only apply if source hasn't changed since
                if self.pipeline.source is source:
                    self.pipeline.set_source_mask(mask)
                    self.request_render()

            self.root.after(0, done)

        threading.Thread(target=work, daemon=True).start()

    def invalidate_mask_cache(self):
        # Mask is per-source (un-rotated); rotation no longer invalidates it.
        pass

    def sync_panels_to_state(self):
        """After programmatic state change (auto-fit), sync widgets."""
        for p in self.panels:
            # crop panel uses angle/zoom vars
            if hasattr(p, "angle_var"):
                p.angle_var.set(round(self.pipeline.state.angle, 2))
            if hasattr(p, "zoom_var"):
                p.zoom_var.set(round(self.pipeline.state.zoom, 3))

    def _update_validation(self):
        if self.pipeline.source is None or not detect.is_available():
            return
        rendered = self.pipeline.render()
        if rendered is None:
            return
        metrics = detect.detect(rendered)
        if metrics is None:
            self.validation_var.set("✗ Face not detected in output.")
            return
        out_w, out_h = self.pipeline.output_size
        spec = self.spec

        true_top_y = None
        mask_in_output = self.pipeline.render_mask_to_output()
        if mask_in_output is not None:
            face_w = abs(metrics.right_eye[0] - metrics.left_eye[0]) * 2.5
            top_y = detect.find_head_top_y(mask_in_output, metrics.face_center_x, face_w)
            if top_y is not None:
                true_top_y = top_y

        head_top_y = true_top_y if true_top_y is not None else metrics.head_top_estimated[1]
        head_px = metrics.chin[1] - head_top_y
        head_mm = head_px / out_h * spec.photo_h_mm
        top_mm = head_top_y / out_h * spec.photo_h_mm
        cx_dev_mm = (metrics.face_center_x - out_w / 2) / out_w * spec.photo_w_mm

        lines = []
        ok_h = spec.head_min_mm <= head_mm <= spec.head_max_mm
        lines.append(f"{'✓' if ok_h else '✗'} Head height: {head_mm:.1f} mm "
                     f"(spec {spec.head_min_mm}-{spec.head_max_mm})")
        ok_top = spec.top_gap_mm <= top_mm <= spec.top_gap_mm + spec.crown_band_mm
        lines.append(f"{'✓' if ok_top else '✗'} Top gap: {top_mm:.1f} mm "
                     f"(spec {spec.top_gap_mm}-{spec.top_gap_mm + spec.crown_band_mm})")
        ok_c = abs(cx_dev_mm) <= spec.horizontal_tolerance_mm
        lines.append(f"{'✓' if ok_c else '✗'} Centered: {cx_dev_mm:+.1f} mm "
                     f"(tol ±{spec.horizontal_tolerance_mm})")
        method = "hair-top from mask" if true_top_y is not None else "forehead landmark (mask pending)"
        lines.append(f"  measured via: {method}")
        self.validation_var.set("\n".join(lines))

    def _show(self, rgb: np.ndarray):
        img = Image.fromarray(rgb)
        self._tk_img = ImageTk.PhotoImage(img)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self._tk_img)

    # --- Save ---

    def _save(self):
        if self.pipeline.source is None:
            messagebox.showerror("Save", "No image to save.")
            return
        out = self.pipeline.render()
        if out is None:
            messagebox.showerror("Save", "Render failed.")
            return
        ext = self.settings["save_format"].lower()
        if ext not in ("jpg", "jpeg", "png"):
            ext = "jpg"
        ts = time.strftime("%Y%m%d_%H%M%S")
        fname = f"passport_{ts}.{ext}"
        full = os.path.join(self.settings["output_folder"], fname)
        pil = Image.fromarray(out)
        if ext in ("jpg", "jpeg"):
            pil.save(full, quality=self.settings["save_quality"], subsampling=0)
        else:
            pil.save(full)
        messagebox.showinfo("Saved", f"Saved to {full}")

    # --- Settings dialog ---

    def _open_settings(self):
        SettingsDialog(self)

    def on_settings_saved(self):
        self.settings = settings_mod.load()
        self.spec = spec_mod.SPECS.get(self.settings["spec"], spec_mod.FINNISH)
        self.pipeline.set_output_size(tuple(self.settings["output_size"]))
        self.pipeline.state.bg_color = tuple(self.settings["default_bg_color"])
        out_w, out_h = self.pipeline.output_size
        self.canvas.configure(width=out_w, height=out_h)
        self._load_overlay()
        if self.pipeline.source is not None:
            self.request_render()


class SettingsDialog(tk.Toplevel):
    def __init__(self, app: PassportApp):
        super().__init__(app.root)
        self.app = app
        self.title("Settings")
        self.transient(app.root)
        self.grab_set()

        s = app.settings
        r = 0
        ttk.Label(self, text="Overlay Image").grid(row=r, column=0, sticky="w", padx=4, pady=2)
        self.overlay_entry = ttk.Entry(self, width=40)
        self.overlay_entry.insert(0, s["overlay_path"])
        self.overlay_entry.grid(row=r, column=1, padx=4, pady=2)
        ttk.Button(self, text="Browse", command=self._pick_overlay).grid(row=r, column=2, padx=4)
        r += 1

        ttk.Label(self, text="Overlay opacity").grid(row=r, column=0, sticky="w", padx=4, pady=2)
        self.opacity_var = tk.IntVar(value=s["opacity"])
        ttk.Scale(self, from_=0, to=100, variable=self.opacity_var, orient="horizontal").grid(
            row=r, column=1, columnspan=2, sticky="ew", padx=4)
        r += 1

        ttk.Label(self, text="Output size (W × H)").grid(row=r, column=0, sticky="w", padx=4, pady=2)
        size_frame = ttk.Frame(self)
        size_frame.grid(row=r, column=1, columnspan=2, sticky="w", padx=4)
        self.w_entry = ttk.Entry(size_frame, width=6)
        self.w_entry.insert(0, str(s["output_size"][0]))
        self.w_entry.pack(side="left")
        ttk.Label(size_frame, text=" × ").pack(side="left")
        self.h_entry = ttk.Entry(size_frame, width=6)
        self.h_entry.insert(0, str(s["output_size"][1]))
        self.h_entry.pack(side="left")
        r += 1

        ttk.Label(self, text="Output folder").grid(row=r, column=0, sticky="w", padx=4, pady=2)
        self.folder_entry = ttk.Entry(self, width=40)
        self.folder_entry.insert(0, s["output_folder"])
        self.folder_entry.grid(row=r, column=1, padx=4, pady=2)
        ttk.Button(self, text="Browse", command=self._pick_folder).grid(row=r, column=2, padx=4)
        r += 1

        ttk.Label(self, text="Save format").grid(row=r, column=0, sticky="w", padx=4, pady=2)
        self.fmt_var = tk.StringVar(value=s["save_format"])
        ttk.Combobox(self, textvariable=self.fmt_var, values=["jpg", "png"],
                     state="readonly", width=6).grid(row=r, column=1, sticky="w", padx=4)
        r += 1

        ttk.Label(self, text="JPG quality").grid(row=r, column=0, sticky="w", padx=4, pady=2)
        self.qual_var = tk.IntVar(value=s["save_quality"])
        ttk.Scale(self, from_=60, to=100, variable=self.qual_var, orient="horizontal").grid(
            row=r, column=1, columnspan=2, sticky="ew", padx=4)
        r += 1

        ttk.Button(self, text="Save", command=self._save).grid(row=r, column=0, columnspan=3, pady=10)

    def _pick_overlay(self):
        path = filedialog.askopenfilename(parent=self, filetypes=[("PNG", "*.png")])
        if path:
            self.overlay_entry.delete(0, tk.END)
            self.overlay_entry.insert(0, path)

    def _pick_folder(self):
        path = filedialog.askdirectory(parent=self)
        if path:
            self.folder_entry.delete(0, tk.END)
            self.folder_entry.insert(0, path)

    def _save(self):
        try:
            w = int(self.w_entry.get())
            h = int(self.h_entry.get())
        except ValueError:
            messagebox.showerror("Settings", "Output size must be integers.")
            return
        new = dict(self.app.settings)
        new["overlay_path"] = self.overlay_entry.get()
        new["opacity"] = int(self.opacity_var.get())
        new["output_size"] = [w, h]
        new["output_folder"] = self.folder_entry.get()
        new["save_format"] = self.fmt_var.get()
        new["save_quality"] = int(self.qual_var.get())
        settings_mod.save(new)
        self.app.on_settings_saved()
        self.destroy()
