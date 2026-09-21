"""Transformers-compatible wrapper for the published custom HairClassifier checkpoint."""

import json
from pathlib import Path

import timm
import torch.nn as nn
from huggingface_hub import hf_hub_download
from safetensors.torch import load_file
from transformers import AutoImageProcessor, PreTrainedModel, PretrainedConfig
from transformers.modeling_outputs import ImageClassifierOutput

from app.config import MODEL_ID, MODEL_LABELS

WEIGHTS_FILENAME = "hair_color-convnext_tiny.fb_in22k.safetensors"
CONFIG_FILENAME = "config.json"


class HairColorConfig(PretrainedConfig):
    model_type = "hair-color-convnext"

    def __init__(self, architecture: str = "convnext_tiny", num_classes: int = 7, **kwargs) -> None:
        super().__init__(**kwargs)
        self.architecture = architecture
        self.num_classes = num_classes
        self.num_labels = num_classes
        self.problem_type = "single_label_classification"


class TimmWrapperForImageClassification(PreTrainedModel):
    config_class = HairColorConfig
    main_input_name = "pixel_values"

    def __init__(self, config: HairColorConfig) -> None:
        super().__init__(config)
        self.model = timm.create_model("convnext_tiny.fb_in22k", pretrained=False, num_classes=config.num_classes)
        in_features = self.model.head.fc.in_features
        self.model.head.fc = nn.Sequential(nn.Dropout(0.15), nn.Linear(in_features, config.num_classes))

    def forward(self, pixel_values, **_kwargs) -> ImageClassifierOutput:
        return ImageClassifierOutput(logits=self.model(pixel_values))


def load_pipeline_components():
    config_path = hf_hub_download(MODEL_ID, CONFIG_FILENAME)
    config = HairColorConfig(**json.loads(Path(config_path).read_text(encoding="utf-8")))
    config.id2label = {index: label for index, label in enumerate(MODEL_LABELS)}
    config.label2id = {label: index for index, label in config.id2label.items()}
    model = TimmWrapperForImageClassification(config)
    weights_path = hf_hub_download(MODEL_ID, WEIGHTS_FILENAME)
    model.load_state_dict(load_file(weights_path))
    model.eval()
    image_processor = AutoImageProcessor.from_pretrained(MODEL_ID)
    return model, image_processor
