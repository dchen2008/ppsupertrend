"""
Test OANDA Connection and Indicator Calculation
Run this script to verify everything is working before starting the trading bot
"""

import sys
from datetime import datetime
from src.config import OANDAConfig, TradingConfig
from src.oanda_client import OANDAClient
from src.indicators import calculate_pp_supertrend, get_current_signal


def print_header(text):
    """Print formatted header"""
    print("\n" + "=" * 80)
    print(text)
    print("=" * 80)


def print_section(text):
    """Print formatted section"""
    print("\n" + "-" * 80)
    print(text)
    print("-" * 80)


def test_connection():
    """Test OANDA API connection"""
    print_header("OANDA Connection Test")

    print(f"\nAccount ID: {OANDAConfig.account_id}")
    print(f"Mode: {'PRACTICE (Demo)' if OANDAConfig.is_practice else 'LIVE (Real Money)'}")
    print(f"Base URL: {OANDAConfig.get_base_url()}")

    client = OANDAClient()

    # Test 1: Account Summary
    print_section("Test 1: Fetching Account Summary")
    account = client.get_account_summary()

    if account:
        print("✅ Connection successful!")
        print(f"\nAccount Balance: ${account['balance']:.2f}")
        print(f"NAV: ${account['nav']:.2f}")
        print(f"Unrealized P/L: ${account['unrealized_pl']:.2f}")
        print(f"Margin Used: ${account['margin_used']:.2f}")
        print(f"Margin Available: ${account['margin_available']:.2f}")
        print(f"Open Trades: {account['open_trade_count']}")
        print(f"Open Positions: {account['open_position_count']}")
    else:
        print("❌ Failed to connect to OANDA")
        print("\nPossible issues:")
        print("- Check your API key")
        print("- Check your account ID")
        print("- Verify internet connection")
        return False

    # Test 2: Current Price
    print_section(f"Test 2: Fetching Current Price for {TradingConfig.instrument}")
    price = client.get_current_price(TradingConfig.instrument)

    if price:
        print("✅ Price data retrieved successfully!")
        print(f"\nBid: {price['bid']:.5f}")
        print(f"Ask: {price['ask']:.5f}")
        print(f"Spread: {(price['ask'] - price['bid']):.5f} ({((price['ask'] - price['bid']) / price['bid'] * 10000):.1f} pips)")
        print(f"Time: {price['time']}")
    else:
        print("❌ Failed to fetch price data")
        return False

    # Test 3: Historical Data
    print_section(f"Test 3: Fetching Historical Candle Data ({TradingConfig.granularity})")
    df = client.get_candles(
        instrument=TradingConfig.instrument,
        granularity=TradingConfig.granularity,
        count=TradingConfig.lookback_candles
    )

    if df is not None and len(df) > 0:
        print("✅ Historical data retrieved successfully!")
        print(f"\nCandles fetched: {len(df)}")
        print(f"Date range: {df.index[0]} to {df.index[-1]}")
        print(f"\nLatest candle:")
        latest = df.iloc[-1]
        print(f"  Time: {df.index[-1]}")
        print(f"  Open: {latest['open']:.5f}")
        print(f"  High: {latest['high']:.5f}")
        print(f"  Low: {latest['low']:.5f}")
        print(f"  Close: {latest['close']:.5f}")
        print(f"  Volume: {latest['volume']}")
    else:
        print("❌ Failed to fetch historical data")
        return False

    # Test 4: Indicator Calculation
    print_section("Test 4: Calculating Pivot Point SuperTrend Indicator")
    print(f"Parameters: Pivot Period={TradingConfig.pivot_period}, "
          f"ATR Factor={TradingConfig.atr_factor}, "
          f"ATR Period={TradingConfig.atr_period}")

    df_with_indicators = calculate_pp_supertrend(
        df,
        pivot_period=TradingConfig.pivot_period,
        atr_factor=TradingConfig.atr_factor,
        atr_period=TradingConfig.atr_period
    )

    if df_with_indicators is not None:
        print("✅ Indicator calculation successful!")

        # Get current signal
        signal_info = get_current_signal(df_with_indicators)

        if signal_info:
            print("\n📊 Current Market Analysis:")
            print(f"  Signal: {signal_info['signal']}")
            print(f"  Trend: {'UPTREND' if signal_info['trend'] == 1 else 'DOWNTREND'}")
            print(f"  Current Price: {signal_info['price']:.5f}")
            print(f"  SuperTrend Line: {signal_info['supertrend']:.5f}" if signal_info['supertrend'] else "  SuperTrend Line: Not available yet")
            print(f"  Support: {signal_info['support']:.5f}" if signal_info['support'] else "  Support: Not detected yet")
            print(f"  Resistance: {signal_info['resistance']:.5f}" if signal_info['resistance'] else "  Resistance: Not detected yet")
            print(f"  ATR: {signal_info['atr']:.5f}" if signal_info['atr'] else "  ATR: Calculating...")

            # Check for recent pivot points
            recent_pivots = df_with_indicators.tail(20)
            pivot_highs = recent_pivots['pivot_high'].dropna()
            pivot_lows = recent_pivots['pivot_low'].dropna()

            print(f"\n  Recent Pivot Highs detected: {len(pivot_highs)}")
            print(f"  Recent Pivot Lows detected: {len(pivot_lows)}")

            if signal_info['signal'] == 'BUY':
                print("\n  🟢 BUY SIGNAL DETECTED!")
                print("  → The bot would enter a LONG position if running")
            elif signal_info['signal'] == 'SELL':
                print("\n  🔴 SELL SIGNAL DETECTED!")
                print("  → The bot would enter a SHORT position if running")
            elif signal_info['signal'] == 'HOLD_LONG':
                print("\n  📈 Currently in UPTREND - Would hold LONG position")
            elif signal_info['signal'] == 'HOLD_SHORT':
                print("\n  📉 Currently in DOWNTREND - Would hold SHORT position")
            else:
                print("\n  ⏸️  No action - Waiting for clear signal")

    else:
        print("❌ Failed to calculate indicators")
        return False

    # Test 5: Open Positions
    print_section("Test 5: Checking Open Positions")
    positions = client.get_open_positions()

    if positions is not None:
        print(f"✅ Successfully retrieved positions")
        if len(positions) > 0:
            print(f"\nYou have {len(positions)} open position(s):")
            for pos in positions:
                print(f"\n  {pos['instrument']}:")
                print(f"    Side: {pos['side']}")
                print(f"    Units: {abs(pos['units'])}")
                print(f"    Unrealized P/L: ${pos['unrealized_pl']:.2f}")
        else:
            print("\nNo open positions")
    else:
        print("❌ Failed to retrieve positions")

    return True


def main():
    """Main test function"""
    print("\n" + "🔍 Pivot Point SuperTrend Trading Bot - Connection Test")
    print("=" * 80)
    print("This script will test:")
    print("  1. OANDA API connection")
    print("  2. Account access")
    print("  3. Market data retrieval")
    print("  4. Indicator calculations")
    print("  5. Current market signals")

    success = test_connection()

    print("\n" + "=" * 80)
    if success:
        print("✅ ALL TESTS PASSED!")
        print("=" * 80)
        print("\nYour setup is ready. You can now run the trading bot:")
        print("  python trading_bot.py")
        print("\nMake sure to:")
        print("  - Review the configuration in config.py")
        print("  - Understand the strategy in the documentation")
        print("  - Start with small position sizes")
        print("  - Monitor the bot regularly")
    else:
        print("❌ SOME TESTS FAILED")
        print("=" * 80)
        print("\nPlease fix the issues above before running the trading bot.")
        print("Check:")
        print("  - API credentials in config.py")
        print("  - Internet connection")
        print("  - OANDA account status")

    print()


if __name__ == "__main__":
    main()
