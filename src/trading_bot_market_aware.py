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
from datetime import datetime
from threading import Lock
import pandas as pd

from .config import OANDAConfig, TradingConfig
from .oanda_client import OANDAClient
from .indicators import calculate_pp_supertrend, get_current_signal
from .risk_manager import RiskManager


class TradeTracker:
    """Track P&L high/low for open trades"""
    def __init__(self):
        self.highest_pl = None
        self.lowest_pl = None
        self.entry_price = None
        self.position_side = None
        self.units = None
        
    def update_pl(self, current_price):
        """Update highest/lowest P&L based on current price"""
        if self.entry_price is None or self.units is None:
            return
            
        # Calculate current P&L
        if self.position_side == 'LONG':
            current_pl = (current_price - self.entry_price) * abs(self.units)
        else:  # SHORT
            current_pl = (self.entry_price - current_price) * abs(self.units)
        
        # Update highest/lowest
        if self.highest_pl is None or current_pl > self.highest_pl:
            self.highest_pl = current_pl
        if self.lowest_pl is None or current_pl < self.lowest_pl:
            self.lowest_pl = current_pl
    
    def reset(self):
        """Reset tracker for new trade"""
        self.highest_pl = None
        self.lowest_pl = None
        self.entry_price = None
        self.position_side = None
        self.units = None


