"""Train a bounded, offline 6E direction baseline from pinned MBO features.

The cohort and session split are fixed before reading labels for fitting. The
reserved test labels are not used until the model parameters have been frozen. This
research artifact has no paper or live execution integration.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path

import numpy as np

from ai_trader.training.metrics import CLASS_LABELS, evaluate_classification

FEATURE_NAMES = (
    "spread_ticks",
    "top_bid_qty",
    "top_ask_qty",
    "imbalance",
    "cvd_rolling",
    "trade_count_rolling",
    "cancel_imbalance_rolling",
    "replenishment_proxy",
)
FIRST_SESSION = date(2025, 3, 27)
LAST_SESSION = date(2025, 4, 15)
SESSION_COUNTS = (8, 3, 3)
CONTRACT = "6EM5"
MAX_ROWS = 100_000
MAX_FILE_BYTES = 256 * 1024 * 1024
MAX_MANIFEST_BYTES = 2 * 1024 * 1024
MAX_ROW_BYTES = 32 * 1024
MIN_ROWS_PER_SESSION = 180
MAX_ROWS_PER_SESSION = 240
SECOND_NS = 1_000_000_000
EPOCHS = 100
LEARNING_RATE = 0.05
L2 = 0.01
STANDARDIZED_CLIP = 10.0
MODEL_VERSION = "6e_numpy_softmax_v1"
CONFIG_SHA256 = "927607008b24877f24c961da1aafc1bc151e0d4b8253a1627bd51699e48fb144"
SOURCE_INTAKE_SHA256 = "de12f9833b951781f27b5ea46d2c6dc2302c422e1080bfc48914b2dc8a82b27a"
SOURCE_INTAKE_REPORT = "data/processed/databento_6e_18_month_intake_20261001_2.json"
ROW_KEYS = frozenset(
    (
        "source_session",
        "decision_ts_ns",
        "label_end_ts_ns",
        "contract",
        "label",
        *FEATURE_NAMES,
    )
)


def _expected_sessions() -> tuple[str, ...]:
    current = FIRST_SESSION
    result = []
    while current <= LAST_SESSION:
        if current.weekday() < 5:
            result.append(current.isoformat())
        current += timedelta(days=1)
    return tuple(result)


EXPECTED_SESSIONS = _expected_sessions()


def _object_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}.")
        result[key] = value
    return result


def _bad_constant(value):
    raise ValueError(f"Non-finite JSON constant: {value}.")


def _loads(raw: bytes) -> dict:
    value = json.loads(raw, object_pairs_hook=_object_pairs, parse_constant=_bad_constant)
    if type(value) is not dict:
        raise ValueError("Expected a JSON object.")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _manifest(path: Path, rows_path: Path) -> tuple[dict, str]:
    if path.stat().st_size > MAX_MANIFEST_BYTES:
        raise ValueError("Feature manifest exceeds the size limit.")
    raw = path.read_bytes()
    manifest = _loads(raw)
    expected = {
        "schema_version": 1,
        "artifact_type": "databento_6e_mbo_features_v1",
        "feature_names": list(FEATURE_NAMES),
        "contract": CONTRACT,
        "quality_passed": True,
        "held_dates": [],
        "first_session": FIRST_SESSION.isoformat(),
        "last_session": LAST_SESSION.isoformat(),
        "sessions": list(EXPECTED_SESSIONS),
        "config_sha256": CONFIG_SHA256,
    }
    for key, value in expected.items():
        if manifest.get(key) != value or type(manifest.get(key)) is not type(value):
            raise ValueError(f"Feature manifest has an unexpected {key!r}.")
    if (
        type(manifest.get("rows")) is not int
        or not 1 <= manifest["rows"] <= MAX_ROWS
        or type(manifest.get("rows_sha256")) is not str
        or not re.fullmatch(r"[0-9a-f]{64}", manifest["rows_sha256"])
    ):
        raise ValueError("Feature manifest has invalid row count or digest.")
    source = manifest.get("source")
    if type(source) is not dict or any(
        source.get(key) != value or type(source.get(key)) is not str
        for key, value in (
            ("intake_report", SOURCE_INTAKE_REPORT),
            ("intake_sha256", SOURCE_INTAKE_SHA256),
            ("experiment_config_sha256", CONFIG_SHA256),
        )
    ):
        raise ValueError("Feature manifest differs from the frozen source provenance.")
    if type(source.get("members")) is not list or not source["members"]:
        raise ValueError("Feature manifest lacks source member provenance.")
    if rows_path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError("Feature dataset exceeds the size limit.")
    if _sha256(rows_path) != manifest["rows_sha256"]:
        raise ValueError("Feature rows differ from the manifest digest.")
    return manifest, hashlib.sha256(raw).hexdigest()


def _config(path: Path) -> None:
    if path.stat().st_size > MAX_MANIFEST_BYTES or _sha256(path) != CONFIG_SHA256:
        raise ValueError("Frozen training config differs from the approved digest.")
    intake_path = path.resolve().parent.parent / SOURCE_INTAKE_REPORT
    if _sha256(intake_path) != SOURCE_INTAKE_SHA256:
        raise ValueError("Source intake report differs from the frozen digest.")


@dataclass(frozen=True, slots=True)
class RowMetadata:
    session: str
    decision_ts_ns: int
    label_end_ts_ns: int


def _row_objects(path: Path):
    with path.open("rb") as source:
        for line_number, raw in enumerate(source, start=1):
            if len(raw) > MAX_ROW_BYTES:
                raise ValueError(f"Feature row {line_number} exceeds the size limit.")
            if not raw.endswith(b"\n"):
                raise ValueError(f"Feature row {line_number} lacks a newline terminator.")
            try:
                row = _loads(raw)
            except (UnicodeError, ValueError) as error:
                raise ValueError(f"Invalid JSONL row {line_number}: {error}") from error
            if set(row) != ROW_KEYS:
                raise ValueError(f"Feature row {line_number} has an unexpected schema.")
            yield line_number, row


def _timestamp(value, name: str) -> int:
    if type(value) is not int or value <= 0:
        raise ValueError(f"{name} must be a positive integer nanosecond timestamp.")
    return value


def _scan_metadata(path: Path, expected_rows: int) -> tuple[RowMetadata, ...]:
    metadata = []
    current_session = None
    previous_time = 0
    completed = set()
    decision_windows = {
        session: (
            int(datetime.combine(date.fromisoformat(session), time.min, UTC).timestamp())
            * SECOND_NS
            + 12 * 3600 * SECOND_NS
        )
        for session in EXPECTED_SESSIONS
    }
    for line_number, row in _row_objects(path):
        session = row["source_session"]
        if type(session) is not str or session not in EXPECTED_SESSIONS:
            raise ValueError(f"Feature row {line_number} has an unexpected session.")
        if row["contract"] != CONTRACT or type(row["contract"]) is not str:
            raise ValueError(f"Feature row {line_number} has an unexpected contract.")
        decision = _timestamp(row["decision_ts_ns"], "decision_ts_ns")
        label_end = _timestamp(row["label_end_ts_ns"], "label_end_ts_ns")
        window_start = decision_windows[session]
        window_end = window_start + 4 * 3600 * SECOND_NS
        if not window_start <= decision < window_end:
            raise ValueError(f"Feature row {line_number} falls outside the fixed UTC window.")
        if not decision + 60 * SECOND_NS <= label_end < window_end:
            raise ValueError(f"Feature row {line_number} has an invalid 60s label endpoint.")
        if session != current_session:
            if session in completed:
                raise ValueError("A source session reappears after another session.")
            if current_session is not None:
                completed.add(current_session)
                if session <= current_session:
                    raise ValueError("Source sessions are not chronological.")
            current_session = session
        if decision <= previous_time:
            raise ValueError("Feature timestamps must be strictly increasing.")
        previous_time = decision
        metadata.append(RowMetadata(session, decision, label_end))
        if len(metadata) > MAX_ROWS:
            raise ValueError("Feature dataset exceeds the row limit.")
    if len(metadata) != expected_rows:
        raise ValueError("Feature row count differs from the manifest.")
    sessions = tuple(dict.fromkeys(item.session for item in metadata))
    if sessions != EXPECTED_SESSIONS:
        raise ValueError("Feature dataset does not contain the complete frozen cohort.")
    first_by_session = {}
    for item in metadata:
        first_by_session.setdefault(item.session, item.decision_ts_ns)
    session_positions = {session: index for index, session in enumerate(EXPECTED_SESSIONS)}
    for item in metadata:
        index = session_positions[item.session]
        if index < len(EXPECTED_SESSIONS) - 1:
            next_start = first_by_session[EXPECTED_SESSIONS[index + 1]]
            if item.label_end_ts_ns >= next_start:
                raise ValueError("A label endpoint crosses its source session boundary.")
    return tuple(metadata)


def _quality(manifest: dict, metadata: tuple[RowMetadata, ...]) -> None:
    quality = manifest.get("quality")
    counts = quality.get("rows_per_session") if type(quality) is dict else None
    if type(counts) is not dict or set(counts) != set(EXPECTED_SESSIONS):
        raise ValueError("Feature manifest lacks complete per-session quality counts.")
    if any(
        type(counts[session]) is not int
        or not MIN_ROWS_PER_SESSION <= counts[session] <= MAX_ROWS_PER_SESSION
        for session in EXPECTED_SESSIONS
    ):
        raise ValueError("At least one source session fails the labeled-row quality floor.")
    observed = Counter(item.session for item in metadata)
    if any(observed[session] != counts[session] for session in EXPECTED_SESSIONS):
        raise ValueError("Per-session quality counts differ from the actual feature rows.")


def _section(index: int) -> str:
    train, validation, _ = SESSION_COUNTS
    if index < train:
        return "train"
    if index < train + validation:
        return "validation"
    return "test"


def _numeric_feature(value, name: str) -> float:
    if type(value) not in (int, float):
        raise ValueError(f"Feature {name!r} must be numeric.")
    result = float(value)
    if not math.isfinite(result) or abs(result) > 1e12:
        raise ValueError(f"Feature {name!r} exceeds numerical bounds.")
    return result


def _load_section(path: Path, metadata: tuple[RowMetadata, ...], section: str):
    features, targets, sessions = [], [], []
    for index, (line_number, row) in enumerate(_row_objects(path)):
        if index >= len(metadata):
            raise ValueError("Feature rows changed after the initial metadata scan.")
        if (
            row["source_session"] != metadata[index].session
            or row["decision_ts_ns"] != metadata[index].decision_ts_ns
            or row["label_end_ts_ns"] != metadata[index].label_end_ts_ns
        ):
            raise ValueError("Feature rows changed after the initial metadata scan.")
        if _section(EXPECTED_SESSIONS.index(metadata[index].session)) != section:
            continue
        label = row["label"]
        if type(label) is not int or label not in CLASS_LABELS:
            raise ValueError(f"Feature row {line_number} has an invalid label.")
        features.append([_numeric_feature(row[name], name) for name in FEATURE_NAMES])
        targets.append(label)
        sessions.append(metadata[index].session)
    if line_number != len(metadata):
        raise ValueError("Feature rows changed after the initial metadata scan.")
    if not features:
        raise ValueError(f"The {section} partition has no rows.")
    return (
        np.asarray(features, dtype=np.float64),
        np.asarray(targets, dtype=np.int64),
        tuple(sessions),
    )


def _softmax(scores: np.ndarray) -> np.ndarray:
    centered = scores - scores.max(axis=1, keepdims=True)
    exp = np.exp(centered)
    return exp / exp.sum(axis=1, keepdims=True)


@dataclass(frozen=True, slots=True)
class FrozenModel:
    means: tuple[float, ...]
    scales: tuple[float, ...]
    weights: tuple[tuple[float, ...], ...]
    bias: tuple[float, float, float]

    def predict(self, features: np.ndarray) -> np.ndarray:
        x = np.clip(
            (features - np.asarray(self.means)) / np.asarray(self.scales),
            -STANDARDIZED_CLIP,
            STANDARDIZED_CLIP,
        )
        return _softmax(x @ np.asarray(self.weights) + np.asarray(self.bias))


def _fit(features: np.ndarray, targets: np.ndarray) -> FrozenModel:
    encoded = targets + 1
    if len(set(targets.tolist())) < 2:
        raise ValueError("At least two training classes are required.")
    means = features.mean(axis=0)
    scales = features.std(axis=0)
    scales[scales == 0] = 1.0
    x = np.clip((features - means) / scales, -STANDARDIZED_CLIP, STANDARDIZED_CLIP)
    weights = np.zeros((len(FEATURE_NAMES), 3), dtype=np.float64)
    bias = np.zeros(3, dtype=np.float64)
    for _ in range(EPOCHS):
        error = _softmax(x @ weights + bias)
        error[np.arange(len(encoded)), encoded] -= 1.0
        weights -= LEARNING_RATE * (x.T @ error / len(encoded) + L2 * weights)
        bias -= LEARNING_RATE * error.mean(axis=0)
    if not np.isfinite(weights).all() or not np.isfinite(bias).all():
        raise ValueError("Model fitting produced nonfinite parameters.")
    return FrozenModel(
        tuple(means.tolist()),
        tuple(scales.tolist()),
        tuple(tuple(row) for row in weights.tolist()),
        tuple(bias.tolist()),
    )


def _scores(targets: np.ndarray, probabilities: np.ndarray) -> dict:
    if not np.isfinite(probabilities).all() or not np.allclose(
        probabilities.sum(axis=1), 1, rtol=0, atol=1e-12
    ):
        raise ValueError("Invalid prediction probabilities.")
    encoded = targets + 1
    predicted = probabilities.argmax(axis=1) - 1
    classification = evaluate_classification(targets.tolist(), predicted.tolist())
    return {
        **asdict(classification),
        "log_loss": float(
            -np.log(np.maximum(probabilities[np.arange(len(encoded)), encoded], 1e-15)).mean()
        ),
        "brier_score": float(((probabilities - np.eye(3)[encoded]) ** 2).sum(axis=1).mean()),
    }


def _evaluate(model, train_targets, features, targets, sessions) -> dict:
    counts = np.bincount(train_targets + 1, minlength=3)
    prior = (counts + 1) / (counts.sum() + 3)
    predicted = {
        "model": model.predict(features),
        "train_majority": np.tile(np.eye(3)[counts.argmax()], (len(targets), 1)),
        "train_laplace_prior": np.tile(prior, (len(targets), 1)),
    }
    unique = tuple(dict.fromkeys(sessions))
    return {
        "rows": len(targets),
        "sessions": list(unique),
        "aggregate": {name: _scores(targets, values) for name, values in predicted.items()},
        "by_session": [
            {
                "source_session": session,
                "rows": sessions.count(session),
                "scores": {
                    name: _scores(targets[mask], values[mask]) for name, values in predicted.items()
                },
            }
            for session in unique
            for mask in [np.asarray([value == session for value in sessions])]
        ],
    }


def train_6e_baseline(
    *, rows_path: Path, manifest_path: Path, config_path: Path, output_path: Path
) -> dict:
    """Produce one immutable data-only research result from the fixed 14-session cohort."""
    rows_path, manifest_path, config_path, output_path = map(
        Path, (rows_path, manifest_path, config_path, output_path)
    )
    if output_path.exists():
        raise FileExistsError(output_path)
    _config(config_path)
    manifest, manifest_sha256 = _manifest(manifest_path, rows_path)
    metadata = _scan_metadata(rows_path, manifest["rows"])
    _quality(manifest, metadata)
    train_x, train_y, train_sessions = _load_section(rows_path, metadata, "train")
    val_x, val_y, val_sessions = _load_section(rows_path, metadata, "validation")
    if _sha256(rows_path) != manifest["rows_sha256"]:
        raise ValueError("Feature rows changed before model fitting.")
    model = _fit(train_x, train_y)
    validation = _evaluate(model, train_y, val_x, val_y, val_sessions)
    test_x, test_y, test_sessions = _load_section(rows_path, metadata, "test")
    if _sha256(rows_path) != manifest["rows_sha256"]:
        raise ValueError("Feature rows changed during model evaluation.")
    test = _evaluate(model, train_y, test_x, test_y, test_sessions)
    if _sha256(manifest_path) != manifest_sha256:
        raise ValueError("Feature manifest changed during training.")
    _config(config_path)
    result = {
        "schema_version": 1,
        "artifact_type": "databento_6e_baseline_research_run",
        "status": "completed",
        "model_version": MODEL_VERSION,
        "trainer_source_sha256": _sha256(Path(__file__).resolve()),
        "rows_sha256": manifest["rows_sha256"],
        "manifest_sha256": manifest_sha256,
        "config_sha256": CONFIG_SHA256,
        "contract": CONTRACT,
        "feature_names": list(FEATURE_NAMES),
        "class_order": list(CLASS_LABELS),
        "session_split": {
            "train": list(EXPECTED_SESSIONS[: SESSION_COUNTS[0]]),
            "validation": list(EXPECTED_SESSIONS[SESSION_COUNTS[0] : sum(SESSION_COUNTS[:2])]),
            "test": list(EXPECTED_SESSIONS[sum(SESSION_COUNTS[:2]) :]),
        },
        "training": {
            "rows": len(train_y),
            "class_counts": np.bincount(train_y + 1, minlength=3).tolist(),
            "epochs": EPOCHS,
            "learning_rate": LEARNING_RATE,
            "l2": L2,
            "standardized_clip": STANDARDIZED_CLIP,
            "preprocessing": "train_mean_and_population_standard_deviation_only",
        },
        "model": asdict(model),
        "validation": validation,
        "test": test,
        "mode": "research_only",
        "promotion_allowed": False,
        "paper_trading_connected": False,
        "live_trading_connected": False,
        "limitation": (
            "This short fixed-contract cohort estimates directional prediction only. "
            "Overlapping labels are dependent, and no CFD spread, slippage, financing, "
            "execution or profitability is measured."
        ),
    }
    encoded = (json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n").encode()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("xb") as destination:
        destination.write(encoded)
        destination.flush()
        os.fsync(destination.fileno())
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = train_6e_baseline(
        rows_path=args.rows,
        manifest_path=args.manifest,
        config_path=args.config,
        output_path=args.output,
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "rows_sha256": result["rows_sha256"],
                "train_rows": result["training"]["rows"],
                "validation_rows": result["validation"]["rows"],
                "test_rows": result["test"]["rows"],
                "promotion_allowed": False,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
