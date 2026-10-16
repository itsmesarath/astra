"""Versioned saving and loading for linear model checkpoints."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch

from ai_trader.models.linear_classifier import (
    DIRECTION_CLASSES,
    LinearDirectionClassifier,
    decode_directions,
)
from ai_trader.training.standardize import Standardizer

CHECKPOINT_SCHEMA_VERSION = 1
MODEL_FILENAME = "model.pt"
SCALER_FILENAME = "scaler.npz"
METADATA_FILENAME = "metadata.json"


@dataclass(frozen=True, slots=True)
class LoadedLinearCheckpoint:
    """Loaded model, scaler, schema, and metadata."""

    model: LinearDirectionClassifier
    standardizer: Standardizer
    feature_names: tuple[str, ...]
    metadata: dict[str, object]

    def predict_probabilities(
        self,
        features: np.ndarray,
    ) -> np.ndarray:
        """Return DOWN, NEUTRAL, and UP probabilities."""
        standardized = self.standardizer.transform(features)
        tensor = torch.from_numpy(standardized.astype(np.float32, copy=False))

        self.model.eval()
        with torch.no_grad():
            logits = self.model(tensor)
            probabilities = torch.softmax(
                logits,
                dim=1,
            )

        return probabilities.cpu().numpy()

    def predict(self, features: np.ndarray) -> np.ndarray:
        """Return decoded direction predictions."""
        probabilities = self.predict_probabilities(features)
        class_indices = probabilities.argmax(axis=1)
        return decode_directions(class_indices)


def validate_checkpoint_components(
    model: LinearDirectionClassifier,
    standardizer: Standardizer,
    feature_names: tuple[str, ...],
) -> None:
    """Verify that model, scaler, and schema dimensions agree."""
    if not feature_names:
        raise ValueError("Checkpoint feature schema cannot be empty.")
    if len(set(feature_names)) != len(feature_names):
        raise ValueError("Checkpoint feature names must be unique.")
    if any(not name for name in feature_names):
        raise ValueError("Checkpoint feature names cannot be empty.")
    if model.input_features != len(feature_names):
        raise ValueError("Model input count does not match feature schema.")
    if standardizer.columns != len(feature_names):
        raise ValueError("Standardizer column count does not match feature schema.")


def save_linear_checkpoint(
    directory: Path,
    model: LinearDirectionClassifier,
    standardizer: Standardizer,
    *,
    feature_names: tuple[str, ...],
    training_metadata: dict[str, object],
) -> Path:
    """Atomically save a versioned linear checkpoint directory."""
    validate_checkpoint_components(
        model,
        standardizer,
        feature_names,
    )

    if directory.exists():
        raise FileExistsError(f"Checkpoint path already exists: {directory}")

    temporary_directory = directory.with_name(f"{directory.name}.tmp")
    if temporary_directory.exists():
        raise FileExistsError(f"Temporary checkpoint path already exists: {temporary_directory}")

    directory.parent.mkdir(parents=True, exist_ok=True)
    temporary_directory.mkdir()

    cpu_state = {name: value.detach().cpu().clone() for name, value in model.state_dict().items()}
    torch.save(
        cpu_state,
        temporary_directory / MODEL_FILENAME,
    )

    np.savez(
        temporary_directory / SCALER_FILENAME,
        means=standardizer.means,
        scales=standardizer.scales,
    )

    metadata: dict[str, object] = {
        "schema_version": CHECKPOINT_SCHEMA_VERSION,
        "model_type": "linear_direction_classifier",
        "input_features": model.input_features,
        "feature_names": list(feature_names),
        "direction_classes": list(DIRECTION_CLASSES),
        "training": training_metadata,
    }

    with (temporary_directory / METADATA_FILENAME).open(
        "w",
        encoding="utf-8",
        newline="\n",
    ) as output_file:
        json.dump(metadata, output_file, indent=2)
        output_file.write("\n")

    temporary_directory.replace(directory)
    return directory


def load_linear_checkpoint(
    directory: Path,
) -> LoadedLinearCheckpoint:
    """Load and validate a linear checkpoint on the CPU."""
    metadata_path = directory / METADATA_FILENAME
    model_path = directory / MODEL_FILENAME
    scaler_path = directory / SCALER_FILENAME

    with metadata_path.open(encoding="utf-8") as input_file:
        metadata = json.load(input_file)

    if metadata.get("schema_version") != CHECKPOINT_SCHEMA_VERSION:
        raise ValueError("Checkpoint has an unsupported schema version.")
    if metadata.get("model_type") != ("linear_direction_classifier"):
        raise ValueError("Checkpoint has an unsupported model type.")

    raw_feature_names = metadata.get("feature_names")
    if (
        not isinstance(raw_feature_names, list)
        or not raw_feature_names
        or any(not isinstance(name, str) or not name for name in raw_feature_names)
    ):
        raise ValueError("Checkpoint contains an invalid feature schema.")

    feature_names = tuple(raw_feature_names)
    input_features = metadata.get("input_features")

    if not isinstance(input_features, int) or input_features != len(feature_names):
        raise ValueError("Checkpoint input count does not match feature schema.")

    if metadata.get("direction_classes") != list(DIRECTION_CLASSES):
        raise ValueError("Checkpoint direction-class mapping is incorrect.")

    with np.load(
        scaler_path,
        allow_pickle=False,
    ) as scaler_data:
        means = np.asarray(
            scaler_data["means"],
            dtype=np.float64,
        )
        scales = np.asarray(
            scaler_data["scales"],
            dtype=np.float64,
        )

    if means.shape != (input_features,):
        raise ValueError("Checkpoint scaler means have an invalid shape.")
    if scales.shape != (input_features,):
        raise ValueError("Checkpoint scaler scales have an invalid shape.")
    if not np.isfinite(means).all():
        raise ValueError("Checkpoint scaler means must be finite.")
    if not np.isfinite(scales).all() or np.any(scales <= 0):
        raise ValueError("Checkpoint scaler scales must be finite and positive.")

    standardizer = Standardizer(
        means=means,
        scales=scales,
    )
    model = LinearDirectionClassifier(input_features=input_features)

    state_dict = torch.load(
        model_path,
        map_location="cpu",
        weights_only=True,
    )
    model.load_state_dict(state_dict)
    model.eval()

    validate_checkpoint_components(
        model,
        standardizer,
        feature_names,
    )

    return LoadedLinearCheckpoint(
        model=model,
        standardizer=standardizer,
        feature_names=feature_names,
        metadata=metadata,
    )
