"""Explicit local Qwen assets: bounded hashing, no download or executable checkpoints."""

import hashlib
import json
import re
from pathlib import Path

MODEL_IDS = ("Qwen/Qwen3-4B-Base", "Qwen/Qwen3-4B")
MAX_CHECKPOINT_BYTES = 20 * 1024**3
MAX_METADATA_BYTES = 16 * 1024**2
ASSETS = {
    "config.json",
    "generation_config.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "vocab.json",
    "merges.txt",
    "special_tokens_map.json",
    "added_tokens.json",
    "model.safetensors",
    "model.safetensors.index.json",
    "chat_template.jinja",
}


def canonical(value):
    return json.dumps(
        value, sort_keys=True, ensure_ascii=True, allow_nan=False, separators=(",", ":")
    )


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def check_digest(value):
    if type(value) is not str or re.fullmatch("[a-f0-9]{64}", value) is None:
        raise ValueError("A caller-pinned lowercase SHA256 is required.")


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON key.")
            result[key] = value
        return result

    def constant(value):
        raise ValueError("Non-finite JSON constant.")

    return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)


def inspect_checkpoint(directory: Path, model_id: str) -> dict:
    """Hash loadable assets, not provenance authentication. Never load tensors or model code."""
    if model_id not in MODEL_IDS or not isinstance(directory, Path) or not directory.is_absolute():
        raise ValueError("Explicit absolute local path and supported Qwen model ID required.")
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("Expected an existing nonsymlink checkpoint directory.")
    root, entries = directory.resolve(), []
    for count, path in enumerate(directory.iterdir(), start=1):
        if count > 64:
            raise ValueError("Excessive checkpoint directory entries.")
        if path.suffix in (".py", ".bin", ".pt", ".pth", ".pkl"):
            raise ValueError("Executable or pickle-based checkpoint assets are not permitted.")
        if path.name not in ASSETS and not re.fullmatch(
            r"model-\d{5}-of-\d{5}\.safetensors", path.name
        ):
            if path.name in {"README.md", "LICENSE", "LICENSE.txt", ".gitattributes", ".cache"}:
                continue  # Documentation/cache bookkeeping is not a model input.
            raise ValueError("Unreviewed checkpoint asset or subdirectory.")
        if path.is_symlink() or not path.is_file() or path.resolve().parent != root:
            raise ValueError("Checkpoint inputs must be regular local files within the directory.")
        entries.append(path)
    names = {p.name for p in entries}
    if len(entries) > 32 or not {"config.json", "tokenizer.json", "tokenizer_config.json"} <= names:
        raise ValueError("Missing or excessive checkpoint/tokenizer assets.")
    weights = {n for n in names if n.endswith(".safetensors")}
    if not weights or (
        ("model.safetensors" in weights)
        != (len(weights) == 1 and "model.safetensors.index.json" not in names)
    ):
        raise ValueError("Expected one unsharded model or explicitly indexed shards.")
    if "model.safetensors" not in weights and "model.safetensors.index.json" not in names:
        raise ValueError("Sharded weights require an index.")
    metadata, files, total = {}, [], 0
    for path in sorted(entries):
        ceiling = (
            MAX_CHECKPOINT_BYTES - total
            if path.name in weights
            else min(MAX_METADATA_BYTES, MAX_CHECKPOINT_BYTES - total)
        )
        checksum, size = hashlib.sha256(), 0
        parts = []
        with path.open("rb") as stream:
            while block := stream.read(min(1024**2, max(1, ceiling - size + 1))):
                size += len(block)
                if size > ceiling:
                    raise ValueError("Checkpoint byte budget exceeded.")
                checksum.update(block)
                if path.suffix == ".json":
                    parts.append(block)
        if not size:
            raise ValueError("Empty checkpoint asset.")
        total += size
        files.append({"name": path.name, "bytes": size, "sha256": checksum.hexdigest()})
        if path.suffix == ".json":
            metadata[path.name] = strict_json(b"".join(parts))
    config = metadata["config.json"]
    if (
        type(config) is not dict
        or config.get("model_type") != "qwen3"
        or config.get("architectures") != ["Qwen3ForCausalLM"]
        or config.get("hidden_size") != 2560
        or config.get("num_hidden_layers") != 36
        or config.get("num_attention_heads") != 32
        or config.get("num_key_value_heads") != 8
        or config.get("vocab_size") != 151936
        or "auto_map" in config
        or "quantization_config" in config
    ):
        raise ValueError(
            "Unsupported Qwen3-4B architecture or unreviewed code/quantization config."
        )
    tokenizer = metadata["tokenizer_config.json"]
    if type(tokenizer) is not dict or "auto_map" in tokenizer:
        raise ValueError("Custom tokenizer code is forbidden.")
    if tokenizer.get("tokenizer_class", "Qwen2Tokenizer") not in (
        "Qwen2Tokenizer",
        "Qwen2TokenizerFast",
    ) or any(key.endswith("_file") or key == "fast_tokenizer_files" for key in tokenizer):
        raise ValueError("Unreviewed tokenizer class or file override.")
    if "model.safetensors.index.json" in metadata:
        index = metadata["model.safetensors.index.json"]
        mapping = index.get("weight_map") if type(index) is dict else None
        if (
            type(mapping) is not dict
            or not mapping
            or any(type(v) is not str for v in mapping.values())
            or set(mapping.values()) != weights
        ):
            raise ValueError("Weight index must reference exactly the local safetensors shards.")
    return {
        "schema_version": 1,
        "model_id": model_id,
        "format": "local_safetensors",
        "files": files,
        "total_bytes": total,
    }
