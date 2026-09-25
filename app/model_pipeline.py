"""Generic Hugging Face model pipeline selection and prediction normalization."""

from dataclasses import dataclass
from typing import Callable, Iterable

from huggingface_hub import snapshot_download
from transformers import pipeline

from app.models import timm, yolo

Predict = Callable[[object, Iterable[str], int], Iterable[list[dict[str, object]]]]


@dataclass(frozen=True, slots=True)
class ModelPipeline:
    engine: object
    predict_with_engine: Predict

    @property
    def device(self):
        return self.engine.device

    @property
    def labels(self) -> tuple[str, ...]:
        labels = self.engine.model.config.id2label
        return tuple(str(label) for _, label in sorted(labels.items(), key=lambda item: int(item[0])))

    def predict(self, inputs: Iterable[str], batch_size: int) -> Iterable[list[dict[str, object]]]:
        return self.predict_with_engine(self.engine, (item for item in inputs), batch_size)


def _predict_image_classification(engine, inputs: Iterable[str], batch_size: int):
    return engine(inputs, batch_size=batch_size, top_k=len(engine.model.config.id2label))


def _predict(engine, inputs: Iterable[str], batch_size: int):
    if engine.task == "image-classification":
        return _predict_image_classification(engine, inputs, batch_size)
    return engine(inputs, batch_size=batch_size)


def create_model_pipeline(model_id: str, device: str) -> ModelPipeline:
    if timm.supports(model_id):
        engine = timm.create_pipeline(model_id, device)
    else:
        arguments = {"model": model_id}
        if device != "auto":
            arguments["device"] = device
        engine = pipeline(**arguments)
    predict_with_engine = yolo.predict if yolo.supports(engine) else _predict
    return ModelPipeline(engine, predict_with_engine)


def download_model(model_id: str) -> str:
    return snapshot_download(model_id)
