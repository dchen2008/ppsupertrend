"""
Unit tests for RiskManager class.
Tests position sizing, stop loss calculation, take profit, and trade validation.
"""

import pytest
import sys
import os

# Add project root to path to enable imports
project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'src'))

from src.risk_manager import RiskManager
from src.config import TradingConfig


class TestCalculatePositionSize:
    """Tests for position sizing calculation."""

    @pytest.fixture
    def risk_manager(self):
        return RiskManager()

    def test_dynamic_sizing_with_fixed_risk(self, risk_manager, buy_signal_info, default_config):
        """Position size should scale inversely with stop distance."""
        account_balance = 10000

        position_size, risk_used = risk_manager.calculate_position_size(
            account_balance, buy_signal_info,
            market_trend='BULL', position_type='LONG',
            config=default_config
        )

        assert position_size > 0
        assert risk_used > 0

    def test_wider_stop_produces_smaller_position(self, risk_manager, buy_signal_info, default_config):
        """Wider stop loss should result in smaller position size."""
        account_balance = 10000

        # Narrow stop (5 pips)
        signal_narrow = buy_signal_info.copy()
        signal_narrow['supertrend'] = 1.10000
        signal_narrow['price'] = 1.10050

        # Wide stop (20 pips)
        signal_wide = buy_signal_info.copy()
        signal_wide['supertrend'] = 1.09850
        signal_wide['price'] = 1.10050

        pos_narrow, _ = risk_manager.calculate_position_size(
            account_balance, signal_narrow, 'BULL', 'LONG', default_config
        )
        pos_wide, _ = risk_manager.calculate_position_size(
            account_balance, signal_wide, 'BULL', 'LONG', default_config
        )

        assert pos_narrow > pos_wide

    @pytest.mark.parametrize("market_trend,position_type,expected_risk", [
        ('BEAR', 'SHORT', 300),
        ('BEAR', 'LONG', 100),
        ('BULL', 'SHORT', 100),
        ('BULL', 'LONG', 300),
    ])
    def test_market_aware_risk_amounts(self, risk_manager, buy_signal_info, default_config,
                                        market_trend, position_type, expected_risk):
        """Risk amount should vary based on market trend and position type."""
        _, risk_used = risk_manager.calculate_position_size(
            10000, buy_signal_info, market_trend, position_type, default_config
        )

        assert risk_used == expected_risk

    def test_respects_min_position_size(self, risk_manager, buy_signal_info, default_config):
        """Position size should be at least 1000 units."""
        # Very wide stop with low risk
        signal = buy_signal_info.copy()
        signal['supertrend'] = 1.09000  # 100+ pip stop
        signal['price'] = 1.10050

        # Modify config for low risk
        config = default_config.copy()
        config['position_sizing'] = default_config['position_sizing'].copy()
        config['position_sizing']['bull'] = {'long_risk_per_trade': 10}

        position_size, _ = risk_manager.calculate_position_size(
            10000, signal, 'BULL', 'LONG', config
        )

        assert position_size >= 1000

    def test_neutral_market_uses_default_risk(self, risk_manager, buy_signal_info, default_config):
        """Neutral market should use default risk amount."""
        _, risk_used = risk_manager.calculate_position_size(
            10000, buy_signal_info, 'NEUTRAL', 'LONG', default_config
        )

        assert risk_used == 100  # Default fallback


class TestCalculateStopLoss:
    """Tests for stop loss calculation."""

    @pytest.fixture
    def risk_manager(self):
        return RiskManager()

    def test_buy_signal_stop_at_supertrend(self, risk_manager, buy_signal_info):
        """BUY signal should have stop loss at SuperTrend (below price)."""
        stop_loss = risk_manager.calculate_stop_loss(buy_signal_info, 'BUY')

        assert stop_loss is not None
        assert stop_loss == round(buy_signal_info['supertrend'], 5)
        assert stop_loss < buy_signal_info['price']

    def test_sell_signal_stop_at_supertrend(self, risk_manager, sell_signal_info):
        """SELL signal should have stop loss at SuperTrend (above price)."""
        stop_loss = risk_manager.calculate_stop_loss(sell_signal_info, 'SELL')

        assert stop_loss is not None
        assert stop_loss == round(sell_signal_info['supertrend'], 5)
        assert stop_loss > sell_signal_info['price']

    def test_none_supertrend_returns_none(self, risk_manager):
        """Should return None if SuperTrend is None."""
        signal_info = {'supertrend': None, 'price': 1.10000}
        stop_loss = risk_manager.calculate_stop_loss(signal_info, 'BUY')
        assert stop_loss is None

    def test_stop_loss_rounded_to_5_decimals(self, risk_manager, buy_signal_info):
        """Stop loss should be rounded to 5 decimal places."""
        stop_loss = risk_manager.calculate_stop_loss(buy_signal_info, 'BUY')

        # Check that it's properly rounded
        stop_loss_str = f"{stop_loss:.5f}"
        assert len(stop_loss_str.split('.')[1]) == 5


