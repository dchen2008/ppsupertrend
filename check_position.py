#!/usr/bin/env python3
"""
Simple script to check OANDA account1 current positions and trades with raw API response.
Shows Stop Loss, Take Profit, and other order details.
"""

import requests
import json
import sys

# Add src to path for config import
sys.path.insert(0, 'src')
from config import OANDAConfig

def main():
    # Set account (default to account1, or pass as argument)
    account = sys.argv[1] if len(sys.argv) > 1 else 'account1'
    OANDAConfig.set_account(account)

    base_url = OANDAConfig.get_base_url()
    headers = OANDAConfig.get_headers()
    account_id = OANDAConfig.account_id

    print(f"=" * 60)
    print(f"Account: {account} ({account_id})")
    print(f"=" * 60)

    # 1. Get open trades (includes SL/TP details)
    print("\n>>> OPEN TRADES (with SL/TP details):")
    print("-" * 60)
    url = f"{base_url}/v3/accounts/{account_id}/openTrades"
    response = requests.get(url, headers=headers, timeout=10)
    trades_data = response.json()
    print(json.dumps(trades_data, indent=2))

    # 2. Get open positions summary
    print("\n>>> OPEN POSITIONS:")
    print("-" * 60)
    url = f"{base_url}/v3/accounts/{account_id}/openPositions"
    response = requests.get(url, headers=headers, timeout=10)
    positions_data = response.json()
    print(json.dumps(positions_data, indent=2))

    # 3. Get current pricing for EUR_USD
    print("\n>>> CURRENT PRICE (EUR_USD):")
    print("-" * 60)
    url = f"{base_url}/v3/accounts/{account_id}/pricing"
    params = {'instruments': 'EUR_USD'}
    response = requests.get(url, headers=headers, params=params, timeout=10)
    price_data = response.json()
    print(json.dumps(price_data, indent=2))

    # 4. Account summary
    print("\n>>> ACCOUNT SUMMARY:")
    print("-" * 60)
    url = f"{base_url}/v3/accounts/{account_id}/summary"
    response = requests.get(url, headers=headers, timeout=10)
    summary_data = response.json()
    print(json.dumps(summary_data, indent=2))

    # 5. Recent transactions (to see order history including TP/SL)
    print("\n>>> RECENT TRANSACTIONS (last 20):")
    print("-" * 60)
    url = f"{base_url}/v3/accounts/{account_id}/transactions"
    params = {'pageSize': 20}
    response = requests.get(url, headers=headers, params=params, timeout=10)
    tx_data = response.json()

    # Fetch transaction details for each
    if 'pages' in tx_data and tx_data['pages']:
        # Get the last page URL which has most recent transactions
        last_page = tx_data['pages'][-1]
        response = requests.get(last_page, headers=headers, timeout=10)
        tx_details = response.json()
        print(json.dumps(tx_details, indent=2))
    else:
        print(json.dumps(tx_data, indent=2))

if __name__ == "__main__":
    main()
