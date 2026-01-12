#!/usr/bin/env python3
"""Test script to verify spread buffer calculation"""

import yaml

def test_spread_buffer_calculation():
    """Test the spread buffer calculation logic"""
    
    # Load config
    with open('src/config.yaml', 'r') as f:
        config = yaml.safe_load(f)
    
    spread_buffer_pips = config.get('stoploss', {}).get('spread_buffer_pips', 3)
    
    # Test values
    typical_spread = 0.00015  # 1.5 pips typical spread
    buffer_price = spread_buffer_pips * 0.0001  # Convert pips to price
    spread_adjustment = (typical_spread / 2.0) + buffer_price
    
    print("=" * 50)
    print("SPREAD BUFFER CALCULATION TEST")
    print("=" * 50)
    print(f"Config buffer setting: {spread_buffer_pips} pips")
    print(f"Typical spread: {typical_spread:.5f} ({typical_spread/0.0001:.1f} pips)")
    print(f"Buffer in price: {buffer_price:.5f}")
    print(f"Half spread: {typical_spread/2.0:.5f}")
    print(f"Total adjustment: {spread_adjustment:.5f} ({spread_adjustment/0.0001:.1f} pips)")
    print()
    
    # Example stop loss calculations
    supertrend = 1.05000
    print("Example Stop Loss Calculations:")
    print(f"SuperTrend line: {supertrend:.5f}")
    print()
    
    # LONG position
    long_stop = supertrend - spread_adjustment
    print(f"LONG position stop loss: {long_stop:.5f}")
    print(f"  Distance from SuperTrend: {spread_adjustment:.5f} ({spread_adjustment/0.0001:.1f} pips below)")
    print()
    
    # SHORT position
    short_stop = supertrend + spread_adjustment
    print(f"SHORT position stop loss: {short_stop:.5f}")
    print(f"  Distance from SuperTrend: {spread_adjustment:.5f} ({spread_adjustment/0.0001:.1f} pips above)")
    print()
    
    print("This ensures the stop loss will trigger when MID price touches SuperTrend line,")
    print("accounting for both the spread (half spread) and an additional safety buffer.")

if __name__ == "__main__":
    test_spread_buffer_calculation()