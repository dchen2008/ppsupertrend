"""
Mock OANDA client for testing without API calls.
Provides realistic responses and state tracking.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta


class MockOANDAClient:
    """
    Comprehensive mock of OANDAClient with state tracking.
    Simulates a realistic trading environment.
    """

    def __init__(self, initial_balance=10000.0):
        self.balance = initial_balance
        self.positions = {}  # instrument -> position dict
        self.trades = {}     # trade_id -> trade dict
        self.orders = {}     # order_id -> order dict
        self.trade_counter = 1000
        self.order_counter = 2000

        # Default price data
        self.current_prices = {
            'EUR_USD': {'bid': 1.10000, 'ask': 1.10015}
        }

        # Candle data storage
        self.candle_data = {}

    def set_candles(self, instrument, granularity, df):
        """Pre-load candle data for testing."""
        key = f"{instrument}_{granularity}"
        self.candle_data[key] = df

    def get_candles(self, instrument, granularity="M15", count=100):
        """Return pre-loaded or generated candle data."""
        key = f"{instrument}_{granularity}"
        if key in self.candle_data:
            return self.candle_data[key].tail(count).copy()

        # Generate default data
        return self._generate_default_candles(count)

    def _generate_default_candles(self, count):
        """Generate minimal valid candle data."""
        base_price = 1.10000
        times = [datetime.now() - timedelta(minutes=5*(count-i)) for i in range(count)]

        return pd.DataFrame({
            'open': [base_price] * count,
            'high': [base_price + 0.0010] * count,
            'low': [base_price - 0.0010] * count,
            'close': [base_price] * count,
            'volume': [500] * count
        }, index=pd.DatetimeIndex(times))

    def get_account_summary(self):
        """Return current account state."""
        unrealized_pl = sum(
            t.get('unrealized_pl', 0) for t in self.trades.values()
        )

        return {
            'balance': self.balance,
            'unrealized_pl': unrealized_pl,
            'nav': self.balance + unrealized_pl,
            'margin_used': sum(abs(t.get('units', 0)) * 0.01 for t in self.trades.values()),
            'margin_available': self.balance - sum(abs(t.get('units', 0)) * 0.01 for t in self.trades.values()),
            'open_trade_count': len(self.trades),
            'open_position_count': len([p for p in self.positions.values() if p.get('units', 0) != 0])
        }

    def get_current_price(self, instrument):
        """Return current price for instrument."""
        if instrument in self.current_prices:
            return {
                **self.current_prices[instrument],
                'time': datetime.now().isoformat()
            }
        return {'bid': 1.10000, 'ask': 1.10015, 'time': datetime.now().isoformat()}

    def get_current_spread(self, instrument):
        """Return current spread."""
        prices = self.current_prices.get(instrument, {'bid': 1.10000, 'ask': 1.10015})
        return prices['ask'] - prices['bid']

    def get_position(self, instrument):
        """Return position for instrument."""
        pos = self.positions.get(instrument)
        if pos and pos.get('units', 0) != 0:
            return pos
        return None

    def get_open_positions(self):
        """Return all open positions."""
        return [p for p in self.positions.values() if p.get('units', 0) != 0]

    def get_trades(self, instrument=None):
        """Return open trades."""
        trades = list(self.trades.values())
        if instrument:
            trades = [t for t in trades if t.get('instrument') == instrument]
        return trades

    def place_market_order(self, instrument, units, stop_loss=None, take_profit=None):
        """Simulate placing a market order."""
        self.trade_counter += 1
        trade_id = str(self.trade_counter)

        prices = self.current_prices.get(instrument, {'bid': 1.10000, 'ask': 1.10015})
        fill_price = prices['ask'] if units > 0 else prices['bid']

        trade = {
            'id': trade_id,
            'instrument': instrument,
            'price': fill_price,
            'units': units,
            'current_units': units,
            'unrealized_pl': 0.0,
            'stop_loss_price': stop_loss,
            'take_profit_price': take_profit
        }

        if stop_loss:
            self.order_counter += 1
            trade['stop_loss_order_id'] = str(self.order_counter)

        if take_profit:
            self.order_counter += 1
            trade['take_profit_order_id'] = str(self.order_counter)

        self.trades[trade_id] = trade

        # Update position
        self._update_position(instrument, units)

        return {
            'orderFillTransaction': {
                'id': str(self.order_counter),
                'price': str(fill_price),
                'units': str(units),
                'pl': '0',
                'tradeOpened': {'tradeID': trade_id}
            }
        }

    def _update_position(self, instrument, units):
        """Update or create position."""
        if instrument in self.positions:
            self.positions[instrument]['units'] += units
        else:
            self.positions[instrument] = {
                'instrument': instrument,
                'units': units,
                'side': 'LONG' if units > 0 else 'SHORT',
                'unrealized_pl': 0.0
            }

        # Update side based on net units
        pos = self.positions[instrument]
        if pos['units'] > 0:
            pos['side'] = 'LONG'
        elif pos['units'] < 0:
            pos['side'] = 'SHORT'
        else:
            pos['side'] = 'NONE'

    def close_position(self, instrument, side="ALL"):
        """Close position and return P&L."""
        if instrument not in self.positions:
            return None

        pos = self.positions[instrument]
        units = pos['units']

        if units == 0:
            return None

        # Calculate P&L
        prices = self.current_prices.get(instrument, {'bid': 1.10000, 'ask': 1.10015})
        close_price = prices['bid'] if units > 0 else prices['ask']

        # Find the trade and calculate P&L
        for trade_id, trade in list(self.trades.items()):
            if trade['instrument'] == instrument:
                entry = trade['price']
                if units > 0:
                    pl = (close_price - entry) * abs(units)
                else:
                    pl = (entry - close_price) * abs(units)

                self.balance += pl
                del self.trades[trade_id]

                self.positions[instrument]['units'] = 0
                self.positions[instrument]['side'] = 'NONE'

                fill_key = 'longOrderFillTransaction' if units > 0 else 'shortOrderFillTransaction'
                return {
                    fill_key: {
                        'id': str(self.order_counter + 1),
                        'price': str(close_price),
                        'pl': str(pl)
                    }
                }

        return None

    def update_stop_loss(self, stop_loss_order_id, new_stop_price, trade_id):
        """Update stop loss for a trade."""
        if trade_id in self.trades:
            self.trades[trade_id]['stop_loss_price'] = new_stop_price
            return {'orderFillTransaction': {'id': stop_loss_order_id}}
        return None

    def update_take_profit(self, trade_id, new_price, existing_tp_order_id=None):
        """Update take profit for a trade."""
        if trade_id in self.trades:
            self.trades[trade_id]['take_profit_price'] = new_price
            return {'orderCreateTransaction': {'id': str(self.order_counter + 1)}}
        return None

    def set_price(self, instrument, bid, ask):
        """Set current price for testing."""
        self.current_prices[instrument] = {'bid': bid, 'ask': ask}

    def simulate_price_move(self, instrument, pips):
        """Move price by specified pips."""
        if instrument in self.current_prices:
            pip_value = 0.0001
            move = pips * pip_value
            self.current_prices[instrument]['bid'] += move
            self.current_prices[instrument]['ask'] += move

            # Update unrealized P&L for trades
            for trade in self.trades.values():
                if trade['instrument'] == instrument:
                    units = trade['units']
                    entry = trade['price']
                    current = self.current_prices[instrument]['bid'] if units > 0 else self.current_prices[instrument]['ask']
                    if units > 0:
                        trade['unrealized_pl'] = (current - entry) * abs(units)
                    else:
                        trade['unrealized_pl'] = (entry - current) * abs(units)

    def reset(self):
        """Reset to initial state."""
        self.positions = {}
        self.trades = {}
        self.current_prices = {'EUR_USD': {'bid': 1.10000, 'ask': 1.10015}}


def create_mock_client_with_scenario(scenario='no_position', initial_balance=10000.0):
    """
    Factory function to create mock client with specific scenarios.

    Scenarios:
    - 'no_position': Clean slate, no open positions
    - 'long_position': Has open LONG EUR_USD position
    - 'short_position': Has open SHORT EUR_USD position
    - 'low_margin': Account with limited margin
    """
    client = MockOANDAClient(initial_balance)

    if scenario == 'long_position':
        client.place_market_order('EUR_USD', 10000, stop_loss=1.09900, take_profit=1.10200)
    elif scenario == 'short_position':
        client.place_market_order('EUR_USD', -10000, stop_loss=1.10150, take_profit=1.09800)
    elif scenario == 'low_margin':
        client.balance = 500

    return client
