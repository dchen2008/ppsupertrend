#!/usr/bin/env python3
"""
Detailed Backtest Analysis for Jan 4, 4pm to Jan 9, 4pm
Prints market trend detection, signal times, and price extremes with unrealized P&L
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging

# Add src directory to path
sys.path.append('src')
sys.path.append('backtest/src')

from src.indicators import calculate_pp_supertrend, get_current_signal
from src.config import TradingConfig, OANDAConfig
from src.risk_manager import RiskManager
from backtest.src.data_downloader import BacktestDataDownloader
from backtest.src.backtest_engine import BacktestEngine

def setup_logging():
    """Setup logging to suppress noise"""
    logging.basicConfig(level=logging.ERROR)  # Only show errors

def get_data_for_period():
    """Download data for the analysis period"""
    print("📥 Downloading data for Jan 4, 4pm to Jan 9, 4pm...")
    
    # Download 10 days to ensure we have enough data
    downloader = BacktestDataDownloader(account='account1')
    
    data = downloader.get_data_for_backtest(
        instrument='EUR_USD',
        trading_timeframe='M5',
        market_timeframe='H3',
        days_back=10,
        include_intrabar=False  # Don't need M1 for this analysis
    )
    
    print(f"✓ Downloaded {len(data['M5'])} 5M candles")
    print(f"✓ Downloaded {len(data['H3'])} 3H candles")
    
    return data['M5'], data['H3']

def filter_to_time_range(df, start_time, end_time):
    """Filter DataFrame to specific time range"""
    mask = (df.index >= start_time) & (df.index <= end_time)
    return df[mask].copy()

def get_market_trend_changes(market_data, trading_data_range):
    """Detect when market trend changes during the period"""
    print("\n🔍 MARKET TREND ANALYSIS (3H PP SuperTrend)")
    print("=" * 60)
    
    # Calculate PP SuperTrend on full 3H data
    df_with_indicators = calculate_pp_supertrend(
        market_data,
        pivot_period=TradingConfig.pivot_period,
        atr_factor=TradingConfig.atr_factor,
        atr_period=TradingConfig.atr_period
    )
    
    if df_with_indicators is None:
        print("❌ Failed to calculate 3H indicators")
        return []
    
    # Filter to our analysis period
    start_time = trading_data_range.index[0]
    end_time = trading_data_range.index[-1]
    
    trend_changes = []
    current_trend = None
    
    # Check each 3H candle in our range
    for timestamp, row in df_with_indicators.iterrows():
        if timestamp < start_time or timestamp > end_time:
            continue
            
        # Get signal at this point
        data_slice = df_with_indicators.loc[:timestamp].copy()
        signal_info = get_current_signal(data_slice)
        
        # Determine trend
        signal = signal_info['signal']
        if signal in ['BUY', 'HOLD_LONG']:
            trend = 'BULL'
        elif signal in ['SELL', 'HOLD_SHORT']:
            trend = 'BEAR'
        else:
            trend = 'NEUTRAL'
        
        # Check for trend change
        if trend != current_trend:
            trend_changes.append({
                'time': timestamp,
                'trend': trend,
                'signal': signal,
                'price': row['close']
            })
            current_trend = trend
            
            print(f"{timestamp}: Market = {trend} (3H Signal: {signal}, Price: {row['close']:.5f})")
    
    return trend_changes

def analyze_trading_signals(trading_data, market_trend_changes):
    """Analyze 5-minute trading signals and calculate price extremes"""
    print("\n📈 5-MINUTE TRADING SIGNALS ANALYSIS")
    print("=" * 60)
    
    # Calculate PP SuperTrend on 5M data
    df_with_indicators = calculate_pp_supertrend(
        trading_data,
        pivot_period=TradingConfig.pivot_period,
        atr_factor=TradingConfig.atr_factor,
        atr_period=TradingConfig.atr_period
    )
    
    if df_with_indicators is None:
        print("❌ Failed to calculate 5M indicators")
        return
    
    signals = []
    
    # Get all 5M signals
    prev_signal = None
    for timestamp, row in df_with_indicators.iterrows():
        # Get signal at this point
        data_slice = df_with_indicators.loc[:timestamp].copy()
        signal_info = get_current_signal(data_slice)
        
        current_signal = signal_info['signal']
        
        # Check for signal change
        if current_signal != prev_signal and current_signal in ['BUY', 'SELL']:
            # Find current market trend at this time
            market_trend = 'NEUTRAL'
            for trend_change in market_trend_changes:
                if trend_change['time'] <= timestamp:
                    market_trend = trend_change['trend']
            
            signals.append({
                'time': timestamp,
                'signal': current_signal,
                'price': row['close'],
                'supertrend': signal_info['supertrend'],
                'market_trend': market_trend
            })
            
            prev_signal = current_signal
    
    # Print signals and analyze price extremes between them
    risk_manager = RiskManager()
    
    for i, signal in enumerate(signals):
        signal_time = signal['time']
        signal_type = signal['signal']
        entry_price = signal['price']
        supertrend = signal['supertrend']
        market_trend = signal['market_trend']
        
        # Determine if this trade would be allowed
        position_type = 'LONG' if signal_type == 'BUY' else 'SHORT'
        
        # Check if trade would be filtered by disable_opposite_trade
        config = {'position_sizing': {'disable_opposite_trade': True}}
        would_be_filtered = False
        
        if market_trend == 'BEAR' and signal_type == 'BUY':
            would_be_filtered = True
        elif market_trend == 'BULL' and signal_type == 'SELL':
            would_be_filtered = True
        
        print(f"\n[{i+1}] {signal_time}: {signal_type} signal")
        print(f"    Market Trend: {market_trend}")
        print(f"    Entry Price: {entry_price:.5f}")
        print(f"    SuperTrend: {supertrend:.5f}")
        print(f"    Position Type: {position_type}")
        print(f"    Trade Status: {'🚫 FILTERED' if would_be_filtered else '✅ ALLOWED'}")
        
        if would_be_filtered:
            print(f"    Reason: disable_opposite_trade blocks {position_type} in {market_trend} market")
            continue
        
        # Calculate stop loss and take profit
        signal_info_full = {
            'price': entry_price,
            'supertrend': supertrend,
            'signal': signal_type
        }
        
        # Get stop loss
        if position_type == 'LONG':
            stop_loss = supertrend - 0.00010  # Spread adjustment
        else:
            stop_loss = supertrend + 0.00010  # Spread adjustment
        
        # Get take profit (1:1 ratio for bear market shorts)
        if market_trend == 'BEAR' and position_type == 'SHORT':
            risk = abs(entry_price - stop_loss)
            take_profit = entry_price - risk  # 1:1 ratio
        else:
            take_profit = None
        
        print(f"    Stop Loss: {stop_loss:.5f}")
        if take_profit:
            print(f"    Take Profit: {take_profit:.5f} (1:1 ratio)")
        
        # Find next signal time or end of data
        if i + 1 < len(signals):
            next_signal_time = signals[i + 1]['time']
        else:
            next_signal_time = df_with_indicators.index[-1]
        
        # Get price data between this signal and next
        mask = (df_with_indicators.index > signal_time) & (df_with_indicators.index <= next_signal_time)
        price_data = df_with_indicators[mask]
        
        if len(price_data) > 0:
            highest_price = price_data['high'].max()
            lowest_price = price_data['low'].min()
            
            highest_time = price_data[price_data['high'] == highest_price].index[0]
            lowest_time = price_data[price_data['low'] == lowest_price].index[0]
            
            # Calculate unrealized P&L at highest and lowest points
            if position_type == 'LONG':
                unrealized_pl_high = (highest_price - entry_price) * 1000  # Per 1000 units
                unrealized_pl_low = (lowest_price - entry_price) * 1000
                
                print(f"    📊 Price Analysis ({signal_time} to {next_signal_time}):")
                print(f"       Highest: {highest_price:.5f} at {highest_time}")
                print(f"       Unrealized P&L at HIGH: +${unrealized_pl_high:.2f} per 1000 units")
                print(f"       Lowest:  {lowest_price:.5f} at {lowest_time}")
                print(f"       Unrealized P&L at LOW:  ${unrealized_pl_low:+.2f} per 1000 units")
                
                # Calculate potential R:R ratios
                max_profit = highest_price - entry_price
                max_loss = entry_price - stop_loss
                if max_loss > 0:
                    max_rr = max_profit / max_loss
                    print(f"       Max Risk:Reward Ratio: {max_rr:.2f}:1")
                    
            else:  # SHORT
                unrealized_pl_high = (entry_price - highest_price) * 1000  # Per 1000 units  
                unrealized_pl_low = (entry_price - lowest_price) * 1000
                
                print(f"    📊 Price Analysis ({signal_time} to {next_signal_time}):")
                print(f"       Highest: {highest_price:.5f} at {highest_time}")
                print(f"       Unrealized P&L at HIGH: ${unrealized_pl_high:+.2f} per 1000 units")
                print(f"       Lowest:  {lowest_price:.5f} at {lowest_time}")
                print(f"       Unrealized P&L at LOW:  +${unrealized_pl_low:.2f} per 1000 units")
                
                # Calculate potential R:R ratios
                max_profit = entry_price - lowest_price
                max_loss = stop_loss - entry_price
                if max_loss > 0:
                    max_rr = max_profit / max_loss
                    print(f"       Max Risk:Reward Ratio: {max_rr:.2f}:1")

def main():
    """Main analysis function"""
    setup_logging()
    
    print("🔍 DETAILED BACKTEST ANALYSIS")
    print("📅 Period: Jan 4, 4pm to Jan 9, 4pm (UTC)")
    print("📊 Instrument: EUR/USD")
    print("⏰ Trading Timeframe: 5 minutes")
    print("📈 Market Trend Timeframe: 3 hours")
    
    # Download data
    trading_data, market_data = get_data_for_period()
    
    # Define analysis period (Jan 4, 4pm to Jan 9, 4pm UTC)
    start_time = pd.Timestamp('2026-01-04 16:00:00+00:00')
    end_time = pd.Timestamp('2026-01-09 16:00:00+00:00')
    
    print(f"\n🎯 Analysis Period: {start_time} to {end_time}")
    
    # Filter data to our analysis period
    trading_range = filter_to_time_range(trading_data, start_time, end_time)
    market_range = filter_to_time_range(market_data, start_time, end_time)
    
    if len(trading_range) == 0:
        print("❌ No trading data found in the specified period")
        return
    
    print(f"✓ Found {len(trading_range)} 5M candles in period")
    print(f"✓ Found {len(market_range)} 3H candles in period")
    
    # Analyze market trend changes
    trend_changes = get_market_trend_changes(market_data, trading_range)
    
    # Analyze trading signals
    analyze_trading_signals(trading_range, trend_changes)
    
    print("\n" + "="*60)
    print("📋 SUMMARY FOR TAKE PROFIT OPTIMIZATION:")
    print("="*60)
    print("• Use the Max Risk:Reward Ratios above to set optimal take profits")
    print("• Focus on SHORT trades during BEAR market periods")
    print("• Consider the unrealized P&L data to understand profit potential")
    print("• Higher R:R ratios indicate better take profit opportunities")

if __name__ == "__main__":
    main()