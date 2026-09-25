import csv
from pathlib import Path
from threading import Event
import cv2
import numpy as np
import pytest
from PIL import Image

from app import media
from app.media import (
    MediaResult,
    ScanOptions,
    discover_media,
    extract_video_frame,
    extract_video_frames,
    move_media,
    normalize_predictions,
    plan_moves,
    scan_media,
)


def test_discover_media_accepts_folder_or_single_file(tmp_path: Path):
    image = tmp_path / "portrait.jpg"
    video = tmp_path / "clip.mp4"
    image.touch()
    video.touch()
    (tmp_path / "notes.txt").touch()
    assert discover_media(tmp_path, include_videos=True) == [video, image]
    assert discover_media(tmp_path, include_videos=False) == [image]
    assert discover_media(video, include_videos=True) == [video]


def test_spectra_style_video_frame_extraction(tmp_path: Path):
    video_path = tmp_path / "colors.avi"
    writer = cv2.VideoWriter(str(video_path), cv2.VideoWriter_fourcc(*"MJPG"), 10, (32, 32))
    for value in (0, 80, 160, 240):
        writer.write(np.full((32, 32, 3), value, dtype=np.uint8))
    writer.release()
    image_path = tmp_path / "frame.png"
    assert extract_video_frame(video_path, image_path, 100, 1) == 3
    assert np.asarray(Image.open(image_path)).mean() == pytest.approx(240, abs=3)


def test_video_worker_setting_controls_process_pool_size(tmp_path: Path, monkeypatch):
    videos = [tmp_path / f"clip-{index}.mp4" for index in range(3)]
    worker_counts = []

    class Pool:
        def __init__(self, processes):
            worker_counts.append(processes)

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def imap_unordered(self, _function, tasks):
            for source, image_path, _frame_percentage, _png_compress_level in tasks:
                image_path.touch()
                yield source, image_path, 0

    class ProcessContext:
        def Pool(self, processes):
            return Pool(processes)

    monkeypatch.setattr(media.multiprocessing, "get_context", lambda method: ProcessContext())
    events = []
    grabs = tmp_path / "frames"
    extracted = extract_video_frames(
        videos,
        grabs,
        ScanOptions(tmp_path, video_workers=2),
        Event(),
        lambda *event: events.append(event),
    )

    assert worker_counts == [2]
    assert extracted == {video: grabs / f"{video.name}.png" for video in videos}
    assert events[-1] == ("frame_progress", (3, 3, "clip-2.mp4", 100, "00:00"))


def test_pipeline_predictions_are_assigned_to_original_video(tmp_path: Path, monkeypatch):
    app_temp = tmp_path / "app-state" / "temp"
    monkeypatch.setattr(media, "TEMP_DIR", app_temp)
    video_path = tmp_path / "clip.avi"
    writer = cv2.VideoWriter(str(video_path), cv2.VideoWriter_fourcc(*"MJPG"), 10, (16, 16))
    writer.write(np.zeros((16, 16, 3), dtype=np.uint8))
    writer.release()
    inputs = []

    class FakeClassifier:
        device = "cpu"
        labels = ("black", "brown")

        def predict(self, paths, batch_size):
            inputs.extend(Path(path) for path in paths)
            assert batch_size == 8
            return iter([[{"label": "black", "score": 0.9}, {"label": "brown", "score": 0.1}]])

    fake = FakeClassifier()
    monkeypatch.setattr(media, "create_classifier", lambda _model_id, _device: fake)
    events = []
    result = scan_media(ScanOptions(tmp_path), Event(), lambda *event: events.append(event))[0]
    assert result.source == video_path
    assert result.media_type == "video"
    assert result.label == "black"
    assert inputs[0].parent == app_temp / "video-frames"
    assert not inputs[0].parent.exists()
    assert not (tmp_path / ".hair_class_organizer_video_grabs").exists()
    assert ("device", "cpu") in events
    assert ("labels", ("black", "brown")) in events
    assert ("status", "Scanning media") in events
    assert ("frame_progress", (1, 1, "clip.avi", 100, "00:00")) in events
    assert ("progress", (1, 1, "clip.avi", 100, "00:00")) in events


def test_detection_predictions_keep_the_highest_score_per_label():
    output = [
        {"label": "brown", "score": 0.7, "box": {}},
        {"label": "black", "score": 0.8, "box": {}},
        {"label": "brown", "score": 0.9, "box": {}},
    ]
    assert normalize_predictions(output) == (("brown", 0.9), ("black", 0.8))


def test_planned_moves_use_labels_confidence_and_do_not_overwrite(tmp_path: Path):
    source = tmp_path / "photo.jpg"
    source.write_bytes(b"original")
    result = MediaResult(source, "image", "silver", 0.91, (("silver", 0.91),))
    assert plan_moves([result], tmp_path, {"silver"}, 0.92) == []
    planned = plan_moves([result], tmp_path, {"silver"}, 0.9)
    destination = tmp_path / "silver" / "photo.jpg"
    assert planned[0].destination == destination
    journal = tmp_path / "moves.csv"
    assert move_media(planned, journal, Event(), lambda *_: None) == 1
    assert destination.read_bytes() == b"original"
    assert not source.exists()
    with journal.open(newline="", encoding="utf-8") as stream:
        assert next(csv.DictReader(stream))["label"] == "silver"
    source.write_bytes(b"new")
    with pytest.raises(FileExistsError):
        move_media(planned, tmp_path / "moves-2.csv", Event(), lambda *_: None)
    assert source.read_bytes() == b"new"
    assert destination.read_bytes() == b"original"


def test_move_worker_setting_controls_thread_pool_size(tmp_path: Path, monkeypatch):
    worker_counts = []

    class Executor:
        def __init__(self, max_workers, thread_name_prefix):
            worker_counts.append(max_workers)

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def map(self, function, results):
            return map(function, results)

    monkeypatch.setattr(media, "ThreadPoolExecutor", Executor)
    results = []
    for index in range(3):
        source = tmp_path / f"photo-{index}.jpg"
        source.write_bytes(b"image")
        results.append(
            MediaResult(
                source,
                "image",
                "black",
                0.9,
                (("black", 0.9),),
                tmp_path / "black" / source.name,
            )
        )

    events = []
    assert move_media(results, tmp_path / "moves.csv", Event(), lambda *event: events.append(event), workers=2) == 3
    assert worker_counts == [2]
    assert all(result.destination.read_bytes() == b"image" for result in results)
    assert events[-1] == ("move_progress", (3, 3, "photo-2.jpg", 100, "00:00"))
