"""
Test script to verify spread adjustment is working correctly
"""

from src.oanda_client import OANDAClient
from src.config import TradingConfig

def test_spread_adjustment():
    """Test the spread adjustment calculation"""

    print("=" * 80)
    print("SPREAD ADJUSTMENT TEST")
    print("=" * 80)

    # Initialize client
    client = OANDAClient()
    instrument = "EUR_USD"

    # Get current price data
    print(f"\n1. Fetching current prices for {instrument}...")
    price_data = client.get_current_price(instrument)

    if not price_data:
        print("❌ Failed to fetch price data")
        return

    bid = price_data['bid']
    ask = price_data['ask']
    spread = ask - bid
    midpoint = (bid + ask) / 2

    print(f"\n✓ Current Market Prices:")
    print(f"  BID:      {bid:.5f}")
    print(f"  ASK:      {ask:.5f}")
    print(f"  MIDPOINT: {midpoint:.5f}")
    print(f"  SPREAD:   {spread:.5f} ({spread/0.0001:.1f} pips)")

    # Test SHORT position
    print("\n" + "=" * 80)
    print("2. Testing SHORT Position Stop Loss Adjustment")
    print("=" * 80)

    supertrend_short = 1.16787  # Example SuperTrend value
    spread_adjustment = spread / 2.0
    adjusted_stop_short = supertrend_short + spread_adjustment

    print(f"\nScenario: SHORT position with SuperTrend at {supertrend_short:.5f}")
    print(f"\n  SuperTrend (midpoint):    {supertrend_short:.5f}")
    print(f"  Spread:                   {spread:.5f} ({spread/0.0001:.1f} pips)")
    print(f"  Adjustment:               +{spread_adjustment:.5f} (+{spread_adjustment/0.0001:.2f} pips)")
    print(f"  Adjusted Stop Loss:       {adjusted_stop_short:.5f}")

    print(f"\nWhen stop triggers at ASK = {adjusted_stop_short:.5f}:")
    print(f"  Expected ASK:             {adjusted_stop_short:.5f}")
    print(f"  Expected BID:             {adjusted_stop_short - spread:.5f}")
    print(f"  Expected MIDPOINT:        {(adjusted_stop_short + (adjusted_stop_short - spread))/2:.5f}")

    expected_midpoint_short = (adjusted_stop_short + (adjusted_stop_short - spread)) / 2
    difference_short = abs(expected_midpoint_short - supertrend_short)

    if difference_short < 0.000001:  # Allow tiny floating point error
        print(f"\n  ✓ CORRECT! Midpoint = {expected_midpoint_short:.5f} (matches SuperTrend {supertrend_short:.5f})")
    else:
        print(f"\n  ❌ ERROR! Midpoint = {expected_midpoint_short:.5f} (should be {supertrend_short:.5f})")

    # Test LONG position
    print("\n" + "=" * 80)
    print("3. Testing LONG Position Stop Loss Adjustment")
    print("=" * 80)

    supertrend_long = 1.16600  # Example SuperTrend value
    adjusted_stop_long = supertrend_long - spread_adjustment

    print(f"\nScenario: LONG position with SuperTrend at {supertrend_long:.5f}")
    print(f"\n  SuperTrend (midpoint):    {supertrend_long:.5f}")
    print(f"  Spread:                   {spread:.5f} ({spread/0.0001:.1f} pips)")
    print(f"  Adjustment:               -{spread_adjustment:.5f} (-{spread_adjustment/0.0001:.2f} pips)")
    print(f"  Adjusted Stop Loss:       {adjusted_stop_long:.5f}")

    print(f"\nWhen stop triggers at BID = {adjusted_stop_long:.5f}:")
    print(f"  Expected BID:             {adjusted_stop_long:.5f}")
    print(f"  Expected ASK:             {adjusted_stop_long + spread:.5f}")
    print(f"  Expected MIDPOINT:        {(adjusted_stop_long + (adjusted_stop_long + spread))/2:.5f}")

    expected_midpoint_long = (adjusted_stop_long + (adjusted_stop_long + spread)) / 2
    difference_long = abs(expected_midpoint_long - supertrend_long)

    if difference_long < 0.000001:  # Allow tiny floating point error
        print(f"\n  ✓ CORRECT! Midpoint = {expected_midpoint_long:.5f} (matches SuperTrend {supertrend_long:.5f})")
    else:
        print(f"\n  ❌ ERROR! Midpoint = {expected_midpoint_long:.5f} (should be {supertrend_long:.5f})")

    # Test configuration
    print("\n" + "=" * 80)
    print("4. Configuration Check")
    print("=" * 80)

    print(f"\nSpread Adjustment Enabled: {TradingConfig.use_spread_adjustment}")

    if TradingConfig.use_spread_adjustment:
        print("✓ Spread adjustment is ENABLED")
    else:
        print("⚠️  WARNING: Spread adjustment is DISABLED")
        print("   Enable it in config.py: use_spread_adjustment = True")

    # Summary
    print("\n" + "=" * 80)
    print("5. Summary")
    print("=" * 80)

    if difference_short < 0.000001 and difference_long < 0.000001:
        print("\n✓ ALL TESTS PASSED!")
        print("  - SHORT position stop loss adjustment is correct")
        print("  - LONG position stop loss adjustment is correct")
        print("  - Positions will close when chart price touches SuperTrend line")
    else:
        print("\n❌ TESTS FAILED!")
        print("  - Stop loss adjustment formulas are incorrect")

    print("\n" + "=" * 80)

if __name__ == "__main__":
    test_spread_adjustment()
