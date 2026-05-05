"""Background removal via rembg.

Lazy session init — first call triggers model download.
"""

from __future__ import annotations

from typing import Optional

import numpy as np

try:
    from rembg import new_session, remove
    _REMBG_AVAILABLE = True
except ImportError:
    _REMBG_AVAILABLE = False


_session = None
_session_model = None


def _ensure_session(model: str):
    global _session, _session_model
    if not _REMBG_AVAILABLE:
        return None
    if _session is None or _session_model != model:
        _session = new_session(model)
        _session_model = model
    return _session


def alpha_mask(rgb: np.ndarray, model: str = "u2net_human_seg") -> Optional[np.ndarray]:
    """Return HxW uint8 alpha (0 bg, 255 foreground), or None on failure."""
    session = _ensure_session(model)
    if session is None:
        return None
    try:
        rgba = remove(rgb, session=session)
    except Exception:
        return None
    if rgba.ndim == 3 and rgba.shape[2] == 4:
        return rgba[:, :, 3]
    return None


def is_available() -> bool:
    return _REMBG_AVAILABLE
