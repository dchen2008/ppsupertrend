"""
OANDA API Client for fetching market data and executing trades
"""

import requests
import pandas as pd
from datetime import datetime
import logging
import time
from functools import wraps
try:
    from .config import OANDAConfig
except ImportError:
    from config import OANDAConfig  # type: ignore


def api_retry_handler(func):
    """
    Decorator to handle API retries with timeout and detailed error logging
    """
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        max_retries = OANDAConfig.api_max_retries
        retry_delay = OANDAConfig.api_retry_delay

        for attempt in range(1, max_retries + 1):
            try:
                return func(self, *args, **kwargs)
            except requests.exceptions.Timeout as e:
                self.logger.error(f"⏱️  API TIMEOUT ({attempt}/{max_retries}): {func.__name__}() - {str(e)}")
                if attempt < max_retries:
                    self.logger.warning(f"   Retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
                else:
                    self.logger.error(f"   ❌ Max retries reached for {func.__name__}(). Giving up.")
                    return None
            except requests.exceptions.ConnectionError as e:
                self.logger.error(f"🔌 CONNECTION ERROR ({attempt}/{max_retries}): {func.__name__}() - {str(e)}")
                if attempt < max_retries:
                    self.logger.warning(f"   Retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
                else:
                    self.logger.error(f"   ❌ Max retries reached for {func.__name__}(). Giving up.")
                    return None
            except requests.exceptions.RequestException as e:
                self.logger.error(f"🚨 API REQUEST ERROR ({attempt}/{max_retries}): {func.__name__}()")
                self.logger.error(f"   Error: {str(e)}")
                if hasattr(e, 'response') and e.response is not None:
                    self.logger.error(f"   Status Code: {e.response.status_code}")
                    self.logger.error(f"   Response: {e.response.text}")
                if attempt < max_retries:
                    self.logger.warning(f"   Retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
                else:
                    self.logger.error(f"   ❌ Max retries reached for {func.__name__}(). Giving up.")
                    return None
            except Exception as e:
                self.logger.error(f"💥 UNEXPECTED ERROR in {func.__name__}(): {str(e)}")
                self.logger.exception("   Full traceback:")
                return None
        return None
    return wrapper


class OANDAClient:
    """Client for interacting with OANDA API"""

    def __init__(self):
        self.base_url = OANDAConfig.get_base_url()
        self.headers = OANDAConfig.get_headers()
        self.account_id = OANDAConfig.account_id
        self.logger = logging.getLogger(__name__)

    @api_retry_handler
    def get_candles(self, instrument, granularity="M15", count=100):
        """
        Fetch historical candle data

        Args:
            instrument: Currency pair (e.g., "EUR_USD")
            granularity: Timeframe (M1, M5, M15, H1, H4, D)
            count: Number of candles to fetch

        Returns:
            DataFrame with OHLC data
        """
        url = f"{self.base_url}/v3/instruments/{instrument}/candles"
        params = {
            'granularity': granularity,
            'count': count,
            'price': 'M'  # Midpoint candles
        }

        response = requests.get(url, headers=self.headers, params=params, timeout=OANDAConfig.api_timeout)
        response.raise_for_status()
        data = response.json()

        if 'candles' not in data:
            self.logger.error("No candles data in response")
            return None

        candles = []
        for candle in data['candles']:
            if candle['complete']:
                candles.append({
                    'time': pd.to_datetime(candle['time']),
                    'open': float(candle['mid']['o']),
                    'high': float(candle['mid']['h']),
                    'low': float(candle['mid']['l']),
                    'close': float(candle['mid']['c']),
                    'volume': int(candle['volume'])
                })

        df = pd.DataFrame(candles)
        df.set_index('time', inplace=True)

        self.logger.debug(f"Fetched {len(df)} candles for {instrument}")
        return df

    @api_retry_handler
    def get_account_summary(self):
        """
        Get account summary information

        Returns:
            dict with account information
        """
        url = f"{self.base_url}/v3/accounts/{self.account_id}/summary"

        response = requests.get(url, headers=self.headers, timeout=OANDAConfig.api_timeout)
        response.raise_for_status()
        data = response.json()

        if 'account' in data:
            account = data['account']
            return {
                'balance': float(account['balance']),
                'unrealized_pl': float(account['unrealizedPL']),
                'nav': float(account['NAV']),
                'margin_used': float(account['marginUsed']),
                'margin_available': float(account['marginAvailable']),
                'open_trade_count': int(account['openTradeCount']),
                'open_position_count': int(account['openPositionCount'])
            }
        return None

    @api_retry_handler
    def get_open_positions(self):
        """
        Get all open positions

        Returns:
            list of open positions
        """
        url = f"{self.base_url}/v3/accounts/{self.account_id}/openPositions"

        response = requests.get(url, headers=self.headers, timeout=OANDAConfig.api_timeout)
        response.raise_for_status()
        data = response.json()

        positions = []
        if 'positions' in data:
            for pos in data['positions']:
                long_units = float(pos['long']['units'])
                short_units = float(pos['short']['units'])
                net_units = long_units + short_units

                if net_units != 0:
                    positions.append({
                        'instrument': pos['instrument'],
                        'units': net_units,
                        'side': 'LONG' if net_units > 0 else 'SHORT',
                        'unrealized_pl': float(pos['unrealizedPL'])
                    })

        return positions

    @api_retry_handler
    def get_position(self, instrument):
        """
        Get position for a specific instrument

        Args:
            instrument: Currency pair (e.g., "EUR_USD")

        Returns:
            Position dict or None
        """
        url = f"{self.base_url}/v3/accounts/{self.account_id}/positions/{instrument}"

        response = requests.get(url, headers=self.headers, timeout=OANDAConfig.api_timeout)

        # Handle 404 specially (no position exists)
        if response.status_code == 404:
            return None

        response.raise_for_status()
        data = response.json()

        if 'position' in data:
            pos = data['position']
            long_units = float(pos['long']['units'])
            short_units = float(pos['short']['units'])
            net_units = long_units + short_units

            return {
                'instrument': pos['instrument'],
                'units': net_units,
                'side': 'LONG' if net_units > 0 else 'SHORT' if net_units < 0 else 'NONE',
                'unrealized_pl': float(pos['unrealizedPL']) if net_units != 0 else 0
            }
        return None

    @api_retry_handler
    def place_market_order(self, instrument, units, stop_loss=None, take_profit=None):
        """
        Place a market order

        Args:
            instrument: Currency pair (e.g., "EUR_USD")
            units: Number of units (positive for buy, negative for sell)
            stop_loss: Stop loss price (optional)
            take_profit: Take profit price (optional)

        Returns:
            Order response dict or None
        """
        url = f"{self.base_url}/v3/accounts/{self.account_id}/orders"

        order_data = {
            "order": {
                "type": "MARKET",
                "instrument": instrument,
                "units": str(units),
                "timeInForce": "FOK",  # Fill or Kill
                "positionFill": "DEFAULT"
            }
        }

        # Add stop loss if provided
        if stop_loss is not None:
            order_data["order"]["stopLossOnFill"] = {
                "price": f"{stop_loss:.5f}"
            }

        # Add take profit if provided
        if take_profit is not None:
            order_data["order"]["takeProfitOnFill"] = {
                "price": f"{take_profit:.5f}"
            }

        response = requests.post(url, headers=self.headers, json=order_data, timeout=OANDAConfig.api_timeout)
        response.raise_for_status()
        data = response.json()

        self.logger.info(f"Order placed: {units} units of {instrument}")
        return data

    @api_retry_handler
    def update_take_profit(self, trade_id, new_price, existing_tp_order_id=None):
        """
        Update or create take profit order for a trade

        Args:
            trade_id: The trade ID to set TP for
            new_price: The new take profit price
            existing_tp_order_id: If provided, updates existing TP order; otherwise creates new

        Returns:
            Response dict or None
        """
        if existing_tp_order_id:
            # Update existing TP order
            url = f"{self.base_url}/v3/accounts/{self.account_id}/orders/{existing_tp_order_id}"
            order_data = {
                "order": {
                    "type": "TAKE_PROFIT",
                    "tradeID": str(trade_id),
                    "price": f"{new_price:.5f}",
                    "timeInForce": "GTC"
                }
            }
            response = requests.put(url, headers=self.headers, json=order_data, timeout=OANDAConfig.api_timeout)
        else:
            # Create new TP order
            url = f"{self.base_url}/v3/accounts/{self.account_id}/orders"
            order_data = {
                "order": {
                    "type": "TAKE_PROFIT",
                    "tradeID": str(trade_id),
                    "price": f"{new_price:.5f}",
                    "timeInForce": "GTC"
                }
            }
            response = requests.post(url, headers=self.headers, json=order_data, timeout=OANDAConfig.api_timeout)

        response.raise_for_status()
        data = response.json()
        self.logger.info(f"Take profit {'updated' if existing_tp_order_id else 'created'}: {new_price:.5f} for trade {trade_id}")
        return data

    @api_retry_handler
    def close_position(self, instrument, side="ALL"):
        """
        Close position for an instrument

        Args:
            instrument: Currency pair (e.g., "EUR_USD")
            side: "LONG", "SHORT", or "ALL"

        Returns:
            Response dict or None
        """
        url = f"{self.base_url}/v3/accounts/{self.account_id}/positions/{instrument}/close"

        data = {}
        if side == "LONG" or side == "ALL":
            data["longUnits"] = "ALL"
        if side == "SHORT" or side == "ALL":
            data["shortUnits"] = "ALL"

        response = requests.put(url, headers=self.headers, json=data, timeout=OANDAConfig.api_timeout)
        response.raise_for_status()
        result = response.json()

        self.logger.info(f"Position closed: {instrument} ({side})")
        return result

    @api_retry_handler
    def get_current_price(self, instrument):
        """
        Get current bid/ask prices

        Args:
            instrument: Currency pair (e.g., "EUR_USD")

        Returns:
            dict with 'bid' and 'ask' prices
        """
        url = f"{self.base_url}/v3/accounts/{self.account_id}/pricing"
        params = {'instruments': instrument}

        response = requests.get(url, headers=self.headers, params=params, timeout=OANDAConfig.api_timeout)
        response.raise_for_status()
        data = response.json()

        if 'prices' in data and len(data['prices']) > 0:
            price = data['prices'][0]
            return {
                'bid': float(price['bids'][0]['price']),
                'ask': float(price['asks'][0]['price']),
                'time': price['time']
            }
        return None

    def get_current_spread(self, instrument):
        """
        Get current spread (ASK - BID) for an instrument

        Args:
            instrument: Currency pair (e.g., "EUR_USD")

        Returns:
            float: Current spread in price units, or None if unable to fetch
        """
        price_data = self.get_current_price(instrument)
        if price_data:
            spread = price_data['ask'] - price_data['bid']
            self.logger.debug(f"Current spread for {instrument}: {spread:.5f} ({spread/0.0001:.1f} pips)")
            return spread
        return None

    @api_retry_handler
    def get_trades(self, instrument=None):
        """
        Get open trades

        Args:
            instrument: Optional filter by instrument

        Returns:
            list of open trades
        """
        url = f"{self.base_url}/v3/accounts/{self.account_id}/openTrades"

        response = requests.get(url, headers=self.headers, timeout=OANDAConfig.api_timeout)
        response.raise_for_status()
        data = response.json()

        trades = []
        if 'trades' in data:
            for trade in data['trades']:
                if instrument is None or trade['instrument'] == instrument:
                    trade_info = {
                        'id': trade['id'],
                        'instrument': trade['instrument'],
                        'price': float(trade['price']),
                        'units': float(trade['initialUnits']),
                        'current_units': float(trade['currentUnits']),
                        'unrealized_pl': float(trade['unrealizedPL']),
                        'stop_loss_order_id': trade.get('stopLossOrder', {}).get('id'),
                        'stop_loss_price': float(trade['stopLossOrder']['price']) if trade.get('stopLossOrder', {}).get('price') else None,
                        'take_profit_order_id': trade.get('takeProfitOrder', {}).get('id'),
                        'take_profit_price': float(trade['takeProfitOrder']['price']) if trade.get('takeProfitOrder', {}).get('price') else None
                    }
                    trades.append(trade_info)

        return trades

    @api_retry_handler
    def update_stop_loss(self, stop_loss_order_id, new_stop_price, trade_id):
        """
        Update an existing stop loss order

        Args:
            stop_loss_order_id: ID of the stop loss order to update
            new_stop_price: New stop loss price
            trade_id: ID of the trade this stop loss is attached to

        Returns:
            Response dict or None
        """
        url = f"{self.base_url}/v3/accounts/{self.account_id}/orders/{stop_loss_order_id}"

        order_data = {
            "order": {
                "type": "STOP_LOSS",
                "tradeID": str(trade_id),
                "price": f"{new_stop_price:.5f}"
            }
        }

        response = requests.put(url, headers=self.headers, json=order_data, timeout=OANDAConfig.api_timeout)
        response.raise_for_status()
        result = response.json()

        self.logger.info(f"Stop loss updated: Order {stop_loss_order_id} → {new_stop_price}")
        return result

    @api_retry_handler
    def get_transaction_history(self, count=100):
        """
        Get recent transaction history

        Args:
            count: Number of transactions to fetch

        Returns:
            list of transactions
        """
        url = f"{self.base_url}/v3/accounts/{self.account_id}/transactions"
        params = {'count': count}

        response = requests.get(url, headers=self.headers, params=params, timeout=OANDAConfig.api_timeout)
        response.raise_for_status()
        data = response.json()

        if 'transactions' in data:
            return data['transactions']
        return []

    @api_retry_handler
    def get_transaction_details(self, transaction_id):
        """
        Get details for a specific transaction

        Args:
            transaction_id: Transaction ID

        Returns:
            dict with transaction details
        """
        url = f"{self.base_url}/v3/accounts/{self.account_id}/transactions/{transaction_id}"

        response = requests.get(url, headers=self.headers, timeout=OANDAConfig.api_timeout)
        response.raise_for_status()
        data = response.json()

        if 'transaction' in data:
            return data['transaction']
        return None

    @api_retry_handler
    def place_limit_order(self, instrument, units, price, stop_loss=None, take_profit=None, expiry_seconds=43200):
        """
        Place a limit order for scalping re-entry

        Args:
            instrument: Currency pair (e.g., "EUR_USD")
            units: Number of units (positive for buy, negative for sell)
            price: Limit price
            stop_loss: Stop loss price (optional)
            take_profit: Take profit price (optional)
            expiry_seconds: Order expiry in seconds (default: 12 hours)

        Returns:
            Order response dict or None
        """
        from datetime import timedelta

        url = f"{self.base_url}/v3/accounts/{self.account_id}/orders"

        expiry_time = datetime.utcnow() + timedelta(seconds=expiry_seconds)

        order_data = {
            "order": {
                "type": "LIMIT",
                "instrument": instrument,
                "units": str(units),
                "price": f"{price:.5f}",
                "timeInForce": "GTD",  # Good Till Date
                "gtdTime": expiry_time.strftime("%Y-%m-%dT%H:%M:%S.000000000Z")
            }
        }

        # Add stop loss if provided
        if stop_loss is not None:
            order_data["order"]["stopLossOnFill"] = {
                "price": f"{stop_loss:.5f}"
            }

        # Add take profit if provided
        if take_profit is not None:
            order_data["order"]["takeProfitOnFill"] = {
                "price": f"{take_profit:.5f}"
            }

        response = requests.post(url, headers=self.headers, json=order_data, timeout=OANDAConfig.api_timeout)
        response.raise_for_status()
        data = response.json()

        self.logger.info(f"Limit order placed: {units} units of {instrument} @ {price:.5f}")
        return data

    @api_retry_handler
    def get_order_status(self, order_id):
        """
        Get status of a specific order

        Args:
            order_id: Order ID to check

        Returns:
            str: Order state ('PENDING', 'FILLED', 'CANCELLED', 'TRIGGERED', 'NOT_FOUND')
        """
        url = f"{self.base_url}/v3/accounts/{self.account_id}/orders/{order_id}"

        response = requests.get(url, headers=self.headers, timeout=OANDAConfig.api_timeout)

        if response.status_code == 404:
            # Order not found - likely filled or cancelled, check transactions
            return 'NOT_FOUND'

        response.raise_for_status()
        data = response.json()

        if 'order' in data:
            return data['order'].get('state', 'UNKNOWN')
        return 'UNKNOWN'

    @api_retry_handler
    def get_order(self, order_id):
        """
        Get full order information

        Args:
            order_id: Order ID to check

        Returns:
            dict: Order information or None if not found
        """
        url = f"{self.base_url}/v3/accounts/{self.account_id}/orders/{order_id}"

        response = requests.get(url, headers=self.headers, timeout=OANDAConfig.api_timeout)

        if response.status_code == 404:
            return None

        response.raise_for_status()
        data = response.json()

        if 'order' in data:
            return data['order']
        return None

    @api_retry_handler
    def cancel_order(self, order_id):
        """
        Cancel a pending order

        Args:
            order_id: Order ID to cancel

        Returns:
            Response dict or None
        """
        url = f"{self.base_url}/v3/accounts/{self.account_id}/orders/{order_id}/cancel"

        response = requests.put(url, headers=self.headers, timeout=OANDAConfig.api_timeout)
        response.raise_for_status()
        result = response.json()

        self.logger.info(f"Order cancelled: {order_id}")
        return result

    @api_retry_handler
    def get_pending_orders(self, instrument=None):
        """
        Get pending orders for an instrument

        Args:
            instrument: Optional filter by instrument

        Returns:
            list of pending orders
        """
        url = f"{self.base_url}/v3/accounts/{self.account_id}/pendingOrders"

        response = requests.get(url, headers=self.headers, timeout=OANDAConfig.api_timeout)
        response.raise_for_status()
        data = response.json()

        orders = []
        if 'orders' in data:
            for order in data['orders']:
                if instrument is None or order.get('instrument') == instrument:
                    orders.append({
                        'id': order['id'],
                        'type': order['type'],
                        'instrument': order.get('instrument'),
                        'units': order.get('units'),
                        'price': order.get('price'),
                        'state': order.get('state')
                    })

        return orders

    @api_retry_handler
    def get_calendar_events(self, instrument='EUR_USD', period=2592000):
        """
        Fetch economic calendar events from OANDA ForexLabs API.

        Args:
            instrument: Currency pair filter (e.g., 'EUR_USD')
            period: Lookahead period in seconds (default: 2592000 = 30 days)

        Returns:
            List of event dicts with fields: title, timestamp, currency, impact, region, etc.
            Returns empty list on error.

        Note: ForexLabs uses the labs/v1/calendar endpoint, not the v3 API.
        Response format: [{
            'title': 'US CPI',
            'timestamp': 1705420800,
            'currency': 'USD',
            'impact': 3,
            'region': 'americas',
            'forecast': '0.2%',
            'previous': '0.3%',
            'actual': ''
        }, ...]
        """
        # ForexLabs API uses the same base host but different path
        if 'fxpractice' in self.base_url:
            labs_url = "https://api-fxpractice.oanda.com"
        else:
            labs_url = "https://api-fxtrade.oanda.com"

        url = f"{labs_url}/labs/v1/calendar"
        params = {
            'instrument': instrument,
            'period': period
        }

        response = requests.get(
            url,
            headers=self.headers,
            params=params,
            timeout=OANDAConfig.api_timeout
        )
        response.raise_for_status()
        data = response.json()

        self.logger.debug(f"Fetched {len(data)} calendar events for {instrument}")
        return data
