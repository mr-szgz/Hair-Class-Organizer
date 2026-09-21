import csv
from pathlib import Path
from threading import Event
import cv2
import numpy as np
import pytest
from PIL import Image

from app import media
from app.media import MediaResult, ScanOptions, discover_media, extract_video_frame, move_media, plan_moves, scan_media


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


def test_pipeline_predictions_are_assigned_to_original_video(tmp_path: Path, monkeypatch):
    video_path = tmp_path / "clip.avi"
    writer = cv2.VideoWriter(str(video_path), cv2.VideoWriter_fourcc(*"MJPG"), 10, (16, 16))
    writer.write(np.zeros((16, 16, 3), dtype=np.uint8))
    writer.release()
    inputs = []

    def classifier(path, top_k):
        inputs.append(Path(path))
        assert top_k == 7
        return [{"label": "black", "score": 0.9}, {"label": "brown", "score": 0.1}]

    class FakeClassifier:
        device = "cpu"

        def __call__(self, path, top_k):
            return classifier(path, top_k)

    fake = FakeClassifier()
    monkeypatch.setattr(media, "create_classifier", lambda _device: fake)
    events = []
    result = scan_media(ScanOptions(tmp_path), Event(), lambda *event: events.append(event))[0]
    assert result.source == video_path
    assert result.media_type == "video"
    assert result.label == "black"
    assert inputs[0].parent.name == ".hair_class_organizer_video_grabs"
    assert not inputs[0].parent.exists()
    assert ("device", "cpu") in events


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
