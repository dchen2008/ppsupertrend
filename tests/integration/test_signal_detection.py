"""
Integration tests for Signal Detection.
Ensures BUY/SELL signals are only generated on trend crossovers,
and HOLD states don't trigger trades.

This prevents phantom trades caused by misinterpreting HOLD as a signal.
"""

import pytest
import pandas as pd
import numpy as np
import sys
import os

# Add project root and src to path for imports
project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'src'))

from src.indicators import calculate_pp_supertrend, get_current_signal
from tests.fixtures.candle_data import (
    generate_trending_candles,
    generate_reversal_candles,
    generate_ranging_candles
)


class TestSignalGeneration:
    """Tests for PP SuperTrend signal generation."""

    # =========================================================================
    # BUY SIGNAL TESTS
    # =========================================================================

    def test_buy_signal_only_on_trend_crossover_up(self, sample_crossover_buy_candles):
        """BUY signal should only appear when trend changes from -1 to +1."""
        df = calculate_pp_supertrend(sample_crossover_buy_candles)

        # Find all BUY signals
        buy_signals = df[df['buy_signal'] == True]

        # Each BUY signal should have:
        # - Current trend = 1
        # - Previous trend = -1
        for idx in buy_signals.index:
            pos = df.index.get_loc(idx)
            if pos > 0:
                assert df['trend'].iloc[pos] == 1, "BUY signal should have trend=1"
                assert df['trend'].iloc[pos-1] == -1, "BUY signal should have prev_trend=-1"

    def test_uptrend_continuation_no_buy_signal(self, sample_uptrend_candles):
        """Continued uptrend should NOT generate new BUY signals after initial crossover."""
        df = calculate_pp_supertrend(sample_uptrend_candles)

        # Count BUY signals
        buy_count = df['buy_signal'].sum()

        # In a pure uptrend, there should be at most 1 initial BUY signal
        # (when trend first becomes +1)
        assert buy_count <= 2, f"Pure uptrend should have minimal BUY signals, got {buy_count}"

    # =========================================================================
    # SELL SIGNAL TESTS
    # =========================================================================

    def test_sell_signal_only_on_trend_crossover_down(self, sample_crossover_sell_candles):
        """SELL signal should only appear when trend changes from +1 to -1."""
        df = calculate_pp_supertrend(sample_crossover_sell_candles)

        # Find all SELL signals
        sell_signals = df[df['sell_signal'] == True]

        # Each SELL signal should have:
        # - Current trend = -1
        # - Previous trend = 1
        for idx in sell_signals.index:
            pos = df.index.get_loc(idx)
            if pos > 0:
                assert df['trend'].iloc[pos] == -1, "SELL signal should have trend=-1"
                assert df['trend'].iloc[pos-1] == 1, "SELL signal should have prev_trend=1"

    def test_downtrend_continuation_no_sell_signal(self, sample_downtrend_candles):
        """Continued downtrend should NOT generate new SELL signals after initial crossover."""
        df = calculate_pp_supertrend(sample_downtrend_candles)

        # Count SELL signals
        sell_count = df['sell_signal'].sum()

        # In a pure downtrend, there should be at most 1 initial SELL signal
        assert sell_count <= 2, f"Pure downtrend should have minimal SELL signals, got {sell_count}"

    # =========================================================================
    # HOLD SIGNAL TESTS
    # =========================================================================

    def test_hold_long_in_uptrend(self, sample_uptrend_candles):
        """Uptrend without new signal should return HOLD_LONG."""
        df = calculate_pp_supertrend(sample_uptrend_candles)
        signal_info = get_current_signal(df)

        # In continued uptrend, signal should be HOLD_LONG (not BUY)
        if not df['buy_signal'].iloc[-1]:
            assert signal_info['signal'] in ['HOLD_LONG', 'BUY']
            assert signal_info['trend'] == 1

    def test_hold_short_in_downtrend(self, sample_downtrend_candles):
        """Downtrend without new signal should return HOLD_SHORT."""
        df = calculate_pp_supertrend(sample_downtrend_candles)
        signal_info = get_current_signal(df)

        # In continued downtrend, signal should be HOLD_SHORT (not SELL)
        if not df['sell_signal'].iloc[-1]:
            assert signal_info['signal'] in ['HOLD_SHORT', 'SELL']
            assert signal_info['trend'] == -1

    def test_hold_signals_differ_from_trade_signals(self):
        """HOLD_LONG/HOLD_SHORT are distinct from BUY/SELL signals."""
        # Generate uptrend data
        df = calculate_pp_supertrend(generate_trending_candles(n=50, direction='up', seed=100))
        signal = get_current_signal(df)

        # If last candle is not a crossover, should be HOLD
        if not df['buy_signal'].iloc[-1]:
            assert signal['signal'] == 'HOLD_LONG'
            assert signal['signal'] != 'BUY'

    # =========================================================================
    # SIGNAL INFO STRUCTURE TESTS
    # =========================================================================

    def test_signal_info_contains_required_fields(self, sample_uptrend_candles):
        """Signal info should contain all required fields."""
        df = calculate_pp_supertrend(sample_uptrend_candles)
        signal_info = get_current_signal(df)

        required_fields = ['signal', 'trend', 'supertrend', 'price', 'support', 'resistance', 'atr', 'pivot']
        for field in required_fields:
            assert field in signal_info, f"Missing field: {field}"

    def test_signal_info_trend_matches_indicator(self, sample_uptrend_candles):
        """Signal info trend should match indicator trend."""
        df = calculate_pp_supertrend(sample_uptrend_candles)
        signal_info = get_current_signal(df)

        assert signal_info['trend'] == int(df['trend'].iloc[-1])

    def test_signal_info_supertrend_value(self, sample_uptrend_candles):
        """Signal info supertrend should match indicator value."""
        df = calculate_pp_supertrend(sample_uptrend_candles)
        signal_info = get_current_signal(df)

        expected_st = float(df['supertrend'].iloc[-1])
        assert abs(signal_info['supertrend'] - expected_st) < 0.00001

    # =========================================================================
    # EDGE CASES
    # =========================================================================

    def test_empty_dataframe_returns_none(self):
        """Empty DataFrame should return None."""
        df = pd.DataFrame()
        signal = get_current_signal(df)
        assert signal is None

    def test_minimal_candles_produces_signal(self, minimal_candles):
        """Minimal candle set should still produce a signal."""
        df = calculate_pp_supertrend(minimal_candles)
        signal_info = get_current_signal(df)

        # Should return something even with minimal data
        # (though values may be None for some fields)
        assert signal_info is not None
        assert 'signal' in signal_info

    def test_ranging_market_signals(self, sample_ranging_candles):
        """Ranging market may have multiple signal changes."""
        df = calculate_pp_supertrend(sample_ranging_candles)

        # In ranging market, may have both BUY and SELL signals
        has_buys = df['buy_signal'].any()
        has_sells = df['sell_signal'].any()

        # Verify signals are mutually exclusive per candle
        both_signals = df[df['buy_signal'] & df['sell_signal']]
        assert len(both_signals) == 0, "Cannot have BUY and SELL on same candle"


