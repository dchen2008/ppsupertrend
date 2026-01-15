#!/usr/bin/env python3
"""
Manual Order Tool with Post-Fill TP/SL Adjustment

Places a new order and then adjusts TP/SL based on actual fill price.

Workflow:
1. Calculate initial TP using entry_price and supertrend_price
2. Place order with init_TP and supertrend as init_SL (no buffer)
3. After fill, recalculate TP using fill_price and current_SL_price
4. Recalculate SL using supertrend + buffer
5. Update position with new TP and SL

Usage:
    python3 tools/manually_new_order_cal_tp_sl_position_size.py at=account1 fr=EUR_USD tf=5m
    python3 tools/manually_new_order_cal_tp_sl_position_size.py at=account1 fr=EUR_USD tf=5m risk=100
"""

import sys
import os
import yaml
import time

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from config import OANDAConfig
from oanda_client import OANDAClient
from indicators import calculate_pp_supertrend, get_current_signal


def load_config(account):
    """Load config from account config with fallback to defaults"""
    config = {
        'risk_reward': {
            'bear_market': {'short_rr': 2.0, 'long_rr': 0.8},
            'bull_market': {'short_rr': 0.8, 'long_rr': 2.0}
        },
        'stoploss': {
            'spread_buffer_pips': 3
        },
        'position_sizing': {
            'bear': {'short_risk_per_trade': 300, 'long_risk_per_trade': 100},
            'bull': {'short_risk_per_trade': 100, 'long_risk_per_trade': 300}
        },
        'signal': {
            'use_closed_candles_only': True  # Default: use only closed candles (no repainting)
        }
    }

    # Load default config
    default_config_path = os.path.join(os.path.dirname(__file__), '..', 'src', 'config.yaml')
    if os.path.exists(default_config_path):
        try:
            with open(default_config_path, 'r') as f:
                default_config = yaml.safe_load(f)
                if default_config:
                    deep_merge(config, default_config)
        except Exception as e:
            print(f"Warning: Could not load default config: {e}")

    # Load account-specific config
    account_config_path = os.path.join(os.path.dirname(__file__), '..', account, 'config.yaml')
    if os.path.exists(account_config_path):
        try:
            with open(account_config_path, 'r') as f:
                account_config = yaml.safe_load(f)
                if account_config:
                    deep_merge(config, account_config)
        except Exception as e:
            print(f"Warning: Could not load account config: {e}")

    return config


def deep_merge(base, override):
    """Deep merge override dict into base dict"""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            deep_merge(base[key], value)
        else:
            base[key] = value


def get_granularity(timeframe):
    """Convert timeframe string to OANDA granularity"""
    tf_map = {
        '1m': 'M1', 'm1': 'M1',
        '5m': 'M5', 'm5': 'M5',
        '15m': 'M15', 'm15': 'M15',
        '1h': 'H1', 'h1': 'H1',
        '3h': 'H3', 'h3': 'H3',
        '4h': 'H4', 'h4': 'H4',
        '1d': 'D', 'd': 'D'
    }
    return tf_map.get(timeframe.lower(), 'M5')


def get_risk_amount(config, market_trend, position_type, risk_override=None):
    """Get risk amount based on config and market conditions"""
    if risk_override is not None:
        return risk_override

    pos_sizing = config.get('position_sizing', {})

    if market_trend == 'BEAR':
        market_config = pos_sizing.get('bear', {})
        if position_type == 'SHORT':
            return market_config.get('short_risk_per_trade', 300)
        else:
            return market_config.get('long_risk_per_trade', 100)
    elif market_trend == 'BULL':
        market_config = pos_sizing.get('bull', {})
        if position_type == 'SHORT':
            return market_config.get('short_risk_per_trade', 100)
        else:
            return market_config.get('long_risk_per_trade', 300)
    else:
        return 100


def get_rr_ratio(config, market_trend, position_type):
    """Get R:R ratio based on config and market conditions"""
    rr_config = config.get('risk_reward', {})

    if market_trend == 'BEAR':
        market_rr = rr_config.get('bear_market', {})
        if position_type == 'SHORT':
            return market_rr.get('short_rr', 2.0)
        else:
            return market_rr.get('long_rr', 0.8)
    elif market_trend == 'BULL':
        market_rr = rr_config.get('bull_market', {})
        if position_type == 'SHORT':
            return market_rr.get('short_rr', 0.8)
        else:
            return market_rr.get('long_rr', 2.0)
    else:
        return 1.0


