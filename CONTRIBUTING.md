# Contributing to Auto-Trader

This is an experimental, paper-only research project. No profitable trading strategy has
been established. Bug reports, reproducible research, tests, and documentation are welcome.

## Development

Follow the Python 3.12 setup in [README.md](README.md). CPU PyTorch is sufficient for the
test suite; a missing CUDA device skips only the GPU smoke test.

Before opening a pull request, run:

```sh
python -m ruff check .
python -m ruff format --check .
python -m pytest -q
```

Keep changes focused, explain the behavior being changed, and add regression tests.
Include the commands and results used to validate research changes. Synthetic fixtures
should run without internet access or exchange credentials.

## Research and safety requirements

- Keep source sessions exclusive to their dataset split and avoid look-ahead leakage.
- Separate training, tuning, evaluation, and untouched holdouts; record every experiment.
- Include fees, spread, slippage, execution timing, and drawdown in evaluations.
- Report negative results and distinguish simulations from verified market behavior.
- Preserve deterministic risk checks and fail-closed execution modes. Live-order connectivity
  is not implemented; changing that boundary requires a separately reviewed design.
- Never commit credentials, private account information, raw market archives, or checkpoints.
  Inspect staged files before committing; `.gitignore` is not a secret scanner.

Use public issues for non-sensitive bugs and proposals, with a minimal reproduction and
environment details. Do not include secrets or private account data in issues or logs.

## Attribution and licensing

By contributing, you agree to license your contribution under this project's MIT license.
Only contribute work you have the right to license. Preserve notices for third-party code,
and clearly document external inspiration. Downloaded market data and dependencies are not
relicensed by this repository.
