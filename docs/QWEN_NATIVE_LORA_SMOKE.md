# Isolated training environment and native tiny LoRA check

Status (2026-09-24): **native CPU adapter optimization and save/reload verified** in a separate
`.venv-qwen-train` environment. This is a dependency/numerical smoke, not Qwen3-4B fine-tuning,
a GPU-memory feasibility result, a trading model or an evaluation-quality pass.

## Provisioned environment

Windows AMD64, Python 3.12.10, no system site packages. The original `.venv` and `.venv-qwen`
environments were not changed. Inference runtime metadata still matches its earlier saved record.
The installed training runtime uses Torch 2.14.0+cu132, Transformers 5.17.0, PEFT 0.21.0,
Accelerate 1.15.0, safetensors 0.8.0, tokenizers 0.23.2 and NumPy 2.5.0.

[`requirements/qwen-training-win-py312.txt`](../requirements/qwen-training-win-py312.txt) contains
39 self-contained `name==version --hash=sha256:...` wheel entries. Runtime dependency resolution,
offline installation with hash enforcement, all 39 installation-report hashes/versions and
`pip check` passed. The editable local project was installed separately with no dependencies,
no index and no build isolation. Bootstrap pip and the editable project are not wheel-lock entries.

The exact 1,993,738,732-byte CUDA Torch wheel was recovered from pip's existing cache and verified
against the inference lock's SHA256, avoiding a second download. Other wheels came from official
PyPI/cache; only PEFT and Accelerate were newly downloaded in this provisioning step. No model
download occurred. The 39-wheel local wheelhouse is `logs/qwen_training_wheels_20260924/`.

