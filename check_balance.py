#!/usr/bin/env python3
"""
Check OANDA Account Balance and Positions
"""

from src.config import OANDAConfig, TradingConfig
from src.oanda_client import OANDAClient

def check_account_status():
    """Check account balance and open positions"""
    
    # Set account
    OANDAConfig.set_account('account1')
    
    # Initialize client
    client = OANDAClient()
    
    # Get account summary
    account_summary = client.get_account_summary()
    
    if account_summary:
        print("\n" + "=" * 60)
        print("ACCOUNT STATUS")
        print("=" * 60)
        print(f"Account ID: {OANDAConfig.account_id}")
        print(f"Mode: {'PRACTICE' if OANDAConfig.is_practice else 'LIVE'}")
        print("-" * 60)
        print(f"Balance: ${account_summary['balance']:,.2f}")
        print(f"NAV (Net Asset Value): ${account_summary['nav']:,.2f}")
        print(f"Unrealized P/L: ${account_summary['unrealized_pl']:,.2f}")
        print(f"Margin Used: ${account_summary['margin_used']:,.2f}")
        print(f"Margin Available: ${account_summary['margin_available']:,.2f}")
        print(f"Open Trade Count: {account_summary['open_trade_count']}")
        print(f"Open Position Count: {account_summary['open_position_count']}")
        print("=" * 60)
        
        # Check position for EUR_USD
        position = client.get_position('EUR_USD')
        if position and position.get('units', 0) != 0:
            print("\nOPEN POSITION:")
            print("-" * 60)
            print(f"Instrument: EUR_USD")
            print(f"  Side: {position['side']}")
            print(f"  Units: {abs(position['units']):,.0f}")
            print(f"  Average Price: {position.get('average_price', 'N/A')}")
            print(f"  Unrealized P/L: ${position['unrealized_pl']:.2f}")
            print(f"  Margin Used: ${position.get('margin_used', 0):.2f}")
            print("-" * 60)
        else:
            print("\nNo open position for EUR_USD")
            
        # Check open trades for EUR_USD
        trades = client.get_trades('EUR_USD')
        if trades:
            print("\nOPEN TRADES:")
            print("-" * 60)
            for trade in trades[:5]:  # Show first 5 trades
                print(f"Trade ID: {trade['id']}")
                print(f"  Units: {trade['units']}")
                print(f"  Entry Price: {trade.get('price', 'N/A')}")
                print(f"  Current Price: {trade.get('current_units_price', 'N/A')}")
                print(f"  Unrealized P/L: ${float(trade.get('unrealized_pl', 0)):.2f}")
                if trade.get('stop_loss_order_id'):
                    print(f"  Stop Loss Order: {trade.get('stop_loss_order_id')}")
                print("-" * 60)
    else:
        print("Failed to fetch account data")
        
    return account_summary

if __name__ == "__main__":
    check_account_status()