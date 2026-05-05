"""Programmatic guide overlay matching the official Finnish diagram.

Layout (per kuvan_mitat_597.png):
- Two short horizontal red lines at y=4mm and y=6mm (crown band), 16.5mm wide centered
- Two short horizontal red lines at y=38mm and y=40mm (chin band), 16.5mm wide centered
- Two vertical red lines forming a 3mm-wide centered band, spanning the head zone
"""

from __future__ import annotations

import cv2
import numpy as np

from spec import PassportSpec


def build_overlay(spec: PassportSpec, output_size: tuple[int, int]) -> np.ndarray:
    out_w, out_h = output_size
    img = np.zeros((out_h, out_w, 4), dtype=np.uint8)

    sx = out_w / spec.photo_w_mm
    sy = out_h / spec.photo_h_mm

    def x(mm: float) -> int:
        return int(round(mm * sx))

    def y(mm: float) -> int:
        return int(round(mm * sy))

    red = (220, 80, 60)  # RGB approx of the diagram orange-red

    def line(p1, p2, c=red, t=2):
        cv2.line(img, p1, p2, (*c, 255), t, cv2.LINE_AA)

    # Horizontal guide lines: width = 16.5 mm, centered
    half_w = x(spec.h_line_width_mm / 2)
    cx = out_w // 2
    h_x1 = cx - half_w
    h_x2 = cx + half_w

    for y_mm in (spec.upper_crown_y_mm, spec.lower_crown_y_mm,
                 spec.upper_chin_y_mm, spec.lower_chin_y_mm):
        yy = y(y_mm)
        line((h_x1, yy), (h_x2, yy))

    # Vertical center band: width = 3 mm, spans from upper crown to lower chin
    half_c = x(spec.center_band_mm / 2)
    v_y1 = y(spec.upper_crown_y_mm)
    v_y2 = y(spec.lower_chin_y_mm)
    line((cx - half_c, v_y1), (cx - half_c, v_y2))
    line((cx + half_c, v_y1), (cx + half_c, v_y2))

    return img
