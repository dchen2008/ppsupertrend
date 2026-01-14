"""
Shared pytest fixtures for the trading bot test suite.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch
import tempfile
import os
import sys
import json

# Add project root and src to path for imports
project_root = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'src'))

from tests.mocks.mock_oanda import MockOANDAClient, create_mock_client_with_scenario
from tests.fixtures.candle_data import (
    generate_trending_candles,
    generate_reversal_candles,
    generate_ranging_candles,
    generate_minimal_candles
)


# ============================================================================
# MOCK OANDA CLIENT FIXTURES
# ============================================================================

@pytest.fixture
def mock_oanda_client():
    """
    Create a fully mocked OANDAClient that doesn't hit real API.
    All methods return sensible defaults that can be overridden in tests.
    """
    return MockOANDAClient(initial_balance=10000.0)


@pytest.fixture
def mock_client_with_long_position():
    """Mock client with an existing LONG position."""
    return create_mock_client_with_scenario('long_position')


@pytest.fixture
def mock_client_with_short_position():
    """Mock client with an existing SHORT position."""
    return create_mock_client_with_scenario('short_position')


@pytest.fixture
def mock_client_low_margin():
    """Mock client with limited margin."""
    return create_mock_client_with_scenario('low_margin')


# ============================================================================
# CANDLE DATA FIXTURES
# ============================================================================

@pytest.fixture
def sample_uptrend_candles():
    """
    Generate 100 candles showing a clear uptrend.
    Prices gradually increase with small retracements.
    """
    return generate_trending_candles(n=100, direction='up', pip_range=100, seed=42)


@pytest.fixture
def sample_downtrend_candles():
    """
    Generate 100 candles showing a clear downtrend.
    """
    return generate_trending_candles(n=100, direction='down', pip_range=100, seed=43)


@pytest.fixture
def sample_crossover_buy_candles():
    """
    Generate candles that produce a BUY signal at the end.
    Downtrend followed by upward reversal crossing above SuperTrend.
    """
    return generate_reversal_candles(n=100, initial_direction='down', reversal_point=0.75, seed=44)


@pytest.fixture
def sample_crossover_sell_candles():
    """
    Generate candles that produce a SELL signal at the end.
    Uptrend followed by downward reversal crossing below SuperTrend.
    """
    return generate_reversal_candles(n=100, initial_direction='up', reversal_point=0.75, seed=45)


@pytest.fixture
def sample_ranging_candles():
    """Generate ranging/sideways candles."""
    return generate_ranging_candles(n=100, range_pips=20, seed=46)


@pytest.fixture
def minimal_candles():
    """Minimal valid candle set (20 candles) for edge case testing."""
    return generate_minimal_candles(n=20)


# ============================================================================
# CONFIG FIXTURES
# ============================================================================

@pytest.fixture
def default_config():
    """Default bot configuration matching src/config.yaml."""
    return {
        'check_interval': 60,
        'market': {
            'indicator': 'ppsupertrend',
            'timeframe': 'H3'
        },
        'stoploss': {
            'type': 'PPSuperTrend',
            'spread_buffer_pips': 3
        },
        'risk_reward': {
            'bear_market': {'short_rr': 2.0, 'long_rr': 0.8},
            'bull_market': {'short_rr': 0.8, 'long_rr': 2.0}
        },
        'position_sizing': {
            'use_dynamic': True,
            'disable_opposite_trade': True,
            'bear': {'short_risk_per_trade': 300, 'long_risk_per_trade': 100},
            'bull': {'short_risk_per_trade': 100, 'long_risk_per_trade': 300}
        },
        'scalping': {
            'enabled': False
        },
        'backtest': {
            'initial_balance': 10000
        }
    }


@pytest.fixture
def config_opposite_trade_disabled(default_config):
    """Config with disable_opposite_trade enabled."""
    config = default_config.copy()
    config['position_sizing'] = default_config['position_sizing'].copy()
    config['position_sizing']['disable_opposite_trade'] = True
    return config


@pytest.fixture
def config_opposite_trade_allowed(default_config):
    """Config with disable_opposite_trade disabled."""
    config = default_config.copy()
    config['position_sizing'] = default_config['position_sizing'].copy()
    config['position_sizing']['disable_opposite_trade'] = False
    return config


# ============================================================================
# SIGNAL INFO FIXTURES
# ============================================================================

@pytest.fixture
def buy_signal_info():
    """Standard BUY signal with typical values."""
    return {
        'signal': 'BUY',
        'trend': 1,
        'supertrend': 1.09900,
        'price': 1.10050,
        'support': 1.09850,
        'resistance': 1.10200,
        'atr': 0.00120,
        'pivot': 1.10000
    }


@pytest.fixture
def sell_signal_info():
    """Standard SELL signal with typical values."""
    return {
        'signal': 'SELL',
        'trend': -1,
        'supertrend': 1.10150,
        'price': 1.10000,
        'support': 1.09850,
        'resistance': 1.10200,
        'atr': 0.00120,
        'pivot': 1.10000
    }


@pytest.fixture
def hold_long_signal_info():
    """HOLD_LONG signal (in uptrend, no new signal)."""
    return {
        'signal': 'HOLD_LONG',
        'trend': 1,
        'supertrend': 1.09950,
        'price': 1.10100,
        'support': 1.09900,
        'resistance': 1.10250,
        'atr': 0.00100,
        'pivot': 1.10050
    }


@pytest.fixture
def hold_short_signal_info():
    """HOLD_SHORT signal (in downtrend, no new signal)."""
    return {
        'signal': 'HOLD_SHORT',
        'trend': -1,
        'supertrend': 1.10100,
        'price': 1.09950,
        'support': 1.09850,
        'resistance': 1.10150,
        'atr': 0.00100,
        'pivot': 1.10000
    }


# ============================================================================
# POSITION FIXTURES
# ============================================================================

@pytest.fixture
def long_position():
    """Mock LONG position."""
    return {
        'instrument': 'EUR_USD',
        'units': 10000,
        'side': 'LONG',
        'unrealized_pl': 50.0
    }


@pytest.fixture
def short_position():
    """Mock SHORT position."""
    return {
        'instrument': 'EUR_USD',
        'units': -10000,
        'side': 'SHORT',
        'unrealized_pl': -25.0
    }


@pytest.fixture
def no_position():
    """No position (units = 0)."""
    return {
        'instrument': 'EUR_USD',
        'units': 0,
        'side': 'NONE',
        'unrealized_pl': 0.0
    }


# ============================================================================
# ACCOUNT SUMMARY FIXTURE
# ============================================================================

@pytest.fixture
def account_summary():
    """Standard account summary for testing."""
    return {
        'balance': 10000.0,
        'unrealized_pl': 0.0,
        'nav': 10000.0,
        'margin_used': 0.0,
        'margin_available': 10000.0,
        'open_trade_count': 0,
        'open_position_count': 0
    }


# ============================================================================
# TEMPORARY STATE FILE FIXTURES
# ============================================================================

@pytest.fixture
def temp_state_dir(tmp_path):
    """Create a temporary directory for state files."""
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    return state_dir


@pytest.fixture
def temp_state_file(temp_state_dir):
    """Create a temporary state file path."""
    return temp_state_dir / 'EUR_USD_5m_state.json'


@pytest.fixture
def existing_state_file(temp_state_file):
    """Create a state file with existing data."""
    state_data = {
        'last_signal_candle_time': '2026-01-10T14:25:00+00:00',
        'updated_at': '2026-01-10T14:26:00'
    }
    with open(temp_state_file, 'w') as f:
        json.dump(state_data, f)
    return temp_state_file


# ============================================================================
# RISK MANAGER FIXTURE
# ============================================================================

@pytest.fixture
def risk_manager():
    """Create a fresh RiskManager instance."""
    from src.risk_manager import RiskManager
    return RiskManager()


# ============================================================================
# TIMESTAMP FIXTURES
# ============================================================================

@pytest.fixture
def candle_time_1():
    """First candle timestamp."""
    return pd.Timestamp('2026-01-10T14:00:00+00:00')


@pytest.fixture
def candle_time_2():
    """Second candle timestamp (5 min later)."""
    return pd.Timestamp('2026-01-10T14:05:00+00:00')


@pytest.fixture
def candle_time_3():
    """Third candle timestamp (10 min later)."""
    return pd.Timestamp('2026-01-10T14:10:00+00:00')
