"""Application constants, per-user storage, and persistent settings."""

import json
import os
import tempfile
from dataclasses import asdict, dataclass

from platformdirs import user_config_path

APP_NAME = "Hair Class Organizer"
MODEL_ID = "electblake/hair_color_classifier"
MODEL_LABELS = ("black", "blonde", "blue", "brown", "pink", "red", "silver")

IMAGE_EXTENSIONS = {".bmp", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"}
VIDEO_EXTENSIONS = {".avi", ".gif", ".m4v", ".mkv", ".mov", ".mp4", ".mpeg", ".mpg", ".webm"}

APP_STATE_DIR = user_config_path("Hair-Class-Organizer", appauthor=False)
CACHE_DIR = APP_STATE_DIR / "cache"
TEMP_DIR = CACHE_DIR / "tmp"
MOVES_DIR = APP_STATE_DIR / "moves"
CONFIG_PATH = APP_STATE_DIR / "settings.json"
HF_CACHE_DIR = APP_STATE_DIR / "models" / "huggingface"
LOG_PATH = APP_STATE_DIR / "hair-class-organizer.log"


@dataclass(slots=True)
class AppSettings:
    source: str = ""
    confidence: float = 0.5
    include_videos: bool = True
    frame_percentage: int = 50
    video_workers: int = 12
    move_workers: int = 12
    png_compress_level: int = 1
    device: str = "auto"
    window_geometry: str = "1100x720"

    @classmethod
    def load(cls) -> "AppSettings":
        if not CONFIG_PATH.exists():
            return cls()
        return cls(**json.loads(CONFIG_PATH.read_text(encoding="utf-8")))

    def save(self) -> None:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")


def configure_runtime() -> None:
    """Keep model and native-library caches in app-owned per-user storage."""
    locations = {
        "HF_HOME": CACHE_DIR / "huggingface",
        "HF_HUB_CACHE": HF_CACHE_DIR,
        "TORCH_HOME": CACHE_DIR / "torch",
        "CUDA_CACHE_PATH": CACHE_DIR / "cuda",
        "MPLCONFIGDIR": CACHE_DIR / "matplotlib",
        "TEMP": TEMP_DIR,
        "TMP": TEMP_DIR,
    }
    for variable, directory in locations.items():
        directory.mkdir(parents=True, exist_ok=True)
        os.environ[variable] = str(directory)
    tempfile.tempdir = str(TEMP_DIR)
