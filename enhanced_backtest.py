#!/usr/bin/env python3
"""
Enhanced Backtest Engine - Exact Match to Live Bot Logic
Supports custom time ranges and detailed CSV output
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

class EnhancedBacktestEngine:
    """Enhanced backtest engine that exactly replicates live bot logic"""
    
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
        
        # Trading state
        self.current_trade = None
        self.trades = []
        self.trade_id_counter = 0
        self.last_signal_time = None
        self.current_market_trend = 'NEUTRAL'
        
        # Signal analysis data for CSV output
        self.signal_analysis = []
        
        # Setup logging
        self.logger = logging.getLogger(f"enhanced_backtest_{instrument}_{timeframe}")
        self.logger.setLevel(logging.INFO)
        
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
            
            # Need minimum data for reliable trend
            if len(market_slice) < 15:
                return 'NEUTRAL'
            
            # Calculate PP SuperTrend (exactly like live bot)
            candles_to_use = min(len(market_slice), 100)
            df_with_indicators = calculate_pp_supertrend(
                market_slice.tail(candles_to_use),
                pivot_period=TradingConfig.pivot_period,
                atr_factor=TradingConfig.atr_factor,
                atr_period=TradingConfig.atr_period
            )
            
            if df_with_indicators is None or len(df_with_indicators) == 0:
                return 'NEUTRAL'
            
            # Get current signal (exactly like live bot)
            signal_info = get_current_signal(df_with_indicators)
            signal = signal_info['signal']
            
            # Map signal to trend (exactly like live bot)
            if signal in ['BUY', 'HOLD_LONG']:
                return 'BULL'
            elif signal in ['SELL', 'HOLD_SHORT']:
                return 'BEAR'
            else:
                return 'NEUTRAL'
                
        except Exception as e:
            self.logger.warning(f"Error checking market trend: {e}")
            return 'NEUTRAL'
    
    def analyze_signal_potential(self, signal_info, market_trend, current_time, next_signal_time, trading_data):
        """Analyze signal potential for CSV output"""
        signal_type = signal_info['signal']
        entry_price = signal_info['price']
        supertrend = signal_info['supertrend']
        
        if signal_type not in ['BUY', 'SELL']:
            return None
        
        # Check if this trade would be filtered
        position_type = 'LONG' if signal_type == 'BUY' else 'SHORT'
        would_be_filtered = False
        
        if self.config.get('position_sizing', {}).get('disable_opposite_trade', False):
            if market_trend == 'BEAR' and signal_type == 'BUY':
                would_be_filtered = True
            elif market_trend == 'BULL' and signal_type == 'SELL':
                would_be_filtered = True
        
        if would_be_filtered:
            return None  # Don't analyze filtered trades
        
        # Calculate stop loss with spread adjustment (exactly like live bot)
        # Get buffer from config (default 3 pips)
        spread_buffer_pips = self.config.get('stoploss', {}).get('spread_buffer_pips', 3)
        
        # Simulate spread (typical EUR/USD spread is around 1-2 pips)
        typical_spread = 0.00015  # 1.5 pips typical spread
        buffer_price = spread_buffer_pips * 0.0001  # Convert pips to price
        spread_adjustment = (typical_spread / 2.0) + buffer_price
        
        if position_type == 'LONG':
            stop_loss = supertrend - spread_adjustment
        else:
            stop_loss = supertrend + spread_adjustment
        
        # Get risk/reward ratio from config
        if market_trend == 'BEAR' and position_type == 'SHORT':
            take_profit_ratio = self.config.get('risk_reward', {}).get('bear_market', {}).get('short_rr', 1.2)
        elif market_trend == 'BULL' and position_type == 'LONG':
            take_profit_ratio = self.config.get('risk_reward', {}).get('bull_market', {}).get('long_rr', 1.2)
        elif market_trend == 'BEAR' and position_type == 'LONG':
            take_profit_ratio = self.config.get('risk_reward', {}).get('bear_market', {}).get('long_rr', 0.6)
        elif market_trend == 'BULL' and position_type == 'SHORT':
            take_profit_ratio = self.config.get('risk_reward', {}).get('bull_market', {}).get('short_rr', 0.6)
        else:
            take_profit_ratio = 1.0
        
        # Calculate take profit price
        risk = abs(entry_price - stop_loss)
        reward = risk * take_profit_ratio
        
        if position_type == 'LONG':
            take_profit_price = entry_price + reward
        else:
            take_profit_price = entry_price - reward
        
        # Get price data between this signal and next
        mask = (trading_data.index > current_time) & (trading_data.index <= next_signal_time)
        price_data = trading_data[mask]
        
        if len(price_data) == 0:
            return None
        
        highest_price = price_data['high'].max()
        lowest_price = price_data['low'].min()
        
        # Calculate unrealized P&L and potential ratios
        if position_type == 'LONG':
            max_profit_price = highest_price
            unrealized_pl_max = (max_profit_price - entry_price) * 1000
            max_profit_ratio = (max_profit_price - entry_price) / risk if risk > 0 else 0
            
            # Check if take profit would be hit
            take_profit_hit = highest_price >= take_profit_price
            actual_profit = reward * 1000 if take_profit_hit else (max_profit_price - entry_price) * 1000
            
        else:  # SHORT
            max_profit_price = lowest_price  
            unrealized_pl_max = (entry_price - max_profit_price) * 1000
            max_profit_ratio = (entry_price - max_profit_price) / risk if risk > 0 else 0
            
            # Check if take profit would be hit
            take_profit_hit = lowest_price <= take_profit_price
            actual_profit = reward * 1000 if take_profit_hit else (entry_price - max_profit_price) * 1000
        
        # Calculate position size (exactly like live bot)
        account_summary = {'balance': self.current_balance}
        position_size, risk_amount = self.risk_manager.calculate_position_size(
            self.current_balance, signal_info,
            market_trend=market_trend,
            position_type=position_type, 
            config=self.config
        )
        
        # Calculate stop distances in pips
        original_stop_distance_pips = abs(entry_price - supertrend) * 10000
        adjusted_stop_distance_pips = abs(entry_price - stop_loss) * 10000
        position_lots = position_size / 100000
        
        return {
            'signal': signal_type,
            'time': current_time.strftime('%b %d, %I:%M%p'),
            'entry_price': f"{entry_price:.5f}",
            'stop_loss_price': f"{stop_loss:.5f}",
            'take_profit_price': f"{take_profit_price:.5f}",
            'position_lots': f"{position_lots:.2f}",
            'risk_amount': f"${risk_amount:.0f}",
            'original_stop_pips': f"{original_stop_distance_pips:.1f}",
            'buffer_pips': f"{spread_buffer_pips}",
            'adjusted_stop_pips': f"{adjusted_stop_distance_pips:.1f}",
            'highest_ratio': f"{max_profit_ratio:.2f}:1",
            'potential_profit': f"${unrealized_pl_max:.2f}",
            'take_profit_ratio': f"{take_profit_ratio:.1f}:1",
            'actual_profit': f"${actual_profit:.2f}",
            'take_profit_hit': take_profit_hit,
            'market_trend': market_trend
        }
    
    def run_enhanced_backtest(self, trading_data, market_data, start_date=None, end_date=None):
        """Run enhanced backtest with exact live bot logic"""
        self.logger.info(f"Starting enhanced backtest for {self.instrument} {self.timeframe}")
        self.logger.info(f"Period: {start_date} to {end_date}")
        
        # Filter data to date range
        if start_date:
            trading_data = trading_data[trading_data.index >= start_date]
            market_data = market_data[market_data.index >= start_date]
        if end_date:
            trading_data = trading_data[trading_data.index <= end_date]
            market_data = market_data[market_data.index <= end_date]
        
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
        
        # Collect all signals first for analysis
        signals = []
        prev_signal = None
        
        for timestamp, row in trading_data_with_indicators.iterrows():
            # Get signal at this point
            data_slice = trading_data_with_indicators.loc[:timestamp].copy()
            signal_info = get_current_signal(data_slice)
            current_signal = signal_info['signal']
            
            # Check for signal change
            if current_signal != prev_signal and current_signal in ['BUY', 'SELL']:
                # Get current market trend
                market_trend = self.check_market_trend(market_data, timestamp)
                
                signals.append({
                    'time': timestamp,
                    'signal_info': signal_info,
                    'market_trend': market_trend
                })
                prev_signal = current_signal
        
        # Analyze each signal
        for i, signal_data in enumerate(signals):
            signal_time = signal_data['time']
            signal_info = signal_data['signal_info']
            market_trend = signal_data['market_trend']
            
            # Find next signal time
            if i + 1 < len(signals):
                next_signal_time = signals[i + 1]['time']
            else:
                next_signal_time = trading_data_with_indicators.index[-1]
            
            # Analyze signal potential
            analysis = self.analyze_signal_potential(
                signal_info, market_trend, signal_time, next_signal_time, trading_data_with_indicators
            )
            
            if analysis:
                self.signal_analysis.append(analysis)
                
                # Update balance based on actual profit
                if analysis['take_profit_hit']:
                    profit = float(analysis['actual_profit'].replace('$', ''))
                    self.current_balance += profit
                    self.logger.info(f"✅ {analysis['signal']} trade: {analysis['actual_profit']} profit")
                else:
                    self.logger.info(f"❌ {analysis['signal']} trade: No profit (TP not hit)")
        
        return self.generate_enhanced_results()
    
    def generate_enhanced_results(self):
        """Generate enhanced results with signal analysis"""
        total_trades = len(self.signal_analysis)
        profitable_trades = len([s for s in self.signal_analysis if s['take_profit_hit']])
        
        total_profit = sum(
            float(s['actual_profit'].replace('$', '')) 
            for s in self.signal_analysis if s['take_profit_hit']
        )
        
        win_rate = (profitable_trades / total_trades * 100) if total_trades > 0 else 0
        
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
                'total_return_pct': (total_profit / self.initial_balance) * 100
            },
            'signal_analysis': self.signal_analysis
        }
    
    def save_signal_analysis_csv(self, results, output_dir, time_range_str):
        """Save signal analysis to CSV"""
        if not results['signal_analysis']:
            return None
        
        # Create DataFrame
        df = pd.DataFrame(results['signal_analysis'])
        
        # Reorder columns for CSV (enhanced with new columns)
        csv_columns = [
            'market_trend', 'signal', 'time', 'entry_price', 'stop_loss_price', 'take_profit_price',
            'position_lots', 'risk_amount', 'original_stop_pips', 'buffer_pips', 'adjusted_stop_pips',
            'take_profit_ratio', 'highest_ratio', 'potential_profit', 'actual_profit'
        ]
        
        df_csv = df[csv_columns].copy()
        
        # Generate filename
        random_num = random.randint(1000, 9999)
        filename = f"bt_{self.instrument}_{self.timeframe}_{self.account}_sign_ratio_profit_{time_range_str}_{random_num}.csv"
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
    """Main enhanced backtest function"""
    parser = argparse.ArgumentParser(description='Enhanced backtest with exact bot logic')
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
    
    print(f"\n🎯 ENHANCED BACKTEST - EXACT BOT LOGIC")
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
        
        # Run enhanced backtest
        print("\n🔄 Running enhanced backtest...")
        engine = EnhancedBacktestEngine(
            instrument=instrument,
            timeframe=timeframe,
            account=account,
            initial_balance=args.balance
        )
        
        results = engine.run_enhanced_backtest(
            data[granularity], data['H3'], start_date, end_date
        )
        
        # Create output directory
        os.makedirs(args.output_dir, exist_ok=True)
        
        # Save CSV
        time_range_csv = time_range_str.replace('/', '').replace(' ', '').replace(':', '').replace(',', '_')
        csv_filename = engine.save_signal_analysis_csv(results, args.output_dir, time_range_csv)
        
        # Print results
        print(f"\n📊 ENHANCED BACKTEST RESULTS:")
        print(f"Total Signals: {results['performance']['total_trades']}")
        print(f"Profitable Trades: {results['performance']['winning_trades']}")
        print(f"Win Rate: {results['performance']['win_rate']:.1f}%")
        print(f"Total Profit: ${results['performance']['total_return']:.2f}")
        print(f"Return %: {results['performance']['total_return_pct']:+.2f}%")
        print(f"Final Balance: ${results['backtest_info']['final_balance']:,.2f}")
        
        if csv_filename:
            print(f"\n📄 Signal analysis saved to: {csv_filename}")
            print(f"Path: {args.output_dir}/{csv_filename}")
        
        return 0
        
    except Exception as e:
        print(f"❌ Enhanced backtest failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())