def calculate_init_take_profit(entry_price, supertrend_price, rr_ratio, position_type):
    """Calculate initial TP using entry_price and supertrend_price as SL reference"""
    risk = abs(entry_price - supertrend_price)
    reward = risk * rr_ratio

    if position_type == 'LONG':
        return entry_price + reward
    else:
        return entry_price - reward


def calculate_take_profit(fill_price, current_sl_price, rr_ratio, position_type):
    """Calculate TP based on fill_price and current_SL_price"""
    risk = abs(fill_price - current_sl_price)
    reward = risk * rr_ratio

    if position_type == 'LONG':
        return fill_price + reward
    else:
        return fill_price - reward


def calculate_stop_loss(supertrend_price, position_type, buffer_pips):
    """Calculate stop loss with buffer"""
    buffer_in_price = buffer_pips * 0.0001  # Convert pips to price for EUR_USD

    if position_type == 'SHORT':
        return supertrend_price + buffer_in_price
    else:
        return supertrend_price - buffer_in_price


def calculate_position_size(risk_amount, entry_price, supertrend_price):
    """Calculate position size in units"""
    stop_distance = abs(entry_price - supertrend_price)
    if stop_distance == 0:
        return 0

    position_units = risk_amount / stop_distance
    position_units = int(round(position_units))

    # Enforce minimum and maximum
    position_units = max(1000, position_units)
    position_units = min(1000000, position_units)

    return position_units


def new_order(client, instrument, supertrend_price, init_take_profit, position_size, position_type):
    """
    Place a new market order with:
    - init_stop_loss = supertrend_price (raw, no buffer)
    - init_take_profit = calculated from entry_price and supertrend_price
    Returns: order response
    """
    units = position_size if position_type == 'LONG' else -position_size

    result = client.place_market_order(
        instrument=instrument,
        units=units,
        stop_loss=supertrend_price,
        take_profit=init_take_profit
    )
    return result


def change_order(client, trade_id, new_take_profit, new_stop_loss, sl_order_id, tp_order_id):
    """Update existing position with new TP and SL via OANDA API"""
    # Update TP
    tp_result = client.update_take_profit(trade_id, new_take_profit, tp_order_id)

    # Update SL
    sl_result = client.update_stop_loss(sl_order_id, new_stop_loss, trade_id)

    return tp_result, sl_result


def close_position_by_side(client, instrument, side):
    """Close position for the instrument by specific side (LONG or SHORT)"""
    result = client.close_position(instrument, side=side)
    return result


