"""
Test script to verify stop loss price formatting
"""
from src.oanda_client import OANDAClient
from src.config import TradingConfig
import json

def test_price_formatting():
    """Test that prices are formatted correctly for OANDA API"""

    # Test stop loss price
    stop_loss = 1.17098

    # Old format (buggy)
    old_format = str(stop_loss)

    # New format (fixed)
    new_format = f"{stop_loss:.5f}"

    print("Price Formatting Test:")
    print(f"  Original value: {stop_loss}")
    print(f"  Old format str(): '{old_format}'")
    print(f"  New format f-string: '{new_format}'")
    print()

    # Test with edge cases
    test_values = [1.17098, 1.170980000001, 1.1709799999, 1.17043, 1.16871]

    print("Edge Case Tests:")
    for val in test_values:
        formatted = f"{val:.5f}"
        print(f"  {val} -> '{formatted}'")
    print()

def test_order_data_structure():
    """Test the order data structure that will be sent to OANDA"""

    stop_loss = 1.17098
    take_profit = 1.17500

    order_data = {
        "order": {
            "type": "MARKET",
            "instrument": "EUR_USD",
            "units": "1",
            "timeInForce": "FOK",
            "positionFill": "DEFAULT",
            "stopLossOnFill": {
                "price": f"{stop_loss:.5f}"
            },
            "takeProfitOnFill": {
                "price": f"{take_profit:.5f}"
            }
        }
    }

    print("Order Data Structure:")
    print(json.dumps(order_data, indent=2))
    print()

def test_live_connection():
    """Test connection to OANDA and fetch current price"""
    print("Testing live connection to OANDA...")

    client = OANDAClient()

    # Get current price
    price = client.get_current_price(TradingConfig.instrument)
    if price:
        print(f"✅ Successfully connected to OANDA")
        print(f"  Current {TradingConfig.instrument} price:")
        print(f"  Bid: {price['bid']:.5f}")
        print(f"  Ask: {price['ask']:.5f}")
    else:
        print("❌ Failed to connect to OANDA")
    print()

if __name__ == "__main__":
    print("=" * 60)
    print("OANDA Order Placement Fix Test")
    print("=" * 60)
    print()

    test_price_formatting()
    test_order_data_structure()
    test_live_connection()

    print("=" * 60)
    print("Test completed!")
    print("=" * 60)
