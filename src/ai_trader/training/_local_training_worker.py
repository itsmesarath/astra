"""Private supervised training process; use advisory_training_run, not this module directly."""

import contextlib
import sys

from ai_trader.models.local_checkpoint import canonical, strict_json
from ai_trader.training.advisory_curriculum import _fields
from ai_trader.training.advisory_training_run import MAX_REQUEST_BYTES, execute_worker


def respond(raw):
    if type(raw) is not bytes or len(raw) > MAX_REQUEST_BYTES:
        raise ValueError("Invalid training request budget.")
    request = strict_json(raw)
    _fields(request, ("enable_local_training", "plan"))
    if request["enable_local_training"] is not True:
        raise ValueError("Explicit training opt-in required.")
    return execute_worker(request["plan"])


def main():
    try:
        raw = sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1)
        with contextlib.redirect_stdout(sys.stderr):
            response = respond(raw)
        print(canonical(response))
        return 0
    except Exception:
        print("local_training_worker_failed", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
