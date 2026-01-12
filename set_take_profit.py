#!/usr/bin/env python3
"""
Script to view current trade details and set/update take profit price.

Usage:
    # View current trade info only
    python3 set_take_profit.py
    python3 set_take_profit.py account1

    # Set/update take profit price
    python3 set_take_profit.py take_profit_price=1.16210
    python3 set_take_profit.py account1 take_profit_price=1.16210

    # Set take profit with custom R:R ratio
    python3 set_take_profit.py rr=1.5
"""

import requests
import json
import sys
import yaml
import os

sys.path.insert(0, 'src')
from config import OANDAConfig


def load_rr_config(account):
    """Load R:R config from account config or defaults"""
    # Default R:R values
    default_rr = {
        'bear_market': {'short_rr': 1.0, 'long_rr': 0.5},
        'bull_market': {'short_rr': 0.5, 'long_rr': 1.0}
    }

    # Try to load from account config
    account_config_path = f"{account}/config.yaml"
    if os.path.exists(account_config_path):
        try:
            with open(account_config_path, 'r') as f:
                config = yaml.safe_load(f)
                if config and 'risk_reward' in config:
                    rr_config = config['risk_reward']
                    # Merge with defaults
                    for market in ['bear_market', 'bull_market']:
                        if market in rr_config:
                            default_rr[market].update(rr_config[market])
        except Exception:
            pass

    return default_rr


def get_open_trades(base_url, headers, account_id):
    """Fetch open trades with SL/TP details"""
    url = f"{base_url}/v3/accounts/{account_id}/openTrades"
    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()
    return response.json()


def create_take_profit_order(base_url, headers, account_id, trade_id, price):
    """Create a new take profit order for a trade"""
    url = f"{base_url}/v3/accounts/{account_id}/orders"
    order_data = {
        "order": {
            "type": "TAKE_PROFIT",
            "tradeID": str(trade_id),
            "price": f"{price:.5f}",
            "timeInForce": "GTC"
        }
    }
    response = requests.post(url, headers=headers, json=order_data, timeout=10)
    response.raise_for_status()
    return response.json()


def update_take_profit_order(base_url, headers, account_id, order_id, trade_id, price):
    """Update an existing take profit order"""
    url = f"{base_url}/v3/accounts/{account_id}/orders/{order_id}"
    order_data = {
        "order": {
            "type": "TAKE_PROFIT",
            "tradeID": str(trade_id),
            "price": f"{price:.5f}",
            "timeInForce": "GTC"
        }
    }
    response = requests.put(url, headers=headers, json=order_data, timeout=10)
    response.raise_for_status()
    return response.json()


