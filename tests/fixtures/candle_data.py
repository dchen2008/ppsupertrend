"""
Candle data generators for various market scenarios.
Provides both programmatic generation and scenario presets.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta


def generate_trending_candles(n=100, direction='up', base_price=1.10000,
                               pip_range=100, volatility=0.0005, seed=42):
    """
    Generate trending candle data.

    Args:
        n: Number of candles
        direction: 'up' or 'down'
        base_price: Starting price
        pip_range: Total pips to move
        volatility: Random noise standard deviation
        seed: Random seed for reproducibility

    Returns:
        pd.DataFrame with OHLCV data
    """
    np.random.seed(seed)

    pip_value = 0.0001
    total_move = pip_range * pip_value * (1 if direction == 'up' else -1)

    trend = np.linspace(0, total_move, n)
    noise = np.random.normal(0, volatility, n)

    closes = base_price + trend + noise
    highs = closes + np.random.uniform(0.0002, 0.0008, n)
    lows = closes - np.random.uniform(0.0002, 0.0008, n)
    opens = np.roll(closes, 1)
    opens[0] = base_price

    start_time = datetime(2026, 1, 1, 0, 0, 0)
    times = [start_time + timedelta(minutes=5*i) for i in range(n)]

    return pd.DataFrame({
        'open': opens,
        'high': highs,
        'low': lows,
        'close': closes,
        'volume': np.random.randint(100, 1000, n)
    }, index=pd.DatetimeIndex(times))


def generate_reversal_candles(n=100, initial_direction='down',
                               reversal_point=0.8, base_price=1.10500,
                               pip_range=80, seed=44):
    """
    Generate candles with a trend reversal.

    Args:
        n: Number of candles
        initial_direction: 'up' or 'down' for initial trend
        reversal_point: Fraction of n where reversal occurs (0.0-1.0)
        base_price: Starting price
        pip_range: Pips to move in each direction
        seed: Random seed

    Returns:
        pd.DataFrame that should produce a signal at the end
    """
    np.random.seed(seed)

    pivot_idx = int(n * reversal_point)
    pip_value = 0.0001

    if initial_direction == 'down':
        # Downtrend then reversal up (produces BUY signal)
        initial_trend = np.linspace(0, -pip_range * pip_value, pivot_idx)
        reversal_trend = np.linspace(-pip_range * pip_value,
                                      pip_range * pip_value * 0.25,
                                      n - pivot_idx)
    else:
        # Uptrend then reversal down (produces SELL signal)
        initial_trend = np.linspace(0, pip_range * pip_value, pivot_idx)
        reversal_trend = np.linspace(pip_range * pip_value,
                                      -pip_range * pip_value * 0.25,
                                      n - pivot_idx)

    trend = np.concatenate([initial_trend, reversal_trend])
    noise = np.random.normal(0, 0.0003, n)

    closes = base_price + trend + noise
    highs = closes + np.random.uniform(0.0002, 0.0006, n)
    lows = closes - np.random.uniform(0.0002, 0.0006, n)
    opens = np.roll(closes, 1)
    opens[0] = base_price

    start_time = datetime(2026, 1, 1, 0, 0, 0)
    times = [start_time + timedelta(minutes=5*i) for i in range(n)]

    return pd.DataFrame({
        'open': opens,
        'high': highs,
        'low': lows,
        'close': closes,
        'volume': np.random.randint(100, 1000, n)
    }, index=pd.DatetimeIndex(times))


def generate_ranging_candles(n=100, base_price=1.10000, range_pips=20, seed=46):
    """
    Generate ranging/sideways candles (no clear trend).
    Useful for testing HOLD signals.
    """
    np.random.seed(seed)

    pip_value = 0.0001
    range_size = range_pips * pip_value

    # Oscillate around base price
    t = np.linspace(0, 4 * np.pi, n)  # Two full oscillations
    oscillation = np.sin(t) * (range_size / 2)
    noise = np.random.normal(0, 0.0002, n)

    closes = base_price + oscillation + noise
    highs = closes + np.random.uniform(0.0001, 0.0005, n)
    lows = closes - np.random.uniform(0.0001, 0.0005, n)
    opens = np.roll(closes, 1)
    opens[0] = base_price

    start_time = datetime(2026, 1, 1, 0, 0, 0)
    times = [start_time + timedelta(minutes=5*i) for i in range(n)]

    return pd.DataFrame({
        'open': opens,
        'high': highs,
        'low': lows,
        'close': closes,
        'volume': np.random.randint(100, 1000, n)
    }, index=pd.DatetimeIndex(times))


def generate_minimal_candles(n=20, base_price=1.10000):
    """Minimal valid candle set for edge case testing."""
    start_time = datetime(2026, 1, 1, 0, 0, 0)
    times = [start_time + timedelta(minutes=5*i) for i in range(n)]

    return pd.DataFrame({
        'open': [base_price] * n,
        'high': [base_price + 0.0010] * n,
        'low': [base_price - 0.0010] * n,
        'close': [base_price + 0.0005] * n,
        'volume': [500] * n
    }, index=pd.DatetimeIndex(times))


# Pre-defined scenario parameters for parametrized tests
SCENARIO_PARAMS = {
    'strong_uptrend': {
        'generator': generate_trending_candles,
        'kwargs': {'n': 100, 'direction': 'up', 'pip_range': 150, 'seed': 100}
    },
    'strong_downtrend': {
        'generator': generate_trending_candles,
        'kwargs': {'n': 100, 'direction': 'down', 'pip_range': 150, 'seed': 101}
    },
    'weak_uptrend': {
        'generator': generate_trending_candles,
        'kwargs': {'n': 100, 'direction': 'up', 'pip_range': 30, 'volatility': 0.0008, 'seed': 102}
    },
    'buy_crossover': {
        'generator': generate_reversal_candles,
        'kwargs': {'n': 100, 'initial_direction': 'down', 'reversal_point': 0.75, 'seed': 103}
    },
    'sell_crossover': {
        'generator': generate_reversal_candles,
        'kwargs': {'n': 100, 'initial_direction': 'up', 'reversal_point': 0.75, 'seed': 104}
    },
    'ranging_market': {
        'generator': generate_ranging_candles,
        'kwargs': {'n': 100, 'range_pips': 15, 'seed': 105}
    }
}


def get_scenario_candles(scenario_name):
    """Get candle data for a named scenario."""
    if scenario_name not in SCENARIO_PARAMS:
        raise ValueError(f"Unknown scenario: {scenario_name}")

    params = SCENARIO_PARAMS[scenario_name]
    return params['generator'](**params['kwargs'])
