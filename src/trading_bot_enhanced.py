"""
Pivot Point SuperTrend Automated Trading Bot - Enhanced Version
Supports multiple configurations and CSV logging for concurrent testing
"""

import time
import logging
import sys
import argparse
import csv
import os
import json
from datetime import datetime
from threading import Lock
import pandas as pd

from .config import OANDAConfig, TradingConfig
from .oanda_client import OANDAClient
from .indicators import calculate_pp_supertrend, get_current_signal
from .risk_manager import RiskManager


class CSVLogger:
    """Thread-safe CSV logger for trade results"""

    def __init__(self, csv_filename):
        self.csv_filename = csv_filename
        self.lock = Lock()
        self.fieldnames = ['tradeID', 'name', 'orderTime', 'closeTime', 'duration', 'superTrend', 'pivotPoint',
                          'signal', 'type', 'positionSize', 'enterPrice', 'stopLoss', 'closePrice',
                          'highestPrice', 'lowestPrice', 'highestProfit', 'lowestLoss',
                          'stopLossHit', 'riskRewardRatio', 'profit', 'accountBalance']

        # Create CSV file with headers if it doesn't exist
        if not os.path.exists(self.csv_filename):
            with open(self.csv_filename, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=self.fieldnames)
                writer.writeheader()

    def log_trade(self, trade_data):
        """
        Log a trade to CSV file in thread-safe manner

        Args:
            trade_data: dict with keys matching fieldnames
        """
        with self.lock:
            with open(self.csv_filename, 'a', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=self.fieldnames)
                writer.writerow(trade_data)


