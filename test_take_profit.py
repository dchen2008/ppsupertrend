#!/usr/bin/env python3
"""Test script to verify take profit is being set correctly"""

import sys
sys.path.insert(0, 'src')

from oanda_client import OANDAClient
from config import OANDAConfig

def check_current_trades():
    """Check current trades and their take profit orders"""
    
    # Set account
    OANDAConfig.set_account('account1')
    client = OANDAClient()
    
    print("=" * 60)
    print("CHECKING CURRENT TRADES AND TAKE PROFIT ORDERS")
    print("=" * 60)
    
    # Get all open trades
    trades = client.get_trades()
    
    if not trades:
        print("No open trades found")
        return
    
    for trade in trades:
        print(f"\nRaw trade data: {trade}")
        print(f"\nTrade ID: {trade.get('id')}")
        print(f"Instrument: {trade.get('instrument')}")
        print(f"Units: {trade.get('currentUnits') or trade.get('units')}")
        print(f"Entry Price: {trade.get('price')}")
        print(f"Unrealized P/L: {trade.get('unrealizedPL') or trade.get('unrealized_pl')}")
        
        # Check if take profit order exists
        take_profit_order = trade.get('takeProfitOrder')
        if take_profit_order:
            print(f"✅ Take Profit Order ID: {take_profit_order.get('id')}")
            print(f"   Take Profit Price: {take_profit_order.get('price')}")
        else:
            print("❌ NO TAKE PROFIT ORDER SET")
            
        # Check if stop loss order exists
        stop_loss_order = trade.get('stopLossOrder')
        if stop_loss_order:
            print(f"✅ Stop Loss Order ID: {stop_loss_order.get('id')}")
            print(f"   Stop Loss Price: {stop_loss_order.get('price')}")
        else:
            print("❌ NO STOP LOSS ORDER SET")
            
        print("-" * 60)

if __name__ == "__main__":
    check_current_trades()