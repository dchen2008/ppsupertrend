"""
Backtest Engine for Market-Aware Trading Bot
Replicates the exact logic of trading_bot_market_aware.py for historical simulation
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
import yaml
import copy

# Add parent directory to path to import from src
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from src.indicators import calculate_pp_supertrend, get_current_signal
from src.config import TradingConfig, OANDAConfig
from src.risk_manager import RiskManager
from backtest.src.data_downloader import BacktestDataDownloader


class BacktestTrade:
    """Represents a single trade in the backtest"""
    
    def __init__(self, trade_id, instrument, position_type, units, entry_price, 
                 entry_time, stop_loss, take_profit=None, market_trend='NEUTRAL'):
        self.trade_id = trade_id
        self.instrument = instrument
        self.position_type = position_type  # 'LONG' or 'SHORT'
        self.units = abs(units)
        self.entry_price = entry_price
        self.entry_time = entry_time
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.market_trend = market_trend
        
        # Trade tracking
        self.exit_price = None
        self.exit_time = None
        self.exit_reason = None  # 'STOP_LOSS', 'TAKE_PROFIT', 'SIGNAL_REVERSAL'
        self.realized_pl = 0.0
        self.highest_pl = 0.0
        self.lowest_pl = 0.0
        self.risk_reward_target = None
        self.risk_reward_actual = None
        
        # Duration tracking
        self.duration_minutes = 0
        
    def update_pl(self, current_price):
        """Update P&L tracking"""
        if self.position_type == 'LONG':
            current_pl = (current_price - self.entry_price) * self.units
        else:  # SHORT
            current_pl = (self.entry_price - current_price) * self.units
        
        # Update highest/lowest
        if current_pl > self.highest_pl:
            self.highest_pl = current_pl
        if current_pl < self.lowest_pl:
            self.lowest_pl = current_pl
    
    def close_trade(self, exit_price, exit_time, exit_reason):
        """Close the trade and calculate final P&L"""
        self.exit_price = exit_price
        self.exit_time = exit_time
        self.exit_reason = exit_reason
        
        # Calculate final P&L
        if self.position_type == 'LONG':
            self.realized_pl = (exit_price - self.entry_price) * self.units
        else:  # SHORT
            self.realized_pl = (self.entry_price - exit_price) * self.units
        
        # Calculate duration
        duration_delta = exit_time - self.entry_time
        self.duration_minutes = int(duration_delta.total_seconds() / 60)
        
        return self.realized_pl


class BacktestEngine:
    """
    Backtest engine that replicates MarketAwareTradingBot logic
    """
    
    def __init__(self, instrument, timeframe, account='account1', 
                 initial_balance=10000, spread=0.00020):
        """
        Initialize backtest engine
        
        Args:
            instrument: Trading pair (e.g., 'EUR_USD')
            timeframe: Trading timeframe ('5m' or '15m')
            account: Account name for configuration
            initial_balance: Starting balance for backtest
            spread: Typical spread for the instrument
        """
        self.instrument = instrument
        self.timeframe = timeframe
        self.account = account
        self.initial_balance = initial_balance
        self.current_balance = initial_balance
        self.spread = spread
        
        # Map timeframe to granularity
        self.granularity = 'M5' if timeframe == '5m' else 'M15'
        
        # Load configuration (same as live bot)
        self.config = self.load_account_config()
        
        # Market trend settings
        self.market_timeframe = self.config.get('market', {}).get('timeframe', 'H3')
        self.market_granularity = self.convert_timeframe_to_granularity(self.market_timeframe)
        
        # Check interval for position monitoring (from config)
        self.check_interval = self.config.get('check_interval', 60)  # seconds
        
        # Risk/reward settings
        self.risk_reward_config = self.config.get('risk_reward', {})
        
        # Stop loss type
        self.stop_loss_type = self.config.get('stoploss', {}).get('type', 'PPSuperTrend').lower()
        if self.stop_loss_type == 'ppsupertrend':
            self.stop_loss_type = 'supertrend'
        
        # Trading state
        self.current_trade = None
        self.trades = []
        self.trade_id_counter = 0
        self.last_signal_time = None
        self.current_market_trend = 'NEUTRAL'
        
        # Risk manager (same as live bot)
        self.risk_manager = RiskManager()
        
        # Setup logging
        self.logger = logging.getLogger(f"backtest_{instrument}_{timeframe}")
        self.logger.setLevel(logging.INFO)
        
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
    
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
        # Load default configuration
        default_config = {
            'check_interval': 60,
            'market': {'indicator': 'ppsupertrend', 'timeframe': 'H3'},
            'stoploss': {'type': 'PPSuperTrend'},
            'risk_reward': {
                'bear_market': {'short_rr': 1.2, 'long_rr': 0.6},
                'bull_market': {'short_rr': 0.6, 'long_rr': 1.2}
            }
        }
        
        default_config_file = "src/config.yaml"
        if os.path.exists(default_config_file):
            with open(default_config_file, 'r') as f:
                loaded_default = yaml.safe_load(f) or {}
                default_config.update(loaded_default)
        
        # Start with default config
        config = copy.deepcopy(default_config)
        
        # Check for account-specific config
        account_config_file = f"{self.account}/config.yaml"
        if os.path.exists(account_config_file):
            with open(account_config_file, 'r') as f:
                account_config = yaml.safe_load(f) or {}
            
            # Deep merge account config into default config
            self._deep_merge(config, account_config)
        
        return config
    
    def _deep_merge(self, base_dict, override_dict):
        """Deep merge override_dict into base_dict"""
        for key, value in override_dict.items():
            if key in base_dict and isinstance(base_dict[key], dict) and isinstance(value, dict):
                self._deep_merge(base_dict[key], value)
            else:
                base_dict[key] = value
    
    def get_risk_reward_ratio(self, market_trend, position_type):
        """Get risk/reward ratio based on market trend and position type"""
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
            return 1.0
    
    def calculate_take_profit(self, entry_price, stop_loss_price, position_type, risk_reward_ratio):
        """Calculate take profit price based on risk/reward ratio"""
        risk = abs(entry_price - stop_loss_price)
        reward = risk * risk_reward_ratio
        
        if position_type == 'LONG':
            return entry_price + reward
        else:  # SHORT
            return entry_price - reward
    
    def calculate_stop_loss(self, signal_info, signal_type):
        """Calculate stop loss based on configured strategy with spread adjustment"""
        base_stop_loss = None
        
        if self.stop_loss_type == 'supertrend':
            supertrend = signal_info['supertrend']
            if supertrend is None:
                return None
            base_stop_loss = supertrend
        elif self.stop_loss_type == 'ppcenterline':
            pivot_center = signal_info.get('pivot')
            if pivot_center is None:
                return None
            base_stop_loss = pivot_center
        
        if base_stop_loss is None:
            return None
        
        # Apply spread adjustment (simulated)
        if TradingConfig.use_spread_adjustment:
            spread_adjustment = self.spread / 2.0
            
            if signal_type == 'SELL':  # SHORT position
                adjusted_stop_loss = base_stop_loss + spread_adjustment
            else:  # BUY / LONG position
                adjusted_stop_loss = base_stop_loss - spread_adjustment
            
            return adjusted_stop_loss
        
        return base_stop_loss
    
    
    def check_market_trend(self, market_data, current_time):
        """Check market trend using 3H data"""
        try:
            # Get market data up to current time
            market_slice = market_data[market_data.index <= current_time].copy()
            
            # Adjust minimum candles based on timeframe  
            min_candles = 15 if self.market_granularity == 'H3' else 50
            if len(market_slice) < min_candles:
                self.logger.warning(f"Insufficient market data: {len(market_slice)} < {min_candles} candles, returning NEUTRAL")
                return 'NEUTRAL'
            
            # Calculate PP SuperTrend on market timeframe
            # Use available candles (max 100) for calculation
            candles_to_use = min(len(market_slice), 100)
            df_with_indicators = calculate_pp_supertrend(
                market_slice.tail(candles_to_use),
                pivot_period=TradingConfig.pivot_period,
                atr_factor=TradingConfig.atr_factor,
                atr_period=TradingConfig.atr_period
            )
            
            if df_with_indicators is None or len(df_with_indicators) == 0:
                return 'NEUTRAL'
            
            # Get latest signal
            signal_info = get_current_signal(df_with_indicators)
            
            # Debug: log the actual signal
            self.logger.info(f"3H PP SuperTrend signal: {signal_info['signal']} (candles: {len(market_slice)})")
            
            # Determine market trend (PP SuperTrend returns BUY, SELL, HOLD_LONG, HOLD_SHORT)
            signal = signal_info['signal']
            if signal in ['BUY', 'HOLD_LONG']:
                return 'BULL'
            elif signal in ['SELL', 'HOLD_SHORT']:
                return 'BEAR'
            else:
                # This should not happen with PP SuperTrend
                self.logger.warning(f"Unexpected 3H signal: {signal}")
                return 'NEUTRAL'
                
        except Exception as e:
            self.logger.warning(f"Error checking market trend: {e}")
            return 'NEUTRAL'
    
    def check_trade_exit(self, current_data, current_time):
        """Check if current trade should be closed"""
        if not self.current_trade:
            return False, None, None
        
        current_price = current_data['close']
        
        # Update P&L tracking
        self.current_trade.update_pl(current_price)
        
        # Check stop loss
        if self.current_trade.position_type == 'LONG':
            if current_price <= self.current_trade.stop_loss:
                return True, self.current_trade.stop_loss, 'STOP_LOSS'
        else:  # SHORT
            if current_price >= self.current_trade.stop_loss:
                return True, self.current_trade.stop_loss, 'STOP_LOSS'
        
        # Check take profit
        if self.current_trade.take_profit:
            if self.current_trade.position_type == 'LONG':
                if current_price >= self.current_trade.take_profit:
                    return True, self.current_trade.take_profit, 'TAKE_PROFIT'
            else:  # SHORT
                if current_price <= self.current_trade.take_profit:
                    return True, self.current_trade.take_profit, 'TAKE_PROFIT'
        
        return False, None, None
    
    def check_intrabar_take_profit(self, m1_data, trade_start_time, trade_end_time):
        """
        Check for take profit hits using M1 data within the trading candle timeframe
        
        Args:
            m1_data: DataFrame with M1 data
            trade_start_time: Start time of the current trading candle
            trade_end_time: End time of the current trading candle
            
        Returns:
            tuple: (should_exit, exit_price, exit_time, exit_reason)
        """
        if not self.current_trade or not self.current_trade.take_profit:
            return False, None, None, None
        
        # Get M1 candles between trade_start_time and trade_end_time
        mask = (m1_data.index > trade_start_time) & (m1_data.index <= trade_end_time)
        intrabar_data = m1_data[mask]
        
        if len(intrabar_data) == 0:
            return False, None, None, None
        
        # Check each M1 candle at check_interval (60 seconds)
        for timestamp, row in intrabar_data.iterrows():
            # Simulate checking every check_interval seconds (60s = every minute for M1 data)
            current_price = row['close']
            
            # Update P&L tracking
            self.current_trade.update_pl(current_price)
            
            # Check stop loss first
            if self.current_trade.position_type == 'LONG':
                if current_price <= self.current_trade.stop_loss:
                    return True, self.current_trade.stop_loss, timestamp, 'STOP_LOSS'
            else:  # SHORT
                if current_price >= self.current_trade.stop_loss:
                    return True, self.current_trade.stop_loss, timestamp, 'STOP_LOSS'
            
            # Check take profit
            if self.current_trade.position_type == 'LONG':
                if current_price >= self.current_trade.take_profit:
                    return True, self.current_trade.take_profit, timestamp, 'TAKE_PROFIT'
            else:  # SHORT
                if current_price <= self.current_trade.take_profit:
                    return True, self.current_trade.take_profit, timestamp, 'TAKE_PROFIT'
        
        return False, None, None, None
    
    def should_trade(self, signal_info, current_time):
        """Determine if a trade should be executed using RiskManager (same as live bot)"""
        # Convert current trade to position format for RiskManager
        current_position = None
        if self.current_trade:
            current_position = {
                'units': self.current_trade.units if self.current_trade.position_type == 'LONG' else -self.current_trade.units,
                'side': self.current_trade.position_type
            }
        
        # Use the same RiskManager logic as the live bot
        should_trade, action, next_action = self.risk_manager.should_trade(
            signal_info,
            current_position,
            current_time,
            self.last_signal_time,
            market_trend=self.current_market_trend,
            config=self.config
        )
        
        if not should_trade:
            return False, None
        
        # Convert RiskManager actions to backtest actions
        if action == 'OPEN_LONG':
            return True, 'OPEN_LONG'
        elif action == 'OPEN_SHORT':
            return True, 'OPEN_SHORT'
        elif action == 'CLOSE':
            if next_action == 'OPEN_LONG':
                return True, 'CLOSE_AND_REVERSE_LONG'
            elif next_action == 'OPEN_SHORT':
                return True, 'CLOSE_AND_REVERSE_SHORT'
            else:
                # Just close, don't open new position (this happens with disable_opposite_trade)
                return True, 'CLOSE_ONLY'
        
        return False, None
    
    def execute_trade(self, action, signal_info, current_time, balance):
        """Execute trade action"""
        current_price = signal_info['price']
        
        if action in ['CLOSE_AND_REVERSE_LONG', 'CLOSE_AND_REVERSE_SHORT', 'CLOSE_ONLY']:
            # Close current position first
            if self.current_trade:
                close_reason = 'SIGNAL_REVERSAL' if action != 'CLOSE_ONLY' else 'OPPOSITE_TRADE_DISABLED'
                self.close_current_trade(current_price, current_time, close_reason)
            
            # Open new position only if not CLOSE_ONLY
            if action == 'CLOSE_AND_REVERSE_LONG':
                action = 'OPEN_LONG'
            elif action == 'CLOSE_AND_REVERSE_SHORT':
                action = 'OPEN_SHORT'
            elif action == 'CLOSE_ONLY':
                # Don't open new position, just return
                return
        
        if action in ['OPEN_LONG', 'OPEN_SHORT']:
            position_type = 'LONG' if action == 'OPEN_LONG' else 'SHORT'
            
            # Calculate position size using RiskManager (same as live bot)
            account_summary = {'balance': balance}
            position_size, risk_amount = self.risk_manager.calculate_position_size(
                balance, signal_info, 
                market_trend=self.current_market_trend,
                position_type=position_type,
                config=self.config
            )
            
            # Calculate stop loss
            signal_type = 'BUY' if action == 'OPEN_LONG' else 'SELL'
            stop_loss = self.calculate_stop_loss(signal_info, signal_type)
            
            if stop_loss is None:
                self.logger.warning("Cannot calculate stop loss, skipping trade")
                return
            
            # Calculate take profit
            risk_reward_ratio = self.get_risk_reward_ratio(self.current_market_trend, position_type)
            take_profit = self.calculate_take_profit(current_price, stop_loss, position_type, risk_reward_ratio)
            
            # Create new trade
            self.trade_id_counter += 1
            self.current_trade = BacktestTrade(
                trade_id=self.trade_id_counter,
                instrument=self.instrument,
                position_type=position_type,
                units=position_size,
                entry_price=current_price,
                entry_time=current_time,
                stop_loss=stop_loss,
                take_profit=take_profit,
                market_trend=self.current_market_trend
            )
            
            self.current_trade.risk_reward_target = risk_reward_ratio
            
            self.logger.info(f"OPENED {position_type} | Price: {current_price:.5f} | "
                           f"SL: {stop_loss:.5f} | TP: {take_profit:.5f} | "
                           f"Size: {position_size:,} | Market: {self.current_market_trend}")
            
            self.last_signal_time = current_time
    
    def close_current_trade(self, exit_price, exit_time, exit_reason):
        """Close the current trade"""
        if not self.current_trade:
            return
        
        realized_pl = self.current_trade.close_trade(exit_price, exit_time, exit_reason)
        
        # Update balance
        self.current_balance += realized_pl
        
        # Calculate actual risk/reward
        if self.current_trade.stop_loss:
            risk = abs(self.current_trade.entry_price - self.current_trade.stop_loss) * self.current_trade.units
            if risk > 0:
                self.current_trade.risk_reward_actual = realized_pl / risk
        
        # Store completed trade
        self.trades.append(self.current_trade)
        
        self.logger.info(f"CLOSED {self.current_trade.position_type} | "
                       f"P/L: ${realized_pl:.2f} | Reason: {exit_reason} | "
                       f"Duration: {self.current_trade.duration_minutes}m")
        
        self.current_trade = None
    
    def run_backtest(self, trading_data, market_data, m1_data=None, start_date=None, end_date=None):
        """
        Run the backtest on historical data
        
        Args:
            trading_data: DataFrame with trading timeframe data
            market_data: DataFrame with market timeframe data
            m1_data: DataFrame with M1 data for intrabar monitoring (optional)
            start_date: Start date for backtest (optional)
            end_date: End date for backtest (optional)
            
        Returns:
            dict: Backtest results
        """
        self.logger.info(f"Starting backtest for {self.instrument} {self.timeframe}")
        self.logger.info(f"Trading data: {len(trading_data)} candles")
        self.logger.info(f"Market data: {len(market_data)} candles")
        if m1_data is not None:
            self.logger.info(f"M1 data: {len(m1_data)} candles (for intrabar monitoring)")
        else:
            self.logger.info("M1 data: Not provided (standard backtest mode)")
        
        # Filter data by date range if specified
        if start_date:
            trading_data = trading_data[trading_data.index >= start_date]
            market_data = market_data[market_data.index >= start_date]
        if end_date:
            trading_data = trading_data[trading_data.index <= end_date]
            market_data = market_data[market_data.index <= end_date]
        
        self.logger.info(f"Backtest period: {trading_data.index[0]} to {trading_data.index[-1]}")
        
        # Calculate indicators on full datasets
        self.logger.info("Calculating indicators...")
        trading_data_with_indicators = calculate_pp_supertrend(
            trading_data,
            pivot_period=TradingConfig.pivot_period,
            atr_factor=TradingConfig.atr_factor,
            atr_period=TradingConfig.atr_period
        )
        
        if trading_data_with_indicators is None:
            raise ValueError("Failed to calculate indicators on trading data")
        
        # Process each candle
        total_candles = len(trading_data_with_indicators)
        processed = 0
        
        for current_time, row in trading_data_with_indicators.iterrows():
            processed += 1
            
            if processed % 1000 == 0:
                progress = (processed / total_candles) * 100
                self.logger.info(f"Progress: {progress:.1f}% ({processed}/{total_candles})")
            
            # Update market trend periodically (every 180 minutes in live bot)
            if processed % 12 == 0:  # Every 12 candles (3 hours for M15, 1 hour for M5)
                self.current_market_trend = self.check_market_trend(market_data, current_time)
            
            # Skip trading until we have enough 3H data for reliable market trend detection
            market_slice = market_data[market_data.index <= current_time]
            if len(market_slice) < 15:
                continue  # Skip this candle and continue to next one
            
            # Check if current trade should be closed
            if self.current_trade:
                should_close, exit_price, exit_reason = self.check_trade_exit(row, current_time)
                if should_close:
                    self.close_current_trade(exit_price, current_time, exit_reason)
            
            # Check for intrabar take profit hits using M1 data (if available and trade is open)
            if self.current_trade and m1_data is not None:
                # Calculate the previous candle time
                if processed > 1:
                    prev_candle_time = trading_data_with_indicators.index[processed - 2]
                    should_close_intrabar, exit_price_intrabar, exit_time_intrabar, exit_reason_intrabar = self.check_intrabar_take_profit(
                        m1_data, prev_candle_time, current_time)
                    
                    if should_close_intrabar:
                        self.close_current_trade(exit_price_intrabar, exit_time_intrabar, exit_reason_intrabar)
            
            # Get signal for current candle
            # Create a slice up to current time for signal calculation
            data_slice = trading_data_with_indicators.loc[:current_time].copy()
            signal_info = get_current_signal(data_slice)
            
            # Check if we should trade
            should_trade, action = self.should_trade(signal_info, current_time)
            
            if should_trade:
                self.execute_trade(action, signal_info, current_time, self.current_balance)
        
        # Close any remaining open trade
        if self.current_trade:
            final_price = trading_data_with_indicators.iloc[-1]['close']
            final_time = trading_data_with_indicators.index[-1]
            self.close_current_trade(final_price, final_time, 'BACKTEST_END')
        
        self.logger.info(f"Backtest completed. Total trades: {len(self.trades)}")
        
        return self.generate_results()
    
    def generate_results(self):
        """Generate comprehensive backtest results"""
        if not self.trades:
            return {
                'total_trades': 0,
                'final_balance': self.current_balance,
                'total_return': 0,
                'total_return_pct': 0
            }
        
        # Basic metrics
        total_trades = len(self.trades)
        winning_trades = [t for t in self.trades if t.realized_pl > 0]
        losing_trades = [t for t in self.trades if t.realized_pl < 0]
        
        total_profit = sum(t.realized_pl for t in self.trades)
        total_return_pct = (total_profit / self.initial_balance) * 100
        
        win_rate = (len(winning_trades) / total_trades) * 100 if total_trades > 0 else 0
        
        avg_win = sum(t.realized_pl for t in winning_trades) / len(winning_trades) if winning_trades else 0
        avg_loss = sum(t.realized_pl for t in losing_trades) / len(losing_trades) if losing_trades else 0
        
        # Risk metrics
        profit_factor = abs(sum(t.realized_pl for t in winning_trades) / sum(t.realized_pl for t in losing_trades)) if losing_trades else float('inf')
        
        # Duration analysis
        avg_duration = sum(t.duration_minutes for t in self.trades) / total_trades if total_trades > 0 else 0
        
        # Market trend analysis
        bull_trades = [t for t in self.trades if t.market_trend == 'BULL']
        bear_trades = [t for t in self.trades if t.market_trend == 'BEAR']
        neutral_trades = [t for t in self.trades if t.market_trend == 'NEUTRAL']
        
        results = {
            'backtest_info': {
                'instrument': self.instrument,
                'timeframe': self.timeframe,
                'account': self.account,
                'initial_balance': self.initial_balance,
                'final_balance': self.current_balance
            },
            'performance': {
                'total_trades': total_trades,
                'winning_trades': len(winning_trades),
                'losing_trades': len(losing_trades),
                'win_rate': win_rate,
                'total_return': total_profit,
                'total_return_pct': total_return_pct,
                'profit_factor': profit_factor,
                'avg_win': avg_win,
                'avg_loss': avg_loss,
                'avg_duration_minutes': avg_duration
            },
            'market_analysis': {
                'bull_market_trades': len(bull_trades),
                'bear_market_trades': len(bear_trades),
                'neutral_market_trades': len(neutral_trades),
                'bull_profit': sum(t.realized_pl for t in bull_trades),
                'bear_profit': sum(t.realized_pl for t in bear_trades),
                'neutral_profit': sum(t.realized_pl for t in neutral_trades)
            },
            'trades': self.trades
        }
        
        return results


def main():
    """CLI for backtest engine"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Run backtest with market-aware logic')
    parser.add_argument('--instrument', default='EUR_USD', help='Trading instrument')
    parser.add_argument('--timeframe', default='5m', help='Trading timeframe (5m or 15m)')
    parser.add_argument('--account', default='account1', help='Account configuration')
    parser.add_argument('--days', type=int, default=30, help='Days to backtest')
    parser.add_argument('--balance', type=float, default=10000, help='Initial balance')
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Download data
    print("Downloading historical data...")
    downloader = BacktestDataDownloader(account=args.account)
    
    granularity = 'M5' if args.timeframe == '5m' else 'M15'
    data = downloader.get_data_for_backtest(
        instrument=args.instrument,
        trading_timeframe=granularity,
        market_timeframe='H3',
        days_back=args.days
    )
    
    if granularity not in data or 'H3' not in data:
        print("Failed to download required data")
        return
    
    # Run backtest
    print("Running backtest...")
    engine = BacktestEngine(
        instrument=args.instrument,
        timeframe=args.timeframe,
        account=args.account,
        initial_balance=args.balance
    )
    
    results = engine.run_backtest(data[granularity], data['H3'])
    
    # Print results
    print("\n" + "="*60)
    print("BACKTEST RESULTS")
    print("="*60)
    print(f"Instrument: {results['backtest_info']['instrument']}")
    print(f"Period: {args.days} days")
    print(f"Total Trades: {results['performance']['total_trades']}")
    print(f"Win Rate: {results['performance']['win_rate']:.1f}%")
    print(f"Total Return: ${results['performance']['total_return']:.2f}")
    print(f"Return %: {results['performance']['total_return_pct']:.2f}%")
    print(f"Profit Factor: {results['performance']['profit_factor']:.2f}")
    print(f"Final Balance: ${results['backtest_info']['final_balance']:.2f}")


if __name__ == "__main__":
    main()