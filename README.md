# AI Trader

An experimental cryptocurrency market-microstructure research system.

## Initial scope

- Market: BTCUSDT on Binance
- Mode: research, backtesting, and paper trading only
- Language: Python
- Hardware: NVIDIA RTX 5080 Laptop GPU with 16 GB VRAM

## Safety boundary

Live trading is disabled during development. Model decisions will never directly control an exchange account. A separate deterministic risk and execution layer must validate every proposed action.

## Research principles

- Use time-based train, validation, and test splits.
- Prevent future information from leaking into model inputs.
- Include fees, spread, slippage, and latency.
- Compare advanced models with simple baselines.
- Evaluate expected value and drawdown, not prediction accuracy alone.
- Require sustained paper-trading evidence before considering small live tests.

## Planned architecture

```text
Binance market data
    -> validated event storage
    -> order-book reconstruction
    -> microstructure features
    -> baseline models
    -> specialized neural models
    -> decision model
    -> hard risk engine
    -> paper-trading execution
    -> evaluation and retraining