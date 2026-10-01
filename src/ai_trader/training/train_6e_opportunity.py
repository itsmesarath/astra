"""One offline development fit of cost-aware opportunity probabilities, never orders.

Reuses only the previously exposed training dates in the pinned microdepth artifact.
The old July 21-25 evaluation rows are excluded. No new holdout is consumed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from ai_trader.research import databento_6e_microdepth as data
from ai_trader.training import metrics, standardize
from ai_trader.training import train_6e_cost_baseline as baseline

TRAIN = data.TRAIN[:7]
DEVELOPMENT = data.TRAIN[7:]
SESSIONS = (*TRAIN, *DEVELOPMENT)
ROWS_SHA256 = "d8064ae8d320cecbdc220ac590f7c8099e8b836c0a75b70ce3dae6505876344a"
REPORT_SHA256 = "72ded08fa3a1eb1b2b316343cd9b99d97c6dbd3d905a3982e89adaf013cecf90"
ROWS_PATH = "data/processed/databento_6e_microdepth_tree_v1_rows.jsonl"
REPORT_PATH = "data/processed/databento_6e_microdepth_tree_v1_report.json"
MAX_BYTES = 256 * 1024 * 1024
MAX_LINE = 16 * 1024
MAX_ROWS = 200_000
EPOCHS = 200
LEARNING_RATE = 0.05
L2 = 0.01
CLIP = 10.0


def canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def _bad_constant(value):
    raise ValueError(f"Nonfinite JSON constant: {value}")


def loads(raw: bytes) -> dict:
    value = json.loads(raw, object_pairs_hook=_pairs, parse_constant=_bad_constant)
    if type(value) is not dict:
        raise ValueError("Expected a JSON object")
    return value


def hash_file(path: Path, limit: int) -> str:
    if path.stat().st_size > limit:
        raise ValueError("Evidence exceeds byte limit")
    size, pin = 0, hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            size += len(chunk)
            if size > limit:
                raise ValueError("Evidence exceeds byte limit")
            pin.update(chunk)
    return pin.hexdigest()


def protocol() -> dict:
    return {
        "artifact_type": "6e_opportunity_development_protocol_v1",
        "input_rows_sha256": ROWS_SHA256,
        "input_report_sha256": REPORT_SHA256,
        "train_sessions": list(TRAIN),
        "development_sessions": list(DEVELOPMENT),
        "excluded_sessions": list((*data.VALIDATION, *data.TEST)),
        "feature_names": list(data.FEATURES),
        "class_order": ["short_positive_net", "neither_positive_net", "long_positive_net"],
        "label_rule": "Existing 100ms-entry, 15s-hold crossed quotes minus one extra cost tick",
        "exposure": "All selected dates already exposed; development only, not independent test",
        "epochs": EPOCHS,
        "learning_rate": LEARNING_RATE,
        "l2": L2,
        "standardized_clip": CLIP,
        "initialization": "Zero weights; Laplace-smoothed training class prior log biases",
        "sampling": "All resolved rows, no class reweighting or oversampling",
        "unknown_outcomes": "Accounted separately, never relabeled as neither",
        "evaluation": "Frozen classifier versus training prior; pooled and per-session scores",
        "calibration": "Ten fixed equal-width bins for any positive opportunity",
        "positive_classification_signal": "Lower log loss and Brier score on every development day",
        "model_selection": "One fit; no early stopping, tuning, threshold selection or refit",
        "promotion_enabled": False,
        "trading_enabled": False,
        "qwen_training": False,
    }


def fingerprints() -> dict:
    paths = [Path(__file__), Path(metrics.__file__), Path(standardize.__file__)]
    return {
        **baseline.fingerprints(),
        **{p.name: hash_file(p, 1024 * 1024) for p in (*paths, Path(data.__file__))},
    }


def _write_new(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as target:
        target.write(canonical(value) + b"\n")


def prepare(path: Path) -> dict:
    """Record the fixed protocol and code pins without opening any market dataset."""
    result = {
        "protocol": protocol(),
        "protocol_sha256": digest(protocol()),
        "implementation_sha256": fingerprints(),
        "prepared_utc": datetime.now(UTC).isoformat(),
    }
    _write_new(path, result)
    return result


def load_rows(path: Path) -> tuple[list[dict], dict]:
    """Bounded hash-verified intake; excluded-session outcomes never enter training."""
    if path.stat().st_size > MAX_BYTES:
        raise ValueError("Rows exceed byte limit")
    pin, count, size = hashlib.sha256(), 0, 0
    rows, counts = [], Counter()
    previous, seen = None, []
    with path.open("rb") as source:
        while raw := source.readline(MAX_LINE + 1):
            size += len(raw)
            count += 1
            if count > MAX_ROWS or size > MAX_BYTES or len(raw) > MAX_LINE:
                raise ValueError("Rows exceed bounded intake")
            if not raw.endswith(b"\n"):
                raise ValueError("Incomplete JSONL row")
            pin.update(raw)
            row = loads(raw)
            session = row.get("source_session")
            if type(session) is not str or session not in data.SESSIONS:
                raise ValueError("Unexpected source session")
            if session != previous:
                if previous is not None and session <= previous:
                    raise ValueError("Source sessions are not chronological")
                seen.append(session)
                previous = session
            counts[session] += 1
            if session in SESSIONS:
                rows.append(row)
    if tuple(seen) != data.SESSIONS or pin.hexdigest() != ROWS_SHA256:
        raise ValueError("Input source cohort or pinned row hash differs")
    return rows, {
        "source_rows": count,
        "selected_rows": len(rows),
        "excluded_rows": count - len(rows),
        "source_rows_by_session": dict(counts),
        "rows_sha256": pin.hexdigest(),
    }


def softmax(scores: np.ndarray) -> np.ndarray:
    values = np.exp(scores - scores.max(axis=1, keepdims=True))
    return values / values.sum(axis=1, keepdims=True)


@dataclass(frozen=True)
class OpportunityModel:
    means: list[float]
    scales: list[float]
    weights: list[list[float]]
    bias: list[float]

    def predict(self, features) -> np.ndarray:
        x = standardize.validate_feature_matrix(features)
        if x.shape[1] != len(self.means):
            raise ValueError("Feature dimension differs from frozen classifier")
        x = np.clip((x - self.means) / self.scales, -CLIP, CLIP)
        probabilities = softmax(x @ self.weights + self.bias)
        _probabilities(probabilities, len(x))
        return probabilities


def _labels(labels, n: int) -> np.ndarray:
    y = np.asarray(labels)
    if y.shape != (n,) or y.dtype.kind not in "iu" or not np.isin(y, [-1, 0, 1]).all():
        raise ValueError("Expected aligned integer opportunity labels -1, 0, 1")
    return y.astype(np.int64) + 1


def _probabilities(p, n: int) -> None:
    if (
        p.shape != (n, 3)
        or not np.isfinite(p).all()
        or (p < 0).any()
        or (p > 1).any()
        or not np.allclose(p.sum(axis=1), 1, rtol=0, atol=1e-12)
    ):
        raise ValueError("Invalid opportunity probabilities")


def fit(features, labels) -> tuple[OpportunityModel, np.ndarray]:
    x = standardize.validate_feature_matrix(features)
    y = _labels(labels, len(x))
    counts = np.bincount(y, minlength=3)
    if (counts == 0).any():
        raise ValueError("Every opportunity class must be present in training")
    scaler = standardize.fit_standardizer(x)
    x = np.clip(scaler.transform(x), -CLIP, CLIP)
    prior = (counts + 1) / (len(y) + 3)
    weights = np.zeros((x.shape[1], 3))
    bias = np.log(prior)
    for _ in range(EPOCHS):
        error = softmax(x @ weights + bias)
        error[np.arange(len(y)), y] -= 1
        weights -= LEARNING_RATE * (x.T @ error / len(y) + L2 * weights)
        bias -= LEARNING_RATE * error.mean(axis=0)
    if not np.isfinite(weights).all() or not np.isfinite(bias).all():
        raise ValueError("Nonfinite trained parameters")
    return OpportunityModel(
        scaler.means.tolist(), scaler.scales.tolist(), weights.tolist(), bias.tolist()
    ), prior


def scores(labels, probabilities: np.ndarray) -> dict:
    y = _labels(labels, len(probabilities))
    if not len(y):
        raise ValueError("No resolved evaluation targets")
    _probabilities(probabilities, len(y))
    one_hot = np.eye(3)[y]
    calibration = []
    opportunity = probabilities[:, 0] + probabilities[:, 2]
    bins = np.minimum((opportunity * 10).astype(int), 9)
    for index in range(10):
        mask = bins == index
        calibration.append(
            {
                "lower": index / 10,
                "upper": (index + 1) / 10,
                "rows": int(mask.sum()),
                "mean_predicted": float(opportunity[mask].mean()) if mask.any() else None,
                "observed_positive_fraction": float((y[mask] != 1).mean()) if mask.any() else None,
            }
        )
    return {
        **asdict(
            metrics.evaluate_classification(
                (y - 1).tolist(), (probabilities.argmax(axis=1) - 1).tolist()
            )
        ),
        "log_loss": float(-np.log(np.maximum(probabilities[np.arange(len(y)), y], 1e-15)).mean()),
        "brier_score": float(((probabilities - one_hot) ** 2).sum(axis=1).mean()),
        "opportunity_calibration": calibration,
    }


def _accounting(rows: list[dict]) -> dict:
    return {
        "rows": len(rows),
        "eligible": sum(r["eligible"] for r in rows),
        "statuses": dict(Counter(r["outcome"]["status"] for r in rows)),
        "resolved_inactivity_exposed": sum(
            r["outcome"]["status"] == "resolved" and r["outcome"].get("inactivity_exposed", False)
            for r in rows
        ),
    }


def evaluate(model: OpportunityModel, prior: np.ndarray, rows: list[dict]) -> dict:
    resolved = [r for r in rows if r["outcome"]["status"] == "resolved"]
    if not resolved:
        raise ValueError("No resolved evaluation targets")
    labels = [r["hindsight_action"] for r in resolved]
    return {
        **_accounting(rows),
        "resolved": len(resolved),
        "class_counts_short_neither_long": np.bincount(np.array(labels) + 1, minlength=3).tolist(),
        "model": scores(labels, model.predict(baseline.feature_matrix(resolved, data.FEATURES))),
        "training_prior": scores(labels, np.tile(prior, (len(resolved), 1))),
    }


def train_once(rows: list[dict]) -> dict:
    baseline.validate_rows(rows, sessions=SESSIONS, feature_names=data.FEATURES)
    train_rows = [r for r in rows if r["source_session"] in TRAIN]
    resolved = [r for r in train_rows if r["outcome"]["status"] == "resolved"]
    counts = Counter(r["source_session"] for r in resolved)
    if any(counts[s] < 100 for s in TRAIN):
        raise ValueError("Insufficient resolved training session support")
    model, prior = fit(
        baseline.feature_matrix(resolved, data.FEATURES),
        [r["hindsight_action"] for r in resolved],
    )
    model_pin = digest(asdict(model))
    development = [r for r in rows if r["source_session"] in DEVELOPMENT]
    pooled = evaluate(model, prior, development)
    by_session = [
        {
            "source_session": session,
            **evaluate(model, prior, [r for r in development if r["source_session"] == session]),
        }
        for session in DEVELOPMENT
    ]
    if digest(asdict(model)) != model_pin:
        raise ValueError("Classifier changed during development evaluation")
    improvements = all(
        section["model"][metric] < section["training_prior"][metric]
        for section in [pooled, *by_session]
        for metric in ("log_loss", "brier_score")
    )
    return {
        "model_kind": "numpy_cost_opportunity_softmax_v1",
        "model": asdict(model),
        "model_sha256": model_pin,
        "feature_names": list(data.FEATURES),
        "class_order": protocol()["class_order"],
        "training": {
            **_accounting(train_rows),
            "resolved": len(resolved),
            "resolved_by_session": dict(counts),
            "prior_short_neither_long": prior.tolist(),
            "class_counts_short_neither_long": np.bincount(
                np.array([r["hindsight_action"] for r in resolved]) + 1, minlength=3
            ).tolist(),
        },
        "development": pooled,
        "by_session": by_session,
        "consistent_development_probability_improvement": improvements,
        "decision": "development_only_not_ready_for_promotion",
        "blockers": [
            "already_exposed_development_dates",
            "classification_probabilities_do_not_estimate_payoff_magnitude",
            "missing_outcome_selection_and_overlapping_labels",
            "broker_execution_and_cross_feed_clock_alignment_unverified",
        ]
        + ([] if improvements else ["no_consistent_development_probability_improvement"]),
        "promotion_enabled": False,
        "trading_enabled": False,
        "qwen_trained": False,
    }


def run(*, root: Path, registration: Path, output: Path) -> dict:
    if output.exists() or output.resolve() in {
        registration.resolve(),
        (root / ROWS_PATH).resolve(),
        (root / REPORT_PATH).resolve(),
    }:
        raise ValueError("Refusing to overwrite research evidence")
    registration_pin = hash_file(registration, 1024 * 1024)
    frozen = loads(registration.read_bytes())
    pins = fingerprints()
    if (
        frozen.get("protocol") != protocol()
        or frozen.get("protocol_sha256") != digest(protocol())
        or frozen.get("implementation_sha256") != pins
    ):
        raise ValueError("Registration protocol or code pins differ")
    if hash_file(root / REPORT_PATH, 1024 * 1024) != REPORT_SHA256:
        raise ValueError("Pinned source report differs")
    rows, intake = load_rows(root / ROWS_PATH)
    result = train_once(rows)
    if (
        fingerprints() != pins
        or hash_file(registration, 1024 * 1024) != registration_pin
        or hash_file(root / ROWS_PATH, MAX_BYTES) != ROWS_SHA256
        or hash_file(root / REPORT_PATH, 1024 * 1024) != REPORT_SHA256
    ):
        raise ValueError("Frozen evidence changed during training")
    report = {
        "artifact_type": "6e_opportunity_development_run_v1",
        "status": "completed",
        "completed_utc": datetime.now(UTC).isoformat(),
        "registration_sha256": registration_pin,
        **frozen,
        **intake,
        **result,
        "runtime": {"python": sys.version.split()[0], "numpy": np.__version__},
    }
    _write_new(output, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    commands = parser.add_subparsers(dest="command", required=True)
    prep = commands.add_parser("prepare")
    prep.add_argument("--output", type=Path, required=True)
    train = commands.add_parser("train")
    train.add_argument("--registration", type=Path, required=True)
    train.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        result = prepare(args.output)
        print(json.dumps({"protocol_sha256": result["protocol_sha256"]}))
    else:
        result = run(root=args.project_root, registration=args.registration, output=args.output)
        print(
            json.dumps(
                {
                    k: result[k]
                    for k in (
                        "decision",
                        "training",
                        "consistent_development_probability_improvement",
                        "model_sha256",
                        "blockers",
                    )
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
