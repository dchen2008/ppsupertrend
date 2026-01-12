#!/usr/bin/env python3
"""
Signal Verification Script - OANDA Data Analysis
Compare PP SuperTrend signals with/without 30-second confirmation delay
Time range: Jan 4, 4:00 PM UTC-8 to Jan 9, 4:00 PM UTC-8
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pytz
import sys
import os

# Add src to path for importing indicators
sys.path.append('src')
from indicators import calculate_pp_supertrend, get_current_signal

# Configuration  
START_TIME = "2026-01-04 16:00:00-08:00"  # Jan 4, 4:00 PM UTC-8 (2026!)
END_TIME = "2026-01-09 16:00:00-08:00"    # Jan 9, 4:00 PM UTC-8 (2026!)
CONFIRMATION_DELAY_SECONDS = 30
DATA_FILE = "backtest/data/EUR_USD_M5_20260104_20260109.csv"

def load_oanda_data(filepath):
    """Load OANDA data from CSV file"""
    print(f"📁 Loading data from: {filepath}")
    
    if not os.path.exists(filepath):
        print(f"❌ File not found: {filepath}")
        return None
    
    df = pd.read_csv(filepath)
    print(f"📊 Loaded {len(df)} rows")
    
    # Convert time column to datetime with UTC timezone
    if 'time' in df.columns:
        df['time'] = pd.to_datetime(df['time'], utc=True)
        df.set_index('time', inplace=True)
    else:
        print("❌ No 'time' column found in data")
        return None
    
    # Rename columns to match expected format
    if 'o' in df.columns:
        df = df.rename(columns={'o': 'open', 'h': 'high', 'l': 'low', 'c': 'close', 'v': 'volume'})
    
    return df

def filter_time_range(df, start_time, end_time):
    """Filter data to specific time range"""
    start_utc = pd.to_datetime(start_time).tz_convert('UTC')
    end_utc = pd.to_datetime(end_time).tz_convert('UTC')
    
    print(f"⏰ Filtering data from {start_utc} to {end_utc}")
    
    filtered_df = df[(df.index >= start_utc) & (df.index <= end_utc)]
    print(f"📈 Filtered to {len(filtered_df)} rows")
    
    return filtered_df

def detect_signals_immediate(df):
    """Detect signals without any delay"""
    print("🔍 Calculating PP SuperTrend indicators...")
    
    # Calculate indicators
    df_with_indicators = calculate_pp_supertrend(
        df,
        pivot_period=2,
        atr_factor=3.0,
        atr_period=10
    )
    
    signals = []
    
    # Find all buy/sell signals
    for i in range(len(df_with_indicators)):
        if df_with_indicators['buy_signal'].iloc[i]:
            signals.append({
                'time': df_with_indicators.index[i],
                'signal': 'BUY',
                'price': df_with_indicators['close'].iloc[i],
                'supertrend': df_with_indicators['supertrend'].iloc[i],
                'trend': df_with_indicators['trend'].iloc[i],
                'type': 'immediate'
            })
        elif df_with_indicators['sell_signal'].iloc[i]:
            signals.append({
                'time': df_with_indicators.index[i],
                'signal': 'SELL', 
                'price': df_with_indicators['close'].iloc[i],
                'supertrend': df_with_indicators['supertrend'].iloc[i],
                'trend': df_with_indicators['trend'].iloc[i],
                'type': 'immediate'
            })
    
    return signals, df_with_indicators

def detect_signals_with_delay(df, delay_seconds=30):
    """Detect signals with confirmation delay"""
    print(f"⏳ Detecting signals with {delay_seconds}s confirmation delay...")
    
    # Calculate indicators
    df_with_indicators = calculate_pp_supertrend(
        df,
        pivot_period=2,
        atr_factor=3.0,
        atr_period=10
    )
    
    signals = []
    
    # Find signals and check if they persist after delay
    for i in range(len(df_with_indicators) - 1):
        current_time = df_with_indicators.index[i]
        delay_time = current_time + timedelta(seconds=delay_seconds)
        
        # Check for initial signal
        initial_signal = None
        if df_with_indicators['buy_signal'].iloc[i]:
            initial_signal = 'BUY'
        elif df_with_indicators['sell_signal'].iloc[i]:
            initial_signal = 'SELL'
        
        if initial_signal:
            # Find the closest data point after delay
            delayed_df = df_with_indicators[df_with_indicators.index >= delay_time]
            
            if len(delayed_df) > 0:
                delayed_idx = delayed_df.index[0]
                delayed_row_idx = df_with_indicators.index.get_loc(delayed_idx)
                
                # Check if trend is still the same after delay
                initial_trend = df_with_indicators['trend'].iloc[i]
                delayed_trend = df_with_indicators['trend'].iloc[delayed_row_idx]
                
                if initial_trend == delayed_trend:
                    # Signal confirmed after delay
                    signals.append({
                        'time': current_time,
                        'confirmed_time': delayed_idx,
                        'signal': initial_signal,
                        'price': df_with_indicators['close'].iloc[i],
                        'confirmed_price': df_with_indicators['close'].iloc[delayed_row_idx],
                        'supertrend': df_with_indicators['supertrend'].iloc[i],
                        'trend': initial_trend,
                        'type': 'delayed_confirmed'
                    })
                else:
                    # Signal was false - trend changed during delay
                    signals.append({
                        'time': current_time,
                        'confirmed_time': delayed_idx,
                        'signal': initial_signal,
                        'price': df_with_indicators['close'].iloc[i],
                        'confirmed_price': df_with_indicators['close'].iloc[delayed_row_idx],
                        'supertrend': df_with_indicators['supertrend'].iloc[i],
                        'trend': initial_trend,
                        'type': 'delayed_rejected'
                    })
    
    return signals

def print_signals(signals, title):
    """Print signals in a formatted way"""
    print(f"\n{'='*60}")
    print(f"📊 {title}")
    print(f"{'='*60}")
    
    if not signals:
        print("❌ No signals found")
        return
    
    for signal in signals:
        time_str = signal['time'].strftime('%Y-%m-%d %H:%M:%S UTC')
        
        if signal['type'] == 'immediate':
            print(f"🎯 {signal['signal']:4} | {time_str} | Price: {signal['price']:.5f} | ST: {signal['supertrend']:.5f}")
        
        elif signal['type'] == 'delayed_confirmed':
            confirmed_time = signal['confirmed_time'].strftime('%Y-%m-%d %H:%M:%S UTC')
            print(f"✅ {signal['signal']:4} | {time_str} | Price: {signal['price']:.5f} | CONFIRMED after 30s")
            print(f"     └── Confirmed: {confirmed_time} | Price: {signal['confirmed_price']:.5f}")
        
        elif signal['type'] == 'delayed_rejected':
            confirmed_time = signal['confirmed_time'].strftime('%Y-%m-%d %H:%M:%S UTC')
            print(f"❌ {signal['signal']:4} | {time_str} | Price: {signal['price']:.5f} | REJECTED after 30s")
            print(f"     └── Checked: {confirmed_time} | Price: {signal['confirmed_price']:.5f}")

def compare_signals(immediate_signals, delayed_signals):
    """Compare immediate vs delayed signals"""
    print(f"\n{'='*60}")
    print(f"📈 SIGNAL COMPARISON ANALYSIS")
    print(f"{'='*60}")
    
    immediate_count = len(immediate_signals)
    confirmed_count = len([s for s in delayed_signals if s['type'] == 'delayed_confirmed'])
    rejected_count = len([s for s in delayed_signals if s['type'] == 'delayed_rejected'])
    
    print(f"📊 Immediate Signals: {immediate_count}")
    print(f"✅ Confirmed Signals: {confirmed_count}")
    print(f"❌ Rejected Signals: {rejected_count}")
    print(f"📈 Confirmation Rate: {(confirmed_count/(confirmed_count+rejected_count)*100):.1f}%")
    
    if rejected_count > 0:
        print(f"\n🚨 FALSE SIGNAL PREVENTION:")
        print(f"   30-second delay would have prevented {rejected_count} false signals")
        print(f"   That's {(rejected_count/immediate_count*100):.1f}% of all signals!")

def main():
    print("🔍 PP SuperTrend Signal Verification - OANDA Data Analysis")
    print("=" * 60)
    
    # Load data
    df = load_oanda_data(DATA_FILE)
    if df is None:
        return
    
    # Filter to specified time range
    filtered_df = filter_time_range(df, START_TIME, END_TIME)
    
    if filtered_df.empty:
        print("❌ No data in specified time range")
        return
    
    print(f"📅 Analysis period: {START_TIME} to {END_TIME}")
    print(f"📊 Total candles: {len(filtered_df)}")
    
    # Detect immediate signals
    immediate_signals, df_with_indicators = detect_signals_immediate(filtered_df)
    
    # Detect signals with delay
    delayed_signals = detect_signals_with_delay(filtered_df, CONFIRMATION_DELAY_SECONDS)
    
    # Print results
    print_signals(immediate_signals, "IMMEDIATE SIGNALS (No Delay)")
    print_signals(delayed_signals, f"DELAYED SIGNALS ({CONFIRMATION_DELAY_SECONDS}s Confirmation)")
    
    # Compare results
    compare_signals(immediate_signals, delayed_signals)
    
    print(f"\n{'='*60}")
    print("✨ Analysis Complete!")

if __name__ == "__main__":
    main()