"""
Market-Aware Trading Bot with 3H PP SuperTrend Market Direction
Implements dynamic risk/reward based on market trend (bull/bear)
"""

import time
import logging
import sys
import argparse
import csv
import os
import yaml
import json
from datetime import datetime
from threading import Lock
import pandas as pd

from .config import OANDAConfig, TradingConfig
from .oanda_client import OANDAClient
from .indicators import calculate_pp_supertrend, get_current_signal
from .risk_manager import RiskManager
from .news_manager import NewsManager


class TradeTracker:
    """Track P&L and R:R high/low for open trades"""
    def __init__(self):
        self.highest_pl = None
        self.lowest_pl = None
        self.highest_ratio = None
        self.lowest_ratio = None
        self.entry_price = None
        self.position_side = None
        self.units = None
        self.risk_amount = None

    def update_pl(self, current_price, unrealized_pl=None):
        """Update highest/lowest P&L and R:R based on current price or OANDA unrealized P/L"""
        if self.entry_price is None or self.units is None:
            return

        # Use OANDA unrealized P/L if provided, otherwise calculate
        if unrealized_pl is not None:
            current_pl = unrealized_pl
        else:
            # Calculate current P&L
            if self.position_side == 'LONG':
                current_pl = (current_price - self.entry_price) * abs(self.units)
            else:  # SHORT
                current_pl = (self.entry_price - current_price) * abs(self.units)

        # Update highest/lowest P&L
        if self.highest_pl is None or current_pl > self.highest_pl:
            self.highest_pl = current_pl
        if self.lowest_pl is None or current_pl < self.lowest_pl:
            self.lowest_pl = current_pl

        # Update highest/lowest R:R ratio
        if self.risk_amount and self.risk_amount > 0:
            current_ratio = current_pl / self.risk_amount
            if self.highest_ratio is None or current_ratio > self.highest_ratio:
                self.highest_ratio = current_ratio
            if self.lowest_ratio is None or current_ratio < self.lowest_ratio:
                self.lowest_ratio = current_ratio

    def reset(self):
        """Reset tracker for new trade"""
        self.highest_pl = None
        self.lowest_pl = None
        self.highest_ratio = None
        self.lowest_ratio = None
        self.entry_price = None
        self.position_side = None
        self.units = None
        self.risk_amount = None


class CSVLogger:
    """Thread-safe CSV logger for trade results"""

    def __init__(self, csv_filename):
        self.csv_filename = csv_filename
        self.lock = Lock()
        self.fieldnames = ['market', 'signal', 'time', 'tradeID', 'entry_price', 'stop_loss_price',
                          'take_profit_price', 'position_lots', 'risk_amount', 'original_stop_pips',
                          'buffer_pips', 'adjusted_stop_pips', 'take_profit_ratio', 'highest_ratio',
                          'potential_profit', 'actual_profit', 'lowest_ratio', 'potential_loss',
                          'position_status', 'take_profit_hit', 'stop_loss_hit']

        # Create CSV file with headers if it doesn't exist
        if not os.path.exists(self.csv_filename):
            with open(self.csv_filename, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=self.fieldnames)
                writer.writeheader()

    def log_trade(self, trade_data):
        """Log a trade to CSV file in thread-safe manner"""
        with self.lock:
            with open(self.csv_filename, 'a', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=self.fieldnames)
                writer.writerow(trade_data)
                
    def trade_exists(self, trade_id, action):
        """Check if a trade with specific action already exists in CSV"""
        if not os.path.exists(self.csv_filename):
            return False
            
        with self.lock:
            try:
                with open(self.csv_filename, 'r', newline='') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if row.get('tradeID') == str(trade_id) and row.get('action') == action:
                            return True
            except Exception:
                pass
        return False


