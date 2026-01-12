#!/usr/bin/env python3
"""
Fetch transaction history for a specific trade to see SL/TP orders
"""

import requests
import json
import sys

sys.path.insert(0, 'src')
from config import OANDAConfig

def main():
    account = sys.argv[1] if len(sys.argv) > 1 else 'account1'
    trade_id = sys.argv[2] if len(sys.argv) > 2 else '769'

    OANDAConfig.set_account(account)
    base_url = OANDAConfig.get_base_url()
    headers = OANDAConfig.get_headers()
    account_id = OANDAConfig.account_id

    print(f"Account: {account} | Trade ID: {trade_id}")
    print("=" * 60)

    # Get transactions related to this trade
    # Fetch transactions around the trade ID (trade_id - 5 to trade_id + 10)
    start_id = max(1, int(trade_id) - 5)
    end_id = int(trade_id) + 10

    url = f"{base_url}/v3/accounts/{account_id}/transactions/idrange"
    params = {'from': start_id, 'to': end_id}

    response = requests.get(url, headers=headers, params=params, timeout=10)
    data = response.json()

    print(f"\n>>> TRANSACTIONS {start_id} to {end_id}:")
    print("-" * 60)
    print(json.dumps(data, indent=2))

if __name__ == "__main__":
    main()