Package metadata was checked against [official PEFT metadata](https://pypi.org/pypi/peft/0.21.0/json)
and [official Accelerate metadata](https://pypi.org/pypi/accelerate/1.15.0/json). The save/reload
interfaces follow [PEFT's adapter API](https://huggingface.co/docs/peft/package_reference/peft_model).
These pins and a successful native smoke are not a dependency-security audit, installed-file
integrity verification or proof of CUDA BF16/4B-model compatibility.

To reproduce offline from the verified wheelhouse, use a **new** isolated Python 3.12 environment.
Do not run venv creation over an existing environment or install into `.venv-qwen`.

```powershell
.venv\Scripts\python.exe -m venv .venv-qwen-train
.venv-qwen-train\Scripts\python.exe -m pip --isolated install --no-index --find-links logs/qwen_training_wheels_20260924 --require-hashes --only-binary=:all: -r requirements/qwen-training-win-py312.txt --disable-pip-version-check
.venv-qwen-train\Scripts\python.exe -m pip --isolated install --no-index --no-deps --no-build-isolation -e . --disable-pip-version-check
.venv-qwen-train\Scripts\python.exe -m pip --isolated check
```

The wheelhouse is a local, Git-ignored artifact, not a published dependency mirror. On another
machine, obtain the same official wheels and verify the lock hashes first. The exact Torch URL
is retained in `requirements/qwen-inference-win-py312.txt`; do not substitute PyPI's CPU build.

## Repeatable bounded smoke

`training/tiny_lora_smoke.py` supervises one private `_tiny_lora_worker.py` process using the
existing scrubbed/offline, bounded-pipe transport. Explicit `--enable-native-smoke` is required.
The request binds the interpreter, dependency lock bytes and selected implementation source.
The child checks every installed lock version before native imports. There is no model ID,
checkpoint, tokenizer, market-data, training-target, step-count or device option.

The fixed test uses a randomly initialized one-layer Qwen3 *architecture*, **not** Qwen3-4B's
checkpoint: vocabulary 64, hidden width 32, intermediate width 64, four attention heads and two
KV heads. It has 13,424 base parameters and 896 trainable q_proj/v_proj LoRA parameters (rank 8,
alpha 16). All tensors are CPU float32. One synthetic 16-token example contains eight prompt
tokens, three supervised completion tokens plus EOS, and four masked padding tokens. No real
curriculum targets or tokenizer assets are read. EOS equals padding but is supervised by position.

The private tiny subclass supplies only random base construction, CPU batching and in-memory
base verification. It exercises the **actual production backend's** step, state, probe and
adapter save/reload methods. Production checkpoint/architecture/CUDA gates are unchanged; the
Qwen training worker cannot select this subclass or use it as a fallback.

Exactly three AdamW steps use learning rate 0.0002, seed 42, gradient clipping at 1 and
non-reentrant gradient checkpointing. Frozen base parameters are checked for exact equality,
absence of gradients and CPU placement after each step and around reload. Only adapter weights
may change. Reload uses a fresh tiny base restored from its original in-memory state, local
adapter safetensors and inference-only parameters. Adapter state must be identical and a
training-example loss probe must agree within absolute 0.00001.

The child explicitly hides GPU devices **before native imports**. This matters with a CUDA Torch
build: the first attempt initialized CUDA during an optimizer call despite CPU tensors, and the
CPU-only guard correctly failed. That failed directory remains at
`logs/tiny_native_lora_cpu_20260924/`, with unknown completed-step count. A forward/backward-only
diagnostic passed; a separate one-step diagnostic reproduced the CUDA initialization. Neither
diagnostic used Qwen weights or market data. After the GPU-visibility fix, one fresh full smoke
passed; no failed directory was overwritten or resumed.

The successful supervisor run lasted **5.125 seconds**, under its fixed 120-second wall deadline.
It recorded three finite losses (4.175911, 4.174366, 4.172797), finite gradient norms, observed
adapter updates, unchanged base parameters and `cuda_initialized: false`. The before/after reload
probe loss was exactly 4.171200275421143. The adapter tensor file is 4,120 bytes; all three adapter
files total 10,402 bytes. A decreasing loss on one synthetic example is not generalization.

Each step has fsynced intent/completion records. The supervisor independently checks response
bindings, runtime, metrics, authority flags and adapter file hashes. Timeout/failure preserves
partial artifacts and never retries automatically. The timeout includes imports and native calls;
process cleanup may add bounded seconds. This is not an OS network sandbox or hard RAM/disk quota.
The inherited `base_checkpoint_unchanged` result refers to the tiny in-memory base verifier here,
not evidence that this worker opened or rehashed any external Qwen checkpoint.

Example (choose a fresh output directory and verify the recorded lock pin before launching):

```powershell
.venv\Scripts\python.exe -m ai_trader.training.tiny_lora_smoke --python .venv-qwen-train/Scripts/python.exe --dependency-lock requirements/qwen-training-win-py312.txt --dependency-lock-sha256 8aedce7455c963753e0c8c5339e8abea7cc74ea0bddfb4c93390d4530d43af57 --output-dir logs/YOUR_NEW_tiny_lora_smoke --enable-native-smoke
```

## Evidence and remaining gates

Local artifacts and raw SHA256 values:

- Training lock: `8aedce7455c963753e0c8c5339e8abea7cc74ea0bddfb4c93390d4530d43af57`.
- `logs/qwen_training_resolution_20260924.json`:
  `a2012d81e609e073121bf99d54e1f9adfa2aa307928641d0cc09e50e17ad94c1`.
- `logs/qwen_training_install_20260924.json`:
  `d7377d90bfe46ea6163f57257f720441201187f603e0a9485bc8b3f58b860ad8`.
- `logs/qwen_training_runtime_versions_20260924.json`:
  `4840c478f76734ca6a9a5eec678a6dfbc314772a3a53a1e278b78f7e80e7a6bb`.
- `logs/tiny_native_lora_cpu_20260924_fixed/run.json`:
  `03b43e40e666f7e2ce5fd5e85d2e9030663c79dec8f84216f2fca4c413954f7d`.
- `logs/tiny_native_lora_cpu_20260924_fixed/request.json`:
  `07f5fd1f9e2ddcb388631f3bcdd72964f729b83a05f86b8c50ba17690dc03938`.

An independent read-only checksum check confirmed the existing Qwen checkpoint manifest remains
`8a1a0f20ba8a2c6d4480309f0f442114c4fa310018d143ee610061b1ecf47d3c`. Frozen curriculum, agent review
proposal and pending protected-reservation hashes also remain unchanged.

Subsequently, [user-delegated AI review](QWEN_DELEGATED_REVIEW.md) accepted all 14 targets and
created a verified candidate without claiming human approval. That curriculum change alters
the implementation hash; this smoke is historical evidence, not a native rerun of current source.

Next: reserve genuinely independent protected evaluation data. Then prepare a fresh pinned
[bounded Qwen LoRA launch](QWEN_LORA_WORKER.md) and test
actual CUDA BF16 memory/optimization/save-reload feasibility. This tiny adapter must never be
loaded into Qwen, the reviewer or paper trading. The tiny smoke itself created no candidate, holdout, model promotion, continuous
training loop or live-trading authority was created. Real-market learning still needs eligible
causal order-book/CVD/microstructure sessions; the failed market capture remains quarantined.
