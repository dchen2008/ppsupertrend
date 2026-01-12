#!/usr/bin/env python3
"""
Analyze signal timing discrepancies between backtest and TradingView
"""

import pandas as pd
import sys
import os
from datetime import datetime, timedelta
sys.path.append('src')
sys.path.append('backtest/src')

from config import OANDAConfig, TradingConfig
from data_downloader import BacktestDataDownloader
from indicators import calculate_pp_supertrend, get_current_signal
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def analyze_signal_timing(instrument='EUR_USD', timeframe='5m', start_time='2026-01-04 16:00:00', end_time='2026-01-09 16:00:00'):
    """Analyze when signals actually occur vs when they're detected"""
    
    # Parse time range
    import pytz
    start_dt = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S').replace(tzinfo=pytz.UTC)
    end_dt = datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S').replace(tzinfo=pytz.UTC)
    
    # Download data
    downloader = BacktestDataDownloader('account1', cache_dir='backtest/data')
    
    # Calculate days back from end_time to start_time (plus buffer)
    days_diff = (end_dt - start_dt).days + 3
    
    # Download data using the correct method
    trading_data = downloader.download_historical_data(
        instrument,
        f'M{timeframe[:-1]}' if timeframe.endswith('m') else f'H{timeframe[:-1]}',
        days_back=days_diff
    )
    
    # Calculate indicators
    trading_data_with_indicators = calculate_pp_supertrend(
        trading_data,
        pivot_period=TradingConfig.pivot_period,
        atr_factor=TradingConfig.atr_factor,
        atr_period=TradingConfig.atr_period
    )
    
    # Track signals using different detection methods
    signals_method1 = []  # Current method: check last row's buy_signal/sell_signal
    signals_method2 = []  # Alternative: check for trend changes
    signals_method3 = []  # Look back: check if signal occurred in recent past
    
    prev_signal = None
    prev_trend = None
    
    for current_time, row in trading_data_with_indicators.iterrows():
        # Skip data before analysis period
        if current_time < start_dt:
            continue
        if current_time > end_dt:
            break
            
        # Method 1: Current implementation (check last row)
        data_slice = trading_data_with_indicators.loc[:current_time].copy()
        signal_info = get_current_signal(data_slice)
        current_signal = signal_info['signal']
        
        if current_signal != prev_signal and current_signal in ['BUY', 'SELL']:
            signals_method1.append({
                'time': current_time,
                'signal': current_signal,
                'price': signal_info['price'],
                'method': 'last_row_flag'
            })
            
        # Method 2: Check for trend changes (more accurate)
        current_trend = row['trend']
        if prev_trend is not None:
            if current_trend == 1 and prev_trend == -1:
                signals_method2.append({
                    'time': current_time,
                    'signal': 'BUY',
                    'price': row['close'],
                    'method': 'trend_change'
                })
            elif current_trend == -1 and prev_trend == 1:
                signals_method2.append({
                    'time': current_time,
                    'signal': 'SELL', 
                    'price': row['close'],
                    'method': 'trend_change'
                })
        
        # Method 3: Look back for signals in recent candles (delayed detection)
        lookback_window = 3  # Check last 3 candles
        if len(data_slice) > lookback_window:
            for i in range(1, min(lookback_window + 1, len(data_slice))):
                check_idx = -i
                if data_slice.iloc[check_idx]['buy_signal'] and 'BUY' not in [s['signal'] for s in signals_method3 if s['time'] == data_slice.index[check_idx]]:
                    signals_method3.append({
                        'time': data_slice.index[check_idx],
                        'signal': 'BUY',
                        'price': data_slice.iloc[check_idx]['close'],
                        'detected_at': current_time,
                        'delay_candles': i-1,
                        'method': 'lookback'
                    })
                elif data_slice.iloc[check_idx]['sell_signal'] and 'SELL' not in [s['signal'] for s in signals_method3 if s['time'] == data_slice.index[check_idx]]:
                    signals_method3.append({
                        'time': data_slice.index[check_idx],
                        'signal': 'SELL',
                        'price': data_slice.iloc[check_idx]['close'],
                        'detected_at': current_time,
                        'delay_candles': i-1,
                        'method': 'lookback'
                    })
        
        prev_signal = current_signal
        prev_trend = current_trend
    
    # Print analysis
    print("\n" + "="*80)
    print("SIGNAL TIMING ANALYSIS")
    print("="*80)
    
    print(f"\nAnalysis Period: {start_time} to {end_time}")
    print(f"Instrument: {instrument}, Timeframe: {timeframe}")
    
    print("\n" + "-"*80)
    print("METHOD 1: Current Implementation (check last row's signal flags)")
    print("-"*80)
    for s in signals_method1:
        print(f"{s['time'].strftime('%b %d, %I:%M%p')} - {s['signal']} at {s['price']:.5f}")
    
    print("\n" + "-"*80)
    print("METHOD 2: Direct Trend Change Detection")
    print("-"*80)
    for s in signals_method2:
        print(f"{s['time'].strftime('%b %d, %I:%M%p')} - {s['signal']} at {s['price']:.5f}")
    
    print("\n" + "-"*80)
    print("METHOD 3: Lookback Detection (finds missed signals)")
    print("-"*80)
    unique_signals = {}
    for s in signals_method3:
        key = (s['time'], s['signal'])
        if key not in unique_signals or s['delay_candles'] < unique_signals[key]['delay_candles']:
            unique_signals[key] = s
    
    for s in sorted(unique_signals.values(), key=lambda x: x['time']):
        if s['delay_candles'] > 0:
            print(f"{s['time'].strftime('%b %d, %I:%M%p')} - {s['signal']} at {s['price']:.5f} (detected {s['delay_candles']} candles late at {s['detected_at'].strftime('%I:%M%p')})")
        else:
            print(f"{s['time'].strftime('%b %d, %I:%M%p')} - {s['signal']} at {s['price']:.5f} (on-time)")
    
    # Compare with known phantom trades
    phantom_trades = [
        ('2026-01-04 14:55:00', 'SELL'),  # Jan 04, 02:55PM
        ('2026-01-06 07:10:00', 'SELL'),  # Jan 06, 07:10AM
        ('2026-01-06 10:50:00', 'SELL'),  # Jan 06, 10:50AM
    ]
    
    print("\n" + "="*80)
    print("PHANTOM TRADE ANALYSIS")
    print("="*80)
    
    for phantom_time_str, phantom_signal in phantom_trades:
        phantom_time = datetime.strptime(phantom_time_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=pytz.UTC)
        print(f"\nPhantom Trade: {phantom_time.strftime('%b %d, %I:%M%p')} - {phantom_signal}")
        
        # Check if this signal exists in each method
        found_m1 = any(abs((s['time'] - phantom_time).total_seconds()) < 300 and s['signal'] == phantom_signal 
                      for s in signals_method1)
        found_m2 = any(abs((s['time'] - phantom_time).total_seconds()) < 300 and s['signal'] == phantom_signal 
                      for s in signals_method2)
        
        print(f"  Found in Method 1 (current): {found_m1}")
        print(f"  Found in Method 2 (trend change): {found_m2}")
        
        # Check actual data around this time
        time_window = trading_data_with_indicators[
            (trading_data_with_indicators.index >= phantom_time - timedelta(minutes=15)) &
            (trading_data_with_indicators.index <= phantom_time + timedelta(minutes=15))
        ]
        
        if not time_window.empty:
            print(f"  Data around this time:")
            for t, r in time_window.iterrows():
                if r['buy_signal'] or r['sell_signal']:
                    sig = 'BUY' if r['buy_signal'] else 'SELL'
                    print(f"    {t.strftime('%I:%M%p')}: {sig} signal, trend={r['trend']:.0f}")
    
    print("\n" + "="*80)
    print("RECOMMENDATIONS")
    print("="*80)
    print("1. The phantom trades occur when using Method 1 (current implementation)")
    print("2. These are likely due to signal flag persistence or lookback issues")
    print("3. Method 2 (direct trend change) appears more accurate")
    print("4. Consider modifying get_current_signal() to check trend changes directly")
    print("5. Or ensure signal flags are only true on the exact candle of change")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Parse command line arguments
        args = {}
        for arg in sys.argv[1:]:
            if '=' in arg:
                key, value = arg.split('=', 1)
                args[key] = value
        
        analyze_signal_timing(
            instrument=args.get('fr', 'EUR_USD'),
            timeframe=args.get('tf', '5m'),
            start_time=args.get('start', '2026-01-04 16:00:00'),
            end_time=args.get('end', '2026-01-09 16:00:00')
        )
    else:
        analyze_signal_timing()