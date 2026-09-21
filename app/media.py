"""Hair-color inference, Spectra-style video snapshots, and reviewed media moves."""

import csv
import os
import shutil
from dataclasses import dataclass, replace
from pathlib import Path
from threading import Event
from typing import Callable

import cv2
from PIL import Image

from app.config import IMAGE_EXTENSIONS, MODEL_ID, MODEL_LABELS, VIDEO_EXTENSIONS, VIDEO_GRABS_FOLDER

Emit = Callable[[str, object], None]


@dataclass(frozen=True, slots=True)
class ScanOptions:
    source: Path
    include_videos: bool = True
    frame_percentage: int = 50
    png_compress_level: int = 1
    device: str = "auto"


@dataclass(frozen=True, slots=True)
class MediaResult:
    source: Path
    media_type: str
    label: str
    confidence: float
    predictions: tuple[tuple[str, float], ...]
    destination: Path | None = None


def discover_media(source: Path, include_videos: bool) -> list[Path]:
    source = source.resolve()
    candidates = [source] if source.is_file() else [path for path in source.iterdir() if path.is_file()]
    extensions = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS if include_videos else IMAGE_EXTENSIONS
    return sorted(path for path in candidates if path.suffix.lower() in extensions)


def extract_video_frame(video_path: Path, image_path: Path, frame_percentage: int, png_compress_level: int) -> int:
    """Extract one lossless frame with the same seek calculation and backend used by Spectra."""
    video = cv2.VideoCapture(
        str(video_path),
        cv2.CAP_FFMPEG,
        [
            cv2.CAP_PROP_OPEN_TIMEOUT_MSEC,
            10_000,
            cv2.CAP_PROP_READ_TIMEOUT_MSEC,
            10_000,
            cv2.CAP_PROP_N_THREADS,
            1,
        ],
    )
    frame_count = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
    frame_number = round((frame_count - 1) * frame_percentage / 100)
    video.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
    _, frame = video.read()
    video.release()
    image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    image.save(image_path, compress_level=png_compress_level)
    return frame_number


def create_classifier(device: str):
    from transformers import pipeline

    from app.model import load_pipeline_components

    model, image_processor = load_pipeline_components()
    arguments = {
        "task": "image-classification",
        "model": model,
        "image_processor": image_processor,
    }
    if device != "auto":
        arguments["device"] = device
    return pipeline(**arguments)


def scan_media(options: ScanOptions, stop: Event, emit: Emit) -> list[MediaResult]:
    media = discover_media(options.source, options.include_videos)
    emit("total", len(media))
    emit("status", f"Loading {MODEL_ID}")
    classifier = create_classifier(options.device)
    emit("device", str(classifier.device))

    root = options.source if options.source.is_dir() else options.source.parent
    videos = [path for path in media if path.suffix.lower() in VIDEO_EXTENSIONS]
    grabs = root / VIDEO_GRABS_FOLDER
    if videos:
        grabs.mkdir(exist_ok=True)

    results = []
    for index, source in enumerate(media, 1):
        if stop.is_set():
            break
        media_type = "video" if source.suffix.lower() in VIDEO_EXTENSIONS else "image"
        inference_path = source
        if media_type == "video":
            inference_path = grabs / f"{source.name}.png"
            frame_number = extract_video_frame(
                source, inference_path, options.frame_percentage, options.png_compress_level
            )
            emit("status", f"Extracted frame {frame_number} from {source.name}")

        output = classifier(str(inference_path), top_k=len(MODEL_LABELS))
        predictions = tuple((str(item["label"]), float(item["score"])) for item in output)
        result = MediaResult(source, media_type, predictions[0][0], predictions[0][1], predictions)
        results.append(result)
        emit("result", result)
        emit("progress", (index, len(media), source.name))

    if videos:
        shutil.rmtree(grabs)
    return results


def plan_moves(
    results: list[MediaResult], source: Path, selected_labels: set[str], confidence: float
) -> list[MediaResult]:
    root = source if source.is_dir() else source.parent
    return [
        replace(result, destination=root / result.label / result.source.name)
        for result in results
        if result.label in selected_labels and result.confidence >= confidence
    ]


def move_media(results: list[MediaResult], journal: Path, stop: Event, emit: Emit) -> int:
    journal.parent.mkdir(parents=True, exist_ok=True)
    moved = 0
    with journal.open("x", newline="", encoding="utf-8") as log:
        writer = csv.writer(log)
        writer.writerow(["source", "destination", "label", "confidence"])
        log.flush()
        for result in results:
            if stop.is_set():
                break
            destination = result.destination
            destination.parent.mkdir(parents=True, exist_ok=True)
            with result.source.open("rb") as source_stream, destination.open("xb") as destination_stream:
                shutil.copyfileobj(source_stream, destination_stream)
                destination_stream.flush()
                os.fsync(destination_stream.fileno())
            shutil.copystat(result.source, destination)
            result.source.unlink()
            writer.writerow([result.source, destination, result.label, result.confidence])
            log.flush()
            os.fsync(log.fileno())
            moved += 1
            emit("moved", result)
    return moved