def main():
    # Parse arguments
    account = 'account1'
    take_profit_price = None
    custom_rr = None

    for arg in sys.argv[1:]:
        if arg.startswith('take_profit_price='):
            take_profit_price = float(arg.split('=')[1])
        elif arg.startswith('rr='):
            custom_rr = float(arg.split('=')[1])
        elif not arg.startswith('-') and '=' not in arg:
            account = arg

    OANDAConfig.set_account(account)
    base_url = OANDAConfig.get_base_url()
    headers = OANDAConfig.get_headers()
    account_id = OANDAConfig.account_id

    # Load R:R config
    rr_config = load_rr_config(account)

    print(f"{'=' * 60}")
    print(f"Account: {account} ({account_id})")
    print(f"{'=' * 60}")

    # Fetch open trades
    trades_data = get_open_trades(base_url, headers, account_id)
    trades = trades_data.get('trades', [])

    if not trades:
        print("\nNo open trades found.")
        return

    print(f"\nFound {len(trades)} open trade(s):\n")

    for trade in trades:
        trade_id = trade['id']
        instrument = trade['instrument']
        entry_price = float(trade['price'])
        current_units = float(trade['currentUnits'])
        unrealized_pl = float(trade['unrealizedPL'])

        # Get stop loss info
        sl_order = trade.get('stopLossOrder')
        sl_price = float(sl_order['price']) if sl_order else None
        sl_order_id = sl_order['id'] if sl_order else None

        # Get take profit info
        tp_order = trade.get('takeProfitOrder')
        tp_price = float(tp_order['price']) if tp_order else None
        tp_order_id = tp_order['id'] if tp_order else None

        # Determine position type
        position_type = 'LONG' if current_units > 0 else 'SHORT'

        print(f"Trade ID:        {trade_id}")
        print(f"Instrument:      {instrument}")
        print(f"Position:        {position_type} ({current_units:,.0f} units)")
        print(f"Entry Price:     {entry_price:.5f}")
        print(f"Unrealized P/L:  ${unrealized_pl:.2f}")
        print(f"Stop Loss:       {sl_price:.5f}" if sl_price else "Stop Loss:       NOT SET")
        print(f"Take Profit:     {tp_price:.5f}" if tp_price else "Take Profit:     NOT SET")

        # Calculate TP based on R:R if SL exists
        calculated_tp = None
        if sl_price is not None:
            # Calculate risk in pips
            risk_pips = abs(entry_price - sl_price) / 0.0001

            # Get R:R ratio from config or custom
            if custom_rr is not None:
                rr_ratio = custom_rr
            elif position_type == 'SHORT':
                rr_ratio = rr_config['bear_market']['short_rr']
            else:
                rr_ratio = rr_config['bull_market']['long_rr']

            # Calculate TP based on R:R
            risk = abs(entry_price - sl_price)
            reward = risk * rr_ratio
            if position_type == 'LONG':
                calculated_tp = entry_price + reward
            else:
                calculated_tp = entry_price - reward

            reward_pips = reward / 0.0001

            # Show suggestion if TP not set and no take_profit_price provided
            if tp_price is None and take_profit_price is None and custom_rr is None:
                print(f"\n{'*' * 60}")
                print(f"SUGGESTED Take Profit:")
                print(f"  For your {position_type} position with entry {entry_price:.5f}")
                print(f"  and R:R={rr_ratio}, TP should be around {calculated_tp:.5f}")
                print(f"  ({reward_pips:.1f} pips {'below' if position_type == 'SHORT' else 'above'} entry,")
                print(f"   matching {risk_pips:.1f} pips SL risk)")
                print(f"\n  To set this TP, run:")
                print(f"  python3 set_take_profit.py {account} take_profit_price={calculated_tp:.5f}")
                print(f"  python3 set_take_profit.py {account} rr={rr_ratio}  # auto-calculate & set")
                print(f"\n  Or set any custom value:")
                print(f"  python3 set_take_profit.py {account} take_profit_price=YOUR_PRICE")
                print(f"{'*' * 60}")

        print(f"{'-' * 60}")

        # Determine which TP price to set
        tp_to_set = take_profit_price if take_profit_price is not None else (calculated_tp if custom_rr is not None else None)

        # Update take profit if requested (either by take_profit_price= or rr=)
        if tp_to_set is not None:
            if custom_rr is not None:
                print(f"\n>>> Setting Take Profit to {tp_to_set:.5f} (R:R={custom_rr})...")
            else:
                print(f"\n>>> Setting Take Profit to {tp_to_set:.5f}...")

            try:
                if tp_order_id:
                    # Update existing TP order
                    result = update_take_profit_order(
                        base_url, headers, account_id,
                        tp_order_id, trade_id, tp_to_set
                    )
                    print(f"✅ Take Profit UPDATED successfully!")
                else:
                    # Create new TP order
                    result = create_take_profit_order(
                        base_url, headers, account_id,
                        trade_id, tp_to_set
                    )
                    print(f"✅ Take Profit CREATED successfully!")

                # Show the result
                if 'takeProfitOrderTransaction' in result:
                    new_tp = result['takeProfitOrderTransaction']
                    print(f"   Order ID: {new_tp['id']}")
                    print(f"   Price: {new_tp['price']}")
                elif 'orderCreateTransaction' in result:
                    new_tp = result['orderCreateTransaction']
                    print(f"   Order ID: {new_tp['id']}")
                    print(f"   Price: {new_tp['price']}")

            except requests.exceptions.HTTPError as e:
                print(f"❌ Failed to set Take Profit: {e}")
                if hasattr(e, 'response') and e.response is not None:
                    print(f"   Response: {e.response.text}")


if __name__ == "__main__":
    main()
