"""Application constants, per-user storage, and persistent settings."""

import json
import os
import tempfile
from dataclasses import asdict, dataclass

from platformdirs import PlatformDirs

APP_NAME = "Hair Class Organizer"
MODEL_ID = "electblake/hair_color_classifier"
MODEL_LABELS = ("black", "blonde", "blue", "brown", "pink", "red", "silver")

IMAGE_EXTENSIONS = {".bmp", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"}
VIDEO_EXTENSIONS = {".avi", ".gif", ".m4v", ".mkv", ".mov", ".mp4", ".mpeg", ".mpg", ".webm"}
VIDEO_GRABS_FOLDER = ".hair_class_organizer_video_grabs"

_dirs = PlatformDirs("Hair-Class-Organizer", appauthor=False)
DATA_DIR = _dirs.user_data_path
CONFIG_PATH = _dirs.user_config_path / "settings.json"
HF_CACHE_DIR = DATA_DIR / "models" / "huggingface"


@dataclass(slots=True)
class AppSettings:
    source: str = ""
    confidence: float = 0.5
    include_videos: bool = True
    frame_percentage: int = 50
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
        "HF_HOME": DATA_DIR / "cache" / "huggingface",
        "HF_HUB_CACHE": HF_CACHE_DIR,
        "TORCH_HOME": DATA_DIR / "cache" / "torch",
        "CUDA_CACHE_PATH": DATA_DIR / "cache" / "cuda",
        "MPLCONFIGDIR": DATA_DIR / "cache" / "matplotlib",
    }
    for variable, directory in locations.items():
        directory.mkdir(parents=True, exist_ok=True)
        os.environ[variable] = str(directory)
    temporary = DATA_DIR / "cache" / "tmp"
    temporary.mkdir(parents=True, exist_ok=True)
    tempfile.tempdir = str(temporary)
