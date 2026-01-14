"""
Integration tests for Disable Opposite Trade filter.
Prevents trades against the 3H market trend when enabled.

BEAR market (3H = SELL) → Block LONG, allow SHORT
BULL market (3H = BUY) → Block SHORT, allow LONG
"""

import pytest
import pandas as pd
import sys
import os

# Add project root and src to path for imports
project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'src'))

from src.risk_manager import RiskManager


class TestDisableOppositeTrade:
    """Tests for the disable_opposite_trade filter."""

    @pytest.fixture
    def risk_manager(self):
        return RiskManager()

    @pytest.fixture
    def config_enabled(self):
        """Config with disable_opposite_trade enabled."""
        return {
            'position_sizing': {
                'use_dynamic': True,
                'disable_opposite_trade': True,
                'bear': {'short_risk_per_trade': 300, 'long_risk_per_trade': 100},
                'bull': {'short_risk_per_trade': 100, 'long_risk_per_trade': 300}
            }
        }

    @pytest.fixture
    def config_disabled(self):
        """Config with disable_opposite_trade disabled."""
        return {
            'position_sizing': {
                'use_dynamic': True,
                'disable_opposite_trade': False,
                'bear': {'short_risk_per_trade': 300, 'long_risk_per_trade': 100},
                'bull': {'short_risk_per_trade': 100, 'long_risk_per_trade': 300}
            }
        }

    # =========================================================================
    # BEAR MARKET TESTS
    # =========================================================================

    def test_bear_market_blocks_long_trade(self, risk_manager, buy_signal_info, config_enabled):
        """In BEAR market with filter enabled, LONG trade should be blocked."""
        candle_time = pd.Timestamp('2026-01-10T14:00:00+00:00')

        should_trade, action, _ = risk_manager.should_trade(
            buy_signal_info,
            None,  # No position
            candle_time,
            None,
            market_trend='BEAR',
            config=config_enabled
        )

        assert should_trade is False
        assert action == 'HOLD'

    def test_bear_market_allows_short_trade(self, risk_manager, sell_signal_info, config_enabled):
        """In BEAR market with filter enabled, SHORT trade should be allowed."""
        candle_time = pd.Timestamp('2026-01-10T14:00:00+00:00')

        should_trade, action, _ = risk_manager.should_trade(
            sell_signal_info,
            None,  # No position
            candle_time,
            None,
            market_trend='BEAR',
            config=config_enabled
        )

        assert should_trade is True
        assert action == 'OPEN_SHORT'

    # =========================================================================
    # BULL MARKET TESTS
    # =========================================================================

    def test_bull_market_blocks_short_trade(self, risk_manager, sell_signal_info, config_enabled):
        """In BULL market with filter enabled, SHORT trade should be blocked."""
        candle_time = pd.Timestamp('2026-01-10T14:00:00+00:00')

        should_trade, action, _ = risk_manager.should_trade(
            sell_signal_info,
            None,  # No position
            candle_time,
            None,
            market_trend='BULL',
            config=config_enabled
        )

        assert should_trade is False
        assert action == 'HOLD'

    def test_bull_market_allows_long_trade(self, risk_manager, buy_signal_info, config_enabled):
        """In BULL market with filter enabled, LONG trade should be allowed."""
        candle_time = pd.Timestamp('2026-01-10T14:00:00+00:00')

        should_trade, action, _ = risk_manager.should_trade(
            buy_signal_info,
            None,  # No position
            candle_time,
            None,
            market_trend='BULL',
            config=config_enabled
        )

        assert should_trade is True
        assert action == 'OPEN_LONG'

    # =========================================================================
    # FILTER DISABLED TESTS
    # =========================================================================

    def test_filter_disabled_allows_long_in_bear(self, risk_manager, buy_signal_info, config_disabled):
        """With filter disabled, LONG trade should be allowed even in BEAR market."""
        candle_time = pd.Timestamp('2026-01-10T14:00:00+00:00')

        should_trade, action, _ = risk_manager.should_trade(
            buy_signal_info,
            None,
            candle_time,
            None,
            market_trend='BEAR',
            config=config_disabled
        )

        assert should_trade is True
        assert action == 'OPEN_LONG'

    def test_filter_disabled_allows_short_in_bull(self, risk_manager, sell_signal_info, config_disabled):
        """With filter disabled, SHORT trade should be allowed even in BULL market."""
        candle_time = pd.Timestamp('2026-01-10T14:00:00+00:00')

        should_trade, action, _ = risk_manager.should_trade(
            sell_signal_info,
            None,
            candle_time,
            None,
            market_trend='BULL',
            config=config_disabled
        )

        assert should_trade is True
        assert action == 'OPEN_SHORT'

    # =========================================================================
    # NEUTRAL MARKET TESTS
    # =========================================================================

    def test_neutral_market_allows_all_trades(self, risk_manager, buy_signal_info, sell_signal_info, config_enabled):
        """NEUTRAL market should allow all trades regardless of filter."""
        candle_time = pd.Timestamp('2026-01-10T14:00:00+00:00')

        # LONG in NEUTRAL
        should_trade_long, action_long, _ = risk_manager.should_trade(
            buy_signal_info,
            None,
            candle_time,
            None,
            market_trend='NEUTRAL',
            config=config_enabled
        )

        # SELL signal requires different candle time
        candle_time_2 = pd.Timestamp('2026-01-10T14:05:00+00:00')

        # SHORT in NEUTRAL
        should_trade_short, action_short, _ = risk_manager.should_trade(
            sell_signal_info,
            None,
            candle_time_2,
            None,
            market_trend='NEUTRAL',
            config=config_enabled
        )

        assert should_trade_long is True
        assert action_long == 'OPEN_LONG'
        assert should_trade_short is True
        assert action_short == 'OPEN_SHORT'

    def test_none_market_trend_allows_all_trades(self, risk_manager, buy_signal_info, config_enabled):
        """When market_trend is None, should allow all trades."""
        candle_time = pd.Timestamp('2026-01-10T14:00:00+00:00')

        should_trade, action, _ = risk_manager.should_trade(
            buy_signal_info,
            None,
            candle_time,
            None,
            market_trend=None,
            config=config_enabled
        )

        assert should_trade is True
        assert action == 'OPEN_LONG'

    # =========================================================================
    # TREND REVERSAL WITH FILTER
    # =========================================================================

    def test_reversal_long_to_short_in_bull_closes_only(self, risk_manager, sell_signal_info, long_position, config_enabled):
        """
        BULL market with LONG position:
        SELL signal should CLOSE the LONG but NOT open SHORT.
        """
        candle_time = pd.Timestamp('2026-01-10T14:00:00+00:00')

        should_trade, action, next_action = risk_manager.should_trade(
            sell_signal_info,
            long_position,
            candle_time,
            None,
            market_trend='BULL',
            config=config_enabled
        )

        assert should_trade is True
        assert action == 'CLOSE'
        assert next_action is None  # No SHORT opening in BULL market

    def test_reversal_short_to_long_in_bear_closes_only(self, risk_manager, buy_signal_info, short_position, config_enabled):
        """
        BEAR market with SHORT position:
        BUY signal should CLOSE the SHORT but NOT open LONG.
        """
        candle_time = pd.Timestamp('2026-01-10T14:00:00+00:00')

        should_trade, action, next_action = risk_manager.should_trade(
            buy_signal_info,
            short_position,
            candle_time,
            None,
            market_trend='BEAR',
            config=config_enabled
        )

        assert should_trade is True
        assert action == 'CLOSE'
        assert next_action is None  # No LONG opening in BEAR market

    def test_reversal_long_to_short_in_bear_closes_and_opens(self, risk_manager, sell_signal_info, long_position, config_enabled):
        """
        BEAR market with LONG position:
        SELL signal should CLOSE the LONG AND open SHORT (favored direction).
        """
        candle_time = pd.Timestamp('2026-01-10T14:00:00+00:00')

        should_trade, action, next_action = risk_manager.should_trade(
            sell_signal_info,
            long_position,
            candle_time,
            None,
            market_trend='BEAR',
            config=config_enabled
        )

        assert should_trade is True
        assert action == 'CLOSE'
        assert next_action == 'OPEN_SHORT'  # SHORT allowed in BEAR market

    def test_reversal_short_to_long_in_bull_closes_and_opens(self, risk_manager, buy_signal_info, short_position, config_enabled):
        """
        BULL market with SHORT position:
        BUY signal should CLOSE the SHORT AND open LONG (favored direction).
        """
        candle_time = pd.Timestamp('2026-01-10T14:00:00+00:00')

        should_trade, action, next_action = risk_manager.should_trade(
            buy_signal_info,
            short_position,
            candle_time,
            None,
            market_trend='BULL',
            config=config_enabled
        )

        assert should_trade is True
        assert action == 'CLOSE'
        assert next_action == 'OPEN_LONG'  # LONG allowed in BULL market

    # =========================================================================
    # FILTER DISABLED REVERSAL TESTS
    # =========================================================================

    def test_reversal_with_filter_disabled_always_opens(self, risk_manager, sell_signal_info, long_position, config_disabled):
        """With filter disabled, reversal should always open opposite position."""
        candle_time = pd.Timestamp('2026-01-10T14:00:00+00:00')

        should_trade, action, next_action = risk_manager.should_trade(
            sell_signal_info,
            long_position,
            candle_time,
            None,
            market_trend='BULL',  # Even in BULL, should open SHORT
            config=config_disabled
        )

        assert should_trade is True
        assert action == 'CLOSE'
        assert next_action == 'OPEN_SHORT'

    # =========================================================================
    # CONFIG EDGE CASES
    # =========================================================================

    def test_missing_config_allows_all_trades(self, risk_manager, buy_signal_info):
        """When config is None, should allow all trades."""
        candle_time = pd.Timestamp('2026-01-10T14:00:00+00:00')

        should_trade, action, _ = risk_manager.should_trade(
            buy_signal_info,
            None,
            candle_time,
            None,
            market_trend='BEAR',
            config=None  # No config
        )

        assert should_trade is True
        assert action == 'OPEN_LONG'

    def test_empty_position_sizing_config_allows_all_trades(self, risk_manager, buy_signal_info):
        """Empty position_sizing config should allow all trades."""
        candle_time = pd.Timestamp('2026-01-10T14:00:00+00:00')
        config = {'position_sizing': {}}  # Empty

        should_trade, action, _ = risk_manager.should_trade(
            buy_signal_info,
            None,
            candle_time,
            None,
            market_trend='BEAR',
            config=config
        )

        assert should_trade is True


