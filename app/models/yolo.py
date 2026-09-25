"""Transformers inference behavior for YOLOS object-detection models."""

from typing import Iterable


def supports(engine) -> bool:
    return engine.model.config.model_type == "yolos"


def predict(engine, inputs: Iterable[str], _batch_size: int):
    return engine(inputs, batch_size=1, threshold=0.0)