def main():
    # Parse arguments
    account = 'account1'
    instrument = 'EUR_USD'
    timeframe = '5m'
    risk_override = None
    close_position_mode = False
    get_position_mode = False
    max_loss_limit = None

    for arg in sys.argv[1:]:
        if arg.startswith('at='):
            account = arg.split('=')[1]
        elif arg.startswith('fr='):
            instrument = arg.split('=')[1]
        elif arg.startswith('tf='):
            timeframe = arg.split('=')[1]
        elif arg.startswith('risk='):
            risk_override = float(arg.split('=')[1])
        elif arg.startswith('limit_max_potential_loss='):
            max_loss_limit = float(arg.split('=')[1])
        elif arg == 'close-position':
            close_position_mode = True
        elif arg == 'get-position':
            get_position_mode = True

    # Load configuration
    config = load_config(account)
    buffer_pips = config.get('stoploss', {}).get('spread_buffer_pips', 3)
    use_closed_candles_only = config.get('signal', {}).get('use_closed_candles_only', True)

    # Initialize OANDA client
    OANDAConfig.set_account(account)
    client = OANDAClient()

    # Handle close-position mode
    if close_position_mode:
        print("")
        print("=" * 60)
        print(f"CLOSE POSITION - {instrument}")
        print("=" * 60)
        print(f"Account:         {account}")
        print("")

        # Check if there's a position to close
        position = client.get_position(instrument)
        if not position or position.get('units', 0) == 0:
            print(">>> NO POSITION TO CLOSE")
            print(f"No open position found for {instrument}")
            print("=" * 60)
            sys.exit(0)

        # Determine position side
        position_side = 'LONG' if position['units'] > 0 else 'SHORT'

        # Show current position
        print(">>> CURRENT POSITION")
        print(f"Side:            {position_side}")
        print(f"Units:           {abs(position['units']):,.0f}")
        print(f"Unrealized P/L:  ${position.get('unrealized_pl', 0):.2f}")
        print("")
        print(f">>> CLOSING {position_side} POSITION...")

        result = close_position_by_side(client, instrument, position_side)

        if result:
            print("Position closed successfully!")
            if 'longOrderFillTransaction' in result:
                tx = result['longOrderFillTransaction']
                print(f"Closed LONG: {tx.get('units', 'N/A')} units at {tx.get('price', 'N/A')}")
                print(f"P/L: ${float(tx.get('pl', 0)):.2f}")
            if 'shortOrderFillTransaction' in result:
                tx = result['shortOrderFillTransaction']
                print(f"Closed SHORT: {tx.get('units', 'N/A')} units at {tx.get('price', 'N/A')}")
                print(f"P/L: ${float(tx.get('pl', 0)):.2f}")
        else:
            print("Failed to close position")

        print("=" * 60)
        sys.exit(0)

    # Handle get-position mode
    if get_position_mode:
        print("")
        print("=" * 60)
        print(f"POSITION INFO - {instrument}")
        print("=" * 60)
        print(f"Account:         {account}")
        print("")

        # Get current position
        position = client.get_position(instrument)
        if not position or position.get('units', 0) == 0:
            print(">>> NO OPEN POSITION")
            print(f"No open position found for {instrument}")
            print("=" * 60)
            sys.exit(0)

        # Get open trades for more details
        trades = client.get_trades(instrument)

        position_side = 'LONG' if position['units'] > 0 else 'SHORT'

        print(">>> CURRENT POSITION")
        print(f"Side:            {position_side}")
        print(f"Units:           {abs(position['units']):,.0f}")
        print(f"Avg Entry:       {position.get('average_price', 'N/A')}")
        print(f"Unrealized P/L:  ${position.get('unrealized_pl', 0):.2f}")

        # Get current price for comparison
        price_data = client.get_current_price(instrument)
        if price_data:
            current_price = price_data['bid'] if position_side == 'LONG' else price_data['ask']
            print(f"Current Price:   {current_price:.5f}")

        # Show trade details if available
        if trades:
            print("")
            print(">>> TRADE DETAILS")
            for trade in trades:
                print(f"Trade ID:        {trade['id']}")
                print(f"Fill Price:      {trade['price']:.5f}")
                print(f"Units:           {abs(trade['current_units']):,.0f}")
                if trade.get('stop_loss_price'):
                    print(f"Stop Loss:       {trade['stop_loss_price']:.5f}")
                if trade.get('take_profit_price'):
                    print(f"Take Profit:     {trade['take_profit_price']:.5f}")
                print(f"Unrealized P/L:  ${trade['unrealized_pl']:.2f}")

                # Calculate potential loss/profit if SL/TP set
                if trade.get('stop_loss_price') and trade.get('take_profit_price'):
                    sl_distance = abs(trade['price'] - trade['stop_loss_price'])
                    tp_distance = abs(trade['price'] - trade['take_profit_price'])
                    potential_loss = abs(trade['current_units']) * sl_distance
                    potential_profit = abs(trade['current_units']) * tp_distance
                    print("")
                    print(">>> RISK/REWARD")
                    print(f"Potential Loss:  ${potential_loss:.2f} (if SL hit)")
                    print(f"Potential Profit: ${potential_profit:.2f} (if TP hit)")

        print("=" * 60)
        sys.exit(0)

    print("")
    print("=" * 60)
    print(f"MANUAL ORDER TOOL - {instrument} ({timeframe})")
    print("=" * 60)
    print(f"Account:         {account}")

    # Fetch current market price
    price_data = client.get_current_price(instrument)
    if not price_data:
        print("ERROR: Could not fetch current price from OANDA")
        sys.exit(1)

    bid = price_data['bid']
    ask = price_data['ask']

    # Fetch candles for trading timeframe
    granularity = get_granularity(timeframe)
    candles_tf = client.get_candles(instrument, granularity=granularity, count=100)
    if candles_tf is None or len(candles_tf) == 0:
        print(f"ERROR: Could not fetch {timeframe} candles")
        sys.exit(1)

    # Calculate PP SuperTrend for trading timeframe
    df_tf = calculate_pp_supertrend(candles_tf)
    signal_tf = get_current_signal(df_tf, use_closed_candles_only)
    if not signal_tf or signal_tf['supertrend'] is None:
        print(f"ERROR: Could not calculate PP SuperTrend for {timeframe}")
        sys.exit(1)

    # Fetch candles for market trend (3H)
    candles_3h = client.get_candles(instrument, granularity='H3', count=100)
    if candles_3h is None or len(candles_3h) == 0:
        print("ERROR: Could not fetch 3H candles for market trend")
        sys.exit(1)

    # Calculate PP SuperTrend for market trend
    df_3h = calculate_pp_supertrend(candles_3h)
    signal_3h = get_current_signal(df_3h, use_closed_candles_only)

    # Determine market trend
    if signal_3h and signal_3h['signal'] in ['SELL', 'HOLD_SHORT']:
        market_trend = 'BEAR'
    elif signal_3h and signal_3h['signal'] in ['BUY', 'HOLD_LONG']:
        market_trend = 'BULL'
    else:
        market_trend = 'NEUTRAL'

    print(f"Market Trend:    {market_trend} (3H PP SuperTrend)")

    # Determine position type from signal
    current_signal = signal_tf['signal']
    if current_signal in ['SELL', 'HOLD_SHORT']:
        position_type = 'SHORT'
        entry_price = bid  # For SHORT, entry at bid
    else:
        position_type = 'LONG'
        entry_price = ask  # For LONG, entry at ask

    print(f"Position Type:   {position_type}")

    # Get supertrend price
    supertrend_price = signal_tf['supertrend']

    # Get risk amount and R:R ratio
    risk_amount = get_risk_amount(config, market_trend, position_type, risk_override)
    rr_ratio = get_rr_ratio(config, market_trend, position_type)

    # Calculate initial values using RAW SuperTrend (no buffer). 
    # Manual only — AI must not modify this section:init_take_profit
    init_take_profit = calculate_init_take_profit(entry_price, supertrend_price, rr_ratio, position_type)
    position_size = calculate_position_size(risk_amount, entry_price, supertrend_price)

    # Calculate the final SL with buffer (this will be set AFTER fill)
    final_sl = calculate_stop_loss(supertrend_price, position_type, buffer_pips)
    sl_distance_with_buffer = abs(entry_price - final_sl)
    estimated_potential_loss = position_size * sl_distance_with_buffer

    # Check if potential loss exceeds limit and adjust position size
    position_size_adjusted = False
    original_position_size = position_size
    if max_loss_limit is not None and estimated_potential_loss > max_loss_limit:
        # Reduce position size to cap potential loss at limit
        position_size = int(max_loss_limit / sl_distance_with_buffer)
        position_size = max(1000, position_size)  # Enforce minimum
        estimated_potential_loss = position_size * sl_distance_with_buffer
        position_size_adjusted = True

    # Display initial order values
    print("")
    print(">>> INITIAL ORDER VALUES")
    print(f"Entry Price:     {entry_price:.5f} ({'bid' if position_type == 'SHORT' else 'ask'})")
    print(f"SuperTrend:      {supertrend_price:.5f}")
    print(f"Init SL:         {supertrend_price:.5f} (raw SuperTrend)")
    print(f"Init TP:         {init_take_profit:.5f} (R:R = {rr_ratio})")
    if position_size_adjusted:
        print(f"Position Size:   {position_size:,} units (reduced from {original_position_size:,} to limit loss)")
        print(f"Max Loss Limit:  ${max_loss_limit:.2f}")
    else:
        print(f"Position Size:   {position_size:,} units")
    print(f"Risk Amount:     ${risk_amount:.2f}")
    print(f"Est. Max Loss:   ${estimated_potential_loss:.2f} (if SL triggered at {final_sl:.5f})")

    # Place order with RAW SuperTrend as init SL (no buffer)
    print("")
    print(">>> PLACING ORDER...")
    order_result = new_order(client, instrument, supertrend_price, init_take_profit, position_size, position_type)

    if not order_result:
        print("ERROR: Failed to place order")
        sys.exit(1)

    # Extract trade ID from order response
    trade_id = None
    if 'orderFillTransaction' in order_result:
        fill_tx = order_result['orderFillTransaction']
        trade_id = fill_tx.get('tradeOpened', {}).get('tradeID')
        if not trade_id and 'tradesClosed' in fill_tx:
            # This shouldn't happen for a new order, but handle it
            print("WARNING: Order filled but no new trade opened")

    if not trade_id:
        print("ERROR: Could not get trade ID from order response")
        print(f"Response: {order_result}")
        sys.exit(1)

    print(f"Order placed successfully!")
    print(f"Trade ID:        {trade_id}")

    # Wait a moment for the order to be fully processed
    time.sleep(1)

    # Get fill details from API
    trades = client.get_trades(instrument)
    trade_info = None
    for trade in trades:
        if str(trade['id']) == str(trade_id):
            trade_info = trade
            break

    if not trade_info:
        print("ERROR: Could not find trade in open trades")
        sys.exit(1)

    fill_price = trade_info['price']
    current_sl_price = trade_info['stop_loss_price']
    sl_order_id = trade_info['stop_loss_order_id']
    tp_order_id = trade_info['take_profit_order_id']

    print(f"Fill Price:      {fill_price:.5f}")

    # Recalculate adjusted values
    print("")
    print(">>> POST-FILL ADJUSTMENT")
    print(f"Current SL:      {current_sl_price:.5f} (raw SuperTrend)")

    # Manual only — AI must not modify this section:new_take_profit
    # A. Recalculate new TP using fill_price and current_SL_price (raw)
    new_take_profit = calculate_take_profit(fill_price, current_sl_price, rr_ratio, position_type)

    # B. Then calculate new SL using supertrend + buffer
    new_stop_loss = calculate_stop_loss(supertrend_price, position_type, buffer_pips)

    print(f"New TP:          {new_take_profit:.5f} (recalculated from fill_price)")
    print(f"New SL:          {new_stop_loss:.5f} (SuperTrend {'+' if position_type == 'SHORT' else '-'} {buffer_pips} pip buffer)")

    # Update position
    print("")
    print(">>> UPDATING POSITION...")
    tp_result, sl_result = change_order(client, trade_id, new_take_profit, new_stop_loss, sl_order_id, tp_order_id)

    if tp_result:
        print(f"TP updated: {init_take_profit:.5f} -> {new_take_profit:.5f}")
    else:
        print("WARNING: Failed to update TP")

    if sl_result:
        print(f"SL updated: {current_sl_price:.5f} -> {new_stop_loss:.5f}")
    else:
        print("WARNING: Failed to update SL")

    # Calculate potential loss/profit
    sl_distance = abs(fill_price - new_stop_loss)
    tp_distance = abs(fill_price - new_take_profit)

    potential_loss = position_size * sl_distance
    potential_profit = position_size * tp_distance

    sl_pips = sl_distance / 0.0001
    tp_pips = tp_distance / 0.0001

    # Final position summary
    print("")
    print(">>> FINAL POSITION")
    print(f"Trade ID:        {trade_id}")
    print(f"Fill Price:      {fill_price:.5f}")
    print(f"Take Profit:     {new_take_profit:.5f}")
    print(f"Stop Loss:       {new_stop_loss:.5f}")
    print("")
    print(">>> RISK/REWARD ANALYSIS")
    print(f"Position Size:   {position_size:,} units")
    print(f"Risk (to SL):    {sl_pips:.1f} pips  |  Potential Loss:   ${potential_loss:.2f}")
    print(f"Reward (to TP):  {tp_pips:.1f} pips  |  Potential Profit: ${potential_profit:.2f}")
    print(f"Actual R:R:      {tp_pips/sl_pips:.2f}" if sl_pips > 0 else "Actual R:R:      N/A")
    print("=" * 60)


if __name__ == "__main__":
    main()