class MarketAwareTradingBot:
    """Enhanced trading bot with market trend awareness and dynamic risk/reward"""

    def __init__(self, instrument, timeframe, account='account1', catch_up=False):
        """
        Initialize bot with specific configuration

        Args:
            instrument: Trading pair (e.g., 'EUR_USD')
            timeframe: '5m' or '15m'
            account: Account name for output directory and config (e.g., 'account1')
            catch_up: If True, enter position based on current trend if no position exists
        """
        # Store configuration
        self.instrument = instrument
        self.timeframe = timeframe
        self.account = account
        self.catch_up = catch_up

        # Map timeframe to granularity
        self.granularity = 'M5' if timeframe == '5m' else 'M15'
        
        # Create account output directories if they don't exist
        csv_dir = f"{account}/csv"
        log_dir = f"{account}/logs"
        os.makedirs(csv_dir, exist_ok=True)
        os.makedirs(log_dir, exist_ok=True)

        # Generate unique CSV filename (account-based path)
        self.csv_filename = f"{csv_dir}/{instrument}_{timeframe}_market_aware.csv"

        # Setup logging with unique log file (account-based path)
        self.log_filename = f"{log_dir}/bot_{instrument}_{timeframe}_market_aware.log"
        self.setup_logging()  # Initialize logger first
        
        # Load account-specific configuration (after logger is initialized)
        self.config = self.load_account_config()
        
        # Market trend settings from config
        self.market_timeframe = self.config.get('market', {}).get('timeframe', 'H3')
        self.market_granularity = self.convert_timeframe_to_granularity(self.market_timeframe)
        
        # Risk/reward settings from config
        self.risk_reward_config = self.config.get('risk_reward', {})
        
        # Check interval from config
        if 'check_interval' in self.config:
            TradingConfig.check_interval = self.config['check_interval']
        
        # Stop loss type from config
        self.stop_loss_type = self.config.get('stoploss', {}).get('type', 'PPSuperTrend').lower()
        if self.stop_loss_type == 'ppsupertrend':
            self.stop_loss_type = 'supertrend'
        
        # Buffer for spread adjustment (in pips, configurable)
        self.spread_buffer_pips = self.config.get('stoploss', {}).get('spread_buffer_pips', 3)

        # Signal detection settings
        # use_closed_candles_only: True = only use closed candles (no repainting)
        self.use_closed_candles_only = self.config.get('signal', {}).get('use_closed_candles_only', True)

        # Initialize components - pass logger for consistent logging
        self.client = OANDAClient(logger=self.logger)
        self.risk_manager = RiskManager()
        self.csv_logger = CSVLogger(self.csv_filename)
        self.trade_tracker = TradeTracker()

        # Bot state
        self.is_running = False
        self.last_signal = None
        self.trade_count = 0

        # Track current position details for trailing stop
        self.current_stop_loss_order_id = None
        self.current_trade_id = None
        self.current_position_side = None
        self.current_stop_loss_price = None
        self.current_take_profit_price = None
        self.current_entry_price = None
        self.highest_price_during_trade = None
        self.lowest_price_during_trade = None

        # Track additional trade metrics for CSV logging
        self.current_trade_open_time = None
        self.current_supertrend_value = None
        self.current_pivot_point_value = None
        self.current_position_size = None
        self.current_market_trend = 'NEUTRAL'  # Track market trend at trade open
        self.current_risk_reward_target = None  # Track target R:R
        self.current_risk_amount = None  # Track actual risk amount used
        self.current_original_stop_pips = None  # Stop loss pips before buffer
        self.current_adjusted_stop_pips = None  # Stop loss pips after buffer

        # Enhanced status display tracking
        self.current_init_sl = None  # Raw SuperTrend (no buffer) at entry
        self.current_init_tp = None  # Initial take profit price
        self.current_fill_price = None  # Actual fill price from OANDA
        self.current_expected_rr = None  # Expected R:R ratio at entry

        # Track unique trade IDs
        self.trade_id_counter = 0

        # Track last signal candle timestamp to prevent duplicate trades
        # Persisted to file so it survives bot restarts
        state_dir = f"{account}/state"
        os.makedirs(state_dir, exist_ok=True)
        self.state_file = f"{state_dir}/{instrument}_{timeframe}_state.json"
        self.last_signal_candle_time = self._load_state()

        # Market trend tracking
        self.last_market_check = None
        self.market_check_interval = 180  # Check market every 3 minutes
        self.current_market_signal = 'NEUTRAL'

        # Scalping strategy state
        self.scalping_config = self.config.get('scalping', {})
        self.scalping_enabled = self.scalping_config.get('enabled', False)
        self.scalping_active = False
        self.scalping_signal_price = None
        self.scalping_signal_time = None
        self.scalping_entry_count = 0
        self.scalping_position_type = None  # 'LONG' or 'SHORT'
        self.scalping_original_supertrend = None
        self.scalping_market_trend = None
        self.scalping_rr_ratio = None
        self.scalping_pending_limit_order_id = None

        # Initialize news manager for high-impact event filtering
        self.news_manager = NewsManager(self.client, self.config, self.account)

        self.logger.info("=" * 80)
        self.logger.info(f"Market-Aware Trading Bot Initialized")
        self.logger.info("=" * 80)
        self.logger.info(f"Account: {OANDAConfig.account_id}")
        self.logger.info(f"Mode: {'PRACTICE' if OANDAConfig.is_practice else 'LIVE'}")
        self.logger.info(f"Instrument: {self.instrument}")
        self.logger.info(f"Trading Timeframe: {self.timeframe} ({self.granularity})")
        self.logger.info(f"Market Trend Timeframe: {self.market_timeframe} ({self.market_granularity})")
        self.logger.info(f"Stop Loss Type: {self.stop_loss_type}")
        self.logger.info(f"Use Closed Candles Only: {self.use_closed_candles_only}")
        self.logger.info(f"CSV Log: {self.csv_filename}")
        self.logger.info(f"Check Interval: {TradingConfig.check_interval} seconds")
        self.logger.info(f"Risk/Reward Config: {self.risk_reward_config}")
        if self.last_signal_candle_time:
            self.logger.info(f"📂 Restored last signal time: {self.last_signal_candle_time}")
        if self.news_manager.is_enabled():
            self.logger.info(f"📰 News Filter: ENABLED")
            self.logger.info(f"   Pre-news buffer: {int(self.news_manager.pre_news_buffer.total_seconds()//60)} mins")
            self.logger.info(f"   Post-news buffer: {int(self.news_manager.post_news_buffer.total_seconds()//60)} mins")
            self.logger.info(f"   Close positions before news: {self.news_manager.close_before_news}")
        else:
            self.logger.info(f"📰 News Filter: DISABLED")
        self.logger.info("=" * 80)

    def convert_timeframe_to_granularity(self, timeframe):
        """Convert timeframe string to OANDA granularity"""
        mapping = {
            'M1': 'M1', 'M5': 'M5', 'M15': 'M15', 'M30': 'M30',
            'H1': 'H1', 'H2': 'H2', 'H3': 'H3', 'H4': 'H4',
            'H6': 'H6', 'H8': 'H8', 'H12': 'H12',
            'D': 'D', 'W': 'W', 'M': 'M'
        }
        return mapping.get(timeframe.upper(), 'H3')
    
    def load_account_config(self):
        """Load configuration with hierarchy: default -> account-specific"""
        import copy
        
        # First, load default configuration from src/config.yaml
        default_config = {}
        default_config_file = "src/config.yaml"
        if os.path.exists(default_config_file):
            with open(default_config_file, 'r') as f:
                default_config = yaml.safe_load(f) or {}
        else:
            # Fallback defaults if src/config.yaml doesn't exist
            default_config = {
                'check_interval': 60,
                'market': {
                    'indicator': 'ppsupertrend',
                    'timeframe': 'H3'
                },
                'stoploss': {
                    'type': 'PPSuperTrend'
                },
                'risk_reward': {
                    'bear_market': {
                        'short_rr': 1.2,
                        'long_rr': 0.6
                    },
                    'bull_market': {
                        'short_rr': 0.6,
                        'long_rr': 1.2
                    }
                }
            }
        
        # Start with default config
        config = copy.deepcopy(default_config)
        
        # Check for account-specific config to override defaults
        account_config_file = f"{self.account}/config.yaml"
        self.config_file = account_config_file  # Track which config is being used
        
        if os.path.exists(account_config_file):
            with open(account_config_file, 'r') as f:
                account_config = yaml.safe_load(f) or {}
            
            # Deep merge account config into default config
            self._deep_merge(config, account_config)
            self.logger.info(f"Loaded account-specific config from: {account_config_file}")
        else:
            self.config_file = default_config_file
            if os.path.exists(default_config_file):
                self.logger.info(f"Using default config from: {default_config_file}")
            else:
                self.logger.info("Using built-in default configuration")
        
        return config
    
    def _deep_merge(self, base_dict, override_dict):
        """Deep merge override_dict into base_dict"""
        for key, value in override_dict.items():
            if key in base_dict and isinstance(base_dict[key], dict) and isinstance(value, dict):
                self._deep_merge(base_dict[key], value)
            else:
                base_dict[key] = value

    def _load_state(self):
        """Load persisted state from file (survives bot restarts)"""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                last_signal_time_str = state.get('last_signal_candle_time')
                if last_signal_time_str:
                    # Parse ISO format timestamp back to pandas Timestamp
                    return pd.Timestamp(last_signal_time_str)
        except Exception as e:
            # Log error but don't fail - just start fresh
            warning_msg = f"Warning: Could not load state from {self.state_file}: {e}"
            print(warning_msg)
            if hasattr(self, 'logger') and self.logger:
                self.logger.warning(warning_msg)
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

    def _get_scalping_status_line(self):
        """Get scalping status line for status display"""
        if not self.scalping_enabled:
            return "SCALPING: ENABLED=FALSE"

        in_window = self.is_in_scalping_window()
        start_time = self.scalping_config.get('time_window', {}).get('start', '20:00')
        end_time = self.scalping_config.get('time_window', {}).get('end', '08:00')

        if self.scalping_active:
            return f"SCALPING: ACTIVE | Entry #{self.scalping_entry_count} | Type: {self.scalping_position_type}"
        elif in_window:
            return f"SCALPING: ENABLED=TRUE | Window: {start_time}-{end_time} PT | IN_WINDOW (waiting for trade)"
        else:
            return f"SCALPING: ENABLED=TRUE | Window: {start_time}-{end_time} PT | OUT_OF_WINDOW"

    def _add_position_details(self, lines, signal_info, current_position):
        """Add detailed position info to status display"""
        units = abs(current_position.get('units', 0))
        side = current_position.get('side', 'UNKNOWN')
        current_price = signal_info['price']
        current_sl = self.current_stop_loss_price
        current_tp = self.current_take_profit_price

        # Trade info line - get entry time from tracking or OANDA
        entry_time_str = 'N/A'
        if self.current_trade_open_time:
            entry_time_str = self.current_trade_open_time.strftime('%Y-%m-%d %H:%M:%S')
        elif self.current_trade_id:
            # Try to get open time from OANDA
            try:
                trades = self.client.get_trades(self.instrument)
                for trade in trades:
                    if str(trade.get('id')) == str(self.current_trade_id):
                        open_time = trade.get('open_time')
                        if open_time:
                            # Parse OANDA timestamp (UTC) and convert to Pacific Time
                            from dateutil import parser
                            import pytz
                            dt_utc = parser.parse(open_time)
                            pacific_tz = pytz.timezone('US/Pacific')
                            dt_pacific = dt_utc.astimezone(pacific_tz)
                            entry_time_str = dt_pacific.strftime('%Y-%m-%d %H:%M:%S')
                        break
            except Exception:
                pass  # Keep N/A if failed

        # Init position section
        lines.append(">>> INIT POSITION")
        lines.append(f"Trade ID:        {self.current_trade_id or 'N/A'} | [{side}] {units:,.0f} units | entry_time: {entry_time_str}")

        # Entry details - handle None values with fallbacks
        fill_price = self.current_fill_price if self.current_fill_price else self.current_entry_price
        # Use the correct trailing stop as fallback based on position direction
        init_sl = self.current_init_sl if self.current_init_sl else self.current_supertrend_value
        if init_sl is None:
            # Use position-specific trailing stop
            if side == 'LONG':
                init_sl = signal_info.get('trailing_up')
            else:
                init_sl = signal_info.get('trailing_down')
            # Final fallback to supertrend
            if init_sl is None:
                init_sl = signal_info.get('supertrend')
        init_tp = self.current_init_tp if self.current_init_tp else current_tp
        # Get risk amount with fallback to default 100
        risk_amount = self.current_risk_amount if self.current_risk_amount else 100
        # Get expected R:R - try tracking vars first, then calculate from config
        expected_rr = self.current_expected_rr if self.current_expected_rr else self.current_risk_reward_target
        if expected_rr is None:
            # Fall back to calculating from config based on current market/position
            # Use current_market_signal (BEAR/BULL) not current_market_trend
            market_trend = self.current_market_signal if self.current_market_signal in ['BEAR', 'BULL'] else 'BEAR'
            expected_rr = self.get_risk_reward_ratio(market_trend, side)

        # Show entry details
        if fill_price:
            lines.append(f"Entry Price:     {fill_price:.5f} ({'ask' if side == 'LONG' else 'bid'})")
        if init_sl:
            lines.append(f"Init SL:         {init_sl:.5f} (same as raw SuperTrend)")
        if init_tp and expected_rr:
            lines.append(f"Init TP:         {init_tp:.5f} (Expected TP R:R = {expected_rr:.1f})")
        lines.append(f"Risk Amount:     ${risk_amount:.2f}")

        # Est max loss calculation
        if fill_price and current_sl:
            if side == 'LONG':
                max_loss_pips = (fill_price - current_sl) / 0.0001
            else:
                max_loss_pips = (current_sl - fill_price) / 0.0001
            max_loss_amount = max_loss_pips * 0.0001 * units
            lines.append(f"Est. Max Loss:   ${max_loss_amount:.2f} (if SL triggered at {current_sl:.5f})")

        # Current position section
        lines.append(">>> CURRENT POSITION")
        if fill_price:
            lines.append(f"Fill Price:      {fill_price:.5f}")
        lines.append(f"Current Price:   {current_price:.5f}")

        # TP with warning if approaching (based on P/L / risk_amount percentage)
        if current_tp:
            # Calculate P/L percentage of risk amount (risk_amount already defined above)
            unrealized_pl = current_position.get('unrealized_pl', 0)
            pl_percentage = (unrealized_pl / risk_amount) * 100 if risk_amount > 0 else 0
            expected_rr_pct = (expected_rr * 100) if expected_rr else 100  # Expected R:R as percentage

            tp_warning = ""
            # Show warning when P/L > 60% of risk amount (approaching TP target)
            if pl_percentage > 60:
                tp_warning = f" (⚠️ Approaching Take Profit Target: {pl_percentage:.2f}% --> {expected_rr_pct:.0f}%)"
            lines.append(f"Take Profit:     {current_tp:.5f}{tp_warning}")

        if current_sl:
            lines.append(f"Stop Loss:       {current_sl:.5f} (trailing SuperTrend + {self.spread_buffer_pips} pip buffer)")

        # Show the relevant trailing stop based on position direction
        # For LONG: trailing_up (support level below price)
        # For SHORT: trailing_down (resistance level above price)
        if side == 'LONG':
            trailing_stop = signal_info.get('trailing_up')
            stop_type = "trailing_up (support)"
        else:
            trailing_stop = signal_info.get('trailing_down')
            stop_type = "trailing_down (resistance)"

        if trailing_stop:
            lines.append(f"SuperTrend:      {trailing_stop:.5f} ({stop_type})")

        # Risk/Reward section
        lines.append(">>> RISK/REWARD estimate")

        # Calculate pips to SL and TP from current price
        if current_sl and current_tp:
            if side == 'LONG':
                risk_pips = (current_price - current_sl) / 0.0001
                reward_pips = (current_tp - current_price) / 0.0001
            else:
                risk_pips = (current_sl - current_price) / 0.0001
                reward_pips = (current_price - current_tp) / 0.0001

            potential_loss = abs(risk_pips) * 0.0001 * units
            potential_profit = abs(reward_pips) * 0.0001 * units
            actual_rr = reward_pips / risk_pips if risk_pips > 0 else 0

            lines.append(f"Risk (to SL):    {risk_pips:.1f} pips  |  Potential Loss:   ${potential_loss:.2f}")
            lines.append(f"Reward (to TP):  {reward_pips:.1f} pips  |  Potential Profit: ${potential_profit:.2f}")
            lines.append(f"Actual R:R:      {actual_rr:.2f}")

    def print_status_display(self, signal_info, account_summary, current_position):
        """Print formatted status display to console (no logger prefix)"""
        lines = []

        # Time line with Pacific Time
        pt_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        lines.append(f"Time: {pt_time} Pacific Time (PT)")

        # Scalping line
        scalping_status = self._get_scalping_status_line()
        lines.append(scalping_status)

        # Account/Market line
        balance = account_summary.get('balance', 0)
        position_pl = current_position.get('unrealized_pl', 0) if current_position and current_position.get('units', 0) != 0 else 0
        lines.append(f"Account: {self.account} | Market: {self.current_market_signal} | "
                    f"Balance: ${balance:.2f} | P/L: ${position_pl:.2f}")

        if current_position and current_position.get('units', 0) != 0:
            # Has position - detailed view
            self._add_position_details(lines, signal_info, current_position)
        else:
            # No position - simple view
            lines.append(f"Signal: {signal_info['signal']} | Price: {signal_info['price']:.5f}")

        lines.append("-" * 80)

        # Print to console and log to file for consistency
        status_output = "\n".join(lines)
        print(status_output)
        # Log each line to file
        for line in lines:
            self.logger.info(line)

    def _check_emergency_close(self, signal_info, current_position):
        """
        Emergency close: If candle close price crosses SuperTrend opposite to position,
        close immediately without waiting for confirmation bar signal change.

        This protects against sudden reversals where waiting for bar-7 confirmation
        would result in larger losses.

        Args:
            signal_info: Current signal info with 'price' and 'supertrend'
            current_position: Current position dict with 'units' and 'side'

        Returns:
            bool: True if emergency close was triggered, False otherwise
        """
        if not current_position or current_position.get('units', 0) == 0:
            return False

        # Use CLOSED candle's close price (not in-progress price) for emergency close
        # This ensures we only trigger based on confirmed candle closes, not live price
        close_price = signal_info.get('closed_candle_close') or signal_info.get('price')

        # Get position-specific trailing stops
        # trailing_up = support level (for LONG positions)
        # trailing_down = resistance level (for SHORT positions)
        trailing_up = signal_info.get('trailing_up')
        trailing_down = signal_info.get('trailing_down')

        position_side = current_position.get('side') or self.current_position_side
        if not position_side:
            return False

        # Check if price crossed the relevant trailing stop for the position direction
        # This is consistent regardless of current trend direction
        should_emergency_close = False
        cross_direction = None
        relevant_stop = None

        if position_side == 'LONG' and trailing_up is not None and close_price < trailing_up:
            # LONG position but close price dropped BELOW trailing_up (support)
            should_emergency_close = True
            cross_direction = "BELOW"
            relevant_stop = trailing_up
        elif position_side == 'SHORT' and trailing_down is not None and close_price > trailing_down:
            # SHORT position but close price rose ABOVE trailing_down (resistance)
            should_emergency_close = True
            cross_direction = "ABOVE"
            relevant_stop = trailing_down

        if close_price is None or relevant_stop is None:
            return False

        if not should_emergency_close:
            return False

        # Execute emergency close
        stop_type = "trailing_up (support)" if position_side == 'LONG' else "trailing_down (resistance)"
        self.logger.warning("=" * 80)
        self.logger.warning(f"⚠️  EMERGENCY CLOSE: Price crossed trailing stop!")
        self.logger.warning(f"   Position: {position_side}")
        self.logger.warning(f"   Close Price: {close_price:.5f} crossed {cross_direction} {stop_type}: {relevant_stop:.5f}")
        self.logger.warning(f"   Reason: Protecting against sudden reversal (not waiting for confirmation bar)")
        self.logger.warning("=" * 80)

        try:
            result = self.client.close_position(self.instrument)

            if result:
                self.logger.info("✅ Emergency close executed successfully")

                # Get profit/loss from result
                profit = 0
                if 'longOrderFillTransaction' in result:
                    profit = float(result['longOrderFillTransaction'].get('pl', 0))
                elif 'shortOrderFillTransaction' in result:
                    profit = float(result['shortOrderFillTransaction'].get('pl', 0))

                self.logger.info(f"📊 P/L: ${profit:.2f}")

                # Reset all position tracking
                self._reset_position_tracking()
                return True
            else:
                # close_position returned None - check if position was already closed
                self.logger.warning("⚠️  Emergency close returned no result - checking if position still exists...")
                check_position = self.client.get_position(self.instrument)
                if check_position is None or check_position.get('units', 0) == 0:
                    self.logger.info("ℹ️  Position already closed (likely SL/TP triggered before emergency close)")
                    self._reset_position_tracking()
                    return True
                else:
                    self.logger.error("❌ Emergency close failed but position still exists - will retry next cycle")
                    return False

        except Exception as e:
            # Handle case where position was already closed (SL triggered)
            error_msg = str(e)
            if 'NO_SUCH_POSITION' in error_msg or 'POSITION_NOT_FOUND' in error_msg or '404' in error_msg or 'CLOSEOUT_POSITION_DOESNT_EXIST' in error_msg:
                self.logger.info("ℹ️  Position already closed (likely SL triggered)")
                self._reset_position_tracking()
                return True
            else:
                self.logger.error(f"❌ Emergency close error: {e}")
                # Still try to reset tracking in case position is actually closed
                try:
                    current_pos = self.client.get_position(self.instrument)
                    if not current_pos or current_pos.get('units', 0) == 0:
                        self.logger.info("ℹ️  Position confirmed closed, resetting tracking")
                        self._reset_position_tracking()
                        return True
                except:
                    pass
                return False

    def _reset_position_tracking(self):
        """Reset all position tracking variables after close"""
        self.trade_tracker.reset()
        self.current_stop_loss_order_id = None
        self.current_trade_id = None
        self.current_stop_loss_price = None
        self.current_take_profit_price = None
        self.current_position_side = None
        self.current_entry_price = None
        self.highest_price_during_trade = None
        self.lowest_price_during_trade = None
        self.current_trade_open_time = None
        self.current_supertrend_value = None
        self.current_pivot_point_value = None
        self.current_position_size = None
        self.current_market_trend = 'NEUTRAL'
        self.current_risk_reward_target = None
        self.current_risk_amount = None
        self.current_original_stop_pips = None
        self.current_adjusted_stop_pips = None
        self.current_init_sl = None
        self.current_init_tp = None
        self.current_fill_price = None
        self.current_expected_rr = None

        # Reset scalping if active
        if self.scalping_active:
            self.reset_scalping_state("Emergency close triggered")

        # Reset signal state
        self.last_signal_candle_time = None
        self._save_state()

    def setup_logging(self):
        """Configure logging with unique logger name"""
        # Create unique logger for this instance
        logger_name = f"bot_{self.instrument}_{self.timeframe}_market"
        self.logger = logging.getLogger(logger_name)
        self.logger.setLevel(getattr(logging, TradingConfig.log_level))

        # Clear any existing handlers
        self.logger.handlers = []

        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_format = logging.Formatter(
            f'[{self.timeframe}-Market] %(asctime)s - %(levelname)s - %(message)s',
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
        
    def check_market_trend(self):
        """
        Check 3H PP SuperTrend for market direction (bull/bear)
        Returns: 'BULL', 'BEAR', or 'NEUTRAL'
        """
        try:
            # Fetch 3H candle data
            df = self.client.get_candles(
                instrument=self.instrument,
                granularity=self.market_granularity,
                count=100  # Get enough candles for reliable PP SuperTrend
            )
            
            if df is None or len(df) == 0:
                self.logger.warning("Failed to fetch market trend data")
                return 'NEUTRAL'
            
            # Calculate PP SuperTrend on 3H timeframe
            df_with_indicators = calculate_pp_supertrend(
                df,
                pivot_period=TradingConfig.pivot_period,
                atr_factor=TradingConfig.atr_factor,
                atr_period=TradingConfig.atr_period
            )
            
            # Get signal from 3H timeframe
            signal_info = get_current_signal(df_with_indicators, self.use_closed_candles_only)

            # Determine market trend based on signal
            # BUY or HOLD_LONG indicates bull market
            # SELL or HOLD_SHORT indicates bear market  
            # PP SuperTrend should NEVER be NEUTRAL - always bullish or bearish
            if signal_info['signal'] in ['BUY', 'HOLD_LONG']:
                market_trend = 'BULL'
            elif signal_info['signal'] in ['SELL', 'HOLD_SHORT']:
                market_trend = 'BEAR'
            else:
                # This should never happen with fixed PP SuperTrend
                self.logger.error(f"⚠️  UNEXPECTED signal: {signal_info['signal']} - defaulting to BEAR")
                market_trend = 'BEAR'
            
            self.logger.info(f"📊 Market Trend Check ({self.market_timeframe}): {market_trend}")
            self.logger.info(f"   3H PP SuperTrend Signal: {signal_info['signal']}")
            self.logger.info(f"   3H Price: {signal_info['price']:.5f}")
            if signal_info['supertrend'] is not None:
                self.logger.info(f"   3H SuperTrend: {signal_info['supertrend']:.5f}")
            
            self.current_market_signal = market_trend
            self.last_market_check = datetime.now()
            
            return market_trend
            
        except Exception as e:
            self.logger.error(f"Error checking market trend: {e}")
            return 'NEUTRAL'

    def get_risk_reward_ratio(self, market_trend, position_type):
        """
        Get appropriate risk/reward ratio based on market trend and position type
        
        Args:
            market_trend: 'BULL', 'BEAR', or 'NEUTRAL'
            position_type: 'LONG' or 'SHORT'
        
        Returns:
            float: Risk/reward ratio for take profit
        """
        if market_trend == 'BEAR':
            if position_type == 'SHORT':
                return self.risk_reward_config.get('bear_market', {}).get('short_rr', 1.2)
            else:  # LONG
                return self.risk_reward_config.get('bear_market', {}).get('long_rr', 0.6)
        elif market_trend == 'BULL':
            if position_type == 'SHORT':
                return self.risk_reward_config.get('bull_market', {}).get('short_rr', 0.6)
            else:  # LONG
                return self.risk_reward_config.get('bull_market', {}).get('long_rr', 1.2)
        else:  # NEUTRAL
            # Use balanced R:R when market is neutral
            return 1.0
    
    def calculate_take_profit(self, entry_price, stop_loss_price, position_type, risk_reward_ratio):
        """
        Calculate take profit price based on risk/reward ratio
        
        Args:
            entry_price: Entry price of the position
            stop_loss_price: Stop loss price
            position_type: 'LONG' or 'SHORT'
            risk_reward_ratio: Target risk/reward ratio
        
        Returns:
            float: Take profit price
        """
        risk = abs(entry_price - stop_loss_price)
        reward = risk * risk_reward_ratio
        
        if position_type == 'LONG':
            take_profit = entry_price + reward
        else:  # SHORT
            take_profit = entry_price - reward
        
        return take_profit

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
        signal_info = get_current_signal(df_with_indicators, self.use_closed_candles_only)

        # Get the timestamp of the last candle
        candle_timestamp = df_with_indicators.index[-1] if len(df_with_indicators) > 0 else None

        # Add candle age for debugging
        if candle_timestamp:
            from datetime import timezone
            candle_age_seconds = (pd.Timestamp.now(tz=timezone.utc) - candle_timestamp).total_seconds()
            signal_info['candle_age_seconds'] = candle_age_seconds

        return df_with_indicators, signal_info, candle_timestamp

    def calculate_stop_loss(self, signal_info, signal_type, entry_price=None):
        """Calculate stop loss based on configured strategy with spread adjustment"""
        # Calculate base stop loss
        base_stop_loss = None

        if self.stop_loss_type == 'supertrend':
            # SuperTrend strategy: Stop exactly at SuperTrend line
            # Use the correct trailing stop based on position direction:
            # - For LONG (BUY): use trailing_up (support level)
            # - For SHORT (SELL): use trailing_down (resistance level)
            if signal_type == 'SELL':  # SHORT position
                base_stop_loss = signal_info.get('trailing_down')
            else:  # BUY / LONG position
                base_stop_loss = signal_info.get('trailing_up')

            # Fallback to supertrend if trailing values not available
            if base_stop_loss is None:
                base_stop_loss = signal_info.get('supertrend')

            if base_stop_loss is None:
                return None

        elif self.stop_loss_type == 'ppcenterline':
            # PPCenterLine strategy: Use pivot point center line
            pivot_center = signal_info.get('pivot')
            if pivot_center is None:
                return None
            base_stop_loss = pivot_center

        if base_stop_loss is None:
            return None

        # Calculate original stop pips (before buffer) if entry price provided
        if entry_price:
            self.current_original_stop_pips = abs(entry_price - base_stop_loss) / 0.0001

        # Apply spread buffer if enabled
        if TradingConfig.use_spread_adjustment:
            # Convert buffer from pips to price (1 pip = 0.0001 for most pairs)
            buffer_price = self.spread_buffer_pips * 0.0001

            if signal_type == 'SELL':  # SHORT position
                adjusted_stop_loss = base_stop_loss + buffer_price
            else:  # BUY / LONG position
                adjusted_stop_loss = base_stop_loss - buffer_price

            # Calculate adjusted stop pips if entry price provided
            if entry_price:
                self.current_adjusted_stop_pips = abs(entry_price - adjusted_stop_loss) / 0.0001

            return adjusted_stop_loss

        # No buffer applied
        if entry_price:
            self.current_adjusted_stop_pips = self.current_original_stop_pips

        return base_stop_loss
    
    def update_take_profit_if_needed(self):
        """Check if take profit was hit and update tracking"""
        if not self.current_trade_id or not self.current_take_profit_price:
            return

        # Check if position still exists
        current_position = self.client.get_position(self.instrument)
        if not current_position or current_position['units'] == 0:
            # Position closed - check if it was due to take profit
            if self.current_position_side and self.current_take_profit_price:
                # Mark that take profit was likely hit
                self.logger.info("📍 Position closed (likely take profit hit)")
                return True
        return False

    # ============================================================================
    # SCALPING STRATEGY METHODS
    # ============================================================================

    def is_in_scalping_window(self):
        """
        Check if current time is within the scalping window (default: 8 PM - 8 AM PT).

        Returns:
            bool: True if within scalping window, False otherwise
        """
        if not self.scalping_enabled:
            return False

        try:
            import pytz
            from datetime import datetime, time as dt_time

            # Get timezone from config
            tz_name = self.scalping_config.get('time_window', {}).get('timezone', 'America/Los_Angeles')
            tz = pytz.timezone(tz_name)

            # Get current time in configured timezone
            now = datetime.now(tz)
            current_time = now.time()

            # Parse start and end times from config
            start_str = self.scalping_config.get('time_window', {}).get('start', '20:00')
            end_str = self.scalping_config.get('time_window', {}).get('end', '08:00')

            start_hour, start_min = map(int, start_str.split(':'))
            end_hour, end_min = map(int, end_str.split(':'))

            start_time = dt_time(start_hour, start_min)
            end_time = dt_time(end_hour, end_min)

            # Handle overnight window (start > end, e.g., 20:00 - 08:00)
            if start_time > end_time:
                # In window if current time >= start OR current time < end
                in_window = current_time >= start_time or current_time < end_time
            else:
                # Normal window (start < end)
                in_window = start_time <= current_time < end_time

            return in_window

        except Exception as e:
            self.logger.error(f"Error checking scalping window: {e}")
            return False

    def start_scalping_mode(self, signal_price, position_type, supertrend_value, market_trend, rr_ratio, signal_time):
        """
        Initialize scalping mode after first trade entry.

        Args:
            signal_price: The entry price of the initial trade (signal_price)
            position_type: 'LONG' or 'SHORT'
            supertrend_value: SuperTrend value at signal time
            market_trend: 'BULL' or 'BEAR'
            rr_ratio: Risk/reward ratio used for take profit
            signal_time: Timestamp of the PP signal
        """
        if not self.scalping_enabled:
            return

        if not self.is_in_scalping_window():
            self.logger.info("📊 Not in scalping window, skipping scalping mode")
            return

        self.scalping_active = True
        self.scalping_signal_price = signal_price
        self.scalping_position_type = position_type
        self.scalping_original_supertrend = supertrend_value
        self.scalping_market_trend = market_trend
        self.scalping_rr_ratio = rr_ratio
        self.scalping_signal_time = signal_time
        self.scalping_entry_count = 1  # First entry

        self.logger.info("=" * 60)
        self.logger.info("🔄 SCALPING MODE ACTIVATED")
        self.logger.info(f"   Signal Price: {signal_price:.5f}")
        self.logger.info(f"   Position Type: {position_type}")
        self.logger.info(f"   Market Trend: {market_trend}")
        self.logger.info(f"   R:R Ratio: {rr_ratio:.2f}")
        self.logger.info(f"   Entry #: {self.scalping_entry_count}")
        self.logger.info("=" * 60)

    def reset_scalping_state(self, reason=""):
        """
        Clear scalping state when:
        - New PP signal occurs (trend reversal)
        - Time window ends
        - Stop loss hit

        Args:
            reason: Optional reason string for logging
        """
        if self.scalping_active:
            self.logger.info(f"🛑 SCALPING MODE DEACTIVATED: {reason}")
            self.logger.info(f"   Total scalping entries: {self.scalping_entry_count}")

        # Cancel any pending limit order
        if self.scalping_pending_limit_order_id:
            try:
                self.client.cancel_order(self.scalping_pending_limit_order_id)
                self.logger.info(f"   Cancelled pending limit order: {self.scalping_pending_limit_order_id}")
            except Exception as e:
                self.logger.warning(f"   Failed to cancel limit order: {e}")

        self.scalping_active = False
        self.scalping_signal_price = None
        self.scalping_signal_time = None
        self.scalping_entry_count = 0
        self.scalping_position_type = None
        self.scalping_original_supertrend = None
        self.scalping_market_trend = None
        self.scalping_rr_ratio = None
        self.scalping_pending_limit_order_id = None

    def check_scalping_re_entry(self, current_price):
        """
        Check if price has returned to signal_price (or better) for scalping re-entry.
        "Better" means:
        - For LONG: price <= signal_price (cheaper entry)
        - For SHORT: price >= signal_price (higher entry to short)

        Args:
            current_price: Current market price

        Returns:
            bool: True if re-entry condition met, False otherwise
        """
        if not self.scalping_active or not self.scalping_signal_price:
            return False

        if not self.is_in_scalping_window():
            self.reset_scalping_state("Time window ended")
            return False

        # Check if at or better than signal price
        if self.scalping_position_type == 'LONG':
            # For long, we want price at or below signal_price (better entry)
            return current_price <= self.scalping_signal_price
        else:  # SHORT
            # For short, we want price at or above signal_price (better entry)
            return current_price >= self.scalping_signal_price

    def execute_scalping_re_entry(self, signal_info, account_summary):
        """
        Execute a scalping re-entry trade using the original signal parameters.
        Uses limit order for precise entry at signal_price.

        Args:
            signal_info: Current signal info (for stop loss calculation)
            account_summary: Account summary for position sizing
        """
        if not self.scalping_active:
            return False

        self.scalping_entry_count += 1

        self.logger.info("=" * 60)
        self.logger.info(f"🔄 SCALPING RE-ENTRY #{self.scalping_entry_count}")
        self.logger.info(f"   Signal Price: {self.scalping_signal_price:.5f}")
        self.logger.info(f"   Position Type: {self.scalping_position_type}")
        self.logger.info(f"   Market Trend: {self.scalping_market_trend}")
        self.logger.info("=" * 60)

        # Calculate position size using original market trend
        position_size, risk_amount_used = self.risk_manager.calculate_position_size(
            account_summary['balance'],
            signal_info,
            market_trend=self.scalping_market_trend,
            position_type=self.scalping_position_type,
            config=self.config
        )

        # Validate trade
        is_valid, reason = self.risk_manager.validate_trade(account_summary, position_size)
        if not is_valid:
            self.logger.warning(f"⚠️  Scalping re-entry validation failed: {reason}")
            return False

        # Determine units
        units = position_size if self.scalping_position_type == 'LONG' else -position_size

        # Calculate stop loss using original supertrend + buffer
        signal_type = 'BUY' if self.scalping_position_type == 'LONG' else 'SELL'

        # Use original supertrend value for consistent stop loss
        if self.scalping_original_supertrend:
            buffer_price = self.spread_buffer_pips * 0.0001
            if signal_type == 'SELL':
                stop_loss = self.scalping_original_supertrend + buffer_price
            else:
                stop_loss = self.scalping_original_supertrend - buffer_price
        else:
            stop_loss = self.calculate_stop_loss(signal_info, signal_type)

        # Calculate take profit based on original R:R ratio
        # Use RAW SuperTrend (no buffer) for TP calculation to match manual order tool logic
        take_profit = self.calculate_take_profit(
            self.scalping_signal_price,  # Use signal_price, not current price
            self.scalping_original_supertrend,  # Use RAW SuperTrend, not buffered stop_loss
            self.scalping_position_type,
            self.scalping_rr_ratio
        )

        self.logger.info(f"💰 Position Size: {abs(units):,} units ({abs(units)/100000:.3f} lots)")
        self.logger.info(f"📍 Entry Price: {self.scalping_signal_price:.5f}")
        self.logger.info(f"🛑 Stop Loss: {stop_loss:.5f}")
        self.logger.info(f"✅ Take Profit: {take_profit:.5f} (R:R {self.scalping_rr_ratio:.2f})")

        # Check if we should use limit orders or market orders
        use_limit_orders = self.scalping_config.get('re_entry', {}).get('use_limit_orders', True)

        if use_limit_orders:
            # Place limit order at signal_price
            price_buffer_pips = self.scalping_config.get('re_entry', {}).get('price_buffer_pips', 0.5)
            buffer = price_buffer_pips * 0.0001

            if self.scalping_position_type == 'LONG':
                limit_price = self.scalping_signal_price + buffer  # Slightly above for execution
            else:
                limit_price = self.scalping_signal_price - buffer  # Slightly below for execution

            result = self.client.place_limit_order(
                instrument=self.instrument,
                units=units,
                price=limit_price,
                stop_loss=stop_loss,
                take_profit=take_profit
            )

            if result and 'orderCreateTransaction' in result:
                order_id = result['orderCreateTransaction']['id']
                self.scalping_pending_limit_order_id = order_id
                self.logger.info(f"✅ Limit order placed: #{order_id} at {limit_price:.5f}")
                return True
            elif result and 'orderFillTransaction' in result:
                # Order filled immediately
                self._handle_scalping_order_fill(result, risk_amount_used)
                return True
            else:
                self.logger.error("❌ Failed to place scalping limit order")
                return False
        else:
            # Use market order for immediate entry
            result = self.client.place_market_order(
                instrument=self.instrument,
                units=units,
                stop_loss=stop_loss,
                take_profit=take_profit
            )

            if result:
                self._handle_scalping_order_fill(result, risk_amount_used)
                return True
            else:
                self.logger.error("❌ Failed to place scalping market order")
                return False

    def _handle_scalping_order_fill(self, result, risk_amount_used):
        """Handle order fill for scalping entry"""
        self.logger.info("✅ Scalping order filled!")
        self.trade_count += 1

        if 'orderFillTransaction' in result:
            fill = result['orderFillTransaction']
            actual_price = float(fill['price'])

            self.logger.info(f"📈 Fill Price: {actual_price:.5f}")

            # Store entry details
            self.current_entry_price = actual_price
            self.highest_price_during_trade = actual_price
            self.lowest_price_during_trade = actual_price
            self.current_trade_open_time = datetime.now()
            self.current_supertrend_value = self.scalping_original_supertrend
            self.current_position_size = abs(int(fill.get('units', 0)))
            self.current_market_trend = self.scalping_market_trend
            self.current_risk_reward_target = self.scalping_rr_ratio
            self.current_risk_amount = risk_amount_used

            # Enhanced status display tracking
            self.current_init_sl = self.scalping_original_supertrend  # Raw SuperTrend (no buffer)
            self.current_fill_price = actual_price  # Actual OANDA fill price
            self.current_expected_rr = self.scalping_rr_ratio  # Expected R:R at entry
            # Calculate init_tp using the same formula as scalping_re_entry
            if self.scalping_original_supertrend:
                self.current_init_tp = self.calculate_take_profit(
                    self.scalping_signal_price,
                    self.scalping_original_supertrend,
                    self.scalping_position_type,
                    self.scalping_rr_ratio
                )

            if 'tradeOpened' in fill:
                self.current_trade_id = fill['tradeOpened']['tradeID']

            if 'stopLossOrderTransaction' in result:
                sl_order = result['stopLossOrderTransaction']
                self.current_stop_loss_order_id = sl_order['id']
                self.current_stop_loss_price = float(sl_order['price'])
                self.current_position_side = self.scalping_position_type

            if 'takeProfitOrderTransaction' in result:
                tp_order = result['takeProfitOrderTransaction']
                self.current_take_profit_price = float(tp_order['price'])

            # Initialize trade tracker
            self.trade_tracker.entry_price = actual_price
            self.trade_tracker.position_side = self.scalping_position_type
            self.trade_tracker.units = self.current_position_size
            self.trade_tracker.risk_amount = risk_amount_used

    def check_pending_scalping_order(self):
        """
        Check if pending scalping limit order was filled.

        Returns:
            bool: True if order was filled, False otherwise
        """
        if not self.scalping_pending_limit_order_id:
            return False

        try:
            order_info = self.client.get_order(self.scalping_pending_limit_order_id)

            if order_info:
                state = order_info.get('state', '')

                if state == 'FILLED':
                    self.logger.info(f"✅ Scalping limit order #{self.scalping_pending_limit_order_id} filled!")
                    self.scalping_pending_limit_order_id = None

                    # Refresh position tracking
                    trades = self.client.get_trades(self.instrument)
                    if trades and len(trades) > 0:
                        trade = trades[0]
                        self._recover_trade_tracking(trade)

                    return True

                elif state == 'CANCELLED':
                    self.logger.info(f"⚠️  Scalping limit order #{self.scalping_pending_limit_order_id} cancelled")
                    self.scalping_pending_limit_order_id = None

        except Exception as e:
            self.logger.error(f"Error checking pending scalping order: {e}")

        return False

    def _recover_trade_tracking(self, trade):
        """Recover trade tracking from trade info"""
        tracking_units = None
        for key in ['currentUnits', 'current_units', 'units', 'initialUnits']:
            if key in trade:
                tracking_units = float(trade[key])
                break

        if tracking_units:
            self.current_trade_id = trade.get('id')
            self.current_position_side = 'LONG' if tracking_units > 0 else 'SHORT'
            self.current_entry_price = float(trade.get('price', 0))
            self.current_position_size = abs(tracking_units)

            if trade.get('stopLossOrder'):
                self.current_stop_loss_price = float(trade['stopLossOrder']['price'])
                self.current_stop_loss_order_id = trade['stopLossOrder']['id']

            if trade.get('takeProfitOrder'):
                self.current_take_profit_price = float(trade['takeProfitOrder']['price'])

    # ============================================================================
    # END SCALPING STRATEGY METHODS
    # ============================================================================

    def _close_position_for_news(self, reason: str):
        """
        Close current position due to upcoming high-impact news event.

        Args:
            reason: Reason string for logging (e.g., "Close before news: US CPI in 5m")
        """
        try:
            current_position = self.client.get_position(self.instrument)
            if not current_position or current_position['units'] == 0:
                return

            side = current_position['side']
            units = abs(current_position['units'])

            self.logger.info("=" * 80)
            self.logger.warning(f"📰 CLOSING POSITION for {self.instrument} - NEWS EVENT")
            self.logger.info(f"Reason: {reason}")
            self.logger.info(f"Position: {side} {units} units")
            self.logger.info(f"Unrealized P/L: ${current_position['unrealized_pl']:.2f}")
            self.logger.info("=" * 80)

            result = self.client.close_position(self.instrument, side)

            if result:
                self.logger.info("✅ Position closed successfully (news event)")

                # Get close details
                close_time = datetime.now()
                profit = current_position['unrealized_pl']

                # Calculate R:R ratios for logging
                risk_amount = self.current_risk_amount if self.current_risk_amount else 100
                actual_rr = profit / risk_amount if risk_amount > 0 else 0
                highest_ratio = self.trade_tracker.highest_ratio if self.trade_tracker.highest_ratio else actual_rr
                lowest_ratio = self.trade_tracker.lowest_ratio if self.trade_tracker.lowest_ratio else actual_rr
                potential_profit = self.trade_tracker.highest_pl if self.trade_tracker.highest_pl else profit
                potential_loss = self.trade_tracker.lowest_pl if self.trade_tracker.lowest_pl else profit
                position_size = self.current_position_size if self.current_position_size else 0

                # Determine market
                market = self.current_market_trend.upper() if self.current_market_trend and self.current_market_trend.upper() in ['BEAR', 'BULL'] else 'NEUTRAL'
                if market not in ['BEAR', 'BULL']:
                    market = 'BEAR'

                # Log to CSV
                csv_data = {
                    'market': market,
                    'signal': self.current_position_side if self.current_position_side else side,
                    'time': self.current_trade_open_time.strftime('%Y-%m-%d %H:%M:%S') if self.current_trade_open_time else 'N/A',
                    'tradeID': self.current_trade_id if self.current_trade_id else 'N/A',
                    'entry_price': f"{self.current_entry_price:.5f}" if self.current_entry_price else 'N/A',
                    'stop_loss_price': f"{self.current_stop_loss_price:.5f}" if self.current_stop_loss_price else 'N/A',
                    'take_profit_price': f"{self.current_take_profit_price:.5f}" if self.current_take_profit_price else 'N/A',
                    'position_lots': f"{position_size / 100000:.3f}" if position_size else 'N/A',
                    'risk_amount': f"{risk_amount:.2f}",
                    'original_stop_pips': f"{self.current_original_stop_pips:.1f}" if self.current_original_stop_pips else 'N/A',
                    'buffer_pips': f"{self.spread_buffer_pips}",
                    'adjusted_stop_pips': f"{self.current_adjusted_stop_pips:.1f}" if self.current_adjusted_stop_pips else 'N/A',
                    'take_profit_ratio': f"{self.current_risk_reward_target:.1f}" if self.current_risk_reward_target else 'N/A',
                    'highest_ratio': f"{highest_ratio:.2f}",
                    'potential_profit': f"{potential_profit:.2f}",
                    'actual_profit': f"{profit:.2f}",
                    'lowest_ratio': f"{lowest_ratio:.2f}",
                    'potential_loss': f"{potential_loss:.2f}",
                    'position_status': 'NEWS_CLOSE',
                    'take_profit_hit': 'FALSE',
                    'stop_loss_hit': 'FALSE'
                }
                self.csv_logger.log_trade(csv_data)
                self.logger.info(f"   💾 Logged news close to CSV: Trade #{self.current_trade_id}, P/L=${profit:.2f}")

                # Reset trade tracker
                self.trade_tracker.reset()

                # Clear position tracking
                self.current_stop_loss_order_id = None
                self.current_trade_id = None
                self.current_stop_loss_price = None
                self.current_take_profit_price = None
                self.current_position_side = None
                self.current_entry_price = None
                self.highest_price_during_trade = None
                self.lowest_price_during_trade = None
                self.current_trade_open_time = None
                self.current_supertrend_value = None
                self.current_pivot_point_value = None
                self.current_position_size = None
                self.current_market_trend = 'NEUTRAL'
                self.current_risk_reward_target = None
                self.current_risk_amount = None
                self.current_original_stop_pips = None
                self.current_adjusted_stop_pips = None

                # Reset enhanced status display tracking
                self.current_init_sl = None
                self.current_init_tp = None
                self.current_fill_price = None
                self.current_expected_rr = None

                # Reset scalping if active
                if self.scalping_active:
                    self.reset_scalping_state("Closed for news event")

                # Reset signal state to allow new trade after news passes
                self.last_signal_candle_time = None
                self._save_state()

            else:
                self.logger.error("❌ Failed to close position for news event")

        except Exception as e:
            self.logger.error(f"Error closing position for news: {e}", exc_info=True)

    def execute_trade(self, action, signal_info, account_summary):
        """Execute trade based on action and log to CSV

        Returns:
            bool: True if trade executed successfully, False otherwise
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

                    # Determine hit status
                    stop_loss_hit = 'FALSE'
                    take_profit_hit = 'FALSE'
                    if fill.get('reason') == 'STOP_LOSS_ORDER':
                        stop_loss_hit = 'TRUE'
                    elif fill.get('reason') == 'TAKE_PROFIT_ORDER':
                        take_profit_hit = 'TRUE'

                    position_size = abs(current_position['units'])

                    # Calculate actual risk/reward
                    risk_reward_actual = 'N/A'
                    if self.current_stop_loss_price and self.current_entry_price:
                        risk = abs(self.current_entry_price - self.current_stop_loss_price) * position_size
                        if risk > 0:
                            risk_reward_actual = f"{(profit / risk):.2f}"

                    # Calculate R:R ratios
                    risk_amount = self.current_risk_amount if self.current_risk_amount else 100
                    actual_rr = profit / risk_amount if risk_amount > 0 else 0
                    highest_ratio = self.trade_tracker.highest_ratio if self.trade_tracker.highest_ratio else actual_rr
                    lowest_ratio = self.trade_tracker.lowest_ratio if self.trade_tracker.lowest_ratio else actual_rr

                    # Calculate potential profit/loss
                    potential_profit = self.trade_tracker.highest_pl if self.trade_tracker.highest_pl else profit
                    potential_loss = self.trade_tracker.lowest_pl if self.trade_tracker.lowest_pl else profit

                    # Determine market (only BEAR or BULL, fallback to current signal)
                    market = self.current_market_trend.upper() if self.current_market_trend and self.current_market_trend.upper() in ['BEAR', 'BULL'] else self.current_market_signal
                    if market not in ['BEAR', 'BULL']:
                        market = 'BEAR'  # Default fallback

                    csv_data = {
                        'market': market,
                        'signal': current_position['side'],
                        'time': self.current_trade_open_time.strftime('%Y-%m-%d %H:%M:%S') if self.current_trade_open_time else 'N/A',
                        'tradeID': self.current_trade_id if self.current_trade_id else 'N/A',
                        'entry_price': f"{self.current_entry_price:.5f}" if self.current_entry_price else 'N/A',
                        'stop_loss_price': f"{self.current_stop_loss_price:.5f}" if self.current_stop_loss_price else 'N/A',
                        'take_profit_price': f"{self.current_take_profit_price:.5f}" if self.current_take_profit_price else 'N/A',
                        'position_lots': f"{position_size / 100000:.3f}",
                        'risk_amount': f"{risk_amount:.2f}",
                        'original_stop_pips': f"{self.current_original_stop_pips:.1f}" if self.current_original_stop_pips else 'N/A',
                        'buffer_pips': f"{self.spread_buffer_pips}",
                        'adjusted_stop_pips': f"{self.current_adjusted_stop_pips:.1f}" if self.current_adjusted_stop_pips else 'N/A',
                        'take_profit_ratio': f"{self.current_risk_reward_target:.1f}" if self.current_risk_reward_target else 'N/A',
                        'highest_ratio': f"{highest_ratio:.2f}",
                        'potential_profit': f"{potential_profit:.2f}",
                        'actual_profit': f"{profit:.2f}",
                        'lowest_ratio': f"{lowest_ratio:.2f}",
                        'potential_loss': f"{potential_loss:.2f}",
                        'position_status': 'CLOSED',
                        'take_profit_hit': take_profit_hit,
                        'stop_loss_hit': stop_loss_hit
                    }
                    self.csv_logger.log_trade(csv_data)

                    self.logger.info(f"📊 Trade #{self.current_trade_id} closed, P/L: ${profit:.2f}")

                # Reset trade tracker
                self.trade_tracker.reset()

                # Clear tracking variables
                self.current_stop_loss_order_id = None
                self.current_trade_id = None
                self.current_stop_loss_price = None
                self.current_take_profit_price = None
                self.current_position_side = None
                self.current_entry_price = None
                self.highest_price_during_trade = None
                self.lowest_price_during_trade = None
                self.current_trade_open_time = None
                self.current_supertrend_value = None
                self.current_pivot_point_value = None
                self.current_position_size = None
                self.current_market_trend = 'NEUTRAL'
                self.current_risk_reward_target = None
                self.current_risk_amount = None
                self.current_original_stop_pips = None
                self.current_adjusted_stop_pips = None

                # Reset enhanced status display tracking
                self.current_init_sl = None
                self.current_init_tp = None
                self.current_fill_price = None
                self.current_expected_rr = None

                # Reset signal tracking so next signal can be acted upon
                self.last_signal_candle_time = None
                self._save_state()
                return True
            else:
                self.logger.error("❌ Failed to close position")
                return False

        elif action in ['OPEN_LONG', 'OPEN_SHORT']:
            # Get current market trend
            market_trend = self.check_market_trend()
            
            # Calculate position size with market-aware dynamic sizing
            position_type = 'LONG' if action == 'OPEN_LONG' else 'SHORT'
            position_size, risk_amount_used = self.risk_manager.calculate_position_size(
                account_summary['balance'],
                signal_info,
                market_trend=market_trend,
                position_type=position_type,
                config=self.config
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
            position_type = 'LONG' if action == 'OPEN_LONG' else 'SHORT'
            stop_loss = self.calculate_stop_loss(signal_info, signal_type)

            current_price = signal_info['price']

            # Get base stop (without buffer) for TP calculation
            # Position sizing uses this distance, so TP must also use it for consistent R:R
            base_stop = signal_info.get('supertrend') if self.stop_loss_type == 'supertrend' else signal_info.get('pivot')

            # Calculate take profit based on market trend and position type
            risk_reward_ratio = self.get_risk_reward_ratio(market_trend, position_type)
            take_profit = None
            if stop_loss and base_stop:
                # Use base_stop (without buffer) to be consistent with position sizing
                take_profit = self.calculate_take_profit(current_price, base_stop, position_type, risk_reward_ratio)

            # Log trade details
            self.logger.info("=" * 80)
            self.logger.info(f"{'🟢 OPENING LONG' if action == 'OPEN_LONG' else '🔴 OPENING SHORT'}")
            self.logger.info(f"Trade #{self.trade_count + 1}")
            self.logger.info(f"Market Trend: {market_trend}")
            self.logger.info(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            self.logger.info(f"Instrument: {self.instrument}")
            self.logger.info(f"Direction: {signal_type}")
            self.logger.info(f"💰 Dynamic Position Size: ${risk_amount_used:.0f} risk → {abs(units):,} units ({abs(units)/100000:.3f} lots)")
            self.logger.info(f"Entry Price: {current_price:.5f}")
            self.logger.info(f"Stop Loss: {stop_loss:.5f}" if stop_loss else "Stop Loss: Not set")
            self.logger.info(f"Take Profit: {take_profit:.5f} (R:R {risk_reward_ratio:.1f})" if take_profit else "Take Profit: Not set")
            self.logger.info("=" * 80)

            # Place order with both stop loss and take profit
            result = self.client.place_market_order(
                instrument=self.instrument,
                units=units,
                stop_loss=stop_loss,
                take_profit=take_profit
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

                    # Store entry price and other tracking data
                    self.current_entry_price = actual_price
                    self.highest_price_during_trade = actual_price
                    self.lowest_price_during_trade = actual_price
                    self.current_trade_open_time = datetime.now()
                    self.current_supertrend_value = signal_info.get('supertrend')
                    self.current_pivot_point_value = signal_info.get('pivot')
                    self.current_position_size = abs(units)
                    self.current_market_trend = market_trend
                    self.current_risk_reward_target = risk_reward_ratio
                    self.current_risk_amount = risk_amount_used

                    # Enhanced status display tracking
                    self.current_init_sl = base_stop  # Raw SuperTrend (no buffer)
                    self.current_init_tp = take_profit  # Initial TP before correction
                    self.current_fill_price = actual_price  # Actual OANDA fill price
                    self.current_expected_rr = risk_reward_ratio  # Expected R:R at entry

                    # Store trade ID
                    if 'tradeOpened' in fill:
                        self.current_trade_id = fill['tradeOpened']['tradeID']

                    # Store stop loss info
                    if 'stopLossOrderTransaction' in result:
                        sl_order = result['stopLossOrderTransaction']
                        self.current_stop_loss_order_id = sl_order['id']
                        self.current_stop_loss_price = float(sl_order['price'])
                        self.current_position_side = position_type

                    # Store take profit info and recalculate if needed based on actual fill price
                    # First try to get TP from order response
                    initial_tp_price = None
                    tp_order_id = None

                    if 'takeProfitOrderTransaction' in result:
                        tp_order = result['takeProfitOrderTransaction']
                        initial_tp_price = float(tp_order['price'])
                        tp_order_id = tp_order['id']
                    else:
                        # OANDA doesn't always return TP in order response - fetch from trade details
                        time.sleep(0.5)  # Brief delay to ensure trade is registered
                        trades = self.client.get_trades(self.instrument)
                        if trades and len(trades) > 0:
                            trade = trades[0]
                            if trade.get('take_profit_price'):
                                initial_tp_price = trade['take_profit_price']
                                tp_order_id = trade.get('take_profit_order_id')
                                self.logger.info(f"📋 Retrieved TP from trade: {initial_tp_price:.5f}")

                    # Now do TP correction if we have the initial TP info
                    if initial_tp_price is not None and base_stop is not None:
                        # Recalculate correct TP based on actual fill price (not signal price)
                        # Use base_stop (without buffer) to be consistent with position sizing
                        correct_tp = self.calculate_take_profit(actual_price, base_stop, position_type, risk_reward_ratio)

                        # Check if TP needs correction (more than 0.5 pip difference)
                        tp_difference_pips = abs(correct_tp - initial_tp_price) / 0.0001
                        if tp_difference_pips > 0.5:
                            self.logger.info(f"📐 TP Correction: {initial_tp_price:.5f} → {correct_tp:.5f} (based on actual fill {actual_price:.5f})")
                            try:
                                self.client.update_take_profit(self.current_trade_id, correct_tp, tp_order_id)
                                self.current_take_profit_price = correct_tp
                                self.logger.info(f"✅ Take profit updated to {correct_tp:.5f}")
                            except Exception as e:
                                self.logger.warning(f"⚠️  Failed to update TP: {e}. Using initial TP {initial_tp_price:.5f}")
                                self.current_take_profit_price = initial_tp_price
                        else:
                            self.current_take_profit_price = initial_tp_price
                    else:
                        self.logger.warning(f"⚠️  Could not retrieve TP info - TP correction skipped")

                    # Initialize trade tracker
                    self.trade_tracker.entry_price = actual_price
                    self.trade_tracker.position_side = position_type
                    self.trade_tracker.units = abs(units)
                    self.trade_tracker.risk_amount = risk_amount_used

                    # Calculate stop loss pips (now that we have actual entry price)
                    if stop_loss:
                        # Base stop loss (before buffer) - need to recalculate from supertrend/pivot
                        base_stop = signal_info.get('supertrend') if self.stop_loss_type == 'supertrend' else signal_info.get('pivot')
                        if base_stop:
                            self.current_original_stop_pips = abs(actual_price - base_stop) / 0.0001
                            self.current_adjusted_stop_pips = abs(actual_price - stop_loss) / 0.0001

                    # Start scalping mode if enabled and within time window
                    # Use actual fill price as the signal_price for re-entries
                    if self.scalping_enabled and self.is_in_scalping_window():
                        self.start_scalping_mode(
                            signal_price=actual_price,
                            position_type=position_type,
                            supertrend_value=signal_info.get('supertrend'),
                            market_trend=market_trend,
                            rr_ratio=risk_reward_ratio,
                            signal_time=self.current_trade_open_time
                        )
                return True
            else:
                self.logger.error("❌ Failed to place order")
                return False

        return False  # Unknown action

    def update_trailing_stop_loss(self, signal_info, current_position):
        """Update trailing stop loss based on SuperTrend movement"""
        if not TradingConfig.enable_trailing_stop:
            return

        # Check if we have the relevant trailing stop for the position direction
        if self.current_position_side == 'LONG':
            relevant_trailing = signal_info.get('trailing_up')
        else:
            relevant_trailing = signal_info.get('trailing_down')

        if not self.current_stop_loss_order_id or not relevant_trailing:
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

            # Refresh stop loss order ID before updating
            trades = self.client.get_trades(self.instrument)
            if trades and len(trades) > 0:
                trade = trades[0]
                if trade.get('stop_loss_order_id'):
                    self.current_stop_loss_order_id = trade['stop_loss_order_id']
                    self.current_trade_id = trade['id']
                    self.logger.info(f"  Refreshed SL Order ID: {self.current_stop_loss_order_id}")
                else:
                    self.logger.warning("⚠️  No stop loss order found on trade - skipping update")
                    return
            else:
                self.logger.warning("⚠️  No open trades found - position may have closed")
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
                self.logger.error("❌ Failed to update stop loss")
                self.current_stop_loss_order_id = None

    def check_and_trade(self):
        """Main trading logic: check signals and execute trades if needed"""
        try:
            # Check if market trend needs update
            if (self.last_market_check is None or
                (datetime.now() - self.last_market_check).total_seconds() > self.market_check_interval):
                self.check_market_trend()

            # Check news filter - close position and pause trading if high-impact news approaching
            if self.news_manager.is_enabled():
                # Check if we should close position before news
                should_close, close_reason, close_event = self.news_manager.should_close_position()
                if should_close:
                    current_position = self.client.get_position(self.instrument)
                    if current_position and current_position['units'] != 0:
                        self.logger.warning(f"📰 {close_reason}")
                        self.logger.info(f"   Event: {close_event}")
                        self._close_position_for_news(close_reason)
                        return  # Skip rest of trading logic this cycle

                # Check if trading is blocked (pre/post news window)
                is_blocked, block_reason, block_event = self.news_manager.is_news_blocked()
                if is_blocked:
                    self.logger.info(f"📰 Trading paused: {block_reason}")
                    # Still check for position closure and tracking, just skip new trades
                    # Continue to the position monitoring code below
                else:
                    # Log next upcoming news event (if within 60 minutes)
                    next_event = self.news_manager.get_upcoming_event(within_minutes=60)
                    if next_event:
                        from datetime import datetime as dt
                        import pytz
                        now = dt.utcnow().replace(tzinfo=pytz.UTC)
                        mins_until = int((next_event.datetime - now).total_seconds() / 60)
                        pre_buffer = int(self.news_manager.pre_news_buffer.total_seconds() / 60)

                        # Convert event time to Pacific Time for display
                        pt_tz = pytz.timezone('America/Los_Angeles')
                        event_time_pt = next_event.datetime.astimezone(pt_tz)
                        event_time_str = event_time_pt.strftime('%m/%d %H:%M PT')

                        self.logger.info(f"📰 Next NEWS: {next_event.title} ({next_event.currency}) at {event_time_str} ({mins_until}m) | "
                                       f"Will close position & pause bot {pre_buffer}m before")

            # Check pending scalping limit orders
            if self.scalping_pending_limit_order_id:
                self.check_pending_scalping_order()

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

            # Check if position was closed by take profit or stop loss
            if (self.current_position_side is not None and
                self.current_entry_price is not None and
                self.current_position_size and self.current_position_size > 0):
                if current_position is None or current_position['units'] == 0:
                    # Log the close to CSV
                    close_time = datetime.now()

                    # Try to get actual P/L from OANDA transaction history
                    stop_loss_hit = 'FALSE'
                    take_profit_hit = 'FALSE'
                    profit = 0.0
                    close_price = self.current_stop_loss_price  # Default to stop loss price
                    reason = ''

                    try:
                        transactions = self.client.get_transaction_history(count=50)
                        if transactions:
                            for txn in reversed(transactions):
                                if (txn.get('type') == 'ORDER_FILL' and
                                    txn.get('instrument') == self.instrument):
                                    close_price = float(txn.get('price', 0))
                                    profit = float(txn.get('pl', 0))
                                    reason = txn.get('reason', '')
                                    self.logger.info(f"   Found close transaction: Price={close_price:.5f}, P/L=${profit:.2f}, Reason={reason}")
                                    break
                    except Exception as e:
                        self.logger.error(f"   Failed to fetch transaction history: {e}")

                    # Calculate P/L percentage of risk amount
                    risk_amount = self.current_risk_amount if self.current_risk_amount else 100
                    pl_percentage = (profit / risk_amount) * 100 if risk_amount > 0 else 0
                    expected_rr = self.current_expected_rr if self.current_expected_rr else self.current_risk_reward_target
                    if expected_rr is None:
                        # Fall back to calculating from config based on current market/position
                        market_trend = self.current_market_signal if self.current_market_signal in ['BEAR', 'BULL'] else 'BEAR'
                        position_type = self.current_position_side if self.current_position_side else 'SHORT'
                        expected_rr = self.get_risk_reward_ratio(market_trend, position_type)
                    expected_rr_pct = expected_rr * 100 if expected_rr else 60  # Default 60% (0.6 R:R)

                    # Determine if TP or SL was hit based on P/L vs expected R:R
                    # First check OANDA's reason field (if available)
                    if 'STOP_LOSS' in reason:
                        stop_loss_hit = 'TRUE'
                        self.logger.info(f"📍 Position closed externally by stop loss: P/L=${profit:.2f} ({pl_percentage:.2f}%)")
                    elif 'TAKE_PROFIT' in reason:
                        take_profit_hit = 'TRUE'
                        self.logger.info(f"📍 Position closed externally by take profit: ({pl_percentage:.2f}% vs expected TP R:R = {expected_rr:.1f})")
                    else:
                        # Calculate based on P/L percentage vs expected R:R
                        # If P/L >= 90% of expected R:R, consider it a TP hit
                        if profit > 0 and pl_percentage >= (expected_rr_pct * 0.9):
                            take_profit_hit = 'TRUE'
                            self.logger.info(f"📍 Position closed externally by take profit: ({pl_percentage:.2f}% vs expected TP R:R = {expected_rr:.1f})")
                        elif profit < 0:
                            stop_loss_hit = 'TRUE'
                            self.logger.info(f"📍 Position closed externally by stop loss: P/L=${profit:.2f} ({pl_percentage:.2f}%)")
                        else:
                            # Small profit but not reaching TP threshold - likely manual close
                            self.logger.info(f"📍 Position closed externally (manual/other): P/L=${profit:.2f} ({pl_percentage:.2f}%)")

                    # Calculate duration
                    duration = 'N/A'
                    if self.current_trade_open_time:
                        duration_seconds = (close_time - self.current_trade_open_time).total_seconds()
                        duration_minutes = int(duration_seconds / 60)
                        duration = f"{duration_minutes}m"

                    # Calculate R:R ratios (risk_amount already defined above)
                    actual_rr = profit / risk_amount if risk_amount > 0 else 0
                    highest_ratio = self.trade_tracker.highest_ratio if self.trade_tracker.highest_ratio else actual_rr
                    lowest_ratio = self.trade_tracker.lowest_ratio if self.trade_tracker.lowest_ratio else actual_rr

                    # Calculate potential profit/loss
                    potential_profit = self.trade_tracker.highest_pl if self.trade_tracker.highest_pl else profit
                    potential_loss = self.trade_tracker.lowest_pl if self.trade_tracker.lowest_pl else profit

                    position_size = self.current_position_size if self.current_position_size else 0

                    # Determine market (only BEAR or BULL, fallback to current signal)
                    market = self.current_market_trend.upper() if self.current_market_trend and self.current_market_trend.upper() in ['BEAR', 'BULL'] else self.current_market_signal
                    if market not in ['BEAR', 'BULL']:
                        market = 'BEAR'  # Default fallback

                    # Log to CSV
                    csv_data = {
                        'market': market,
                        'signal': self.current_position_side if self.current_position_side else 'N/A',
                        'time': self.current_trade_open_time.strftime('%Y-%m-%d %H:%M:%S') if self.current_trade_open_time else 'N/A',
                        'tradeID': self.current_trade_id if self.current_trade_id else 'N/A',
                        'entry_price': f"{self.current_entry_price:.5f}" if self.current_entry_price else 'N/A',
                        'stop_loss_price': f"{self.current_stop_loss_price:.5f}" if self.current_stop_loss_price else 'N/A',
                        'take_profit_price': f"{self.current_take_profit_price:.5f}" if self.current_take_profit_price else 'N/A',
                        'position_lots': f"{position_size / 100000:.3f}" if position_size else 'N/A',
                        'risk_amount': f"{risk_amount:.2f}",
                        'original_stop_pips': f"{self.current_original_stop_pips:.1f}" if self.current_original_stop_pips else 'N/A',
                        'buffer_pips': f"{self.spread_buffer_pips}",
                        'adjusted_stop_pips': f"{self.current_adjusted_stop_pips:.1f}" if self.current_adjusted_stop_pips else 'N/A',
                        'take_profit_ratio': f"{self.current_risk_reward_target:.1f}" if self.current_risk_reward_target else 'N/A',
                        'highest_ratio': f"{highest_ratio:.2f}",
                        'potential_profit': f"{potential_profit:.2f}",
                        'actual_profit': f"{profit:.2f}",
                        'lowest_ratio': f"{lowest_ratio:.2f}",
                        'potential_loss': f"{potential_loss:.2f}",
                        'position_status': 'CLOSED',
                        'take_profit_hit': take_profit_hit,
                        'stop_loss_hit': stop_loss_hit
                    }
                    self.csv_logger.log_trade(csv_data)
                    self.logger.info(f"   💾 Logged external close to CSV: Trade #{self.current_trade_id}, P/L=${profit:.2f} ({pl_percentage:.2f}%), TP={take_profit_hit}, SL={stop_loss_hit}")

                    # Reset trade tracker
                    self.trade_tracker.reset()

                    # Clear position tracking
                    self.current_stop_loss_order_id = None
                    self.current_trade_id = None
                    self.current_stop_loss_price = None
                    self.current_take_profit_price = None
                    self.current_position_side = None
                    self.current_entry_price = None
                    self.highest_price_during_trade = None
                    self.lowest_price_during_trade = None
                    self.current_trade_open_time = None
                    self.current_supertrend_value = None
                    self.current_pivot_point_value = None
                    self.current_position_size = None
                    self.current_market_trend = 'NEUTRAL'
                    self.current_risk_reward_target = None
                    self.current_risk_amount = None
                    self.current_original_stop_pips = None
                    self.current_adjusted_stop_pips = None

                    # SCALPING: Check if TP was hit and scalping is active
                    if self.scalping_active and take_profit_hit == 'TRUE':
                        self.logger.info("🔄 SCALPING: Take profit hit - checking for re-entry opportunity")
                        # Don't reset signal state - keep scalping active for re-entry
                        # The scalping re-entry will be checked below
                    elif self.scalping_active and stop_loss_hit == 'TRUE':
                        # Stop loss hit - deactivate scalping
                        self.reset_scalping_state("Stop loss hit")
                        self.last_signal_candle_time = None
                        self._save_state()
                    else:
                        # Normal close or unknown - reset signal state
                        if self.scalping_active:
                            self.reset_scalping_state("Position closed (unknown reason)")
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
                        self.current_entry_price = float(trade.get('price')) if trade.get('price') else None
                        self.current_position_size = abs(float(trade['units']))

                        # Get stop loss price
                        if trade.get('stop_loss_price'):
                            self.current_stop_loss_price = trade['stop_loss_price']

                        # Get take profit price
                        if trade.get('take_profit_price'):
                            self.current_take_profit_price = trade['take_profit_price']

                        if self.highest_price_during_trade is None and self.current_entry_price:
                            self.highest_price_during_trade = float(self.current_entry_price)
                        if self.lowest_price_during_trade is None and self.current_entry_price:
                            self.lowest_price_during_trade = float(self.current_entry_price)

                        self.logger.info(f"📌 Recovered tracking: Trade {self.current_trade_id}")
                        if self.current_entry_price:
                            self.logger.info(f"   Entry: {self.current_entry_price:.5f}")
                        if self.current_stop_loss_price:
                            self.logger.info(f"   Stop Loss: {self.current_stop_loss_price:.5f}")
                        if self.current_take_profit_price:
                            self.logger.info(f"   Take Profit: {self.current_take_profit_price:.5f}")

            # Print status display (no logger prefix for clean console output)
            self.print_status_display(signal_info, account_summary, current_position)

            # Update P&L tracking if position exists
            if current_position and current_position['units'] != 0:
                current_profit = float(current_position['unrealized_pl'])
                current_price = signal_info.get('close_price')
                self.trade_tracker.update_pl(current_price, unrealized_pl=current_profit)
            
            # Log debug info if available
            if 'debug' in signal_info:
                debug = signal_info['debug']
                if debug.get('trend_changed'):
                    self.logger.info(f"🔄 TREND CHANGED: {debug['prev_trend']} → {debug['curr_trend']}")
                self.logger.debug(f"   Trend: {debug['prev_trend']} → {debug['curr_trend']} | "
                                f"Price: {debug['prev_close']:.5f} → {debug['curr_close']:.5f} | "
                                f"ST: {debug['prev_st']:.5f} → {debug['curr_st']:.5f}")

            # Add diagnostic logging for BUY/SELL signals
            if signal_info['signal'] in ['BUY', 'SELL']:
                self.logger.info(f"🔍 SIGNAL DETECTED: {signal_info['signal']}")
                self.logger.info(f"   Candle Time: {candle_timestamp}")
                if 'candle_age_seconds' in signal_info:
                    age_minutes = signal_info['candle_age_seconds'] / 60
                    self.logger.info(f"   Candle Age: {age_minutes:.1f} minutes")
                self.logger.info(f"   Price: {signal_info['price']:.5f}")
                supertrend_str = f"{signal_info['supertrend']:.5f}" if signal_info['supertrend'] is not None else 'N/A'
                self.logger.info(f"   SuperTrend: {supertrend_str}")
                self.logger.info(f"   Trend: {signal_info['trend']}")

            # Update highest and lowest price tracking during open position
            if current_position and current_position['units'] != 0:
                current_price = signal_info['price']
                if self.highest_price_during_trade is not None:
                    if current_price > self.highest_price_during_trade:
                        self.highest_price_during_trade = current_price
                if self.lowest_price_during_trade is not None:
                    if current_price < self.lowest_price_during_trade:
                        self.lowest_price_during_trade = current_price

            # SCALPING: Check for re-entry when no position and scalping is active
            if self.scalping_active and (current_position is None or current_position['units'] == 0):
                current_price = signal_info['price']

                # Log scalping status
                if self.scalping_signal_price:
                    price_diff = current_price - self.scalping_signal_price
                    price_diff_pips = price_diff / 0.0001
                    self.logger.info(f"🔄 SCALPING: Waiting for re-entry | Signal Price: {self.scalping_signal_price:.5f} | "
                                   f"Current: {current_price:.5f} | Diff: {price_diff_pips:.1f} pips | "
                                   f"Type: {self.scalping_position_type}")

                # Check if price has returned to signal_price (or better)
                if self.check_scalping_re_entry(current_price):
                    self.logger.info(f"🎯 SCALPING: Re-entry condition met! Price at/better than signal price")
                    self.execute_scalping_re_entry(signal_info, account_summary)
                    # Skip normal trading logic this cycle
                    self.last_signal = signal_info
                    return

            # Determine if we should trade
            should_trade, action, next_action = self.risk_manager.should_trade(
                signal_info,
                current_position,
                candle_timestamp,
                self.last_signal_candle_time,
                market_trend=self.current_market_signal,
                config=self.config,
                news_manager=self.news_manager
            )

            if should_trade:
                # SCALPING: Reset scalping on new PP signal (trend reversal)
                if self.scalping_active and action in ['OPEN_LONG', 'OPEN_SHORT', 'CLOSE']:
                    # Check if this is a genuine new PP signal (opposite direction or new signal)
                    is_new_signal = False
                    if action == 'OPEN_LONG' and self.scalping_position_type == 'SHORT':
                        is_new_signal = True
                    elif action == 'OPEN_SHORT' and self.scalping_position_type == 'LONG':
                        is_new_signal = True
                    elif action == 'CLOSE':
                        is_new_signal = True

                    if is_new_signal:
                        self.reset_scalping_state("New PP signal detected (trend reversal)")

                self.logger.info(f"🎯 TRADE SIGNAL: {action}")
                trade_success = self.execute_trade(action, signal_info, account_summary)

                # If closing position with intent to open opposite, do it immediately
                if trade_success and action == 'CLOSE' and next_action in ['OPEN_LONG', 'OPEN_SHORT']:
                    self.logger.info(f"➡️  Immediately opening opposite position: {next_action}")
                    time.sleep(1)
                    account_summary = self.client.get_account_summary()
                    current_position = self.client.get_position(self.instrument)
                    trade_success = self.execute_trade(next_action, signal_info, account_summary)

                # Update last signal candle time ONLY if trade succeeded
                if trade_success:
                    self.last_signal_candle_time = candle_timestamp
                    self._save_state()
                    self.logger.info(f"📝 Saved signal state: {candle_timestamp}")
                else:
                    self.logger.warning(f"⚠️  Trade failed - NOT saving signal state (will retry on next cycle)")
            else:
                if current_position and current_position['units'] != 0:
                    # Check for emergency close (price crossed SuperTrend)
                    # This triggers immediate close without waiting for confirmation bar
                    if self._check_emergency_close(signal_info, current_position):
                        self.logger.info("🔄 Emergency close complete - skipping trailing stop update")
                    else:
                        # Normal trailing stop update
                        self.update_trailing_stop_loss(signal_info, current_position)

            self.last_signal = signal_info

        except Exception as e:
            self.logger.error(f"Error in check_and_trade: {e}", exc_info=True)

    def check_existing_trades(self):
        """Check for existing trades on startup and initialize tracking"""
        try:
            trades = self.client.get_trades()
            if not trades:
                self.logger.info("💡 No existing trades found")
                return
                
            account_summary = self.client.get_account_summary()
            if not account_summary:
                self.logger.warning("⚠️  Could not fetch account summary")
                return
                
            self.logger.info(f"🔍 Checking {len(trades)} existing trades...")
            
            for trade in trades:
                # Add error handling for individual trade processing
                try:
                    trade_id = trade.get('id')
                    if not trade_id:
                        self.logger.error(f"❌ Trade missing ID: {trade}")
                        continue

                    # Initialize tracking for existing trade (CSV only logged on close)
                    if trade['instrument'] == self.instrument:
                        # Handle different possible key names for units (same as above)
                        tracking_units = None
                        for key in ['currentUnits', 'current_units', 'units', 'initialUnits']:
                            if key in trade:
                                tracking_units = float(trade[key])
                                break
                        
                        if tracking_units is None:
                            self.logger.error(f"❌ Unable to find units for tracking trade {trade_id}. Available keys: {list(trade.keys())}")
                            continue
                            
                        self.current_trade_id = trade_id
                        self.current_position_side = 'LONG' if tracking_units > 0 else 'SHORT'
                        self.current_entry_price = float(trade['price'])
                        self.current_position_size = abs(tracking_units)
                        
                        # Initialize trade tracker
                        self.trade_tracker.entry_price = self.current_entry_price
                        self.trade_tracker.position_side = self.current_position_side
                        self.trade_tracker.units = self.current_position_size
                        
                        if trade.get('stopLossOrder'):
                            self.current_stop_loss_price = float(trade['stopLossOrder']['price'])
                            self.current_stop_loss_order_id = trade['stopLossOrder']['id']
                        
                        self.logger.info(f"🔄 Resumed tracking existing {self.current_position_side} position (Trade ID: {trade_id})")
                
                except Exception as e:
                    self.logger.error(f"❌ Error processing trade {trade_id}: {e}")
                    continue
                    
        except Exception as e:
            self.logger.error(f"❌ Error in check_existing_trades: {e}", exc_info=True)

    def _execute_catch_up(self):
        """
        Catch-up: Enter position based on current trend if no position exists.
        Used when bot missed a signal and needs to enter on the current HOLD state.
        """
        self.logger.info("🔄 Catch-up mode: Checking if we should enter on current trend...")

        try:
            # Check current position
            current_position = self.client.get_position(self.instrument)
            if current_position and current_position['units'] != 0:
                self.logger.info("📊 Position already exists, skipping catch-up")
                return

            # Get current signal
            df, signal_info, candle_timestamp = self.fetch_and_calculate_indicators()
            signal = signal_info['signal']

            self.logger.info(f"📊 Current signal: {signal}")

            # Determine action based on HOLD state
            action = None
            if signal == 'HOLD_SHORT':
                action = 'OPEN_SHORT'
            elif signal == 'HOLD_LONG':
                action = 'OPEN_LONG'
            elif signal == 'SELL':
                action = 'OPEN_SHORT'
            elif signal == 'BUY':
                action = 'OPEN_LONG'

            if action:
                # Check market trend for opposite trade filter
                market_trend = self.check_market_trend()
                disable_opposite = self.config.get('position_sizing', {}).get('disable_opposite_trade', False)

                if disable_opposite:
                    if market_trend == 'BEAR' and action == 'OPEN_LONG':
                        self.logger.info("⚠️  Catch-up skipped: LONG blocked in BEAR market (disable_opposite_trade)")
                        return
                    if market_trend == 'BULL' and action == 'OPEN_SHORT':
                        self.logger.info("⚠️  Catch-up skipped: SHORT blocked in BULL market (disable_opposite_trade)")
                        return

                self.logger.info(f"🎯 CATCH-UP: Executing {action} based on current trend")
                account_summary = self.client.get_account_summary()
                self.execute_trade(action, signal_info, account_summary)

                # Save state to prevent re-entry on restart
                self.last_signal_candle_time = candle_timestamp
                self._save_state()
                self.logger.info(f"📝 Saved catch-up signal state: {candle_timestamp}")
            else:
                self.logger.info("📊 No actionable signal for catch-up")

        except Exception as e:
            self.logger.error(f"❌ Error in catch-up: {e}", exc_info=True)

    def run(self):
        """Main bot loop"""
        self.is_running = True
        self.logger.info("🚀 Market-aware trading bot started")

        # Check for existing trades on startup
        self.check_existing_trades()

        # Catch-up: Enter position based on current trend if no position exists
        if self.catch_up:
            self._execute_catch_up()

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
        self.logger.info("Market-Aware Trading Bot Stopped")
        self.logger.info(f"Total trades: {self.trade_count}")
        self.logger.info(f"CSV Log: {self.csv_filename}")
        self.logger.info("=" * 80)


def parse_arguments():
    """Parse command line arguments with new format"""
    parser = argparse.ArgumentParser(
        description='Market-Aware Trading Bot with Dynamic Risk/Reward',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python trading_bot_market_aware.py at=account1 fr=EUR_USD tf=5m
  python trading_bot_market_aware.py at=account2 fr=EUR_USD tf=15m
  python trading_bot_market_aware.py at=account1 fr=EUR_USD tf=5m catch-up        # Enter on current trend
  python trading_bot_market_aware.py at=account1 fr=EUR_USD tf=5m close-position  # Close position immediately
        """
    )

    parser.add_argument('account', type=str, help='Account: at=account1, at=account2, etc.')
    parser.add_argument('instrument', type=str, help='Trading instrument: fr=EUR_USD, fr=GBP_USD, etc.')
    parser.add_argument('timeframe', type=str, help='Timeframe: tf=5m or tf=15m')
    parser.add_argument('action', nargs='?', default=None, help='Optional: catch-up or close-position')

    args = parser.parse_args()

    # Parse account
    if not args.account.startswith('at='):
        parser.error("Account must be in format at=account1, at=account2, etc.")
    account = args.account.split('=')[1]
    
    # Parse instrument
    if not args.instrument.startswith('fr='):
        parser.error("Instrument must be in format fr=EUR_USD, fr=GBP_USD, etc.")
    instrument = args.instrument.split('=')[1]
    
    # Parse timeframe
    if not args.timeframe.startswith('tf='):
        parser.error("Timeframe must be in format tf=5m or tf=15m")
    timeframe = args.timeframe.split('=')[1]
    if timeframe not in ['5m', '15m']:
        parser.error("Timeframe must be 5m or 15m")

    # Validate account exists
    if account not in OANDAConfig.list_accounts():
        available = ', '.join(OANDAConfig.list_accounts())
        parser.error(f"Account '{account}' not found. Available accounts: {available}")

    # Parse action flag (catch-up or close-position)
    catch_up = False
    close_position = False
    if args.action:
        if args.action == 'catch-up':
            catch_up = True
        elif args.action == 'close-position':
            close_position = True

    return account, instrument, timeframe, catch_up, close_position


