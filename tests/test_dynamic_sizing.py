"""
Test dynamic position sizing with different stop loss distances
"""
from src.risk_manager import RiskManager
from src.config import TradingConfig
import sys

def test_dynamic_position_sizing():
    """Test position sizing with various stop loss scenarios"""

    print("=" * 80)
    print("DYNAMIC POSITION SIZING TEST")
    print("=" * 80)
    print()
    print(f"Configuration:")
    print(f"  use_dynamic_sizing: {TradingConfig.use_dynamic_sizing}")
    print(f"  risk_per_trade: {TradingConfig.risk_per_trade}")
    print(f"  Account Balance: $500,000 (example)")
    print()

    risk_manager = RiskManager()
    account_balance = 500000

    # Test scenarios with different stop losses
    scenarios = [
        {
            'name': 'Tight Stop (5 pips)',
            'entry': 1.17300,
            'stop': 1.17250,
            'supertrend': 1.17250,
        },
        {
            'name': 'Normal Stop (10 pips)',
            'entry': 1.17300,
            'stop': 1.17200,
            'supertrend': 1.17200,
        },
        {
            'name': 'Wide Stop (20 pips)',
            'entry': 1.17300,
            'stop': 1.17100,
            'supertrend': 1.17100,
        },
        {
            'name': 'Very Wide Stop (50 pips)',
            'entry': 1.17300,
            'stop': 1.16800,
            'supertrend': 1.16800,
        },
    ]

    print("=" * 80)
    print("TEST RESULTS")
    print("=" * 80)
    print()

    for scenario in scenarios:
        print(f"{scenario['name']}:")
        print(f"  Entry Price: {scenario['entry']:.5f}")
        print(f"  Stop Loss: {scenario['stop']:.5f}")

        stop_distance = abs(scenario['entry'] - scenario['stop'])
        stop_pips = stop_distance / 0.0001
        print(f"  Stop Distance: {stop_distance:.5f} ({stop_pips:.1f} pips)")

        # Create signal info
        signal_info = {
            'price': scenario['entry'],
            'supertrend': scenario['supertrend'],
            'atr': stop_distance / TradingConfig.atr_factor
        }

        # Calculate position size
        position_size = risk_manager.calculate_position_size(account_balance, signal_info)

        # Calculate metrics
        lots = position_size / 100000
        notional_value = position_size * scenario['entry']
        actual_risk = position_size * stop_distance
        value_per_pip = (position_size / 100000) * 10

        print(f"  Position Size: {position_size:,} units ({lots:.3f} lots)")
        print(f"  Notional Value: ${notional_value:,.2f}")
        print(f"  Actual Risk: ${actual_risk:.2f}")
        print(f"  Value per Pip: ${value_per_pip:.2f}")
        print()

    print("=" * 80)
    print()

    # Test with fixed position size mode
    print("COMPARISON: Fixed Position Size Mode")
    print("=" * 80)
    print(f"If use_dynamic_sizing = False:")
    print(f"  position_size = {TradingConfig.position_size}")
    print(f"  Every trade uses exactly {TradingConfig.position_size} units")
    print(f"  Risk varies with stop loss distance!")
    print()
    print("Example with 10 pip stop:")
    fixed_risk_10pips = TradingConfig.position_size * 0.00100
    print(f"  Risk = {TradingConfig.position_size} × 0.00100 = ${fixed_risk_10pips:.2f}")
    print()
    print("Example with 50 pip stop:")
    fixed_risk_50pips = TradingConfig.position_size * 0.00500
    print(f"  Risk = {TradingConfig.position_size} × 0.00500 = ${fixed_risk_50pips:.2f}")
    print()
    print("=" * 80)
    print()

    # Summary
    print("RECOMMENDATION:")
    print("-" * 80)
    print("✅ use_dynamic_sizing = True (ENABLED)")
    print(f"   risk_per_trade = {TradingConfig.risk_per_trade}")
    if TradingConfig.risk_per_trade >= 1:
        print(f"   → Risk ${TradingConfig.risk_per_trade} per trade (fixed dollar amount)")
    else:
        print(f"   → Risk {TradingConfig.risk_per_trade*100}% per trade (percentage of balance)")
    print()
    print("Benefits:")
    print("  • Consistent risk per trade regardless of stop loss distance")
    print("  • Larger positions with tight stops, smaller with wide stops")
    print("  • Better risk management and capital preservation")
    print("=" * 80)

if __name__ == "__main__":
    # Check if dynamic sizing is enabled
    if not TradingConfig.use_dynamic_sizing:
        print("\n⚠️  WARNING: Dynamic sizing is currently DISABLED")
        print(f"Set use_dynamic_sizing = True in config.py to enable risk-based position sizing\n")
        sys.exit(1)

    test_dynamic_position_sizing()
