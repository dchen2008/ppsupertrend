"""
Pivot Point SuperTrend Indicator Implementation
Translated from Pine Script to Python
"""

import numpy as np
import pandas as pd


def calculate_atr(df, period=14):
    """
    Calculate Average True Range (ATR)

    Args:
        df: DataFrame with 'high', 'low', 'close' columns
        period: ATR period

    Returns:
        Series with ATR values
    """
    high = df['high']
    low = df['low']
    close = df['close']

    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))

    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()

    return atr


def detect_pivot_highs(df, period=2):
    """
    Detect pivot highs

    A pivot high is a high that is higher than 'period' highs to the left
    and 'period' highs to the right

    Args:
        df: DataFrame with 'high' column
        period: Number of bars on each side

    Returns:
        Series with pivot high values (NaN where no pivot)
    """
    highs = df['high'].values
    pivot_highs = pd.Series(index=df.index, dtype=float)

    for i in range(period, len(highs) - period):
        is_pivot = True

        # Check left side
        for j in range(1, period + 1):
            if highs[i] <= highs[i - j]:
                is_pivot = False
                break

        # Check right side
        if is_pivot:
            for j in range(1, period + 1):
                if highs[i] <= highs[i + j]:
                    is_pivot = False
                    break

        if is_pivot:
            pivot_highs.iloc[i] = highs[i]

    return pivot_highs


def detect_pivot_lows(df, period=2):
    """
    Detect pivot lows

    A pivot low is a low that is lower than 'period' lows to the left
    and 'period' lows to the right

    Args:
        df: DataFrame with 'low' column
        period: Number of bars on each side

    Returns:
        Series with pivot low values (NaN where no pivot)
    """
    lows = df['low'].values
    pivot_lows = pd.Series(index=df.index, dtype=float)

    for i in range(period, len(lows) - period):
        is_pivot = True

        # Check left side
        for j in range(1, period + 1):
            if lows[i] >= lows[i - j]:
                is_pivot = False
                break

        # Check right side
        if is_pivot:
            for j in range(1, period + 1):
                if lows[i] >= lows[i + j]:
                    is_pivot = False
                    break

        if is_pivot:
            pivot_lows.iloc[i] = lows[i]

    return pivot_lows


def calculate_pivot_center(pivot_highs, pivot_lows):
    """
    Calculate the dynamic center line using pivot points

    The center line is calculated as a weighted average:
    center = (center * 2 + new_pivot) / 3

    Args:
        pivot_highs: Series with pivot high values
        pivot_lows: Series with pivot low values

    Returns:
        Series with center line values
    """
    center = pd.Series(index=pivot_highs.index, dtype=float)
    current_center = None

    for i in range(len(pivot_highs)):
        # Get the last pivot (high or low)
        lastpp = None
        if not pd.isna(pivot_highs.iloc[i]):
            lastpp = pivot_highs.iloc[i]
        elif not pd.isna(pivot_lows.iloc[i]):
            lastpp = pivot_lows.iloc[i]

        # Update center if we have a new pivot
        if lastpp is not None:
            if current_center is None:
                current_center = lastpp
            else:
                # Weighted calculation: (center * 2 + lastpp) / 3
                current_center = (current_center * 2 + lastpp) / 3

        center.iloc[i] = current_center

    return center


