"""Smoke tests for the local numerical-computing environment."""

import numpy as np
import pytest
import torch


def test_numpy_calculation() -> None:
    """NumPy should perform a basic calculation correctly."""
    values = np.array([1.0, 2.0, 3.0])
    assert values.mean() == 2.0


def test_cpu_tensor_calculation() -> None:
    """The numerical stack must also work without an NVIDIA GPU."""
    values = torch.tensor([1.0, 2.0, 3.0, 4.0], device="cpu")
    assert (values * values).sum().item() == 30.0


@pytest.mark.skipif(not torch.cuda.is_available(), reason="CUDA GPU is not available")
def test_cuda_tensor_calculation() -> None:
    """PyTorch should execute a tensor calculation on the NVIDIA GPU."""
    assert torch.cuda.is_available()

    values = torch.tensor([1.0, 2.0, 3.0, 4.0], device="cuda")
    squared_sum = (values * values).sum().item()

    assert squared_sum == 30.0