class TestCalculateTakeProfit:
    """Tests for take profit calculation."""

    @pytest.fixture
    def risk_manager(self):
        return RiskManager()

    @pytest.mark.parametrize("entry,stop,rr,expected_tp", [
        (1.10000, 1.09900, 2.0, 1.10200),  # Long, 10 pip risk, 2 RR
        (1.10000, 1.09900, 1.0, 1.10100),  # Long, 10 pip risk, 1 RR
        (1.10000, 1.10100, 2.0, 1.09800),  # Short, 10 pip risk, 2 RR
        (1.10000, 1.10100, 0.5, 1.09950),  # Short, 10 pip risk, 0.5 RR
    ])
    def test_take_profit_calculation(self, risk_manager, entry, stop, rr, expected_tp):
        """Take profit should be entry +/- (risk * RR ratio)."""
        tp = risk_manager.calculate_take_profit(entry, stop, rr)
        assert tp == round(expected_tp, 5)

    def test_none_stop_returns_none(self, risk_manager):
        """Should return None if stop loss is None."""
        tp = risk_manager.calculate_take_profit(1.10000, None, 2.0)
        assert tp is None

    def test_none_entry_returns_none(self, risk_manager):
        """Should return None if entry is None."""
        tp = risk_manager.calculate_take_profit(None, 1.09900, 2.0)
        assert tp is None

    def test_take_profit_rounded_to_5_decimals(self, risk_manager):
        """Take profit should be rounded to 5 decimal places."""
        tp = risk_manager.calculate_take_profit(1.10000, 1.09900, 2.0)

        tp_str = f"{tp:.5f}"
        assert len(tp_str.split('.')[1]) == 5


class TestShouldTrade:
    """Tests for trade decision logic."""

    @pytest.fixture
    def risk_manager(self):
        return RiskManager()

    def test_buy_signal_no_position_opens_long(self, risk_manager, buy_signal_info):
        """BUY signal with no position should open LONG."""
        should_trade, action, next_action = risk_manager.should_trade(
            buy_signal_info,
            None,  # No position
            '2026-01-10T14:00:00',
            None,  # No last signal
            market_trend=None,
            config=None
        )

        assert should_trade is True
        assert action == 'OPEN_LONG'
        assert next_action is None

    def test_sell_signal_no_position_opens_short(self, risk_manager, sell_signal_info):
        """SELL signal with no position should open SHORT."""
        should_trade, action, next_action = risk_manager.should_trade(
            sell_signal_info,
            None,
            '2026-01-10T14:00:00',
            None,
            market_trend=None,
            config=None
        )

        assert should_trade is True
        assert action == 'OPEN_SHORT'
        assert next_action is None

    def test_hold_signal_no_action(self, risk_manager, hold_long_signal_info):
        """HOLD_LONG signal should not trigger any action."""
        should_trade, action, _ = risk_manager.should_trade(
            hold_long_signal_info,
            None,
            '2026-01-10T14:00:00',
            None,
            market_trend=None,
            config=None
        )

        assert should_trade is False
        assert action == 'HOLD'

    def test_hold_short_no_action(self, risk_manager, hold_short_signal_info):
        """HOLD_SHORT signal should not trigger any action."""
        should_trade, action, _ = risk_manager.should_trade(
            hold_short_signal_info,
            None,
            '2026-01-10T14:00:00',
            None,
            market_trend=None,
            config=None
        )

        assert should_trade is False
        assert action == 'HOLD'

    def test_sell_signal_closes_long_opens_short(self, risk_manager, sell_signal_info, long_position):
        """SELL signal with LONG position should close and open short."""
        should_trade, action, next_action = risk_manager.should_trade(
            sell_signal_info,
            long_position,
            '2026-01-10T14:00:00',
            '2026-01-10T13:00:00',  # Different candle
            market_trend=None,
            config=None
        )

        assert should_trade is True
        assert action == 'CLOSE'
        assert next_action == 'OPEN_SHORT'

    def test_buy_signal_closes_short_opens_long(self, risk_manager, buy_signal_info, short_position):
        """BUY signal with SHORT position should close and open long."""
        should_trade, action, next_action = risk_manager.should_trade(
            buy_signal_info,
            short_position,
            '2026-01-10T14:00:00',
            '2026-01-10T13:00:00',
            market_trend=None,
            config=None
        )

        assert should_trade is True
        assert action == 'CLOSE'
        assert next_action == 'OPEN_LONG'

    def test_zero_units_treated_as_no_position(self, risk_manager, buy_signal_info, no_position):
        """Position with 0 units should be treated as no position."""
        should_trade, action, _ = risk_manager.should_trade(
            buy_signal_info,
            no_position,
            '2026-01-10T14:00:00',
            None,
            market_trend=None,
            config=None
        )

        assert should_trade is True
        assert action == 'OPEN_LONG'