def close_position_immediately(account, instrument):
    """Close all positions for the specified instrument immediately"""
    print(f"\n🔒 CLOSE POSITION MODE")
    print("=" * 60)
    print(f"Account:    {account}")
    print(f"Instrument: {instrument}")
    print("=" * 60)

    # Create OANDA client
    client = OANDAClient()

    # Get current positions
    positions = client.get_open_positions()

    # Find position for this instrument
    target_position = None
    for pos in positions:
        if pos.get('instrument') == instrument:
            target_position = pos
            break

    if not target_position:
        print(f"\n⚠️  No open position found for {instrument}")
        return

    # Display position details
    # get_open_positions() returns simplified format with 'units' and 'side' keys
    units = int(float(target_position.get('units', 0)))
    side = target_position.get('side')
    unrealized_pl = float(target_position.get('unrealized_pl', 0))

    if side == "LONG" and units > 0:
        print(f"\n📈 LONG Position: {units} units")
    elif side == "SHORT" and units < 0:
        print(f"\n📉 SHORT Position: {abs(units)} units")
    else:
        print(f"\n⚠️  No active position to close for {instrument}")
        return

    print(f"💰 Unrealized P/L: ${unrealized_pl:.2f}")

    # Close the position
    try:
        result = client.close_position(instrument, side)

        if result:
            print(f"\n✅ Position closed successfully!")

            # Extract realized P/L from response
            if 'longOrderFillTransaction' in result:
                fill = result['longOrderFillTransaction']
                realized_pl = float(fill.get('pl', 0))
                print(f"💵 Realized P/L: ${realized_pl:.2f}")
            elif 'shortOrderFillTransaction' in result:
                fill = result['shortOrderFillTransaction']
                realized_pl = float(fill.get('pl', 0))
                print(f"💵 Realized P/L: ${realized_pl:.2f}")
        else:
            print(f"\n❌ Failed to close position")

    except Exception as e:
        print(f"\n❌ Error closing position: {e}")

    print("\n" + "=" * 60)


def main():
    """Main entry point"""
    # Parse command line arguments
    account, instrument, timeframe, catch_up, close_position = parse_arguments()

    # Set the active account BEFORE any API calls
    try:
        OANDAConfig.set_account(account)
        print(f"\n✓ Using account: {account} ({OANDAConfig.account_id})")
    except ValueError as e:
        print(f"\n❌ Error: {e}")
        return

    # Handle close-position mode (no confirmation needed - immediate action)
    if close_position:
        close_position_immediately(account, instrument)
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
    bot = MarketAwareTradingBot(instrument, timeframe, account, catch_up=catch_up)

    print(f"\n📊 Starting market-aware bot...")
    print(f"Account: {account}")
    print(f"Instrument: {instrument}")
    print(f"Trading Timeframe: {timeframe}")
    print(f"Market Trend Timeframe: {bot.market_timeframe}")
    print(f"CSV Log: {bot.csv_filename}")
    print(f"Config File: {bot.config_file}")
    print("\nPress Ctrl+C to stop\n")

    bot.run()


if __name__ == "__main__":
    main()