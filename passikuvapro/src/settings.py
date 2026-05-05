"""Settings load/save."""

import json
import os
from typing import Any

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETTINGS_FILE = os.path.join(ROOT, "settings.json")
DEFAULT_OUTPUT_DIR = os.path.join(ROOT, "output")

DEFAULTS: dict[str, Any] = {
    "overlay_path": "",
    "use_generated_overlay": True,
    "opacity": 70,
    "output_size": [500, 653],
    "output_folder": "",
    "spec": "finnish",
    "default_bg_color": [255, 255, 255],
    "rembg_model": "u2net_human_seg",
    "save_format": "jpg",
    "save_quality": 95,
}


def load() -> dict[str, Any]:
    settings = dict(DEFAULTS)
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            for k, v in loaded.items():
                settings[k] = v
        except (json.JSONDecodeError, OSError):
            pass
    if not settings["output_folder"]:
        settings["output_folder"] = DEFAULT_OUTPUT_DIR
    os.makedirs(settings["output_folder"], exist_ok=True)
    save(settings)
    return settings


def save(settings: dict[str, Any]) -> None:
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)