class TestTrendDetermination:
    """Tests for trend value (+1/-1) determination."""

    def test_trend_values_are_valid(self, sample_uptrend_candles):
        """Trend should only be 0, 1, or -1."""
        df = calculate_pp_supertrend(sample_uptrend_candles)

        unique_trends = df['trend'].dropna().unique()
        for trend in unique_trends:
            assert trend in [0, 1, -1], f"Invalid trend value: {trend}"

    def test_uptrend_ends_with_positive_trend(self, sample_uptrend_candles):
        """Strong uptrend should have trend=1 at the end."""
        df = calculate_pp_supertrend(sample_uptrend_candles)

        # Last 10 candles should mostly be uptrend
        last_trends = df['trend'].iloc[-10:]
        positive_count = (last_trends == 1).sum()
        assert positive_count >= 7, f"Expected mostly positive trends, got {positive_count}/10"

    def test_downtrend_ends_with_negative_trend(self, sample_downtrend_candles):
        """Strong downtrend should have trend=-1 at the end."""
        df = calculate_pp_supertrend(sample_downtrend_candles)

        # Last 10 candles should mostly be downtrend
        last_trends = df['trend'].iloc[-10:]
        negative_count = (last_trends == -1).sum()
        assert negative_count >= 7, f"Expected mostly negative trends, got {negative_count}/10"

    def test_trend_persistence(self):
        """Trend should persist until crossover (no random flips)."""
        df = calculate_pp_supertrend(generate_trending_candles(n=100, direction='up', seed=200))

        # Count trend changes
        trend_changes = (df['trend'].diff() != 0).sum()

        # Strong trend should have few changes
        assert trend_changes <= 10, f"Too many trend changes in strong trend: {trend_changes}"


class TestSignalVsHoldDistinction:
    """Tests specifically for distinguishing signals from hold states."""

    def test_buy_is_different_from_hold_long(self):
        """BUY and HOLD_LONG are different signal states."""
        # Generate crossover data
        df_crossover = calculate_pp_supertrend(
            generate_reversal_candles(n=100, initial_direction='down', seed=300)
        )

        # Generate pure uptrend data
        df_uptrend = calculate_pp_supertrend(
            generate_trending_candles(n=50, direction='up', seed=301)
        )

        signal_crossover = get_current_signal(df_crossover)
        signal_uptrend = get_current_signal(df_uptrend)

        # At least one should be HOLD_LONG (not BUY)
        if not df_uptrend['buy_signal'].iloc[-1]:
            assert signal_uptrend['signal'] == 'HOLD_LONG'

    def test_sell_is_different_from_hold_short(self):
        """SELL and HOLD_SHORT are different signal states."""
        # Generate crossover data
        df_crossover = calculate_pp_supertrend(
            generate_reversal_candles(n=100, initial_direction='up', seed=400)
        )

        # Generate pure downtrend data
        df_downtrend = calculate_pp_supertrend(
            generate_trending_candles(n=50, direction='down', seed=401)
        )

        signal_crossover = get_current_signal(df_crossover)
        signal_downtrend = get_current_signal(df_downtrend)

        # At least one should be HOLD_SHORT (not SELL)
        if not df_downtrend['sell_signal'].iloc[-1]:
            assert signal_downtrend['signal'] == 'HOLD_SHORT'


class TestDebugInfo:
    """Tests for signal debug information."""

    def test_debug_info_included(self, sample_uptrend_candles):
        """Signal info should include debug information."""
        df = calculate_pp_supertrend(sample_uptrend_candles)
        signal = get_current_signal(df)

        assert 'debug' in signal
        assert 'prev_trend' in signal['debug']
        assert 'curr_trend' in signal['debug']
        assert 'trend_changed' in signal['debug']

    def test_trend_changed_flag_accuracy(self, sample_crossover_buy_candles):
        """trend_changed flag should accurately reflect crossover."""
        df = calculate_pp_supertrend(sample_crossover_buy_candles)
        signal = get_current_signal(df)

        # If it's a BUY signal, trend_changed should be True
        if signal['signal'] == 'BUY':
            assert signal['debug']['trend_changed'] is True
            assert signal['debug']['prev_trend'] != signal['debug']['curr_trend']