class TradingBotEnhanced:
    """Enhanced automated trading bot with configurable parameters"""

    def __init__(self, instrument, timeframe, stop_loss_type, account='account1'):
        """
        Initialize bot with specific configuration

        Args:
            instrument: Trading pair (e.g., 'EUR_USD')
            timeframe: '5m' or '15m'
            stop_loss_type: 'SuperTrend' or 'PPCenterLine'
            account: Account name for output directory (e.g., 'account1', 'account2')
        """
        # Store configuration
        self.instrument = instrument
        self.timeframe = timeframe
        self.stop_loss_type = stop_loss_type.lower()
        self.account = account

        # Map timeframe to granularity
        self.granularity = 'M5' if timeframe == '5m' else 'M15'

        # Create account output directories if they don't exist
        csv_dir = f"{account}/csv"
        log_dir = f"{account}/logs"
        os.makedirs(csv_dir, exist_ok=True)
        os.makedirs(log_dir, exist_ok=True)

        # Generate unique CSV filename (account-based path)
        self.csv_filename = f"{csv_dir}/{instrument}_{timeframe}_sl-{stop_loss_type}.csv"

        # Initialize components
        self.client = OANDAClient()
        self.risk_manager = RiskManager()
        self.csv_logger = CSVLogger(self.csv_filename)

        # Setup logging with unique log file (account-based path)
        self.log_filename = f"{log_dir}/bot_{instrument}_{timeframe}_{stop_loss_type}.log"
        self.setup_logging()

        # Bot state
        self.is_running = False
        self.last_signal = None
        self.trade_count = 0

        # Track current position details for trailing stop
        self.current_stop_loss_order_id = None
        self.current_trade_id = None
        self.current_position_side = None
        self.current_stop_loss_price = None
        self.current_entry_price = None  # Track entry price for CSV logging
        self.highest_price_during_trade = None  # Track highest price during open position
        self.lowest_price_during_trade = None  # Track lowest price during open position

        # Track additional trade metrics for CSV logging
        self.current_trade_open_time = None
        self.current_supertrend_value = None
        self.current_pivot_point_value = None
        self.current_position_size = None

        # Track unique trade IDs
        self.trade_id_counter = 0

        # Track last signal candle timestamp to prevent duplicate trades
        # Persisted to file so it survives bot restarts
        state_dir = f"{account}/state"
        os.makedirs(state_dir, exist_ok=True)
        self.state_file = f"{state_dir}/{instrument}_{timeframe}_state.json"
        self.last_signal_candle_time = self._load_state()

        self.logger.info("=" * 80)
        self.logger.info(f"Enhanced Trading Bot Initialized")
        self.logger.info("=" * 80)
        self.logger.info(f"Account: {OANDAConfig.account_id}")
        self.logger.info(f"Mode: {'PRACTICE' if OANDAConfig.is_practice else 'LIVE'}")
        self.logger.info(f"Instrument: {self.instrument}")
        self.logger.info(f"Timeframe: {self.timeframe} ({self.granularity})")
        self.logger.info(f"Stop Loss Type: {stop_loss_type}")
        self.logger.info(f"CSV Log: {self.csv_filename}")
        self.logger.info(f"Text Log: {self.log_filename}")
        self.logger.info(f"Parameters: PP={TradingConfig.pivot_period}, "
                        f"ATR Factor={TradingConfig.atr_factor}, "
                        f"ATR Period={TradingConfig.atr_period}")
        self.logger.info(f"Check Interval: {TradingConfig.check_interval} seconds")
        self.logger.info(f"Trailing Stop: {'ENABLED' if TradingConfig.enable_trailing_stop else 'DISABLED'}")
        if self.last_signal_candle_time:
            self.logger.info(f"📂 Restored last signal time: {self.last_signal_candle_time}")
        self.logger.info("=" * 80)

    def _load_state(self):
        """Load persisted state from file (survives bot restarts)"""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                last_signal_time_str = state.get('last_signal_candle_time')
                if last_signal_time_str:
                    return pd.Timestamp(last_signal_time_str)
        except Exception as e:
            print(f"Warning: Could not load state from {self.state_file}: {e}")
        return None

    def _save_state(self):
        """Save state to file for persistence across restarts"""
        try:
            state = {
                'last_signal_candle_time': self.last_signal_candle_time.isoformat() if self.last_signal_candle_time else None,
                'updated_at': datetime.now().isoformat()
            }
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            self.logger.warning(f"Could not save state to {self.state_file}: {e}")

    def setup_logging(self):
        """Configure logging with unique logger name"""
        # Create unique logger for this instance
        logger_name = f"bot_{self.instrument}_{self.timeframe}_{self.stop_loss_type}"
        self.logger = logging.getLogger(logger_name)
        self.logger.setLevel(getattr(logging, TradingConfig.log_level))

        # Clear any existing handlers
        self.logger.handlers = []

        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_format = logging.Formatter(
            f'[{self.timeframe}-{self.stop_loss_type}] %(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(console_format)

        # File handler - unique per configuration
        file_handler = logging.FileHandler(self.log_filename)
        file_handler.setLevel(logging.DEBUG)
        file_format = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_format)

        # Add handlers
        self.logger.addHandler(console_handler)
        self.logger.addHandler(file_handler)

    def fetch_and_calculate_indicators(self):
        """
        Fetch market data and calculate indicators

        Returns:
            tuple: (DataFrame with indicators, signal_info dict, candle_timestamp)
        """
        # Fetch candle data with configured granularity
        df = self.client.get_candles(
            instrument=self.instrument,
            granularity=self.granularity,
            count=TradingConfig.lookback_candles
        )

        if df is None or len(df) == 0:
            self.logger.error("Failed to fetch candle data")
            return None, None, None

        # Calculate indicators
        df_with_indicators = calculate_pp_supertrend(
            df,
            pivot_period=TradingConfig.pivot_period,
            atr_factor=TradingConfig.atr_factor,
            atr_period=TradingConfig.atr_period
        )

        # Get current signal
        signal_info = get_current_signal(df_with_indicators)

        # Get the timestamp of the last candle
        candle_timestamp = df_with_indicators.index[-1] if len(df_with_indicators) > 0 else None

        # Add candle age for debugging (how old is the last completed candle)
        if candle_timestamp:
            from datetime import timezone
            candle_age_seconds = (pd.Timestamp.now(tz=timezone.utc) - candle_timestamp).total_seconds()
            signal_info['candle_age_seconds'] = candle_age_seconds

        return df_with_indicators, signal_info, candle_timestamp

    def calculate_stop_loss(self, signal_info, signal_type):
        """
        Calculate stop loss based on configured strategy with spread adjustment

        Args:
            signal_info: Signal information dict
            signal_type: 'BUY' or 'SELL'

        Returns:
            float: Stop loss price (adjusted for spread)
        """
        # Calculate base stop loss
        base_stop_loss = None

        if self.stop_loss_type == 'supertrend':
            # SuperTrend strategy: Stop exactly at SuperTrend line (matching Pine Script)
            supertrend = signal_info['supertrend']
            if supertrend is None:
                return None
            base_stop_loss = supertrend

        elif self.stop_loss_type == 'ppcenterline':
            # PPCenterLine strategy: Use pivot point center line
            pivot_center = signal_info.get('pivot')
            if pivot_center is None:
                return None
            base_stop_loss = pivot_center

        if base_stop_loss is None:
            return None

        # Apply spread adjustment if enabled
        if TradingConfig.use_spread_adjustment:
            # Get current spread
            spread = self.client.get_current_spread(self.instrument)

            if spread:
                # The bot calculates SuperTrend using MIDPOINT prices
                # But OANDA triggers stop losses on BID/ASK prices:
                #   - SHORT positions: Stop triggered when ASK reaches stop level (you buy to close)
                #   - LONG positions: Stop triggered when BID reaches stop level (you sell to close)
                #
                # For the position to close when MIDPOINT touches SuperTrend:
                #   MIDPOINT = (BID + ASK) / 2
                #
                # For SHORT: When MIDPOINT = SuperTrend
                #   ASK = MIDPOINT + (spread/2) = SuperTrend + (spread/2)
                #   So stop should be: SuperTrend + (spread/2)
                #
                # For LONG: When MIDPOINT = SuperTrend
                #   BID = MIDPOINT - (spread/2) = SuperTrend - (spread/2)
                #   So stop should be: SuperTrend - (spread/2)

                spread_adjustment = spread / 2.0

                if signal_type == 'SELL':  # SHORT position
                    adjusted_stop_loss = base_stop_loss + spread_adjustment
                    self.logger.info(f"  Stop Loss Adjustment (SHORT): {base_stop_loss:.5f} → {adjusted_stop_loss:.5f}")
                    self.logger.info(f"    SuperTrend (midpoint): {base_stop_loss:.5f}")
                    self.logger.info(f"    Spread: {spread:.5f} ({spread/0.0001:.1f} pips)")
                    self.logger.info(f"    Adjustment: +{spread_adjustment:.5f} (+{spread_adjustment/0.0001:.1f} pips)")
                    self.logger.info(f"    → Position closes when midpoint touches {base_stop_loss:.5f}")
                else:  # BUY / LONG position
                    adjusted_stop_loss = base_stop_loss - spread_adjustment
                    self.logger.info(f"  Stop Loss Adjustment (LONG): {base_stop_loss:.5f} → {adjusted_stop_loss:.5f}")
                    self.logger.info(f"    SuperTrend (midpoint): {base_stop_loss:.5f}")
                    self.logger.info(f"    Spread: {spread:.5f} ({spread/0.0001:.1f} pips)")
                    self.logger.info(f"    Adjustment: -{spread_adjustment:.5f} (-{spread_adjustment/0.0001:.1f} pips)")
                    self.logger.info(f"    → Position closes when midpoint touches {base_stop_loss:.5f}")

                return adjusted_stop_loss
            else:
                self.logger.warning("  Unable to fetch spread - using unadjusted stop loss")

        return base_stop_loss

    def execute_trade(self, action, signal_info, account_summary):
        """
        Execute trade based on action and log to CSV

        Args:
            action: 'OPEN_LONG', 'OPEN_SHORT', 'CLOSE'
            signal_info: Signal information dict
            account_summary: Account summary dict
        """
        if action == 'CLOSE':
            # Close existing position
            current_position = self.client.get_position(self.instrument)

            self.logger.info("=" * 80)
            self.logger.info(f"🔴 CLOSING POSITION for {self.instrument}")
            self.logger.info(f"Reason: Trend reversal - {signal_info['signal']}")
            self.logger.info(f"Position: {current_position['side']} {abs(current_position['units'])} units")
            self.logger.info(f"Unrealized P/L: ${current_position['unrealized_pl']:.2f}")
            self.logger.info("=" * 80)

            result = self.client.close_position(self.instrument)

            if result:
                self.logger.info("✅ Position closed successfully")
                self.trade_count += 1

                # Log to CSV
                if 'longOrderFillTransaction' in result or 'shortOrderFillTransaction' in result:
                    fill_key = 'longOrderFillTransaction' if 'longOrderFillTransaction' in result else 'shortOrderFillTransaction'
                    fill = result[fill_key]

                    profit = float(fill.get('pl', 0))
                    close_price = float(fill['price'])
                    close_time = datetime.now()

                    # Calculate duration
                    duration = 'N/A'
                    if self.current_trade_open_time:
                        duration_seconds = (close_time - self.current_trade_open_time).total_seconds()
                        duration_minutes = int(duration_seconds / 60)
                        duration = f"{duration_minutes}m"

                    # Determine if stop loss was hit
                    stop_loss_hit = 'FALSE'
                    if fill.get('reason') == 'STOP_LOSS_ORDER':
                        stop_loss_hit = 'TRUE'

                    position_size = abs(current_position['units'])

                    # Calculate highest profit
                    highest_profit = 'N/A'
                    if self.highest_price_during_trade and self.current_entry_price:
                        if current_position['side'] == 'LONG':
                            # For LONG: profit when price goes up
                            highest_profit = (self.highest_price_during_trade - self.current_entry_price) * position_size
                        else:  # SHORT
                            # For SHORT: profit when price goes down (lowest price gives highest profit)
                            if self.lowest_price_during_trade:
                                highest_profit = (self.current_entry_price - self.lowest_price_during_trade) * position_size
                        highest_profit = f"{highest_profit:.2f}"

                    # Calculate lowest loss
                    lowest_loss = 'N/A'
                    if self.lowest_price_during_trade and self.current_entry_price:
                        if current_position['side'] == 'LONG':
                            # For LONG: loss when price goes down (lowest price gives worst loss)
                            lowest_loss = (self.lowest_price_during_trade - self.current_entry_price) * position_size
                        else:  # SHORT
                            # For SHORT: loss when price goes up (highest price gives worst loss)
                            if self.highest_price_during_trade:
                                lowest_loss = (self.current_entry_price - self.highest_price_during_trade) * position_size
                        lowest_loss = f"{lowest_loss:.2f}"

                    # Calculate risk-reward ratio
                    risk_reward_ratio = 'N/A'
                    if self.current_stop_loss_price and self.current_entry_price:
                        risk = abs(self.current_entry_price - self.current_stop_loss_price) * position_size
                        if risk > 0:
                            reward = profit
                            risk_reward_ratio = f"{(reward / risk):.2f}"

                    csv_data = {
                        'tradeID': self.trade_id_counter,
                        'name': self.instrument,
                        'orderTime': self.current_trade_open_time.strftime('%Y-%m-%d %H:%M:%S') if self.current_trade_open_time else 'N/A',
                        'closeTime': close_time.strftime('%Y-%m-%d %H:%M:%S'),
                        'duration': duration,
                        'superTrend': f"{self.current_supertrend_value:.5f}" if self.current_supertrend_value else 'N/A',
                        'pivotPoint': f"{self.current_pivot_point_value:.5f}" if self.current_pivot_point_value else 'N/A',
                        'signal': current_position['side'],
                        'type': 'CLOSE',
                        'positionSize': position_size,
                        'enterPrice': f"{self.current_entry_price:.5f}" if self.current_entry_price else 'N/A',
                        'stopLoss': f"{self.current_stop_loss_price:.5f}" if self.current_stop_loss_price else 'N/A',
                        'closePrice': f"{close_price:.5f}",
                        'highestPrice': f"{self.highest_price_during_trade:.5f}" if self.highest_price_during_trade else 'N/A',
                        'lowestPrice': f"{self.lowest_price_during_trade:.5f}" if self.lowest_price_during_trade else 'N/A',
                        'highestProfit': highest_profit,
                        'lowestLoss': lowest_loss,
                        'stopLossHit': stop_loss_hit,
                        'riskRewardRatio': risk_reward_ratio,
                        'profit': f"{profit:.2f}",
                        'accountBalance': account_summary['balance']
                    }
                    self.csv_logger.log_trade(csv_data)

                    self.logger.info(f"📊 Profit/Loss: ${profit:.2f}")

                # Clear stop loss tracking
                self.current_stop_loss_order_id = None
                self.current_trade_id = None
                self.current_stop_loss_price = None
                self.current_position_side = None
                self.current_entry_price = None
                self.highest_price_during_trade = None
                self.lowest_price_during_trade = None
                self.current_trade_open_time = None
                self.current_supertrend_value = None
                self.current_pivot_point_value = None
                self.current_position_size = None

                # Reset signal tracking so next signal can be acted upon
                self.last_signal_candle_time = None
                self._save_state()
            else:
                self.logger.error("❌ Failed to close position")

        elif action in ['OPEN_LONG', 'OPEN_SHORT']:
            # Calculate position size
            position_size = self.risk_manager.calculate_position_size(
                account_summary['balance'],
                signal_info
            )

            # Validate trade
            is_valid, reason = self.risk_manager.validate_trade(account_summary, position_size)
            if not is_valid:
                self.logger.warning(f"⚠️  Trade validation failed: {reason}")
                return

            # Determine units
            units = position_size if action == 'OPEN_LONG' else -position_size

            # Calculate stop loss using configured strategy
            signal_type = 'BUY' if action == 'OPEN_LONG' else 'SELL'
            stop_loss = self.calculate_stop_loss(signal_info, signal_type)

            current_price = signal_info['price']

            # Log trade details
            self.logger.info("=" * 80)
            self.logger.info(f"{'🟢 OPENING LONG' if action == 'OPEN_LONG' else '🔴 OPENING SHORT'}")
            self.logger.info(f"Trade #{self.trade_count + 1}")
            self.logger.info(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            self.logger.info(f"Instrument: {self.instrument}")
            self.logger.info(f"Direction: {signal_type}")
            self.logger.info(f"Units: {abs(units)}")
            self.logger.info(f"Entry Price: {current_price:.5f}")
            self.logger.info(f"Stop Loss ({self.stop_loss_type}): {stop_loss:.5f}" if stop_loss else "Stop Loss: Not set")
            self.logger.info("=" * 80)

            # Place order
            result = self.client.place_market_order(
                instrument=self.instrument,
                units=units,
                stop_loss=stop_loss,
                take_profit=None
            )

            if result:
                self.logger.info("✅ Order placed successfully")
                self.trade_count += 1

                # Log order fill details
                if 'orderFillTransaction' in result:
                    fill = result['orderFillTransaction']
                    actual_price = float(fill['price'])

                    self.logger.info(f"📈 Fill Price: {actual_price:.5f}")

                    # Increment trade ID counter
                    self.trade_id_counter += 1

                    # Store entry price for later CSV logging
                    self.current_entry_price = actual_price

                    # Initialize highest and lowest price tracking with entry price
                    self.highest_price_during_trade = actual_price
                    self.lowest_price_during_trade = actual_price

                    # Store trade open time
                    self.current_trade_open_time = datetime.now()

                    # Store superTrend and pivot point values
                    self.current_supertrend_value = signal_info.get('supertrend')
                    self.current_pivot_point_value = signal_info.get('pivot')

                    # Store position size
                    self.current_position_size = abs(units)

                    # Store trade ID
                    if 'tradeOpened' in fill:
                        self.current_trade_id = fill['tradeOpened']['tradeID']

                    # Store stop loss info
                    if 'stopLossOrderTransaction' in result:
                        sl_order = result['stopLossOrderTransaction']
                        self.current_stop_loss_order_id = sl_order['id']
                        self.current_stop_loss_price = float(sl_order['price'])
                        self.current_position_side = 'LONG' if action == 'OPEN_LONG' else 'SHORT'

                    # Calculate risk-reward ratio
                    risk_reward_ratio = 'N/A'
                    if stop_loss and self.current_stop_loss_price:
                        risk = abs(actual_price - self.current_stop_loss_price)
                        if risk > 0:
                            # For initial entry, we don't have a target, so just show the risk
                            risk_reward_ratio = f"{risk:.5f}"

                    # Log to CSV
                    csv_data = {
                        'tradeID': self.trade_id_counter,
                        'name': self.instrument,
                        'orderTime': self.current_trade_open_time.strftime('%Y-%m-%d %H:%M:%S'),
                        'closeTime': 'N/A',
                        'duration': 'N/A',
                        'superTrend': f"{self.current_supertrend_value:.5f}" if self.current_supertrend_value else 'N/A',
                        'pivotPoint': f"{self.current_pivot_point_value:.5f}" if self.current_pivot_point_value else 'N/A',
                        'signal': 'LONG' if action == 'OPEN_LONG' else 'SHORT',
                        'type': 'buy' if action == 'OPEN_LONG' else 'sell',
                        'positionSize': abs(units),
                        'enterPrice': f"{actual_price:.5f}",
                        'stopLoss': f"{stop_loss:.5f}" if stop_loss else 'N/A',
                        'closePrice': 'N/A',
                        'highestPrice': 'N/A',
                        'lowestPrice': 'N/A',
                        'highestProfit': 'N/A',
                        'lowestLoss': 'N/A',
                        'stopLossHit': 'N/A',
                        'riskRewardRatio': 'N/A',
                        'profit': '0.00',
                        'accountBalance': account_summary['balance']
                    }
                    self.csv_logger.log_trade(csv_data)
            else:
                self.logger.error("❌ Failed to place order")

    def update_trailing_stop_loss(self, signal_info, current_position):
        """Update trailing stop loss based on SuperTrend movement"""
        if not TradingConfig.enable_trailing_stop:
            return

        if not self.current_stop_loss_order_id or not signal_info['supertrend']:
            return

        if not current_position or current_position['units'] == 0:
            return

        # Calculate new stop loss
        signal_type = 'BUY' if self.current_position_side == 'LONG' else 'SELL'
        new_stop_loss = self.calculate_stop_loss(signal_info, signal_type)

        if new_stop_loss is None:
            return

        # Initialize if needed
        if self.current_stop_loss_price is None:
            self.current_stop_loss_price = new_stop_loss
            self.logger.info(f"Initialized trailing stop: {new_stop_loss:.5f}")
            return

        # Check if update is needed
        should_update = False

        if self.current_position_side == 'LONG':
            if new_stop_loss > self.current_stop_loss_price:
                distance = new_stop_loss - self.current_stop_loss_price
                if distance >= TradingConfig.min_stop_update_distance:
                    should_update = True
        else:
            if new_stop_loss < self.current_stop_loss_price:
                distance = self.current_stop_loss_price - new_stop_loss
                if distance >= TradingConfig.min_stop_update_distance:
                    should_update = True

        if should_update:
            self.logger.info(f"🔄 Updating trailing stop: {self.current_stop_loss_price:.5f} → {new_stop_loss:.5f}")

            # Refresh stop loss order ID before updating (in case it changed)
            trades = self.client.get_trades(self.instrument)
            if trades and len(trades) > 0:
                trade = trades[0]
                if trade.get('stop_loss_order_id'):
                    # Update our cached IDs
                    self.current_stop_loss_order_id = trade['stop_loss_order_id']
                    self.current_trade_id = trade['id']
                    self.logger.info(f"  Refreshed SL Order ID: {self.current_stop_loss_order_id}")
                else:
                    self.logger.warning("⚠️  No stop loss order found on trade - skipping update")
                    return
            else:
                self.logger.warning("⚠️  No open trades found - position may have closed")
                # Clear tracking variables
                self.current_stop_loss_order_id = None
                self.current_trade_id = None
                self.current_stop_loss_price = None
                self.current_position_side = None
                return

            result = self.client.update_stop_loss(
                self.current_stop_loss_order_id,
                new_stop_loss,
                self.current_trade_id
            )

            if result:
                self.current_stop_loss_price = new_stop_loss
                self.logger.info("✅ Stop loss updated")
            else:
                self.logger.error("❌ Failed to update stop loss - order may not exist")
                # Clear cached stop loss order ID so we refresh next time
                self.current_stop_loss_order_id = None

    def check_and_trade(self):
        """Main trading logic: check signals and execute trades if needed"""
        try:
            # Fetch account summary
            account_summary = self.client.get_account_summary()
            if account_summary is None:
                self.logger.error("Failed to fetch account summary")
                return

            # Fetch and calculate indicators
            df, signal_info, candle_timestamp = self.fetch_and_calculate_indicators()
            if df is None or signal_info is None:
                return

            # Get current position
            current_position = self.client.get_position(self.instrument)

            # Detect if position was closed externally (by stop loss)
            # Only log if we have valid tracking data (prevent ghost entries from other bot instances)
            if (self.current_position_side is not None and
                self.current_entry_price is not None and
                self.current_position_size and self.current_position_size > 0):
                if current_position is None or current_position['units'] == 0:
                    self.logger.info("📍 Position closed externally (likely by stop loss)")

                    # Fetch transaction history to get close details
                    close_time = datetime.now()
                    close_price = None
                    profit = 0.0
                    stop_loss_hit = 'UNKNOWN'

                    try:
                        # Get recent transactions to find the close
                        transactions = self.client.get_transaction_history(count=50)
                        if transactions:
                            # Find most recent ORDER_FILL transaction for this instrument
                            for txn in reversed(transactions):
                                if (txn.get('type') == 'ORDER_FILL' and
                                    txn.get('instrument') == self.instrument):
                                    close_price = float(txn.get('price', 0))
                                    profit = float(txn.get('pl', 0))
                                    close_time = pd.to_datetime(txn.get('time'))
                                    reason = txn.get('reason', '')
                                    stop_loss_hit = 'TRUE' if 'STOP_LOSS' in reason else 'FALSE'
                                    self.logger.info(f"   Found close transaction: ID={txn.get('id')}, Price={close_price:.5f}, P/L=${profit:.2f}, Reason={reason}")
                                    break
                    except Exception as e:
                        self.logger.error(f"   Failed to fetch transaction history: {e}")

                    # Calculate duration
                    duration = 'N/A'
                    if self.current_trade_open_time:
                        duration_seconds = (close_time - self.current_trade_open_time).total_seconds()
                        duration_minutes = int(duration_seconds / 60)
                        duration = f"{duration_minutes}m"

                    # Calculate highest profit and lowest loss
                    highest_profit = 'N/A'
                    lowest_loss = 'N/A'
                    if self.current_entry_price and self.current_position_size:
                        if self.current_position_side == 'LONG':
                            if self.highest_price_during_trade:
                                highest_profit = (self.highest_price_during_trade - self.current_entry_price) * self.current_position_size
                                highest_profit = f"{highest_profit:.2f}"
                            if self.lowest_price_during_trade:
                                lowest_loss = (self.lowest_price_during_trade - self.current_entry_price) * self.current_position_size
                                lowest_loss = f"{lowest_loss:.2f}"
                        else:  # SHORT
                            if self.lowest_price_during_trade:
                                highest_profit = (self.current_entry_price - self.lowest_price_during_trade) * self.current_position_size
                                highest_profit = f"{highest_profit:.2f}"
                            if self.highest_price_during_trade:
                                lowest_loss = (self.current_entry_price - self.highest_price_during_trade) * self.current_position_size
                                lowest_loss = f"{lowest_loss:.2f}"

                    # Calculate risk-reward ratio
                    risk_reward_ratio = 'N/A'
                    if self.current_stop_loss_price and self.current_entry_price and self.current_position_size:
                        risk = abs(self.current_entry_price - self.current_stop_loss_price) * self.current_position_size
                        if risk > 0:
                            risk_reward_ratio = f"{(profit / risk):.2f}"

                    # Log to CSV
                    csv_data = {
                        'tradeID': self.trade_id_counter,
                        'name': self.instrument,
                        'orderTime': self.current_trade_open_time.strftime('%Y-%m-%d %H:%M:%S') if self.current_trade_open_time else 'N/A',
                        'closeTime': close_time.strftime('%Y-%m-%d %H:%M:%S'),
                        'duration': duration,
                        'superTrend': f"{self.current_supertrend_value:.5f}" if self.current_supertrend_value else 'N/A',
                        'pivotPoint': f"{self.current_pivot_point_value:.5f}" if self.current_pivot_point_value else 'N/A',
                        'signal': self.current_position_side if self.current_position_side else 'N/A',
                        'type': 'EXTERNAL_CLOSE',
                        'positionSize': self.current_position_size if self.current_position_size else 0,
                        'enterPrice': f"{self.current_entry_price:.5f}" if self.current_entry_price else 'N/A',
                        'stopLoss': f"{self.current_stop_loss_price:.5f}" if self.current_stop_loss_price else 'N/A',
                        'closePrice': f"{close_price:.5f}" if close_price else 'N/A',
                        'highestPrice': f"{self.highest_price_during_trade:.5f}" if self.highest_price_during_trade else 'N/A',
                        'lowestPrice': f"{self.lowest_price_during_trade:.5f}" if self.lowest_price_during_trade else 'N/A',
                        'highestProfit': highest_profit,
                        'lowestLoss': lowest_loss,
                        'stopLossHit': stop_loss_hit,
                        'riskRewardRatio': risk_reward_ratio,
                        'profit': f"{profit:.2f}",
                        'accountBalance': account_summary['balance']
                    }
                    self.csv_logger.log_trade(csv_data)
                    self.logger.info(f"   💾 Logged external close to CSV: P/L=${profit:.2f}")

                    # Clear all tracking
                    self.current_stop_loss_order_id = None
                    self.current_trade_id = None
                    self.current_stop_loss_price = None
                    self.current_position_side = None
                    self.current_entry_price = None
                    self.highest_price_during_trade = None
                    self.lowest_price_during_trade = None
                    self.current_trade_open_time = None
                    self.current_supertrend_value = None
                    self.current_pivot_point_value = None
                    self.current_position_size = None
                    self.last_signal_candle_time = None
                    self._save_state()

            # Recover tracking if needed
            if current_position and current_position['units'] != 0 and not self.current_stop_loss_order_id:
                trades = self.client.get_trades(self.instrument)
                if trades and len(trades) > 0:
                    trade = trades[0]
                    if trade.get('stop_loss_order_id'):
                        self.current_stop_loss_order_id = trade['stop_loss_order_id']
                        self.current_trade_id = trade['id']
                        self.current_position_side = 'LONG' if trade['units'] > 0 else 'SHORT'
                        self.current_entry_price = trade.get('price')  # Recover entry price
                        # Initialize highest and lowest price with entry price if not set
                        if self.highest_price_during_trade is None and self.current_entry_price:
                            self.highest_price_during_trade = float(self.current_entry_price)
                        if self.lowest_price_during_trade is None and self.current_entry_price:
                            self.lowest_price_during_trade = float(self.current_entry_price)
                        self.logger.info(f"📌 Recovered tracking: Trade {self.current_trade_id} @ {self.current_entry_price}")

            # Log status
            self.logger.info("-" * 80)
            self.logger.info(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            self.logger.info(f"Balance: ${account_summary['balance']:.2f} | "
                           f"P/L: ${account_summary['unrealized_pl']:.2f}")

            if current_position and current_position['units'] != 0:
                self.logger.info(f"Position: {current_position['side']} {abs(current_position['units'])} units")

            self.logger.info(f"Signal: {signal_info['signal']} | Price: {signal_info['price']:.5f}")

            # Add diagnostic logging for BUY/SELL signals to help identify false signals
            if signal_info['signal'] in ['BUY', 'SELL']:
                self.logger.info(f"🔍 SIGNAL DETECTED: {signal_info['signal']}")
                self.logger.info(f"   Candle Time: {candle_timestamp}")
                self.logger.info(f"   Current Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                if 'candle_age_seconds' in signal_info:
                    age_minutes = signal_info['candle_age_seconds'] / 60
                    self.logger.info(f"   Candle Age: {age_minutes:.1f} minutes")
                self.logger.info(f"   Price: {signal_info['price']:.5f}")
                supertrend_str = f"{signal_info['supertrend']:.5f}" if signal_info['supertrend'] is not None else 'N/A'
                self.logger.info(f"   SuperTrend: {supertrend_str}")
                self.logger.info(f"   Trend: {signal_info['trend']}")
                pivot_str = f"{signal_info['pivot']:.5f}" if signal_info['pivot'] is not None else 'N/A'
                self.logger.info(f"   Pivot Center: {pivot_str}")

            # Update highest and lowest price tracking during open position
            if current_position and current_position['units'] != 0:
                current_price = signal_info['price']

                # Track highest price (for LONG profit, SHORT drawdown)
                if self.highest_price_during_trade is not None:
                    if current_price > self.highest_price_during_trade:
                        self.highest_price_during_trade = current_price

                # Track lowest price (for SHORT profit, LONG drawdown)
                if self.lowest_price_during_trade is not None:
                    if current_price < self.lowest_price_during_trade:
                        self.lowest_price_during_trade = current_price

            # Determine if we should trade
            should_trade, action, next_action = self.risk_manager.should_trade(
                signal_info,
                current_position,
                candle_timestamp,
                self.last_signal_candle_time
            )

            if should_trade:
                self.logger.info(f"🎯 TRADE SIGNAL: {action}")
                self.execute_trade(action, signal_info, account_summary)

                # If closing position with intent to open opposite, do it immediately
                if action == 'CLOSE' and next_action in ['OPEN_LONG', 'OPEN_SHORT']:
                    self.logger.info(f"➡️  Immediately opening opposite position: {next_action}")
                    # Small delay to ensure close completes
                    time.sleep(1)
                    # Refresh account and position data
                    account_summary = self.client.get_account_summary()
                    current_position = self.client.get_position(self.instrument)
                    # Execute the opposite order
                    self.execute_trade(next_action, signal_info, account_summary)

                # Update last signal candle time after ALL actions complete
                self.last_signal_candle_time = candle_timestamp
                self._save_state()
                self.logger.info(f"📝 Saved signal state: {candle_timestamp}")
            else:
                if current_position and current_position['units'] != 0:
                    self.update_trailing_stop_loss(signal_info, current_position)

            self.last_signal = signal_info

        except Exception as e:
            self.logger.error(f"Error in check_and_trade: {e}", exc_info=True)

    def run(self):
        """Main bot loop"""
        self.is_running = True
        self.logger.info("🚀 Trading bot started")

        try:
            while self.is_running:
                self.check_and_trade()
                time.sleep(TradingConfig.check_interval)

        except KeyboardInterrupt:
            self.logger.info("\n⏹️  Bot stopped by user")
        except Exception as e:
            self.logger.error(f"Fatal error: {e}", exc_info=True)
        finally:
            self.stop()

    def stop(self):
        """Stop the bot"""
        self.is_running = False
        self.logger.info("=" * 80)
        self.logger.info("Trading Bot Stopped")
        self.logger.info(f"Total trades: {self.trade_count}")
        self.logger.info(f"CSV Log: {self.csv_filename}")
        self.logger.info("=" * 80)


def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='Enhanced Pivot Point SuperTrend Trading Bot',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python trading_bot_enhanced.py EUR_USD tf:5m sl:SuperTrend
  python trading_bot_enhanced.py EUR_USD tf:5m sl:SuperTrend account1
  python trading_bot_enhanced.py EUR_USD tf:15m sl:PPCenterLine account2
        """
    )

    parser.add_argument('instrument', type=str, help='Trading instrument (e.g., EUR_USD)')
    parser.add_argument('timeframe', type=str, help='Timeframe: tf:5m or tf:15m')
    parser.add_argument('stop_loss', type=str, help='Stop loss type: sl:SuperTrend or sl:PPCenterLine')
    parser.add_argument('account', type=str, nargs='?', default='account1',
                       help='Account name (e.g., account1, account2). Default: account1')

    args = parser.parse_args()

    # Parse timeframe
    if not args.timeframe.startswith('tf:'):
        parser.error("Timeframe must be in format tf:5m or tf:15m")
    timeframe = args.timeframe.split(':')[1]
    if timeframe not in ['5m', '15m']:
        parser.error("Timeframe must be 5m or 15m")

    # Parse stop loss type
    if not args.stop_loss.startswith('sl:'):
        parser.error("Stop loss must be in format sl:SuperTrend or sl:PPCenterLine")
    stop_loss_type = args.stop_loss.split(':')[1]
    if stop_loss_type.lower() not in ['supertrend', 'ppcenterline']:
        parser.error("Stop loss type must be SuperTrend or PPCenterLine")

    # Validate account exists
    if args.account not in OANDAConfig.list_accounts():
        available = ', '.join(OANDAConfig.list_accounts())
        parser.error(f"Account '{args.account}' not found. Available accounts: {available}")

    return args.instrument, timeframe, stop_loss_type, args.account


def main():
    """Main entry point"""
    # Parse command line arguments
    instrument, timeframe, stop_loss_type, account = parse_arguments()

    # Set the active account BEFORE any API calls
    try:
        OANDAConfig.set_account(account)
        print(f"\n✓ Using account: {account} ({OANDAConfig.account_id})")
    except ValueError as e:
        print(f"\n❌ Error: {e}")
        return

    # Display warning
    if OANDAConfig.is_practice:
        print("\n" + "=" * 80)
        print("⚠️  RUNNING IN PRACTICE MODE")
        print("=" * 80)
    else:
        print("\n" + "=" * 80)
        print("🚨 WARNING: RUNNING IN LIVE MODE WITH REAL MONEY 🚨")
        print("=" * 80)
        response = input("Are you sure? (yes/no): ")
        if response.lower() != 'yes':
            print("Exiting...")
            return

    # Create and run bot
    bot = TradingBotEnhanced(instrument, timeframe, stop_loss_type, account)

    print(f"\n📊 Starting bot...")
    print(f"Account: {account}")
    print(f"Instrument: {instrument}")
    print(f"Timeframe: {timeframe}")
    print(f"Stop Loss: {stop_loss_type}")
    print(f"CSV Log: {bot.csv_filename}")
    print("\nPress Ctrl+C to stop\n")

    bot.run()


if __name__ == "__main__":
    main()
