#!/usr/bin/env python3
"""
Enhanced Signal Filter for OANDA Bot
Reduces false signals by implementing additional validation checks
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def enhanced_signal_filter(df_with_indicators, current_signal, lookback_periods=3):
    """
    Enhanced signal filtering to reduce false positives
    
    Args:
        df_with_indicators: DataFrame with PP SuperTrend calculations
        current_signal: Current signal from get_current_signal()
        lookback_periods: Number of periods to look back for validation
        
    Returns:
        dict: Filtered signal with validation results
    """
    
    if not current_signal or current_signal['signal'] in ['HOLD', 'HOLD_LONG', 'HOLD_SHORT']:
        return current_signal
    
    # Get current index
    current_idx = len(df_with_indicators) - 1
    
    # Validation checks
    validations = {
        'trend_strength': False,
        'price_momentum': False, 
        'volatility_check': False,
        'support_resistance': False
    }
    
    # 1. Trend Strength Validation
    if current_idx >= lookback_periods:
        recent_trends = df_with_indicators['trend'].iloc[current_idx-lookback_periods:current_idx]
        trend_consistency = len(recent_trends[recent_trends == current_signal['trend']]) / len(recent_trends)
        validations['trend_strength'] = trend_consistency >= 0.6  # 60% trend consistency
    
    # 2. Price Momentum Validation
    if current_idx >= lookback_periods:
        recent_closes = df_with_indicators['close'].iloc[current_idx-lookback_periods:current_idx+1]
        price_direction = (recent_closes.iloc[-1] - recent_closes.iloc[0]) / recent_closes.iloc[0]
        
        if current_signal['signal'] == 'BUY':
            validations['price_momentum'] = price_direction > -0.0005  # Not falling too fast
        elif current_signal['signal'] == 'SELL':
            validations['price_momentum'] = price_direction < 0.0005   # Not rising too fast
    
    # 3. Volatility Check (ATR-based)
    if current_idx >= 10:  # Need enough data for ATR
        current_atr = df_with_indicators['atr'].iloc[current_idx]
        avg_atr = df_with_indicators['atr'].iloc[current_idx-10:current_idx].mean()
        
        # Reject signals during extremely high volatility
        validations['volatility_check'] = current_atr <= avg_atr * 2.0
    
    # 4. Support/Resistance Validation
    current_price = current_signal['price']
    support_level = current_signal.get('support', 0)
    resistance_level = current_signal.get('resistance', 0)
    
    if support_level and resistance_level:
        if current_signal['signal'] == 'BUY':
            # Buy signal should be near support
            distance_to_support = abs(current_price - support_level) / current_price
            validations['support_resistance'] = distance_to_support <= 0.002  # Within 0.2%
        elif current_signal['signal'] == 'SELL':
            # Sell signal should be near resistance
            distance_to_resistance = abs(current_price - resistance_level) / current_price
            validations['support_resistance'] = distance_to_resistance <= 0.002  # Within 0.2%
    
    # Calculate validation score
    validation_score = sum(validations.values()) / len(validations)
    
    # Enhanced signal with validation info
    enhanced_signal = current_signal.copy()
    enhanced_signal['validations'] = validations
    enhanced_signal['validation_score'] = validation_score
    enhanced_signal['filter_passed'] = validation_score >= 0.6  # 60% threshold
    
    # Override signal if validation fails
    if not enhanced_signal['filter_passed']:
        enhanced_signal['signal'] = 'HOLD_FILTERED'
        enhanced_signal['filter_reason'] = f"Failed validation (score: {validation_score:.2f})"
    
    return enhanced_signal

def volume_based_filter(df_with_indicators, current_signal, min_volume_percentile=30):
    """
    Additional volume-based filtering
    """
    if not current_signal or 'volume' not in df_with_indicators.columns:
        return current_signal
        
    current_volume = df_with_indicators['volume'].iloc[-1]
    volume_percentile = df_with_indicators['volume'].rolling(50).quantile(min_volume_percentile/100).iloc[-1]
    
    # Require minimum volume for signal validity
    if current_volume < volume_percentile:
        enhanced_signal = current_signal.copy()
        enhanced_signal['signal'] = 'HOLD_LOW_VOLUME'
        enhanced_signal['volume_filter'] = f"Volume too low: {current_volume} < {volume_percentile:.0f}"
        return enhanced_signal
    
    return current_signal

# Example integration into existing bot
def get_filtered_signal(df):
    """
    Enhanced signal detection with filtering
    """
    from indicators import calculate_pp_supertrend, get_current_signal
    
    # Calculate indicators (existing logic)
    df_with_indicators = calculate_pp_supertrend(
        df,
        pivot_period=2,
        atr_factor=3.0,
        atr_period=10
    )
    
    # Get raw signal
    raw_signal = get_current_signal(df_with_indicators)
    
    # Apply enhanced filtering
    filtered_signal = enhanced_signal_filter(df_with_indicators, raw_signal)
    
    # Apply volume filtering
    final_signal = volume_based_filter(df_with_indicators, filtered_signal)
    
    return final_signal, df_with_indicators

if __name__ == "__main__":
    print("Enhanced Signal Filter Module")
    print("This module provides additional validation for PP SuperTrend signals")
    print("Integration: Replace get_current_signal() with get_filtered_signal()")