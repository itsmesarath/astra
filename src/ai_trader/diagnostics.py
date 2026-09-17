"""Verify the local Python, NumPy, PyTorch, and NVIDIA GPU setup."""

from __future__ import annotations

import platform
import sys

import numpy as np
import torch


def main() -> None:
    """Print environment details and run a small GPU calculation."""
    print(f"Python: {sys.version.split()[0]}")
    print(f"Operating system: {platform.platform()}")
    print(f"NumPy: {np.__version__}")
    print(f"PyTorch: {torch.__version__}")
    print(f"PyTorch CUDA runtime: {torch.version.cuda}")
    print(f"CUDA available: {torch.cuda.is_available()}")

    if not torch.cuda.is_available():
        raise SystemExit("FAILED: PyTorch cannot access the NVIDIA GPU.")

    device = torch.device("cuda")
    properties = torch.cuda.get_device_properties(device)

    print(f"GPU: {properties.name}")
    print(f"Compute capability: {properties.major}.{properties.minor}")
    print(f"VRAM: {properties.total_memory / 1024**3:.2f} GiB")

    left = torch.rand((1024, 1024), device=device)
    right = torch.rand((1024, 1024), device=device)
    result = (left @ right).mean()
    torch.cuda.synchronize()

    print(f"GPU matrix test result: {result.item():.6f}")
    print("PASSED: Python and GPU acceleration are working.")


if __name__ == "__main__":
    main()
