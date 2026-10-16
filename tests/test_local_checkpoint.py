"""Synthetic assets only: hash inspection never loads weights or downloads anything."""

import json

import pytest

from ai_trader.models import local_checkpoint as checkpoint

MODEL = "Qwen/Qwen3-4B-Base"
ARCHITECTURE = {
    "model_type": "qwen3",
    "architectures": ["Qwen3ForCausalLM"],
    "hidden_size": 2560,
    "num_hidden_layers": 36,
    "num_attention_heads": 32,
    "num_key_value_heads": 8,
    "vocab_size": 151936,
}


@pytest.fixture
def assets(tmp_path):
    (tmp_path / "config.json").write_text(json.dumps(ARCHITECTURE))
    (tmp_path / "tokenizer.json").write_text("{}")
    (tmp_path / "tokenizer_config.json").write_text("{}")
    (tmp_path / "model.safetensors").write_bytes(b"synthetic-not-loadable-weights")
    return tmp_path


def test_manifest_hashes_assets_not_documentation(assets):
    before = checkpoint.inspect_checkpoint(assets, MODEL)
    (assets / "README.md").write_text("documentation")
    assert checkpoint.inspect_checkpoint(assets, MODEL) == before
    assert len(before["files"]) == 4
    assert before["total_bytes"] == sum(item["bytes"] for item in before["files"])
    (assets / "model.safetensors").write_bytes(b"different")
    assert checkpoint.digest(checkpoint.inspect_checkpoint(assets, MODEL)) != checkpoint.digest(
        before
    )


@pytest.mark.parametrize(
    "name",
    [
        "model.py",
        "pytorch_model.bin",
        "bad.pt",
        "bad.pth",
        "bad.pkl",
        "custom_generate",
        "chat_templates",
        "other.json",
    ],
)
def test_unreviewed_assets_refused(assets, name):
    (assets / name).write_bytes(b"untrusted")
    with pytest.raises(ValueError):
        checkpoint.inspect_checkpoint(assets, MODEL)


@pytest.mark.parametrize(
    "name", ["config.json", "tokenizer.json", "tokenizer_config.json", "model.safetensors"]
)
def test_required_assets(assets, name):
    (assets / name).unlink()
    with pytest.raises(ValueError):
        checkpoint.inspect_checkpoint(assets, MODEL)


@pytest.mark.parametrize(
    "changes",
    [{"hidden_size": 1024}, {"auto_map": {}}, {"quantization_config": {}}, {"model_type": "other"}],
)
def test_architecture_and_remote_code_refused(assets, changes):
    (assets / "config.json").write_text(json.dumps({**ARCHITECTURE, **changes}))
    with pytest.raises(ValueError, match="Unsupported"):
        checkpoint.inspect_checkpoint(assets, MODEL)


def test_tokenizer_custom_code_refused(assets):
    (assets / "tokenizer_config.json").write_text('{"auto_map":{}}')
    with pytest.raises(ValueError, match="Custom tokenizer"):
        checkpoint.inspect_checkpoint(assets, MODEL)


@pytest.mark.parametrize(
    "changes",
    [
        {"tokenizer_class": "OtherTokenizer"},
        {"tokenizer_file": "../external.json"},
        {"vocab_file": "C:/elsewhere.json"},
        {"fast_tokenizer_files": ["outside.json"]},
    ],
)
def test_tokenizer_inputs_cannot_escape_pinned_assets(assets, changes):
    (assets / "tokenizer_config.json").write_text(json.dumps(changes))
    with pytest.raises(ValueError, match="file override"):
        checkpoint.inspect_checkpoint(assets, MODEL)


@pytest.mark.parametrize("raw", ['{"a":1,"a":2}', '{"a":NaN}', '{"a":Infinity}', "[] extra"])
def test_strict_metadata_parser(raw):
    with pytest.raises(ValueError):
        checkpoint.strict_json(raw)


def test_shard_index_cannot_escape_or_skip_a_weight_file(assets):
    (assets / "model.safetensors").rename(assets / "model-00001-of-00001.safetensors")
    with pytest.raises(ValueError, match="index"):
        checkpoint.inspect_checkpoint(assets, MODEL)
    index = assets / "model.safetensors.index.json"
    index.write_text('{"weight_map":{"tensor":"../elsewhere.safetensors"}}')
    with pytest.raises(ValueError, match="index"):
        checkpoint.inspect_checkpoint(assets, MODEL)
    index.write_text('{"weight_map":{"tensor":"model-00001-of-00001.safetensors"}}')
    assert len(checkpoint.inspect_checkpoint(assets, MODEL)["files"]) == 5
    (assets / "model.safetensors").write_bytes(b"ambiguous")
    with pytest.raises(ValueError):
        checkpoint.inspect_checkpoint(assets, MODEL)


def test_bounds_and_empty_assets(assets, monkeypatch):
    monkeypatch.setattr(checkpoint, "MAX_CHECKPOINT_BYTES", 10)
    with pytest.raises(ValueError, match="budget"):
        checkpoint.inspect_checkpoint(assets, MODEL)
    monkeypatch.setattr(checkpoint, "MAX_CHECKPOINT_BYTES", 100000)
    monkeypatch.setattr(checkpoint, "MAX_METADATA_BYTES", 10)
    with pytest.raises(ValueError, match="budget"):
        checkpoint.inspect_checkpoint(assets, MODEL)
    monkeypatch.setattr(checkpoint, "MAX_METADATA_BYTES", 10000)
    (assets / "tokenizer.json").write_bytes(b"")
    with pytest.raises(ValueError, match="Empty"):
        checkpoint.inspect_checkpoint(assets, MODEL)


def test_chat_template_is_pinned(assets):
    before = checkpoint.digest(checkpoint.inspect_checkpoint(assets, MODEL))
    (assets / "chat_template.jinja").write_text("template")
    assert before != checkpoint.digest(checkpoint.inspect_checkpoint(assets, MODEL))


def test_symlink_asset_refused_without_requiring_os_symlink_privilege(assets, monkeypatch):
    original = type(assets).is_symlink
    monkeypatch.setattr(
        type(assets), "is_symlink", lambda p: p.name == "tokenizer.json" or original(p)
    )
    with pytest.raises(ValueError, match="regular local"):
        checkpoint.inspect_checkpoint(assets, MODEL)


@pytest.mark.parametrize("model", [None, "Qwen/Qwen3.5-4B", "https://example.com/model"])
def test_only_explicit_supported_model_id(assets, model):
    with pytest.raises(ValueError):
        checkpoint.inspect_checkpoint(assets, model)