class CSVLogger:
    """Thread-safe CSV logger for trade results"""

    def __init__(self, csv_filename):
        self.csv_filename = csv_filename
        self.lock = Lock()
        self.fieldnames = ['tradeID', 'market', 'action', 'pp_sign', 'pp_sign_time', 'order_time', 
                          'close_time', 'duration(m)', 'open_position', 'entry_price', 'stop_loss', 
                          'highest_pl', 'lowest_pl', 'realized_pl', 'accountBalance']

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

    def __init__(self, instrument, timeframe, account='account1'):
        """
        Initialize bot with specific configuration
        
        Args:
            instrument: Trading pair (e.g., 'EUR_USD')
            timeframe: '5m' or '15m'
            account: Account name for output directory and config (e.g., 'account1')
        """
        # Store configuration
        self.instrument = instrument
        self.timeframe = timeframe
        self.account = account

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

        # Initialize components
        self.client = OANDAClient()
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

        # Track unique trade IDs
        self.trade_id_counter = 0

        # Track last signal candle timestamp to prevent duplicate trades
        self.last_signal_candle_time = None
        
        # Market trend tracking
        self.last_market_check = None
        self.market_check_interval = 180  # Check market every 3 minutes
        self.current_market_signal = 'NEUTRAL'

        self.logger.info("=" * 80)
        self.logger.info(f"Market-Aware Trading Bot Initialized")
        self.logger.info("=" * 80)
        self.logger.info(f"Account: {OANDAConfig.account_id}")
        self.logger.info(f"Mode: {'PRACTICE' if OANDAConfig.is_practice else 'LIVE'}")
        self.logger.info(f"Instrument: {self.instrument}")
        self.logger.info(f"Trading Timeframe: {self.timeframe} ({self.granularity})")
        self.logger.info(f"Market Trend Timeframe: {self.market_timeframe} ({self.market_granularity})")
        self.logger.info(f"Stop Loss Type: {self.stop_loss_type}")
        self.logger.info(f"CSV Log: {self.csv_filename}")
        self.logger.info(f"Check Interval: {TradingConfig.check_interval} seconds")
        self.logger.info(f"Risk/Reward Config: {self.risk_reward_config}")
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
            signal_info = get_current_signal(df_with_indicators)
            
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
        signal_info = get_current_signal(df_with_indicators)

        # Get the timestamp of the last candle
        candle_timestamp = df_with_indicators.index[-1] if len(df_with_indicators) > 0 else None

        # Add candle age for debugging
        if candle_timestamp:
            from datetime import timezone
            candle_age_seconds = (pd.Timestamp.now(tz=timezone.utc) - candle_timestamp).total_seconds()
            signal_info['candle_age_seconds'] = candle_age_seconds

        return df_with_indicators, signal_info, candle_timestamp

    def calculate_stop_loss(self, signal_info, signal_type):
        """Calculate stop loss based on configured strategy with spread adjustment"""
        # Calculate base stop loss
        base_stop_loss = None

        if self.stop_loss_type == 'supertrend':
            # SuperTrend strategy: Stop exactly at SuperTrend line
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
            spread = self.client.get_current_spread(self.instrument)

            if spread:
                # Convert buffer from pips to price (1 pip = 0.0001 for most pairs)
                buffer_price = self.spread_buffer_pips * 0.0001
                spread_adjustment = (spread / 2.0) + buffer_price

                if signal_type == 'SELL':  # SHORT position
                    adjusted_stop_loss = base_stop_loss + spread_adjustment
                    self.logger.info(f"  Stop Loss Adjustment (SHORT): {base_stop_loss:.5f} → {adjusted_stop_loss:.5f} (spread/2 + {self.spread_buffer_pips} pips buffer)")
                else:  # BUY / LONG position
                    adjusted_stop_loss = base_stop_loss - spread_adjustment
                    self.logger.info(f"  Stop Loss Adjustment (LONG): {base_stop_loss:.5f} → {adjusted_stop_loss:.5f} (spread/2 + {self.spread_buffer_pips} pips buffer)")

                return adjusted_stop_loss
            else:
                self.logger.warning("  Unable to fetch spread - using unadjusted stop loss")

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

    def execute_trade(self, action, signal_info, account_summary):
        """Execute trade based on action and log to CSV"""
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

                    # Calculate duration in minutes
                    duration_minutes = 'N/A'
                    if self.current_trade_open_time:
                        duration_seconds = (close_time - self.current_trade_open_time).total_seconds()
                        duration_minutes = int(duration_seconds / 60)
                    
                    csv_data = {
                        'tradeID': self.current_trade_id if self.current_trade_id else self.trade_id_counter,
                        'market': self.current_market_trend.lower() if self.current_market_trend else 'neutral',
                        'action': 'CLOSE',
                        'pp_sign': current_position['side'],
                        'pp_sign_time': self.current_trade_open_time.strftime('%Y-%m-%d %H:%M:%S') if self.current_trade_open_time else 'N/A',
                        'order_time': self.current_trade_open_time.strftime('%Y-%m-%d %H:%M:%S') if self.current_trade_open_time else 'N/A',
                        'close_time': close_time.strftime('%Y-%m-%d %H:%M:%S'),
                        'duration(m)': duration_minutes,
                        'open_position': f"{self.instrument} {current_position['side']} {position_size:,.0f} units",
                        'entry_price': f"{self.current_entry_price:.5f}" if self.current_entry_price else 'N/A',
                        'stop_loss': f"{self.current_stop_loss_price:.5f}" if self.current_stop_loss_price else 'N/A',
                        'highest_pl': f"+${self.trade_tracker.highest_pl:.2f}" if self.trade_tracker.highest_pl and self.trade_tracker.highest_pl > 0 else 'N/A',
                        'lowest_pl': f"-${abs(self.trade_tracker.lowest_pl):.2f}" if self.trade_tracker.lowest_pl and self.trade_tracker.lowest_pl < 0 else 'N/A',
                        'realized_pl': f"+${profit:.2f}" if profit >= 0 else f"-${abs(profit):.2f}",
                        'accountBalance': f"${float(account_summary['balance']):,.2f}"
                    }
                    self.csv_logger.log_trade(csv_data)

                    self.logger.info(f"📊 Profit/Loss: ${profit:.2f}")

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

                # Reset signal tracking so next signal can be acted upon
                self.last_signal_candle_time = None
            else:
                self.logger.error("❌ Failed to close position")

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
            
            # Calculate take profit based on market trend and position type
            risk_reward_ratio = self.get_risk_reward_ratio(market_trend, position_type)
            take_profit = None
            if stop_loss:
                take_profit = self.calculate_take_profit(current_price, stop_loss, position_type, risk_reward_ratio)

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

                    # Store trade ID
                    if 'tradeOpened' in fill:
                        self.current_trade_id = fill['tradeOpened']['tradeID']

                    # Store stop loss info
                    if 'stopLossOrderTransaction' in result:
                        sl_order = result['stopLossOrderTransaction']
                        self.current_stop_loss_order_id = sl_order['id']
                        self.current_stop_loss_price = float(sl_order['price'])
                        self.current_position_side = position_type
                    
                    # Store take profit info
                    if 'takeProfitOrderTransaction' in result:
                        tp_order = result['takeProfitOrderTransaction']
                        self.current_take_profit_price = float(tp_order['price'])

                    # Initialize trade tracker
                    self.trade_tracker.entry_price = actual_price
                    self.trade_tracker.position_side = position_type
                    self.trade_tracker.units = abs(units)

                    # Log to CSV (initial entry)
                    csv_data = {
                        'tradeID': self.current_trade_id,
                        'market': market_trend.lower() if market_trend else 'neutral',
                        'action': 'NEW_ORDER',
                        'pp_sign': position_type,
                        'pp_sign_time': self.current_trade_open_time.strftime('%Y-%m-%d %H:%M:%S'),
                        'order_time': self.current_trade_open_time.strftime('%Y-%m-%d %H:%M:%S'),
                        'close_time': 'N/A',
                        'duration(m)': 'N/A',
                        'open_position': f"{self.instrument} {position_type} {abs(units):,.0f} units",
                        'entry_price': f"{actual_price:.5f}",
                        'stop_loss': f"{stop_loss:.5f}" if stop_loss else 'N/A',
                        'highest_pl': 'N/A',
                        'lowest_pl': 'N/A',
                        'realized_pl': 'N/A',
                        'accountBalance': f"${float(account_summary['balance']):,.2f}"
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
                    self.logger.info("📍 Position closed externally (stop loss or take profit)")
                    
                    # Log the close to CSV
                    close_time = datetime.now()
                    
                    # Try to determine what closed the position
                    stop_loss_hit = 'UNKNOWN'
                    take_profit_hit = 'UNKNOWN'
                    profit = 0.0
                    close_price = self.current_stop_loss_price  # Default to stop loss price
                    
                    try:
                        transactions = self.client.get_transaction_history(count=50)
                        if transactions:
                            for txn in reversed(transactions):
                                if (txn.get('type') == 'ORDER_FILL' and
                                    txn.get('instrument') == self.instrument):
                                    close_price = float(txn.get('price', 0))
                                    profit = float(txn.get('pl', 0))
                                    reason = txn.get('reason', '')
                                    stop_loss_hit = 'TRUE' if 'STOP_LOSS' in reason else 'FALSE'
                                    take_profit_hit = 'TRUE' if 'TAKE_PROFIT' in reason else 'FALSE'
                                    self.logger.info(f"   Found close transaction: Price={close_price:.5f}, P/L=${profit:.2f}, Reason={reason}")
                                    break
                    except Exception as e:
                        self.logger.error(f"   Failed to fetch transaction history: {e}")
                    
                    # Calculate duration
                    duration = 'N/A'
                    if self.current_trade_open_time:
                        duration_seconds = (close_time - self.current_trade_open_time).total_seconds()
                        duration_minutes = int(duration_seconds / 60)
                        duration = f"{duration_minutes}m"
                    
                    # Calculate actual risk/reward
                    risk_reward_actual = 'N/A'
                    if self.current_stop_loss_price and self.current_entry_price and self.current_position_size:
                        risk = abs(self.current_entry_price - self.current_stop_loss_price) * self.current_position_size
                        if risk > 0:
                            risk_reward_actual = f"{(profit / risk):.2f}"
                    
                    # Calculate duration in minutes
                    duration_minutes = 'N/A'
                    if self.current_trade_open_time:
                        duration_seconds = (close_time - self.current_trade_open_time).total_seconds()
                        duration_minutes = int(duration_seconds / 60)
                    
                    # Log to CSV
                    csv_data = {
                        'tradeID': self.current_trade_id if self.current_trade_id else self.trade_id_counter,
                        'market': self.current_market_trend.lower() if self.current_market_trend else 'neutral',
                        'action': 'CLOSE',
                        'pp_sign': self.current_position_side if self.current_position_side else 'N/A',
                        'pp_sign_time': self.current_trade_open_time.strftime('%Y-%m-%d %H:%M:%S') if self.current_trade_open_time else 'N/A',
                        'order_time': self.current_trade_open_time.strftime('%Y-%m-%d %H:%M:%S') if self.current_trade_open_time else 'N/A',
                        'close_time': close_time.strftime('%Y-%m-%d %H:%M:%S'),
                        'duration(m)': duration_minutes,
                        'open_position': f"{self.instrument} {self.current_position_side} {self.current_position_size:,.0f} units" if self.current_position_side and self.current_position_size else 'N/A',
                        'entry_price': f"{self.current_entry_price:.5f}" if self.current_entry_price else 'N/A',
                        'stop_loss': f"{self.current_stop_loss_price:.5f}" if self.current_stop_loss_price else 'N/A',
                        'highest_pl': f"+${self.trade_tracker.highest_pl:.2f}" if self.trade_tracker.highest_pl and self.trade_tracker.highest_pl > 0 else 'N/A',
                        'lowest_pl': f"-${abs(self.trade_tracker.lowest_pl):.2f}" if self.trade_tracker.lowest_pl and self.trade_tracker.lowest_pl < 0 else 'N/A',
                        'realized_pl': f"+${profit:.2f}" if profit >= 0 else f"-${abs(profit):.2f}",
                        'accountBalance': f"${float(account_summary['balance']):,.2f}"
                    }
                    self.csv_logger.log_trade(csv_data)
                    self.logger.info(f"   💾 Logged external close to CSV: P/L=${profit:.2f}")
                    
                    # Reset trade tracker
                    self.trade_tracker.reset()
                    
                    # Clear all tracking
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
                    self.last_signal_candle_time = None

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
                        
                        # Try to get stop loss price from order
                        if trade.get('stop_loss_order'):
                            self.current_stop_loss_price = float(trade['stop_loss_order'].get('price', 0))
                        
                        if self.highest_price_during_trade is None and self.current_entry_price:
                            self.highest_price_during_trade = float(self.current_entry_price)
                        if self.lowest_price_during_trade is None and self.current_entry_price:
                            self.lowest_price_during_trade = float(self.current_entry_price)
                        
                        self.logger.info(f"📌 Recovered tracking: Trade {self.current_trade_id}")
                        if self.current_entry_price:
                            self.logger.info(f"   Entry: {self.current_entry_price:.5f}")
                        if self.current_stop_loss_price:
                            self.logger.info(f"   Stop Loss: {self.current_stop_loss_price:.5f}")

            # Log status
            self.logger.info("-" * 80)
            self.logger.info(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            self.logger.info(f"OVERALL Market: {self.current_market_signal} | Balance: ${account_summary['balance']:.2f} | "
                           f"P/L: ${account_summary['unrealized_pl']:.2f}")

            if current_position and current_position['units'] != 0:
                position_units = abs(current_position['units'])
                position_lots = position_units / 100000
                risk_used = self.current_risk_amount if self.current_risk_amount else 100
                self.logger.info(f"Position: {current_position['side']} {position_units:,} units ({position_lots:.3f} lots) [${risk_used:.0f} risk]")
                
                # Calculate and display risk/reward information
                if self.current_entry_price and self.current_stop_loss_price and self.current_position_size:
                    # Use the actual risk amount that was used for this trade
                    # This could be different based on market trend and position direction
                    risk_amount = self.current_risk_amount if self.current_risk_amount else 100
                    
                    # Get expected R:R ratio based on market and position
                    position_type = 'LONG' if current_position['side'] == 'LONG' else 'SHORT'
                    expected_rr = self.get_risk_reward_ratio(self.current_market_signal, position_type)
                    
                    # Calculate current profit in dollars (P/L from position)
                    current_profit = float(current_position['unrealized_pl'])
                    
                    current_rr = current_profit / risk_amount if risk_amount > 0 else 0
                    
                    self.logger.info(f"Expected Take Profit R:R: {expected_rr:.1f} | Current R:R Reached: {current_rr:.2f}")
                    
                    # Update P&L tracking with current price
                    if signal_info.get('close_price'):
                        current_price = signal_info['close_price']
                        self.trade_tracker.update_pl(current_price)
                    
                    # Show if approaching take profit
                    if current_rr >= expected_rr * 0.8:  # Within 80% of target
                        self.logger.info(f"⚠️  Approaching Take Profit Target ({current_rr:.2f}/{expected_rr:.1f})")

            self.logger.info(f"Signal: {signal_info['signal']} | Price: {signal_info['price']:.5f}")
            
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

            # Determine if we should trade
            should_trade, action, next_action = self.risk_manager.should_trade(
                signal_info,
                current_position,
                candle_timestamp,
                self.last_signal_candle_time,
                market_trend=self.current_market_signal,
                config=self.config
            )

            if should_trade:
                self.logger.info(f"🎯 TRADE SIGNAL: {action}")
                self.execute_trade(action, signal_info, account_summary)

                # If closing position with intent to open opposite, do it immediately
                if action == 'CLOSE' and next_action in ['OPEN_LONG', 'OPEN_SHORT']:
                    self.logger.info(f"➡️  Immediately opening opposite position: {next_action}")
                    time.sleep(1)
                    account_summary = self.client.get_account_summary()
                    current_position = self.client.get_position(self.instrument)
                    self.execute_trade(next_action, signal_info, account_summary)

                # Update last signal candle time after ALL actions complete
                self.last_signal_candle_time = candle_timestamp
            else:
                if current_position and current_position['units'] != 0:
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
            
                    # Check if NEW_ORDER entry already exists in CSV
                    if not self.csv_logger.trade_exists(trade_id, 'NEW_ORDER'):
                        # Log the existing trade as NEW_ORDER (external)
                        # Handle different possible key names for units
                        current_units = None
                        for key in ['currentUnits', 'current_units', 'units', 'initialUnits']:
                            if key in trade:
                                current_units = float(trade[key])
                                break
                        
                        if current_units is None:
                            self.logger.error(f"❌ Unable to find units for trade {trade_id}. Available keys: {list(trade.keys())}")
                            continue
                        
                        position_side = 'LONG' if current_units > 0 else 'SHORT'
                        units = abs(current_units)
                        
                        csv_data = {
                            'tradeID': trade_id,
                            'market': 'NEUTRAL',  # Unknown at restart
                            'action': 'NEW_ORDER',
                            'pp_sign': position_side,
                            'pp_sign_time': trade['openTime'][:19].replace('T', ' '),
                            'order_time': trade['openTime'][:19].replace('T', ' '),
                            'close_time': 'N/A',
                            'duration(m)': 'N/A',
                            'open_position': f"{trade['instrument']} {position_side} {units:,.0f} units",
                            'entry_price': f"{float(trade['price']):.5f}",
                            'stop_loss': f"{float(trade.get('stopLossOrder', {}).get('price', 0)):.5f}" if trade.get('stopLossOrder') else 'N/A',
                            'highest_pl': 'N/A',
                            'lowest_pl': 'N/A',
                            'realized_pl': 'N/A',
                            'accountBalance': f"${float(account_summary['balance']):,.2f}"
                        }
                        self.csv_logger.log_trade(csv_data)
                        self.logger.info(f"📊 Logged existing trade {trade_id} as NEW_ORDER")
            
                    # Initialize tracking for existing trade
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

    def run(self):
        """Main bot loop"""
        self.is_running = True
        self.logger.info("🚀 Market-aware trading bot started")
        
        # Check for existing trades on startup
        self.check_existing_trades()

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
  python trading_bot_market_aware.py at=account1 fr=GBP_USD tf=5m
        """
    )

    parser.add_argument('account', type=str, help='Account: at=account1, at=account2, etc.')
    parser.add_argument('instrument', type=str, help='Trading instrument: fr=EUR_USD, fr=GBP_USD, etc.')
    parser.add_argument('timeframe', type=str, help='Timeframe: tf=5m or tf=15m')

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

    return account, instrument, timeframe


def main():
    """Main entry point"""
    # Parse command line arguments
    account, instrument, timeframe = parse_arguments()

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
    bot = MarketAwareTradingBot(instrument, timeframe, account)

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