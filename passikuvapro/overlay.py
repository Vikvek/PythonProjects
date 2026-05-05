"""Programmatic guide overlay drawn from the passport spec.

Mimics the Finnish police passport tool: red bands at top (crown range)
and bottom (chin range), red vertical centerline, on a transparent canvas.
"""

from __future__ import annotations

import cv2
import numpy as np

from spec import PassportSpec


def build_overlay(spec: PassportSpec, output_size: tuple[int, int]) -> np.ndarray:
    out_w, out_h = output_size
    img = np.zeros((out_h, out_w, 4), dtype=np.uint8)

    px_per_mm_y = out_h / spec.photo_h_mm

    def y(mm: float) -> int:
        return int(round(mm * px_per_mm_y))

    cx = out_w // 2
    red = (60, 60, 220)        # BGR-ish but we treat as RGB → red
    red_dim = (90, 90, 200)
    grey = (160, 160, 160)

    def hline(yy: int, c, t=1):
        cv2.line(img, (0, yy), (out_w, yy), (*c, 255), t, cv2.LINE_AA)

    def vline(xx: int, c, t=1):
        cv2.line(img, (xx, 0), (xx, out_h), (*c, 255), t, cv2.LINE_AA)

    # Crown band (top of head must fall here)
    y_crown_top = y(spec.top_gap_min_mm)
    y_crown_bot = y(spec.top_gap_max_mm)
    hline(y_crown_top, red, 1)
    hline(y_crown_bot, red, 1)

    # Chin band (chin must fall here)
    y_chin_top = y(spec.top_gap_min_mm + spec.head_min_mm)
    y_chin_bot = y(spec.top_gap_max_mm + spec.head_max_mm)
    hline(y_chin_top, red, 1)
    hline(y_chin_bot, red, 1)

    # Vertical center
    vline(cx, red, 1)

    # Eye-line guide (around 50% of head height down from crown target)
    y_eye = y(spec.top_gap_mm + spec.head_target_mm * 0.45)
    cv2.line(img, (out_w // 4, y_eye), (3 * out_w // 4, y_eye), (*grey, 200), 1, cv2.LINE_AA)

    # Tiny mm labels (off to the side, dim)
    font = cv2.FONT_HERSHEY_SIMPLEX

    def label(text, pos, c=red_dim):
        cv2.putText(img, text, pos, font, 0.32, (*c, 230), 1, cv2.LINE_AA)

    label(f"crown {spec.top_gap_min_mm:.0f}-{spec.top_gap_max_mm:.0f}mm",
          (4, max(10, y_crown_top - 3)))
    label(f"chin {spec.top_gap_min_mm + spec.head_min_mm:.0f}-"
          f"{spec.top_gap_max_mm + spec.head_max_mm:.0f}mm",
          (4, y_chin_bot + 11))
    label(f"{spec.photo_w_mm:.0f}x{spec.photo_h_mm:.0f}mm",
          (out_w - 56, out_h - 5))

    return img