def calculate_pp_supertrend(df, pivot_period=2, atr_factor=3.0, atr_period=10):
    """
    Calculate Pivot Point SuperTrend indicator

    Args:
        df: DataFrame with OHLC data
        pivot_period: Period for pivot point detection
        atr_factor: Multiplier for ATR
        atr_period: Period for ATR calculation

    Returns:
        DataFrame with additional columns:
        - pivot_high, pivot_low: Detected pivot points
        - center: Dynamic center line
        - atr: Average True Range
        - supertrend: SuperTrend line value
        - trend: 1 for uptrend, -1 for downtrend
        - buy_signal: True where buy signal occurs
        - sell_signal: True where sell signal occurs
    """
    result = df.copy()

    # Calculate ATR
    result['atr'] = calculate_atr(result, atr_period)

    # Detect pivot points
    result['pivot_high'] = detect_pivot_highs(result, pivot_period)
    result['pivot_low'] = detect_pivot_lows(result, pivot_period)

    # Calculate center line
    result['center'] = calculate_pivot_center(result['pivot_high'], result['pivot_low'])

    # Forward fill center line where no new pivots exist
    result['center'] = result['center'].ffill()

    # Calculate upper and lower bands
    result['upper_band'] = result['center'] + (atr_factor * result['atr'])
    result['lower_band'] = result['center'] - (atr_factor * result['atr'])

    # Initialize columns
    result['trailing_up'] = np.nan
    result['trailing_down'] = np.nan
    result['trend'] = 0
    result['supertrend'] = np.nan

    # Calculate trailing stops and trend
    for i in range(1, len(result)):
        # Skip if we don't have necessary data yet
        if pd.isna(result['lower_band'].iloc[i]) or pd.isna(result['upper_band'].iloc[i]):
            continue

        # Calculate Trailing Up
        if not pd.isna(result['trailing_up'].iloc[i-1]):
            if result['close'].iloc[i-1] > result['trailing_up'].iloc[i-1]:
                result.loc[result.index[i], 'trailing_up'] = max(
                    result['lower_band'].iloc[i],
                    result['trailing_up'].iloc[i-1]
                )
            else:
                result.loc[result.index[i], 'trailing_up'] = result['lower_band'].iloc[i]
        else:
            result.loc[result.index[i], 'trailing_up'] = result['lower_band'].iloc[i]

        # Calculate Trailing Down
        if not pd.isna(result['trailing_down'].iloc[i-1]):
            if result['close'].iloc[i-1] < result['trailing_down'].iloc[i-1]:
                result.loc[result.index[i], 'trailing_down'] = min(
                    result['upper_band'].iloc[i],
                    result['trailing_down'].iloc[i-1]
                )
            else:
                result.loc[result.index[i], 'trailing_down'] = result['upper_band'].iloc[i]
        else:
            result.loc[result.index[i], 'trailing_down'] = result['upper_band'].iloc[i]

        # Determine trend
        prev_trend = result['trend'].iloc[i-1] if result['trend'].iloc[i-1] != 0 else 1

        if result['close'].iloc[i] > result['trailing_down'].iloc[i-1]:
            result.loc[result.index[i], 'trend'] = 1
        elif result['close'].iloc[i] < result['trailing_up'].iloc[i-1]:
            result.loc[result.index[i], 'trend'] = -1
        else:
            result.loc[result.index[i], 'trend'] = prev_trend

        # Set SuperTrend line
        if result['trend'].iloc[i] == 1:
            result.loc[result.index[i], 'supertrend'] = result['trailing_up'].iloc[i]
        else:
            result.loc[result.index[i], 'supertrend'] = result['trailing_down'].iloc[i]

    # Generate buy/sell signals
    result['buy_signal'] = False
    result['sell_signal'] = False

    for i in range(1, len(result)):
        if result['trend'].iloc[i] == 1 and result['trend'].iloc[i-1] == -1:
            result.loc[result.index[i], 'buy_signal'] = True
        elif result['trend'].iloc[i] == -1 and result['trend'].iloc[i-1] == 1:
            result.loc[result.index[i], 'sell_signal'] = True

    # Calculate support and resistance levels
    result['support'] = result['pivot_low'].ffill()
    result['resistance'] = result['pivot_high'].ffill()

    return result


def get_current_signal(df):
    """
    Get the current trading signal from the indicator

    Args:
        df: DataFrame with calculated indicators

    Returns:
        dict with signal information:
        {
            'signal': 'BUY', 'SELL', or 'HOLD',
            'trend': 1 or -1,
            'supertrend': current supertrend value,
            'price': current close price,
            'support': current support level,
            'resistance': current resistance level
        }
    """
    if len(df) == 0:
        return None

    last_row = df.iloc[-1]
    prev_row = df.iloc[-2] if len(df) > 1 else None

    signal_info = {
        'signal': 'HOLD',
        'trend': int(last_row['trend']),
        'supertrend': float(last_row['supertrend']) if not pd.isna(last_row['supertrend']) else None,
        'price': float(last_row['close']),
        'support': float(last_row['support']) if not pd.isna(last_row['support']) else None,
        'resistance': float(last_row['resistance']) if not pd.isna(last_row['resistance']) else None,
        'atr': float(last_row['atr']) if not pd.isna(last_row['atr']) else None,
        'pivot': float(last_row['center']) if not pd.isna(last_row['center']) else None
    }

    # Check for buy signal
    if last_row['buy_signal']:
        signal_info['signal'] = 'BUY'
    # Check for sell signal
    elif last_row['sell_signal']:
        signal_info['signal'] = 'SELL'
    # If in uptrend but no new signal, trend continuation
    elif last_row['trend'] == 1:
        signal_info['signal'] = 'HOLD_LONG'
    # If in downtrend but no new signal, trend continuation
    elif last_row['trend'] == -1:
        signal_info['signal'] = 'HOLD_SHORT'

    return signal_info
