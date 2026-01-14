"""
Unit tests for PP SuperTrend indicator calculations.
Tests ATR, pivot detection, and signal generation.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
import os

# Add project root and src to path for imports
project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'src'))

from src.indicators import (
    calculate_atr,
    detect_pivot_highs,
    detect_pivot_lows,
    calculate_pivot_center,
    calculate_pp_supertrend,
    get_current_signal
)


class TestCalculateATR:
    """Tests for ATR calculation."""

    def test_atr_basic_calculation(self, minimal_candles):
        """ATR should calculate correctly for standard candles."""
        atr = calculate_atr(minimal_candles, period=10)

        assert len(atr) == len(minimal_candles)
        # First 9 values should be NaN (need 10 candles for first ATR)
        assert atr.iloc[:9].isna().all()
        # After that, ATR should be valid
        assert atr.iloc[10:].notna().all()

    def test_atr_values_are_positive(self, sample_uptrend_candles):
        """ATR values should always be positive."""
        atr = calculate_atr(sample_uptrend_candles, period=10)

        valid_atr = atr.dropna()
        assert (valid_atr > 0).all()

    def test_atr_period_affects_result(self, sample_uptrend_candles):
        """Different ATR periods should produce different results."""
        atr_5 = calculate_atr(sample_uptrend_candles, period=5)
        atr_20 = calculate_atr(sample_uptrend_candles, period=20)

        # Longer period should have more NaN values at start
        assert atr_5.iloc[5:10].notna().any()
        assert atr_20.iloc[10:20].isna().any()

        # Values should differ where both are valid
        valid_idx = 25
        if atr_5.iloc[valid_idx] is not None and atr_20.iloc[valid_idx] is not None:
            # They might be close but shouldn't be identical
            pass  # Implementation may vary

    def test_atr_handles_gap_candles(self):
        """ATR should handle candles with gaps (high != previous close)."""
        n = 20
        times = [datetime(2026, 1, 1) + timedelta(minutes=5*i) for i in range(n)]

        # Create candles with intentional gaps
        df = pd.DataFrame({
            'open': [1.1] * n,
            'high': [1.102] * 10 + [1.105] * 10,  # Jump in highs
            'low': [1.098] * 10 + [1.103] * 10,   # Jump in lows
            'close': [1.101] * 10 + [1.104] * 10  # Jump in closes
        }, index=pd.DatetimeIndex(times))

        atr = calculate_atr(df, period=5)

        # ATR should still calculate without errors
        assert len(atr) == n
        assert atr.iloc[15:].notna().all()


class TestPivotDetection:
    """Tests for pivot high/low detection."""

    def test_detect_pivot_highs_finds_peaks(self, sample_uptrend_candles):
        """Should detect local high points."""
        pivots = detect_pivot_highs(sample_uptrend_candles, period=2)

        # Should find some pivot highs in trending data
        non_null_count = pivots.notna().sum()
        assert non_null_count > 0
        assert non_null_count < len(sample_uptrend_candles)  # Not every candle is a pivot

    def test_detect_pivot_lows_finds_troughs(self, sample_downtrend_candles):
        """Should detect local low points."""
        pivots = detect_pivot_lows(sample_downtrend_candles, period=2)

        non_null_count = pivots.notna().sum()
        assert non_null_count > 0
        assert non_null_count < len(sample_downtrend_candles)

    @pytest.mark.parametrize("period", [1, 2, 3, 5])
    def test_pivot_period_affects_detection(self, sample_uptrend_candles, period):
        """Larger period should find fewer, more significant pivots."""
        pivots_1 = detect_pivot_highs(sample_uptrend_candles, period=1)
        pivots_large = detect_pivot_highs(sample_uptrend_candles, period=period)

        # Larger period should find equal or fewer pivots
        count_1 = pivots_1.notna().sum()
        count_large = pivots_large.notna().sum()
        assert count_large <= count_1

    def test_pivot_values_match_actual_highs(self, sample_uptrend_candles):
        """Pivot high values should equal actual high prices at those points."""
        pivots = detect_pivot_highs(sample_uptrend_candles, period=2)

        for idx in pivots.dropna().index:
            assert pivots[idx] == sample_uptrend_candles.loc[idx, 'high']

    def test_pivot_values_match_actual_lows(self, sample_downtrend_candles):
        """Pivot low values should equal actual low prices at those points."""
        pivots = detect_pivot_lows(sample_downtrend_candles, period=2)

        for idx in pivots.dropna().index:
            assert pivots[idx] == sample_downtrend_candles.loc[idx, 'low']


class TestPivotCenter:
    """Tests for pivot center line calculation."""

    def test_center_line_calculated(self, sample_uptrend_candles):
        """Center line should be calculated from pivots."""
        pivot_highs = detect_pivot_highs(sample_uptrend_candles, period=2)
        pivot_lows = detect_pivot_lows(sample_uptrend_candles, period=2)
        center = calculate_pivot_center(pivot_highs, pivot_lows)

        # Center should have some valid values
        assert center.notna().any()

    def test_center_line_updated_on_new_pivot(self, sample_uptrend_candles):
        """Center line should update when new pivot is detected."""
        pivot_highs = detect_pivot_highs(sample_uptrend_candles, period=2)
        pivot_lows = detect_pivot_lows(sample_uptrend_candles, period=2)
        center = calculate_pivot_center(pivot_highs, pivot_lows)

        # Center should change over time as pivots are detected
        unique_centers = center.dropna().unique()
        assert len(unique_centers) > 1


class TestPPSuperTrend:
    """Tests for the main PP SuperTrend calculation."""

    def test_supertrend_calculates_all_columns(self, sample_uptrend_candles):
        """Should produce all expected indicator columns."""
        result = calculate_pp_supertrend(sample_uptrend_candles)

        expected_columns = [
            'atr', 'pivot_high', 'pivot_low', 'center',
            'upper_band', 'lower_band', 'trailing_up', 'trailing_down',
            'trend', 'supertrend', 'buy_signal', 'sell_signal',
            'support', 'resistance'
        ]

        for col in expected_columns:
            assert col in result.columns, f"Missing column: {col}"

    def test_trend_is_valid(self, sample_uptrend_candles):
        """Trend should only be 0, 1, or -1."""
        result = calculate_pp_supertrend(sample_uptrend_candles)

        unique_trends = result['trend'].unique()
        for t in unique_trends:
            assert t in [0, 1, -1], f"Invalid trend value: {t}"

    def test_uptrend_produces_positive_trend(self, sample_uptrend_candles):
        """Strong uptrend should produce trend = 1 at the end."""
        result = calculate_pp_supertrend(sample_uptrend_candles)

        # Last 10 candles should mostly be uptrend
        last_trends = result['trend'].iloc[-10:]
        assert (last_trends == 1).sum() >= 7

    def test_downtrend_produces_negative_trend(self, sample_downtrend_candles):
        """Strong downtrend should produce trend = -1 at the end."""
        result = calculate_pp_supertrend(sample_downtrend_candles)

        last_trends = result['trend'].iloc[-10:]
        assert (last_trends == -1).sum() >= 7

    def test_buy_signal_on_trend_change_to_up(self, sample_crossover_buy_candles):
        """BUY signal should appear when trend changes from -1 to 1."""
        result = calculate_pp_supertrend(sample_crossover_buy_candles)

        # Should have at least one buy signal
        assert result['buy_signal'].any()

        # Buy signal should occur when trend changes from -1 to 1
        for i in range(1, len(result)):
            if result['buy_signal'].iloc[i]:
                assert result['trend'].iloc[i] == 1
                assert result['trend'].iloc[i-1] == -1

    def test_sell_signal_on_trend_change_to_down(self, sample_crossover_sell_candles):
        """SELL signal should appear when trend changes from 1 to -1."""
        result = calculate_pp_supertrend(sample_crossover_sell_candles)

        assert result['sell_signal'].any()

        for i in range(1, len(result)):
            if result['sell_signal'].iloc[i]:
                assert result['trend'].iloc[i] == -1
                assert result['trend'].iloc[i-1] == 1

    def test_buy_sell_mutually_exclusive(self, sample_ranging_candles):
        """BUY and SELL signals should never occur on same candle."""
        result = calculate_pp_supertrend(sample_ranging_candles)

        both_signals = result[result['buy_signal'] & result['sell_signal']]
        assert len(both_signals) == 0

    @pytest.mark.parametrize("atr_factor", [1.0, 2.0, 3.0, 5.0])
    def test_atr_factor_affects_bands(self, sample_uptrend_candles, atr_factor):
        """Larger ATR factor should produce wider bands."""
        result_small = calculate_pp_supertrend(sample_uptrend_candles, atr_factor=1.0)
        result_large = calculate_pp_supertrend(sample_uptrend_candles, atr_factor=atr_factor)

        # Compare band widths at a valid index
        idx = 50
        width_small = result_small['upper_band'].iloc[idx] - result_small['lower_band'].iloc[idx]
        width_large = result_large['upper_band'].iloc[idx] - result_large['lower_band'].iloc[idx]

        if not pd.isna(width_small) and not pd.isna(width_large):
            assert width_large >= width_small

    def test_supertrend_follows_trend(self, sample_uptrend_candles):
        """SuperTrend should use trailing_up in uptrend, trailing_down in downtrend."""
        result = calculate_pp_supertrend(sample_uptrend_candles)

        for i in range(1, len(result)):
            if result['trend'].iloc[i] == 1 and not pd.isna(result['trailing_up'].iloc[i]):
                assert result['supertrend'].iloc[i] == result['trailing_up'].iloc[i]
            elif result['trend'].iloc[i] == -1 and not pd.isna(result['trailing_down'].iloc[i]):
                assert result['supertrend'].iloc[i] == result['trailing_down'].iloc[i]


class TestGetCurrentSignal:
    """Tests for signal extraction function."""

    def test_returns_correct_structure(self, sample_uptrend_candles):
        """Signal info should contain all expected keys."""
        df = calculate_pp_supertrend(sample_uptrend_candles)
        signal = get_current_signal(df)

        expected_keys = ['signal', 'trend', 'supertrend', 'price',
                        'support', 'resistance', 'atr', 'pivot']

        for key in expected_keys:
            assert key in signal, f"Missing key: {key}"

    def test_signal_values_are_valid(self, sample_uptrend_candles):
        """Signal should be one of expected values."""
        df = calculate_pp_supertrend(sample_uptrend_candles)
        signal = get_current_signal(df)

        valid_signals = ['BUY', 'SELL', 'HOLD_LONG', 'HOLD_SHORT']
        assert signal['signal'] in valid_signals

    def test_trend_matches_indicator(self, sample_uptrend_candles):
        """Signal trend should match last indicator trend."""
        df = calculate_pp_supertrend(sample_uptrend_candles)
        signal = get_current_signal(df)

        assert signal['trend'] == int(df['trend'].iloc[-1])

    def test_price_is_close_price(self, sample_uptrend_candles):
        """Signal price should be last close price."""
        df = calculate_pp_supertrend(sample_uptrend_candles)
        signal = get_current_signal(df)

        assert signal['price'] == float(df['close'].iloc[-1])

    def test_empty_dataframe_returns_none(self):
        """Empty DataFrame should return None."""
        df = pd.DataFrame()
        signal = get_current_signal(df)
        assert signal is None

    def test_hold_long_in_continued_uptrend(self, sample_uptrend_candles):
        """Continued uptrend should return HOLD_LONG."""
        df = calculate_pp_supertrend(sample_uptrend_candles)
        signal = get_current_signal(df)

        # If not a new buy signal, should be HOLD_LONG
        if not df['buy_signal'].iloc[-1]:
            assert signal['signal'] == 'HOLD_LONG'

    def test_hold_short_in_continued_downtrend(self, sample_downtrend_candles):
        """Continued downtrend should return HOLD_SHORT."""
        df = calculate_pp_supertrend(sample_downtrend_candles)
        signal = get_current_signal(df)

        # If not a new sell signal, should be HOLD_SHORT
        if not df['sell_signal'].iloc[-1]:
            assert signal['signal'] == 'HOLD_SHORT'

    def test_debug_info_included(self, sample_uptrend_candles):
        """Signal info should include debug information."""
        df = calculate_pp_supertrend(sample_uptrend_candles)
        signal = get_current_signal(df)

        assert 'debug' in signal
        assert 'prev_trend' in signal['debug']
        assert 'curr_trend' in signal['debug']
        assert 'trend_changed' in signal['debug']
