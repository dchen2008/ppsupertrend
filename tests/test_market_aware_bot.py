#!/usr/bin/env python3
"""
Test script for Market-Aware Trading Bot
Verifies configuration loading and market trend detection
"""

import sys
import os
import yaml

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import OANDAConfig, TradingConfig
from src.oanda_client import OANDAClient
from src.indicators import calculate_pp_supertrend, get_current_signal


def test_config_loading():
    """Test loading configuration hierarchy: default -> account-specific"""
    print("\n" + "=" * 60)
    print("Testing Configuration Loading Hierarchy")
    print("=" * 60)
    
    # Check default config
    default_config_file = "src/config.yaml"
    default_config = {}
    if os.path.exists(default_config_file):
        with open(default_config_file, 'r') as f:
            default_config = yaml.safe_load(f)
        print(f"✓ Default config loaded: {default_config_file}")
    else:
        print(f"✗ Default config not found: {default_config_file}")
        print("  Using built-in defaults")
    
    # Check account-specific configs
    for account in ['account1', 'account2', 'account3']:
        account_config_file = f"{account}/config.yaml"
        print(f"\n{account}:")
        
        if os.path.exists(account_config_file):
            with open(account_config_file, 'r') as f:
                account_config = yaml.safe_load(f)
            
            # Merge with defaults (simplified merge for display)
            import copy
            final_config = copy.deepcopy(default_config) if default_config else {}
            if account_config:
                # Simple merge for display purposes
                for key, value in account_config.items():
                    if isinstance(value, dict) and key in final_config and isinstance(final_config[key], dict):
                        final_config[key].update(value)
                    else:
                        final_config[key] = value
            
            print(f"  ✓ Account config found: {account_config_file}")
            print(f"    Check Interval: {final_config.get('check_interval', 60)}s")
            print(f"    Market Timeframe: {final_config.get('market', {}).get('timeframe', 'N/A')}")
            
            risk_reward = final_config.get('risk_reward', {})
            bear_short = risk_reward.get('bear_market', {}).get('short_rr', 'N/A')
            bear_long = risk_reward.get('bear_market', {}).get('long_rr', 'N/A')
            bull_short = risk_reward.get('bull_market', {}).get('short_rr', 'N/A')
            bull_long = risk_reward.get('bull_market', {}).get('long_rr', 'N/A')
            
            print(f"    Risk/Reward: Bear(S:{bear_short}/L:{bear_long}) Bull(S:{bull_short}/L:{bull_long})")
        else:
            print(f"  - No account config (will use defaults)")


def test_market_trend_detection():
    """Test market trend detection using 3H timeframe"""
    print("\n" + "=" * 60)
    print("Testing Market Trend Detection (3H PP SuperTrend)")
    print("=" * 60)
    
    try:
        # Set account for testing
        if 'account1' in OANDAConfig.list_accounts():
            OANDAConfig.set_account('account1')
        else:
            print("✗ Account1 not configured. Please configure OANDA credentials.")
            return
        
        client = OANDAClient()
        
        # Test with EUR_USD on H3 timeframe
        instrument = 'EUR_USD'
        print(f"\nFetching 3H data for {instrument}...")
        
        df = client.get_candles(
            instrument=instrument,
            granularity='H3',
            count=100
        )
        
        if df is not None and len(df) > 0:
            print(f"✓ Retrieved {len(df)} 3H candles")
            
            # Calculate PP SuperTrend
            df_with_indicators = calculate_pp_supertrend(
                df,
                pivot_period=TradingConfig.pivot_period,
                atr_factor=TradingConfig.atr_factor,
                atr_period=TradingConfig.atr_period
            )
            
            # Get current signal
            signal_info = get_current_signal(df_with_indicators)
            
            # Determine market trend
            if signal_info['signal'] == 'BUY':
                market_trend = 'BULL'
            elif signal_info['signal'] == 'SELL':
                market_trend = 'BEAR'
            else:
                market_trend = 'NEUTRAL'
            
            print(f"\n📊 Market Analysis Results:")
            print(f"  Market Trend: {market_trend}")
            print(f"  3H Signal: {signal_info['signal']}")
            print(f"  Current Price: {signal_info['price']:.5f}")
            if signal_info['supertrend']:
                print(f"  3H SuperTrend: {signal_info['supertrend']:.5f}")
            if signal_info['pivot']:
                print(f"  3H Pivot Point: {signal_info['pivot']:.5f}")
            print(f"  Trend Direction: {signal_info['trend']}")
            
            # Show what R:R would be used
            print(f"\n💡 Risk/Reward Strategy for {market_trend} Market:")
            if market_trend == 'BULL':
                print(f"  Long positions: Favorable R:R = 1.2")
                print(f"  Short positions: Conservative R:R = 0.6")
            elif market_trend == 'BEAR':
                print(f"  Short positions: Favorable R:R = 1.2")
                print(f"  Long positions: Conservative R:R = 0.6")
            else:
                print(f"  All positions: Balanced R:R = 1.0")
                
        else:
            print("✗ Failed to fetch 3H candle data")
            
    except Exception as e:
        print(f"✗ Error during market trend test: {e}")


