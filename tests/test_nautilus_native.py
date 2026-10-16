"""Opt-in by dependency installation, not silently skipped on native-load errors."""

from importlib.util import find_spec

import pytest

from ai_trader.research.nautilus_probe import evaluate


@pytest.mark.skipif(find_spec("nautilus_trader") is None, reason="optional evaluation dependency")
def test_native_replay_matches_reference_and_repeats():
    # An installed-but-blocked/broken engine FAILS here, rather than being skipped.
    assert evaluate()["status"] == "PASS"
