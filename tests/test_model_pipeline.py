from types import SimpleNamespace
from types import GeneratorType

from app import model_pipeline


class FakeEngine:
    device = "cpu"

    def __init__(self, model_type: str, task: str = "image-classification") -> None:
        self.model = SimpleNamespace(config=SimpleNamespace(model_type=model_type, id2label={0: "black", 1: "brown"}))
        self.task = task
        self.calls = []

    def __call__(self, inputs, **kwargs):
        self.calls.append((inputs, kwargs))
        return []


def test_generic_repository_uses_vanilla_transformers_pipeline(monkeypatch):
    engine = FakeEngine("vit")
    calls = []
    monkeypatch.setattr(model_pipeline, "pipeline", lambda **kwargs: calls.append(kwargs) or engine)

    loaded = model_pipeline.create_model_pipeline("owner/model", "cuda:0")
    loaded.predict(["image.jpg"], batch_size=8)

    assert calls == [{"model": "owner/model", "device": "cuda:0"}]
    assert loaded.labels == ("black", "brown")
    inputs, arguments = engine.calls[0]
    assert isinstance(inputs, GeneratorType)
    assert list(inputs) == ["image.jpg"]
    assert arguments == {"batch_size": 8, "top_k": 2}


def test_yolos_repository_uses_object_detection_inference(monkeypatch):
    engine = FakeEngine("yolos", "object-detection")
    monkeypatch.setattr(model_pipeline, "pipeline", lambda **_kwargs: engine)

    loaded = model_pipeline.create_model_pipeline("owner/yolos", "auto")
    loaded.predict(["image.jpg"], batch_size=4)

    inputs, arguments = engine.calls[0]
    assert isinstance(inputs, GeneratorType)
    assert list(inputs) == ["image.jpg"]
    assert arguments == {"batch_size": 1, "threshold": 0.0}


def test_download_model_downloads_the_repository(monkeypatch):
    calls = []
    monkeypatch.setattr(model_pipeline, "snapshot_download", lambda model_id: calls.append(model_id) or "cache/model")

    assert model_pipeline.download_model("owner/model") == "cache/model"
    assert calls == ["owner/model"]