def test_risk_reward_calculation():
    """Test risk/reward calculation logic"""
    print("\n" + "=" * 60)
    print("Testing Risk/Reward Calculation")
    print("=" * 60)
    
    # Example calculations
    entry_price = 1.10000
    stop_loss = 1.09900
    risk = abs(entry_price - stop_loss)  # 0.00100
    
    print(f"\nExample Trade Setup:")
    print(f"  Entry Price: {entry_price:.5f}")
    print(f"  Stop Loss: {stop_loss:.5f}")
    print(f"  Risk: {risk:.5f} ({risk/0.0001:.1f} pips)")
    
    print(f"\nTake Profit Calculations:")
    
    # Bear market scenarios
    print(f"\n  BEAR Market:")
    # Short position in bear market (favorable)
    rr = 1.2
    tp_short_bear = entry_price - (risk * rr)
    print(f"    Short Position (R:R={rr}):")
    print(f"      Take Profit: {tp_short_bear:.5f}")
    print(f"      Potential Reward: {risk * rr:.5f} ({(risk * rr)/0.0001:.1f} pips)")
    
    # Long position in bear market (conservative)
    rr = 0.6
    tp_long_bear = entry_price + (risk * rr)
    print(f"    Long Position (R:R={rr}):")
    print(f"      Take Profit: {tp_long_bear:.5f}")
    print(f"      Potential Reward: {risk * rr:.5f} ({(risk * rr)/0.0001:.1f} pips)")
    
    # Bull market scenarios
    print(f"\n  BULL Market:")
    # Long position in bull market (favorable)
    rr = 1.2
    tp_long_bull = entry_price + (risk * rr)
    print(f"    Long Position (R:R={rr}):")
    print(f"      Take Profit: {tp_long_bull:.5f}")
    print(f"      Potential Reward: {risk * rr:.5f} ({(risk * rr)/0.0001:.1f} pips)")
    
    # Short position in bull market (conservative)
    rr = 0.6
    tp_short_bull = entry_price - (risk * rr)
    print(f"    Short Position (R:R={rr}):")
    print(f"      Take Profit: {tp_short_bull:.5f}")
    print(f"      Potential Reward: {risk * rr:.5f} ({(risk * rr)/0.0001:.1f} pips)")


def main():
    """Run all tests"""
    print("\n" + "=" * 80)
    print("MARKET-AWARE TRADING BOT TEST SUITE")
    print("=" * 80)
    
    # Test 1: Configuration loading
    test_config_loading()
    
    # Test 2: Risk/Reward calculations
    test_risk_reward_calculation()
    
    # Test 3: Market trend detection (requires API connection)
    print("\n" + "-" * 60)
    response = input("Test market trend detection? (requires API) [y/n]: ")
    if response.lower() == 'y':
        test_market_trend_detection()
    
    print("\n" + "=" * 80)
    print("TEST SUITE COMPLETE")
    print("=" * 80)
    print("\nTo run the bot:")
    print("  ./scripts/auto_trade_market.sh at=account1 fr=EUR_USD tf=5m")
    print("\nBot features:")
    print("  ✓ Loads configuration from account1/config.yaml")
    print("  ✓ Checks 3H PP SuperTrend for market direction")
    print("  ✓ Applies dynamic R:R based on market trend")
    print("  ✓ Trails stop loss using trading timeframe PP SuperTrend")
    print("  ✓ Logs trades to CSV with market trend and R:R data")


if __name__ == "__main__":
    main()