class TestMarketTrendValues:
    """Tests for different market_trend value handling."""

    @pytest.fixture
    def risk_manager(self):
        return RiskManager()

    @pytest.fixture
    def config_enabled(self):
        return {
            'position_sizing': {
                'disable_opposite_trade': True
            }
        }

    @pytest.mark.parametrize("market_trend,signal,expected_action", [
        ('BEAR', 'BUY', 'HOLD'),      # Blocked
        ('BEAR', 'SELL', 'OPEN_SHORT'),  # Allowed
        ('BULL', 'BUY', 'OPEN_LONG'),    # Allowed
        ('BULL', 'SELL', 'HOLD'),      # Blocked
        ('NEUTRAL', 'BUY', 'OPEN_LONG'),  # Allowed
        ('NEUTRAL', 'SELL', 'OPEN_SHORT'),  # Allowed
        (None, 'BUY', 'OPEN_LONG'),    # Allowed
        (None, 'SELL', 'OPEN_SHORT'),   # Allowed
    ])
    def test_market_trend_signal_combinations(
        self, risk_manager, config_enabled, market_trend, signal, expected_action
    ):
        """Test all market_trend × signal combinations."""
        candle_time = pd.Timestamp('2026-01-10T14:00:00+00:00')

        signal_info = {
            'signal': signal,
            'trend': 1 if signal == 'BUY' else -1,
            'supertrend': 1.10000,
            'price': 1.10050,
            'support': 1.09900,
            'resistance': 1.10200,
            'atr': 0.00100,
            'pivot': 1.10000
        }

        should_trade, action, _ = risk_manager.should_trade(
            signal_info,
            None,
            candle_time,
            None,
            market_trend=market_trend,
            config=config_enabled
        )

        if expected_action == 'HOLD':
            assert should_trade is False
            assert action == 'HOLD'
        else:
            assert should_trade is True
            assert action == expected_action
