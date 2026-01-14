#!/usr/bin/env python3
"""
TP/SL/Position Size Calculator Tool

Calculates and displays take profit, stop loss, and position size values
for verification purposes before trading.

Usage:
    python3 tools/calculate_tp_sl_position_size.py at=account1 fr=EUR_USD tf=5m
    python3 tools/calculate_tp_sl_position_size.py at=account1 fr=EUR_USD tf=5m risk=100
"""

import sys
import os
import yaml

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from config import OANDAConfig
from oanda_client import OANDAClient
from indicators import calculate_pp_supertrend, get_current_signal


def load_config(account):
    """Load config from account config with fallback to defaults"""
    # Default configuration
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

    # Load account-specific config (overrides defaults)
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
        # NEUTRAL - use lower risk
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


def calculate_stop_loss(supertrend_price, position_type, buffer_pips):
    """Calculate stop loss with buffer"""
    buffer_in_price = buffer_pips * 0.0001  # Convert pips to price for EUR_USD

    if position_type == 'SHORT':
        # For SHORT, SL is above entry, add buffer
        return supertrend_price + buffer_in_price
    else:
        # For LONG, SL is below entry, subtract buffer
        return supertrend_price - buffer_in_price


def calculate_take_profit(entry_price, stop_loss, rr_ratio, position_type):
    """Calculate take profit based on R:R ratio"""
    risk = abs(entry_price - stop_loss)
    reward = risk * rr_ratio

    if position_type == 'LONG':
        return entry_price + reward
    else:
        return entry_price - reward


def calculate_position_size(risk_amount, entry_price, stop_loss):
    """Calculate position size in units"""
    stop_distance = abs(entry_price - stop_loss)
    if stop_distance == 0:
        return 0

    position_units = risk_amount / stop_distance
    position_units = int(round(position_units))

    # Enforce minimum and maximum
    position_units = max(1000, position_units)
    position_units = min(1000000, position_units)  # Max 1M units

    return position_units


def main():
    # Parse arguments
    account = 'account1'
    instrument = 'EUR_USD'
    timeframe = '5m'
    risk_override = None

    for arg in sys.argv[1:]:
        if arg.startswith('at='):
            account = arg.split('=')[1]
        elif arg.startswith('fr='):
            instrument = arg.split('=')[1]
        elif arg.startswith('tf='):
            timeframe = arg.split('=')[1]
        elif arg.startswith('risk='):
            risk_override = float(arg.split('=')[1])

    # Load configuration
    config = load_config(account)
    buffer_pips = config.get('stoploss', {}).get('spread_buffer_pips', 3)

    # Initialize OANDA client
    OANDAConfig.set_account(account)
    client = OANDAClient()

    print("")
    print("=" * 60)
    print(f"POSITION CALCULATOR - {instrument} ({timeframe})")
    print("=" * 60)
    print(f"Account:         {account}")

    # Fetch current market price
    price_data = client.get_current_price(instrument)
    if not price_data:
        print("ERROR: Could not fetch current price from OANDA")
        sys.exit(1)

    bid = price_data['bid']
    ask = price_data['ask']
    mid = (bid + ask) / 2
    spread_pips = (ask - bid) / 0.0001

    # Fetch candles for trading timeframe
    granularity = get_granularity(timeframe)
    candles_tf = client.get_candles(instrument, granularity=granularity, count=100)
    if candles_tf is None or len(candles_tf) == 0:
        print(f"ERROR: Could not fetch {timeframe} candles")
        sys.exit(1)

    # Calculate PP SuperTrend for trading timeframe
    df_tf = calculate_pp_supertrend(candles_tf)
    signal_tf = get_current_signal(df_tf)
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
    signal_3h = get_current_signal(df_3h)

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
    else:
        position_type = 'LONG'

    print(f"Current Signal:  {current_signal} ({position_type} position)")

    # Display market data
    print("")
    print(">>> CURRENT MARKET DATA")
    print(f"Bid:             {bid:.5f}")
    print(f"Ask:             {ask:.5f}")
    print(f"Mid:             {mid:.5f}")
    print(f"Spread:          {spread_pips:.1f} pips")

    # Display PP SuperTrend data
    print("")
    print(f">>> PP SUPERTREND ({timeframe})")
    print(f"SuperTrend Line: {signal_tf['supertrend']:.5f}")
    print(f"Signal:          {signal_tf['signal']}")
    if signal_tf['atr']:
        print(f"ATR:             {signal_tf['atr']:.5f}")

    # Calculate values
    supertrend_price = signal_tf['supertrend']
    entry_price = mid  # Use mid as estimated entry

    # Get risk amount
    risk_amount = get_risk_amount(config, market_trend, position_type, risk_override)

    # Get R:R ratio
    rr_ratio = get_rr_ratio(config, market_trend, position_type)

    # Step 1: Calculate TP FIRST using raw PP SuperTrend as risk reference (no buffer)
    take_profit = calculate_take_profit(entry_price, supertrend_price, rr_ratio, position_type)

    # Step 2: Calculate SL with buffer SECOND
    stop_loss = calculate_stop_loss(supertrend_price, position_type, buffer_pips)

    # Calculate position size using raw PP SuperTrend distance
    position_size = calculate_position_size(risk_amount, entry_price, supertrend_price)

    # Calculate distances in pips
    sl_distance_pips = abs(supertrend_price - entry_price) / 0.0001
    entry_to_sl_pips = abs(entry_price - stop_loss) / 0.0001
    entry_to_tp_pips = abs(entry_price - take_profit) / 0.0001

    # Display calculated values
    print("")
    print(">>> CALCULATED VALUES")
    print(f"Position Type:   {position_type}")
    print(f"Risk Amount:     ${risk_amount:.2f}" + (" (from config)" if risk_override is None else " (CLI override)"))
    print(f"SL Distance:     {sl_distance_pips:.1f} pips (price to SuperTrend)")
    print("")
    print(f"Position Size:   {position_size:,} units")
    print(f"Take Profit:     {take_profit:.5f} (R:R = {rr_ratio})")
    print(f"Stop Loss:       {stop_loss:.5f} (SuperTrend {'+' if position_type == 'SHORT' else '-'} {buffer_pips} pip buffer)")

    # Verification section
    print("")
    print(">>> VERIFICATION")
    print(f"Entry Price:     ~{entry_price:.5f} (current mid)")
    print(f"Risk in pips:    {entry_to_sl_pips:.1f} pips (entry to SL)")
    print(f"Reward in pips:  {entry_to_tp_pips:.1f} pips (entry to TP)")

    actual_rr = entry_to_tp_pips / entry_to_sl_pips if entry_to_sl_pips > 0 else 0
    print(f"Actual R:R:      {actual_rr:.2f}")

    # Calculate actual risk at position size
    actual_risk = position_size * abs(entry_price - stop_loss)
    print(f"Actual Risk:     ${actual_risk:.2f}")

    # Show config source
    print("")
    print(">>> CONFIG SOURCE")
    print(f"R:R Ratio:       {rr_ratio} ({market_trend.lower()}_market.{'short' if position_type == 'SHORT' else 'long'}_rr)")
    print(f"Buffer Pips:     {buffer_pips} (stoploss.spread_buffer_pips)")
    if risk_override is None:
        risk_key = f"{'short' if position_type == 'SHORT' else 'long'}_risk_per_trade"
        print(f"Risk Amount:     ${risk_amount} (position_sizing.{market_trend.lower()}.{risk_key})")

    print("=" * 60)


if __name__ == "__main__":
    main()