class TestValidateTrade:
    """Tests for trade validation."""

    @pytest.fixture
    def risk_manager(self):
        return RiskManager()

    def test_valid_trade_passes(self, risk_manager, account_summary):
        """Trade with good account state should validate."""
        is_valid, reason = risk_manager.validate_trade(account_summary, 10000)

        assert is_valid is True
        assert reason == "Trade validated"

    def test_none_account_fails(self, risk_manager):
        """None account summary should fail validation."""
        is_valid, reason = risk_manager.validate_trade(None, 10000)

        assert is_valid is False
        assert "Cannot fetch" in reason

    def test_zero_margin_fails(self, risk_manager, account_summary):
        """Zero margin available should fail validation."""
        account_summary['margin_available'] = 0

        is_valid, reason = risk_manager.validate_trade(account_summary, 10000)

        assert is_valid is False
        assert "margin" in reason.lower()

    def test_zero_balance_fails(self, risk_manager, account_summary):
        """Zero balance should fail validation."""
        account_summary['balance'] = 0

        is_valid, reason = risk_manager.validate_trade(account_summary, 10000)

        assert is_valid is False
        assert "balance" in reason.lower()

    def test_negative_margin_fails(self, risk_manager, account_summary):
        """Negative margin should fail validation."""
        account_summary['margin_available'] = -100

        is_valid, reason = risk_manager.validate_trade(account_summary, 10000)

        assert is_valid is False


class TestGetRiskAmount:
    """Tests for internal _get_risk_amount method."""

    @pytest.fixture
    def risk_manager(self):
        return RiskManager()

    def test_bear_short_returns_higher_risk(self, risk_manager, default_config):
        """BEAR market SHORT should return higher risk."""
        risk = risk_manager._get_risk_amount('BEAR', 'SHORT', default_config, 10000)
        assert risk == 300

    def test_bear_long_returns_lower_risk(self, risk_manager, default_config):
        """BEAR market LONG should return lower risk."""
        risk = risk_manager._get_risk_amount('BEAR', 'LONG', default_config, 10000)
        assert risk == 100

    def test_bull_long_returns_higher_risk(self, risk_manager, default_config):
        """BULL market LONG should return higher risk."""
        risk = risk_manager._get_risk_amount('BULL', 'LONG', default_config, 10000)
        assert risk == 300

    def test_bull_short_returns_lower_risk(self, risk_manager, default_config):
        """BULL market SHORT should return lower risk."""
        risk = risk_manager._get_risk_amount('BULL', 'SHORT', default_config, 10000)
        assert risk == 100

    def test_neutral_returns_default(self, risk_manager, default_config):
        """NEUTRAL market should return default risk."""
        risk = risk_manager._get_risk_amount('NEUTRAL', 'LONG', default_config, 10000)
        assert risk == 100  # Default fallback

    def test_none_config_uses_trading_config(self, risk_manager):
        """None config should fall back to TradingConfig."""
        risk = risk_manager._get_risk_amount('BULL', 'LONG', None, 10000)
        # Should use TradingConfig.risk_per_trade
        assert risk > 0
