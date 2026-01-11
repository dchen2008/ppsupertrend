#!/usr/bin/env python3
"""
Debug phantom trades to find root cause
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
import pytz

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def debug_phantom_trades():
    """Debug specific phantom trade timestamps"""
    
    phantom_timestamps = [
        '2026-01-04 14:55:00',  # Jan 04, 02:55PM
        '2026-01-06 07:10:00',  # Jan 06, 07:10AM
        '2026-01-06 10:50:00',  # Jan 06, 10:50AM
    ]
    
    # Download data
    downloader = BacktestDataDownloader('account1', cache_dir='backtest/data')
    trading_data = downloader.download_historical_data(
        'EUR_USD',
        'M5',
        days_back=10
    )
    
    # Calculate indicators
    trading_data_with_indicators = calculate_pp_supertrend(
        trading_data,
        pivot_period=TradingConfig.pivot_period,
        atr_factor=TradingConfig.atr_factor,
        atr_period=TradingConfig.atr_period
    )
    
    print("\n" + "="*80)
    print("PHANTOM TRADE DEBUG")
    print("="*80)
    
    for phantom_str in phantom_timestamps:
        phantom_time = datetime.strptime(phantom_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=pytz.UTC)
        
        print(f"\n\nDEBUGGING: {phantom_time.strftime('%b %d, %I:%M%p')}")
        print("-"*60)
        
        # Get data around phantom time
        time_window = trading_data_with_indicators[
            (trading_data_with_indicators.index >= phantom_time - timedelta(minutes=30)) &
            (trading_data_with_indicators.index <= phantom_time + timedelta(minutes=30))
        ]
        
        if time_window.empty:
            print("No data found for this timestamp")
            continue
        
        # Track signal changes
        prev_signal = None
        prev_trend = None
        
        print("\nSignal progression:")
        for idx, (current_time, row) in enumerate(time_window.iterrows()):
            # Get signal using get_current_signal
            data_slice = trading_data_with_indicators.loc[:current_time].copy()
            signal_info = get_current_signal(data_slice)
            current_signal = signal_info['signal']
            
            # Check if this would trigger a trade in backtest
            would_trigger = (current_signal != prev_signal and current_signal in ['BUY', 'SELL'])
            
            # Print if relevant
            if row['buy_signal'] or row['sell_signal'] or would_trigger or current_time == phantom_time:
                print(f"{current_time.strftime('%I:%M%p')}: "
                      f"trend={row['trend']:.0f}, "
                      f"buy_sig={row['buy_signal']}, "
                      f"sell_sig={row['sell_signal']}, "
                      f"signal={current_signal}, "
                      f"prev_signal={prev_signal}, "
                      f"would_trigger={'YES' if would_trigger else 'NO'}")
                
                if current_time == phantom_time:
                    print(f"  ^^ THIS IS THE PHANTOM TRADE TIME - Signal: {current_signal}")
                    if would_trigger:
                        print(f"  ⚠️ PHANTOM WOULD TRIGGER! prev={prev_signal} -> curr={current_signal}")
            
            # Update prev values
            if current_signal in ['BUY', 'SELL']:
                # This is the issue! The backtest updates prev_signal even for non-triggering signals
                # It should only update after a trade is actually executed
                pass
            
            prev_signal = current_signal
            prev_trend = row['trend']
        
        # Also check what the correct signal should be
        print("\nCorrect signal detection (trend changes only):")
        prev_trend = None
        for current_time, row in time_window.iterrows():
            current_trend = row['trend']
            if prev_trend is not None:
                if current_trend == 1 and prev_trend == -1:
                    print(f"{current_time.strftime('%I:%M%p')}: BUY signal (trend changed -1 -> 1)")
                elif current_trend == -1 and prev_trend == 1:
                    print(f"{current_time.strftime('%I:%M%p')}: SELL signal (trend changed 1 -> -1)")
            prev_trend = current_trend

if __name__ == "__main__":
    debug_phantom_trades()