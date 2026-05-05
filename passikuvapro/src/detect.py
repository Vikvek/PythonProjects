"""Face landmark detection + auto-crop math.

Uses mediapipe Tasks API (FaceLandmarker). Model file auto-downloads on first run.
Returns None if mediapipe missing, model unavailable, or no face found.
"""

from __future__ import annotations

import math
import os
import urllib.request
from dataclasses import dataclass
from typing import Optional

import numpy as np

try:
    import mediapipe as mp
    from mediapipe.tasks import python as mp_python
    from mediapipe.tasks.python import vision as mp_vision
    _MP_AVAILABLE = True
except ImportError:
    _MP_AVAILABLE = False

# FaceLandmarker uses 478 landmarks — same indices as old FaceMesh
IDX_CHIN = 152
IDX_FOREHEAD_TOP = 10
IDX_LEFT_EYE_OUTER = 33
IDX_RIGHT_EYE_OUTER = 263
IDX_NOSE_TIP = 1

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/face_landmarker/"
    "face_landmarker/float16/1/face_landmarker.task"
)
MODEL_FILE = "face_landmarker.task"


@dataclass
class FaceMetrics:
    chin: tuple[float, float]
    forehead: tuple[float, float]
    left_eye: tuple[float, float]
    right_eye: tuple[float, float]
    nose: tuple[float, float]
    head_top_estimated: tuple[float, float]
    eye_tilt_deg: float

    @property
    def head_height_px(self) -> float:
        return math.dist(self.chin, self.head_top_estimated)

    @property
    def face_center_x(self) -> float:
        return (self.left_eye[0] + self.right_eye[0]) / 2


_landmarker = None
_init_failed = False


def _model_path() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(here)
    models_dir = os.path.join(root, "models")
    os.makedirs(models_dir, exist_ok=True)
    return os.path.join(models_dir, MODEL_FILE)


def _ensure_model() -> Optional[str]:
    path = _model_path()
    if os.path.exists(path):
        return path
    try:
        urllib.request.urlretrieve(MODEL_URL, path)
        return path
    except Exception:
        return None


def _get_landmarker():
    global _landmarker, _init_failed
    if not _MP_AVAILABLE or _init_failed:
        return None
    if _landmarker is not None:
        return _landmarker
    model_path = _ensure_model()
    if model_path is None:
        _init_failed = True
        return None
    try:
        base_options = mp_python.BaseOptions(model_asset_path=model_path)
        options = mp_vision.FaceLandmarkerOptions(
            base_options=base_options,
            running_mode=mp_vision.RunningMode.IMAGE,
            num_faces=1,
        )
        _landmarker = mp_vision.FaceLandmarker.create_from_options(options)
        return _landmarker
    except Exception:
        _init_failed = True
        return None


def detect(rgb: np.ndarray) -> Optional[FaceMetrics]:
    lm_runner = _get_landmarker()
    if lm_runner is None:
        return None
    mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
    res = lm_runner.detect(mp_img)
    if not res.face_landmarks:
        return None
    lm = res.face_landmarks[0]
    h, w = rgb.shape[:2]

    def pt(i):
        return (lm[i].x * w, lm[i].y * h)

    chin = pt(IDX_CHIN)
    forehead = pt(IDX_FOREHEAD_TOP)
    left = pt(IDX_LEFT_EYE_OUTER)
    right = pt(IDX_RIGHT_EYE_OUTER)
    nose = pt(IDX_NOSE_TIP)

    # forehead landmark is at hairline; pad upward for crown estimate
    face_h = math.dist(chin, forehead)
    hair_allowance = face_h * 0.12
    dx, dy = forehead[0] - chin[0], forehead[1] - chin[1]
    norm = math.hypot(dx, dy) or 1.0
    head_top = (forehead[0] + dx / norm * hair_allowance,
                forehead[1] + dy / norm * hair_allowance)

    eye_dx = right[0] - left[0]
    eye_dy = right[1] - left[1]
    tilt = math.degrees(math.atan2(eye_dy, eye_dx))

    return FaceMetrics(
        chin=chin, forehead=forehead,
        left_eye=left, right_eye=right, nose=nose,
        head_top_estimated=head_top,
        eye_tilt_deg=tilt,
    )


@dataclass
class AutoFitResult:
    angle_delta: float
    zoom: float
    offset_x: int
    offset_y: int


def find_head_top_y(mask: np.ndarray, face_center_x: float, face_width: float,
                    threshold: int = 64) -> Optional[float]:
    """Topmost foreground pixel above the face, within a column band around face_center_x."""
    if mask is None:
        return None
    h, w = mask.shape[:2]
    half = max(int(face_width * 0.6), 20)
    x1 = max(0, int(face_center_x - half))
    x2 = min(w, int(face_center_x + half))
    if x2 <= x1:
        return None
    band = mask[:, x1:x2] >= threshold
    rows = np.where(band.any(axis=1))[0]
    if rows.size == 0:
        return None
    return float(rows[0])


def compute_autofit(rgb: np.ndarray, output_size: tuple[int, int],
                    spec_target_head_ratio: float, spec_top_gap_ratio: float,
                    current_angle: float,
                    foreground_mask: Optional[np.ndarray] = None
                    ) -> Optional[AutoFitResult]:
    metrics = detect(rgb)
    if metrics is None:
        return None

    # If a foreground mask is given, replace landmark-based head top with the
    # actual topmost foreground pixel — accurate for people with hair.
    if foreground_mask is not None:
        face_w = abs(metrics.right_eye[0] - metrics.left_eye[0]) * 2.5
        true_top = find_head_top_y(foreground_mask, metrics.face_center_x, face_w)
        if true_top is not None:
            metrics = FaceMetrics(
                chin=metrics.chin,
                forehead=metrics.forehead,
                left_eye=metrics.left_eye,
                right_eye=metrics.right_eye,
                nose=metrics.nose,
                head_top_estimated=(metrics.face_center_x, true_top),
                eye_tilt_deg=metrics.eye_tilt_deg,
            )

    out_w, out_h = output_size
    target_head_px = spec_target_head_ratio * out_h
    current_head_px = metrics.head_height_px
    if current_head_px < 1:
        return None

    zoom = target_head_px / current_head_px
    top_gap_px = spec_top_gap_ratio * out_h

    target_src_x = metrics.face_center_x
    target_src_y = (metrics.chin[1] + metrics.head_top_estimated[1]) / 2

    zoomed_src_x = target_src_x * zoom
    zoomed_src_y = target_src_y * zoom
    zoomed_w = rgb.shape[1] * zoom
    zoomed_h = rgb.shape[0] * zoom

    out_cx = out_w / 2
    out_cy = top_gap_px + target_head_px / 2

    offset_x = zoomed_src_x - zoomed_w / 2 - (out_cx - out_w / 2)
    offset_y = zoomed_src_y - zoomed_h / 2 - (out_cy - out_h / 2)

    return AutoFitResult(
        angle_delta=-metrics.eye_tilt_deg,
        zoom=zoom,
        offset_x=int(round(offset_x)),
        offset_y=int(round(offset_y)),
    )


def is_available() -> bool:
    return _MP_AVAILABLE
