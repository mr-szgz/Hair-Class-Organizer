"""Hair-color inference, Spectra-style video snapshots, and reviewed media moves."""

import csv
import multiprocessing
import os
import shutil
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from pathlib import Path
from threading import Event
from time import monotonic
from typing import Callable

import cv2
from PIL import Image

from app.config import IMAGE_EXTENSIONS, MODEL_ID, MODEL_LABELS, TEMP_DIR, VIDEO_EXTENSIONS

Emit = Callable[[str, object], None]


@dataclass(frozen=True, slots=True)
class ScanOptions:
    source: Path
    include_videos: bool = True
    frame_percentage: int = 50
    video_workers: int = 12
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


def _extract_video_frame_task(task: tuple[Path, Path, int, int]) -> tuple[Path, Path, int]:
    video_path, image_path, frame_percentage, png_compress_level = task
    frame_number = extract_video_frame(video_path, image_path, frame_percentage, png_compress_level)
    return video_path, image_path, frame_number


def extract_video_frames(
    videos: list[Path], grabs: Path, options: ScanOptions, stop: Event, emit: Emit
) -> dict[Path, Path]:
    grabs.mkdir(parents=True, exist_ok=True)
    emit("total", len(videos))
    tasks = [
        (source, grabs / f"{source.name}.png", options.frame_percentage, options.png_compress_level)
        for source in videos
    ]
    extracted_paths = {}
    extraction_started = monotonic()
    process_context = multiprocessing.get_context("spawn")
    with process_context.Pool(processes=min(options.video_workers, len(videos))) as pool:
        for source, inference_path, _frame_number in pool.imap_unordered(_extract_video_frame_task, tasks):
            if stop.is_set():
                break
            extracted_paths[source] = inference_path
            extracted = len(extracted_paths)
            elapsed = monotonic() - extraction_started
            eta_seconds = round(elapsed / extracted * (len(videos) - extracted))
            eta = f"{eta_seconds // 60:02d}:{eta_seconds % 60:02d}"
            percentage = round(extracted / len(videos) * 100)
            emit("frame_progress", (extracted, len(videos), source.name, percentage, eta))

    if stop.is_set():
        shutil.rmtree(grabs)
        return {}
    return extracted_paths


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

    videos = [path for path in media if path.suffix.lower() in VIDEO_EXTENSIONS]
    grabs = TEMP_DIR / "video-frames"
    video_frames = extract_video_frames(videos, grabs, options, stop, emit) if videos else {}
    if stop.is_set():
        return []

    sources = []
    media_types = []
    inference_paths = []
    for source in media:
        if stop.is_set():
            break
        media_type = "video" if source.suffix.lower() in VIDEO_EXTENSIONS else "image"
        inference_path = video_frames[source] if media_type == "video" else source

        sources.append(source)
        media_types.append(media_type)
        inference_paths.append(str(inference_path))

    if not inference_paths:
        if videos:
            shutil.rmtree(grabs)
        return []

    from transformers.pipelines.pt_utils import KeyDataset

    dataset = KeyDataset([{"image": path} for path in inference_paths], "image")
    emit("total", len(inference_paths))
    emit("status", f"Loading {MODEL_ID}")
    classifier = create_classifier(options.device)
    emit("device", str(classifier.device))
    outputs = classifier(dataset, batch_size=8, top_k=len(MODEL_LABELS))

    results = []
    classification_started = monotonic()
    for index, (source, media_type, output) in enumerate(zip(sources, media_types, outputs), 1):
        if stop.is_set():
            break
        predictions = tuple((str(item["label"]), float(item["score"])) for item in output)
        result = MediaResult(source, media_type, predictions[0][0], predictions[0][1], predictions)
        results.append(result)
        emit("result", result)
        elapsed = monotonic() - classification_started
        eta_seconds = round(elapsed / index * (len(sources) - index))
        eta = f"{eta_seconds // 60:02d}:{eta_seconds % 60:02d}"
        percentage = round(index / len(sources) * 100)
        emit("progress", (index, len(sources), source.name, percentage, eta))

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


def _copy_media(result: MediaResult) -> MediaResult:
    destination = result.destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    with result.source.open("rb") as source_stream, destination.open("xb") as destination_stream:
        shutil.copyfileobj(source_stream, destination_stream)
        destination_stream.flush()
        os.fsync(destination_stream.fileno())
    shutil.copystat(result.source, destination)
    return result


def move_media(results: list[MediaResult], journal: Path, stop: Event, emit: Emit, workers: int = 12) -> int:
    journal.parent.mkdir(parents=True, exist_ok=True)
    moved = 0
    move_started = monotonic()
    with journal.open("x", newline="", encoding="utf-8") as log:
        writer = csv.writer(log)
        writer.writerow(["source", "destination", "label", "confidence"])
        log.flush()
        batches = (results[start : start + workers] for start in range(0, len(results), workers))
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="media-move") as executor:
            for batch in batches:
                if stop.is_set():
                    break
                for result in executor.map(_copy_media, batch):
                    result.source.unlink()
                    writer.writerow([result.source, result.destination, result.label, result.confidence])
                    log.flush()
                    os.fsync(log.fileno())
                    moved += 1
                    emit("moved", result)
                    elapsed = monotonic() - move_started
                    eta_seconds = round(elapsed / moved * (len(results) - moved))
                    eta = f"{eta_seconds // 60:02d}:{eta_seconds % 60:02d}"
                    percentage = round(moved / len(results) * 100)
                    emit("move_progress", (moved, len(results), result.source.name, percentage, eta))
    return moved
