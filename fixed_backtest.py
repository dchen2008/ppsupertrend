#!/usr/bin/env python3
"""
FIXED Backtest Engine - EXACT Live Bot Logic Match
This version applies the exact same filtering and logic as the live bot
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
import yaml
import copy
import argparse
import random

# Add src directory to path
sys.path.append('src')
sys.path.append('backtest/src')

from src.indicators import calculate_pp_supertrend, get_current_signal
from src.config import TradingConfig, OANDAConfig
from src.risk_manager import RiskManager
from backtest.src.data_downloader import BacktestDataDownloader

class FixedBacktestEngine:
    """Fixed backtest engine that EXACTLY replicates live bot logic with proper filtering"""
    
    def __init__(self, instrument, timeframe, account='account1', initial_balance=None):
        self.instrument = instrument
        self.timeframe = timeframe
        self.account = account
        
        # Map timeframe to granularity
        self.granularity = 'M5' if timeframe == '5m' else 'M15'
        
        # Load configuration (exactly like live bot)
        self.config = self.load_account_config()
        
        # Get initial balance from config if not provided
        if initial_balance is None:
            initial_balance = self.config.get('backtest', {}).get('initial_balance', 10000)
        self.initial_balance = initial_balance
        self.current_balance = initial_balance
        
        # Market trend settings
        self.market_timeframe = self.config.get('market', {}).get('timeframe', 'H3')
        self.check_interval = self.config.get('check_interval', 60)
        
        # Initialize components exactly like live bot
        self.risk_manager = RiskManager()
        
        # Trading state (exactly like live bot)
        self.current_trade = None
        self.trades = []
        self.trade_id_counter = 0
        self.last_signal_time = None
        self.current_market_trend = 'BEAR'  # Default to BEAR since PP SuperTrend is never NEUTRAL
        
        # Signal analysis data for CSV output
        self.signal_analysis = []
        
        # Track current open position (simulating live bot position tracking)
        self.current_position = None  # {'signal': 'BUY'/'SELL', 'entry_time': time, 'entry_price': price, 'position_size': size, 'risk_amount': amount, 'stop_loss': price, 'take_profit': price}
        
        # Setup logging
        self.logger = logging.getLogger(f"fixed_backtest_{instrument}_{timeframe}")
        self.logger.setLevel(logging.INFO)
    
    def _close_position_at_market(self, close_time, close_price, close_reason):
        """Close current position at market price and record result"""
        if self.current_position is None:
            return
            
        position = self.current_position
        
        # Calculate P&L based on position direction
        if position['signal'] == 'BUY':  # LONG position
            pnl = (close_price - position['entry_price']) * position['position_size']
        else:  # SHORT position
            pnl = (position['entry_price'] - close_price) * position['position_size']
        
        # Update balance
        self.current_balance += pnl
        
        # Log closure
        self.logger.info(f"   💼 Position CLOSED: {pnl:+.2f} P&L (Reason: {close_reason})")
        
        # Update the existing record in signal_analysis
        # Find the last trade record that matches this position
        for i in range(len(self.signal_analysis) - 1, -1, -1):
            trade = self.signal_analysis[i]
            if (trade['signal'] == position['signal'] and 
                trade['entry_price'] == f"{position['entry_price']:.5f}"):
                
                # Update with market close results
                trade['actual_profit'] = f"${pnl:.2f}"
                trade['position_status'] = 'MARKET_CLOSE'
                trade['take_profit_hit'] = 'NO'
                trade['stop_loss_hit'] = 'NO'
                break
        
        # Clear current position
        self.current_position = None
        
    def load_account_config(self):
        """Load configuration exactly like live bot"""
        # Default config
        default_config = {
            'check_interval': 60,
            'market': {'indicator': 'ppsupertrend', 'timeframe': 'H3'},
            'stoploss': {'type': 'PPSuperTrend', 'spread_buffer_pips': 3},
            'position_sizing': {'use_dynamic': True, 'disable_opposite_trade': True},
            'risk_reward': {
                'bear_market': {'short_rr': 1.2, 'long_rr': 0.6},
                'bull_market': {'short_rr': 0.6, 'long_rr': 1.2}
            }
        }
        
        # Load default YAML config
        default_config_file = "src/config.yaml"
        if os.path.exists(default_config_file):
            with open(default_config_file, 'r') as f:
                loaded_default = yaml.safe_load(f) or {}
                default_config.update(loaded_default)
        
        # Start with default
        config = copy.deepcopy(default_config)
        
        # Load account-specific overrides
        account_config_file = f"{self.account}/config.yaml"
        if os.path.exists(account_config_file):
            with open(account_config_file, 'r') as f:
                account_config = yaml.safe_load(f) or {}
            self._deep_merge(config, account_config)
        
        return config
        
    def _deep_merge(self, base_dict, override_dict):
        """Deep merge override_dict into base_dict"""
        for key, value in override_dict.items():
            if key in base_dict and isinstance(base_dict[key], dict) and isinstance(value, dict):
                self._deep_merge(base_dict[key], value)
            else:
                base_dict[key] = value
    
    def check_market_trend(self, market_data, current_time):
        """Check market trend exactly like live bot"""
        try:
            # Get market data up to current time (exactly like live bot)
            market_slice = market_data[market_data.index <= current_time].copy()
            
            # Need minimum data for reliable trend (reduced for H3)
            if len(market_slice) < 15:
                return 'BEAR'  # Default to BEAR when insufficient data
            
            # Calculate PP SuperTrend (exactly like live bot)
            candles_to_use = min(len(market_slice), 100)
            df_with_indicators = calculate_pp_supertrend(
                market_slice.tail(candles_to_use),
                pivot_period=TradingConfig.pivot_period,
                atr_factor=TradingConfig.atr_factor,
                atr_period=TradingConfig.atr_period
            )
            
            if df_with_indicators is None or len(df_with_indicators) == 0:
                return 'BEAR'  # Default to BEAR when calculation fails
            
            # Get current signal (exactly like live bot)
            signal_info = get_current_signal(df_with_indicators)
            signal = signal_info['signal']
            
            # DEBUG: Log 3H signal details (disabled - use only for debugging)
            # if current_time.strftime('%Y-%m-%d') in ['2026-01-06', '2026-01-07', '2026-01-08', '2026-01-09']:
            #     self.logger.info(f"🔍 3H Signal Debug at {current_time}: signal={signal}, price={signal_info.get('price', 'N/A'):.5f}, trend={df_with_indicators.iloc[-1]['trend']}")
            
            # Map signal to trend (exactly like live bot - PP SuperTrend never NEUTRAL)
            if signal in ['BUY', 'HOLD_LONG']:
                return 'BULL'
            elif signal in ['SELL', 'HOLD_SHORT']:
                return 'BEAR'
            else:
                # This should never happen with fixed PP SuperTrend
                self.logger.warning(f"⚠️  UNEXPECTED backtest signal: {signal} - defaulting to BEAR")
                return 'BEAR'
                
        except Exception as e:
            self.logger.warning(f"Error checking market trend: {e}")
            return 'BEAR'  # Default to BEAR on error
    
    def run_fixed_backtest(self, trading_data, market_data, start_date=None, end_date=None):
        """Run fixed backtest with EXACT live bot logic and filtering"""
        self.logger.info(f"🎯 Starting FIXED backtest (exact live bot logic)")
        self.logger.info(f"Period: {start_date} to {end_date}")
        
        # Filter data to date range
        # CRITICAL: Only filter trading data to date range, preserve full market history for 3H calculations
        if start_date:
            trading_data = trading_data[trading_data.index >= start_date]
            # DO NOT filter market_data - need historical 3H data for PP SuperTrend
        if end_date:
            trading_data = trading_data[trading_data.index <= end_date]
            # DO NOT filter market_data - need historical 3H data for PP SuperTrend
        
        self.logger.info(f"Filtered to {len(trading_data)} trading candles")
        
        # Calculate indicators on full dataset (exactly like live bot)
        trading_data_with_indicators = calculate_pp_supertrend(
            trading_data,
            pivot_period=TradingConfig.pivot_period,
            atr_factor=TradingConfig.atr_factor,
            atr_period=TradingConfig.atr_period
        )
        
        if trading_data_with_indicators is None:
            raise ValueError("Failed to calculate indicators")
        
        # Process each candle exactly like live bot (chronological order)
        prev_signal = None
        prev_actual_signal = None  # Track only BUY/SELL signals, not HOLD states
        processed = 0
        
        for current_time, row in trading_data_with_indicators.iterrows():
            processed += 1
            
            # Update market trend periodically (exactly like live bot)
            if processed % 12 == 0:  # Every 12 candles (3 hours for M15, 1 hour for M5)
                prev_trend = self.current_market_trend
                self.current_market_trend = self.check_market_trend(market_data, current_time)
                if prev_trend != self.current_market_trend:
                    self.logger.info(f"📊 3H Market Trend UPDATE at {current_time}: {prev_trend} → {self.current_market_trend}")
            
            # Skip until we have enough 3H data (exactly like live bot)
            market_slice = market_data[market_data.index <= current_time]
            if len(market_slice) < 15:
                continue
            
            # Get signal for current candle (exactly like live bot)
            data_slice = trading_data_with_indicators.loc[:current_time].copy()
            signal_info = get_current_signal(data_slice)
            current_signal = signal_info['signal']
            
            # Extract actual signal (BUY/SELL) from current signal (which could be HOLD_LONG/HOLD_SHORT)
            if current_signal == 'BUY':
                current_actual_signal = 'BUY'
            elif current_signal == 'SELL':
                current_actual_signal = 'SELL'
            else:
                current_actual_signal = prev_actual_signal  # Keep previous actual signal
            
            # Check for actual signal change (not HOLD state changes)
            if current_actual_signal != prev_actual_signal and current_actual_signal in ['BUY', 'SELL']:
                
                # Use current 3H market trend (not 5m signal!)
                current_market_trend = self.current_market_trend
                
                self.logger.info(f"\n📍 Signal at {current_time}: {current_actual_signal}")
                self.logger.info(f"   Market Trend: {current_market_trend}")
                self.logger.info(f"   Entry Price: {signal_info['price']:.5f}")
                
                # STEP 1: Close existing position (if any) when new signal occurs
                if self.current_position is not None:
                    self.logger.info(f"   🔄 Closing existing {self.current_position['signal']} position")
                    self._close_position_at_market(current_time, signal_info['price'], "NEW_SIGNAL")
                
                # Apply EXACT live bot logic using RiskManager
                position_type = 'LONG' if current_actual_signal == 'BUY' else 'SHORT'
                
                # Convert to position format for RiskManager (exactly like live bot)
                current_position = None  # No existing position after closure
                
                # Use RiskManager to check if trade should execute (EXACT live bot logic)
                should_trade, action, next_action = self.risk_manager.should_trade(
                    signal_info,
                    current_position,
                    current_time,
                    self.last_signal_time,
                    market_trend=current_market_trend,
                    config=self.config
                )
                
                if should_trade and action in ['OPEN_LONG', 'OPEN_SHORT']:
                    self.logger.info(f"   ✅ Trade ALLOWED: {action}")
                    
                    # Calculate position size (exactly like live bot)
                    position_size, risk_amount = self.risk_manager.calculate_position_size(
                        self.current_balance, signal_info,
                        market_trend=current_market_trend,
                        position_type=position_type,
                        config=self.config
                    )
                    
                    # Calculate stop loss with spread adjustment (exactly like live bot)
                    # Get buffer from config (default 3 pips)
                    spread_buffer_pips = self.config.get('stoploss', {}).get('spread_buffer_pips', 3)
                    
                    # Simulate spread (typical EUR/USD spread is around 1-2 pips)
                    typical_spread = 0.00015  # 1.5 pips typical spread
                    buffer_price = spread_buffer_pips * 0.0001  # Convert pips to price
                    spread_adjustment = (typical_spread / 2.0) + buffer_price
                    
                    if position_type == 'LONG':
                        stop_loss = signal_info['supertrend'] - spread_adjustment
                    else:
                        stop_loss = signal_info['supertrend'] + spread_adjustment
                    
                    # Get take profit ratio from config (exactly like live bot)
                    if current_market_trend == 'BEAR' and position_type == 'SHORT':
                        take_profit_ratio = self.config.get('risk_reward', {}).get('bear_market', {}).get('short_rr', 1.2)
                    elif current_market_trend == 'BULL' and position_type == 'LONG':
                        take_profit_ratio = self.config.get('risk_reward', {}).get('bull_market', {}).get('long_rr', 1.2)
                    elif current_market_trend == 'BEAR' and position_type == 'LONG':
                        take_profit_ratio = self.config.get('risk_reward', {}).get('bear_market', {}).get('long_rr', 0.6)
                    elif current_market_trend == 'BULL' and position_type == 'SHORT':
                        take_profit_ratio = self.config.get('risk_reward', {}).get('bull_market', {}).get('short_rr', 0.6)
                    else:
                        take_profit_ratio = 1.0
                    
                    # Calculate take profit price (exactly like live bot)
                    risk = abs(signal_info['price'] - stop_loss)
                    reward = risk * take_profit_ratio
                    
                    if position_type == 'LONG':
                        take_profit_price = signal_info['price'] + reward
                    else:
                        take_profit_price = signal_info['price'] - reward
                    
                    # Find next signal to calculate potential profit
                    next_signal_time = None
                    for future_time, future_row in trading_data_with_indicators.loc[current_time:].iterrows():
                        if future_time <= current_time:
                            continue
                        future_data_slice = trading_data_with_indicators.loc[:future_time].copy()
                        future_signal_info = get_current_signal(future_data_slice)
                        if future_signal_info['signal'] != current_signal and future_signal_info['signal'] in ['BUY', 'SELL']:
                            next_signal_time = future_time
                            break
                    
                    if next_signal_time is None:
                        next_signal_time = trading_data_with_indicators.index[-1]
                    
                    # Get price data between signals
                    mask = (trading_data_with_indicators.index > current_time) & (trading_data_with_indicators.index <= next_signal_time)
                    price_data = trading_data_with_indicators[mask]
                    
                    # Calculate potential profits
                    if len(price_data) > 0:
                        highest_price = price_data['high'].max()
                        lowest_price = price_data['low'].min()
                        
                        if position_type == 'LONG':
                            max_profit_price = highest_price
                            min_loss_price = lowest_price
                            unrealized_pl_max = (max_profit_price - signal_info['price']) * position_size
                            max_profit_ratio = (max_profit_price - signal_info['price']) / risk if risk > 0 else 0
                            
                            # Check if take profit or stop loss would be hit
                            take_profit_hit = highest_price >= take_profit_price
                            stop_loss_hit = lowest_price <= stop_loss
                            
                            if take_profit_hit:
                                actual_profit = reward * position_size
                            elif stop_loss_hit:
                                actual_profit = -risk_amount  # Full loss
                            else:
                                actual_profit = 0  # Position still open, no realized P&L
                            
                        else:  # SHORT
                            max_profit_price = lowest_price
                            min_loss_price = highest_price
                            unrealized_pl_max = (signal_info['price'] - max_profit_price) * position_size
                            max_profit_ratio = (signal_info['price'] - max_profit_price) / risk if risk > 0 else 0
                            
                            # Check if take profit or stop loss would be hit
                            take_profit_hit = lowest_price <= take_profit_price
                            stop_loss_hit = highest_price >= stop_loss
                            
                            if take_profit_hit:
                                actual_profit = reward * position_size
                            elif stop_loss_hit:
                                actual_profit = -risk_amount  # Full loss
                            else:
                                actual_profit = 0  # Position still open, no realized P&L
                        
                        # Log the result (exactly like live bot)
                        if take_profit_hit:
                            self.logger.info(f"   💰 Take Profit HIT: ${actual_profit:.2f} profit")
                            self.current_balance += actual_profit
                        elif 'stop_loss_hit' in locals() and stop_loss_hit:
                            self.logger.info(f"   ❌ Stop Loss HIT: ${actual_profit:.2f} loss")
                            self.current_balance += actual_profit  # actual_profit is negative
                        else:
                            self.logger.info(f"   📊 Max Potential: ${unrealized_pl_max:.2f} (ratio: {max_profit_ratio:.2f}:1)")
                            self.logger.info(f"   ⏸️  Position OPEN: TP={take_profit_price:.5f}, SL={stop_loss:.5f}, Max={max_profit_price:.5f}")
                        
                        # Store for CSV (convert to UTC-8 timezone)
                        from datetime import timezone, timedelta
                        utc_minus_8 = current_time.tz_convert(timezone(timedelta(hours=-8)))
                        
                        # Convert position size to lots for readability
                        position_lots = position_size / 100000
                        
                        # Calculate stop loss distances in pips
                        # Original distance (without buffer)
                        original_stop_distance_pips = abs(signal_info['price'] - signal_info['supertrend']) * 10000
                        # Adjusted distance (with buffer)
                        adjusted_stop_distance_pips = abs(signal_info['price'] - stop_loss) * 10000
                        
                        # Determine position status
                        if take_profit_hit:
                            position_status = 'TP_HIT'
                        elif 'stop_loss_hit' in locals() and stop_loss_hit:
                            position_status = 'SL_HIT'
                        else:
                            position_status = 'OPEN'
                        
                        self.signal_analysis.append({
                            'market': current_market_trend,  # 3H PP market trend 
                            'signal': current_actual_signal,       # 5m/15m PP signal
                            'time': utc_minus_8.strftime('%b %d, %I:%M%p'),
                            'entry_price': f"{signal_info['price']:.5f}",
                            'stop_loss_price': f"{stop_loss:.5f}",
                            'take_profit_price': f"{take_profit_price:.5f}",
                            'position_lots': f"{position_lots:.2f}",
                            'risk_amount': f"${risk_amount:.0f}",
                            'original_stop_pips': f"{original_stop_distance_pips:.1f}",
                            'buffer_pips': f"{spread_buffer_pips}",
                            'adjusted_stop_pips': f"{adjusted_stop_distance_pips:.1f}",
                            'take_profit_ratio': f"{take_profit_ratio:.1f}:1",
                            'highest_ratio': f"{max_profit_ratio:.2f}:1",
                            'potential_profit': f"${unrealized_pl_max:.2f}",
                            'actual_profit': f"${actual_profit:.2f}",
                            'position_status': position_status,
                            'take_profit_hit': 'YES' if take_profit_hit else 'NO',
                            'stop_loss_hit': 'YES' if ('stop_loss_hit' in locals() and stop_loss_hit) else 'NO'
                        })
                        
                        # STEP 2: Track position if it's still open after analysis
                        if position_status == 'OPEN':
                            self.current_position = {
                                'signal': current_actual_signal,
                                'entry_time': current_time, 
                                'entry_price': signal_info['price'],
                                'position_size': position_size,
                                'risk_amount': risk_amount,
                                'stop_loss': stop_loss,
                                'take_profit': take_profit_price
                            }
                            self.logger.info(f"   📊 Position OPENED: {position_type} at {signal_info['price']:.5f}")
                        else:
                            # Position already closed (TP or SL hit), update balance
                            self.current_balance += actual_profit
                        
                        self.last_signal_time = current_time
                
                else:
                    self.logger.info(f"   🚫 Trade FILTERED: {current_actual_signal} blocked by disable_opposite_trade in {current_market_trend} market")
                
                prev_signal = current_signal
                prev_actual_signal = current_actual_signal  # Update the actual signal tracker
        
        # STEP 3: Close any remaining open position at end of backtest period
        if self.current_position is not None:
            final_time = trading_data_with_indicators.index[-1]
            final_price = trading_data_with_indicators.iloc[-1]['close']
            self.logger.info(f"\n⏰ End of backtest period - closing remaining position")
            self._close_position_at_market(final_time, final_price, "END_OF_PERIOD")
        
        return self.generate_fixed_results()
    
    def generate_fixed_results(self):
        """Generate fixed results with accurate filtering"""
        total_trades = len(self.signal_analysis)
        profitable_trades = len([s for s in self.signal_analysis if s['take_profit_hit'] == 'YES'])
        
        total_profit = sum(
            float(s['actual_profit'].replace('$', '')) 
            for s in self.signal_analysis if s['take_profit_hit'] == 'YES'
        )
        
        win_rate = (profitable_trades / total_trades * 100) if total_trades > 0 else 0
        
        # Calculate potential profit if using optimal ratios
        total_potential = sum(
            float(s['potential_profit'].replace('$', '')) 
            for s in self.signal_analysis
        )
        
        return {
            'backtest_info': {
                'instrument': self.instrument,
                'timeframe': self.timeframe,
                'account': self.account,
                'initial_balance': self.initial_balance,
                'final_balance': self.current_balance
            },
            'performance': {
                'total_trades': total_trades,
                'winning_trades': profitable_trades,
                'win_rate': win_rate,
                'total_return': total_profit,
                'total_return_pct': (total_profit / self.initial_balance) * 100,
                'total_potential': total_potential
            },
            'signal_analysis': self.signal_analysis
        }
    
    def save_signal_analysis_csv(self, results, output_dir, time_range_str):
        """Save signal analysis to CSV"""
        if not results['signal_analysis']:
            return None
        
        # Create DataFrame
        df = pd.DataFrame(results['signal_analysis'])
        
        # Reorder columns for CSV (more readable format with new enhancements)
        csv_columns = [
            'market', 'signal', 'time', 'entry_price', 'stop_loss_price', 'take_profit_price',
            'position_lots', 'risk_amount', 'original_stop_pips', 'buffer_pips', 'adjusted_stop_pips',
            'take_profit_ratio', 'highest_ratio', 'potential_profit', 'actual_profit',
            'position_status', 'take_profit_hit', 'stop_loss_hit'
        ]
        
        df_csv = df[csv_columns].copy()
        
        # Generate filename with new format: EUR_USD_5m_account1_sign_ratio_profit_Jan-4_Jan-9_xxx.csv
        random_num = random.randint(100, 999)  # 3-digit number
        
        # Convert time range to readable format
        # time_range_str format: "01042026160000_01092026160000"
        start_str = time_range_str.split('_')[0]  # "01042026160000"
        end_str = time_range_str.split('_')[1]    # "01092026160000"
        
        # Extract month and day for readable format
        start_month = int(start_str[0:2])  # 01 -> 1
        start_day = int(start_str[2:4])    # 04 -> 4
        end_month = int(end_str[0:2])      # 01 -> 1  
        end_day = int(end_str[2:4])        # 09 -> 9
        
        # Create month names
        month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", 
                      "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        start_month_name = month_names[start_month - 1]
        end_month_name = month_names[end_month - 1]
        
        readable_range = f"{start_month_name}-{start_day}_{end_month_name}-{end_day}"
        filename = f"{self.instrument}_{self.timeframe}_{self.account}_sign_ratio_profit_{readable_range}_{random_num}.csv"
        filepath = os.path.join(output_dir, filename)
        
        # Save CSV
        df_csv.to_csv(filepath, index=False)
        
        return filename

def parse_time_range(time_range_str):
    """Parse time range string like '01/04/2026 16:00:00,01/09/2026 16:00:00'"""
    try:
        start_str, end_str = time_range_str.split(',')
        start_date = pd.to_datetime(start_str.strip(), format='%m/%d/%Y %H:%M:%S')
        end_date = pd.to_datetime(end_str.strip(), format='%m/%d/%Y %H:%M:%S')
        
        # Make timezone aware (assume UTC)
        start_date = start_date.tz_localize('UTC')
        end_date = end_date.tz_localize('UTC')
        
        return start_date, end_date
    except Exception as e:
        raise ValueError(f"Invalid time range format. Use: MM/DD/YYYY HH:MM:SS,MM/DD/YYYY HH:MM:SS")

def main():
    """Main fixed backtest function"""
    parser = argparse.ArgumentParser(description='FIXED backtest with EXACT live bot logic')
    parser.add_argument('account', help='Account (format: at=account1)')
    parser.add_argument('instrument', help='Instrument (format: fr=EUR_USD)')
    parser.add_argument('timeframe', help='Timeframe (format: tf=5m)')
    parser.add_argument('time_range', help='Time range (format: bt=MM/DD/YYYY HH:MM:SS,MM/DD/YYYY HH:MM:SS)')
    parser.add_argument('--balance', type=float, default=None, help='Initial balance (defaults to config value)')
    parser.add_argument('--output-dir', default='backtest/results', help='Output directory')
    
    args = parser.parse_args()
    
    # Parse arguments
    try:
        account = args.account.split('=')[1]
        instrument = args.instrument.split('=')[1] 
        timeframe = args.timeframe.split('=')[1]
        time_range_str = args.time_range.split('=')[1]
        
        start_date, end_date = parse_time_range(time_range_str)
        
    except Exception as e:
        print(f"Error parsing arguments: {e}")
        return 1
    
    # Setup logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    print(f"\n🎯 FIXED BACKTEST - EXACT LIVE BOT LOGIC")
    print(f"Account: {account}")
    print(f"Instrument: {instrument}")
    print(f"Timeframe: {timeframe}")
    print(f"Period: {start_date} to {end_date}")
    print(f"Initial Balance: ${args.balance:,.2f}")
    
    try:
        # Download data
        print("\n📥 Downloading data...")
        downloader = BacktestDataDownloader(account=account)
        
        granularity = 'M5' if timeframe == '5m' else 'M15'
        data = downloader.get_data_for_backtest(
            instrument=instrument,
            trading_timeframe=granularity,
            market_timeframe='H3',
            days_back=30  # Get enough historical data
        )
        
        # Run fixed backtest
        print("\n🔧 Running FIXED backtest with exact live bot logic...")
        engine = FixedBacktestEngine(
            instrument=instrument,
            timeframe=timeframe,
            account=account,
            initial_balance=args.balance
        )
        
        results = engine.run_fixed_backtest(
            data[granularity], data['H3'], start_date, end_date
        )
        
        # Create output directory
        os.makedirs(args.output_dir, exist_ok=True)
        
        # Save CSV
        time_range_csv = time_range_str.replace('/', '').replace(' ', '').replace(':', '').replace(',', '_')
        csv_filename = engine.save_signal_analysis_csv(results, args.output_dir, time_range_csv)
        
        # Print results
        print(f"\n📊 FIXED BACKTEST RESULTS:")
        print(f"Total Allowed Trades: {results['performance']['total_trades']}")
        print(f"Profitable Trades (TP Hit): {results['performance']['winning_trades']}")
        print(f"Win Rate (TP Hit Rate): {results['performance']['win_rate']:.1f}%")
        print(f"Actual Profit (TP Hits): ${results['performance']['total_return']:.2f}")
        print(f"Max Potential Profit: ${results['performance']['total_potential']:.2f}")
        print(f"Return %: {results['performance']['total_return_pct']:+.2f}%")
        print(f"Final Balance: ${results['backtest_info']['final_balance']:,.2f}")
        
        # Show breakdown by signal type
        signal_df = pd.DataFrame(results['signal_analysis'])
        if len(signal_df) > 0:
            print(f"\n📈 TRADE BREAKDOWN:")
            for signal_type in ['BUY', 'SELL']:
                trades = signal_df[signal_df['signal'] == signal_type]
                if len(trades) > 0:
                    count = len(trades)
                    profitable = len(trades[trades['take_profit_hit'] == 'YES'])
                    print(f"  {signal_type} trades: {count} total, {profitable} profitable ({profitable/count*100:.1f}%)")
        
        if csv_filename:
            print(f"\n📄 Signal analysis saved to: {csv_filename}")
            print(f"Path: {args.output_dir}/{csv_filename}")
        
        return 0
        
    except Exception as e:
        print(f"❌ Fixed backtest failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())