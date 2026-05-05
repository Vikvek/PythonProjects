"""Image render pipeline.

Holds source image + state dict, renders preview/final on demand.
Transform order: rotate -> bg-remove -> color adjust -> zoom/offset crop -> overlay (preview only).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Optional

import cv2
import numpy as np
from PIL import Image, ImageEnhance


@dataclass
class PipelineState:
    angle: float = 0.0  # degrees, +/- 0.1 resolution
    zoom: float = 1.0
    offset_x: int = 0  # pixels in output coords
    offset_y: int = 0
    crop_rect: Optional[tuple[int, int, int, int]] = None  # (x1,y1,x2,y2) in source-rotated coords
    brightness: float = 1.0
    contrast: float = 1.0
    saturation: float = 1.0
    greyscale: bool = False
    bg_remove: bool = False
    bg_color: tuple[int, int, int] = (255, 255, 255)
    feather: int = 2  # px


class ImagePipeline:
    def __init__(self, output_size: tuple[int, int]):
        self.output_size = output_size  # (w, h)
        self.source: Optional[np.ndarray] = None  # RGB uint8
        self.state = PipelineState()
        self.source_mask: Optional[np.ndarray] = None  # HxW uint8 alpha for un-rotated source

    def set_source(self, rgb: np.ndarray) -> None:
        self.source = rgb.copy()
        self.state = PipelineState()
        self.source_mask = None

    def set_output_size(self, size: tuple[int, int]) -> None:
        self.output_size = size

    def source_id(self) -> str:
        if self.source is None:
            return ""
        return hashlib.md5(self.source.tobytes()).hexdigest()[:12]

    def set_source_mask(self, mask: np.ndarray) -> None:
        self.source_mask = mask

    def has_mask(self) -> bool:
        return self.source_mask is not None

    # --- transforms ---

    @staticmethod
    def _rotate(img: np.ndarray, angle: float) -> np.ndarray:
        if abs(angle) < 0.01:
            return img
        pil = Image.fromarray(img)
        return np.array(pil.rotate(angle, expand=True, resample=Image.BICUBIC))

    @staticmethod
    def _adjust(img: np.ndarray, b: float, c: float, s: float, grey: bool) -> np.ndarray:
        pil = Image.fromarray(img)
        if abs(b - 1.0) > 0.01:
            pil = ImageEnhance.Brightness(pil).enhance(b)
        if abs(c - 1.0) > 0.01:
            pil = ImageEnhance.Contrast(pil).enhance(c)
        if abs(s - 1.0) > 0.01:
            pil = ImageEnhance.Color(pil).enhance(s)
        if grey:
            pil = pil.convert("L").convert("RGB")
        return np.array(pil)

    def _composite_bg(self, rgba: np.ndarray) -> np.ndarray:
        """rgba: HxWx4 with alpha. Return RGB composited over state.bg_color."""
        rgb = rgba[:, :, :3].astype(np.float32)
        alpha = rgba[:, :, 3].astype(np.float32) / 255.0
        if self.state.feather > 0:
            k = self.state.feather * 2 + 1
            alpha = cv2.GaussianBlur(alpha, (k, k), 0)
        bg = np.full_like(rgb, self.state.bg_color, dtype=np.float32)
        out = rgb * alpha[..., None] + bg * (1.0 - alpha[..., None])
        return out.clip(0, 255).astype(np.uint8)

    def _crop_to_output(self, img: np.ndarray) -> np.ndarray:
        out_w, out_h = self.output_size
        if self.state.crop_rect is not None:
            x1, y1, x2, y2 = self.state.crop_rect
            x1 = max(0, x1); y1 = max(0, y1)
            x2 = min(img.shape[1], x2); y2 = min(img.shape[0], y2)
            if x2 <= x1 or y2 <= y1:
                return self._center_crop(img)
            cropped = img[y1:y2, x1:x2]
            return cv2.resize(cropped, (out_w, out_h), interpolation=cv2.INTER_LANCZOS4)
        return self._center_crop(img)

    def _center_crop(self, img: np.ndarray) -> np.ndarray:
        out_w, out_h = self.output_size
        zoom = self.state.zoom
        h, w = img.shape[:2]
        # zoom by resizing source larger, then crop center+offset
        zw, zh = int(w * zoom), int(h * zoom)
        zoomed = cv2.resize(img, (zw, zh), interpolation=cv2.INTER_LANCZOS4)
        cx = zw // 2 + self.state.offset_x
        cy = zh // 2 + self.state.offset_y
        x1 = cx - out_w // 2
        y1 = cy - out_h // 2
        x2 = x1 + out_w
        y2 = y1 + out_h
        # pad if needed
        pad_l = max(0, -x1); pad_t = max(0, -y1)
        pad_r = max(0, x2 - zw); pad_b = max(0, y2 - zh)
        if pad_l or pad_t or pad_r or pad_b:
            zoomed = cv2.copyMakeBorder(zoomed, pad_t, pad_b, pad_l, pad_r,
                                         cv2.BORDER_CONSTANT, value=self.state.bg_color)
            x1 += pad_l; x2 += pad_l; y1 += pad_t; y2 += pad_t
        return zoomed[y1:y2, x1:x2]

    # --- entry points ---

    def _rotated_mask(self) -> Optional[np.ndarray]:
        """Return source mask rotated by current angle, matching rotated source dims."""
        if self.source_mask is None:
            return None
        return self._rotate(self.source_mask, self.state.angle)

    def render(self) -> Optional[np.ndarray]:
        """Return RGB output_size image, or None if no source."""
        if self.source is None:
            return None

        img = self._rotate(self.source, self.state.angle)

        if self.state.bg_remove and self.source_mask is not None:
            mask = self._rotated_mask()
            if mask is not None:
                rgba = np.dstack([img, mask])
                img = self._composite_bg(rgba)

        img = self._adjust(img, self.state.brightness, self.state.contrast,
                           self.state.saturation, self.state.greyscale)

        img = self._crop_to_output(img)
        return img

    def render_mask_to_output(self) -> Optional[np.ndarray]:
        """Return the source foreground mask transformed (rotate + crop) to output size.

        Returns HxW uint8, or None if no mask cached.
        """
        if self.source_mask is None:
            return None
        m = self._rotate(self.source_mask, self.state.angle)
        # _crop_to_output expects 3-channel; expand and shrink back
        m3 = np.dstack([m, m, m])
        # Avoid bg_color padding bleeding into mask: temporarily override
        saved = self.state.bg_color
        self.state.bg_color = (0, 0, 0)
        try:
            out = self._crop_to_output(m3)
        finally:
            self.state.bg_color = saved
        return out[:, :, 0]

    def render_with_overlay(self, overlay_rgba: Optional[np.ndarray],
                             opacity: float) -> Optional[np.ndarray]:
        base = self.render()
        if base is None or overlay_rgba is None:
            return base
        ov = cv2.resize(overlay_rgba, (base.shape[1], base.shape[0]),
                        interpolation=cv2.INTER_LINEAR)
        if ov.shape[2] == 4:
            ov_rgb = ov[:, :, :3]
            ov_a = (ov[:, :, 3].astype(np.float32) / 255.0) * opacity
        else:
            ov_rgb = ov
            ov_a = np.full(base.shape[:2], opacity, dtype=np.float32)
        out = base.astype(np.float32) * (1 - ov_a[..., None]) + ov_rgb.astype(np.float32) * ov_a[..., None]
        return out.clip(0, 255).astype(np.uint8)
