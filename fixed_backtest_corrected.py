#!/usr/bin/env python3
"""
Fixed backtest engine with corrected signal detection to eliminate phantom trades
"""

import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import logging
import random
import pytz

# Add project paths
sys.path.append('src')
sys.path.append('backtest/src')

from config import OANDAConfig, TradingConfig
from data_downloader import BacktestDataDownloader
from indicators import calculate_pp_supertrend, get_current_signal

# Import RiskManager directly to avoid relative import issues
sys.path.insert(0, 'src')
from risk_manager import RiskManager
sys.path.pop(0)

class CorrectedBacktestEngine:
    """Backtest engine with fixed signal detection"""
    
    def __init__(self, account, instrument, timeframe, initial_balance=None):
        self.account = account
        self.instrument = instrument
        self.timeframe = timeframe
        
        # Set up account
        OANDAConfig.set_account(account)
        
        # Initialize risk manager
        self.risk_manager = RiskManager()
        
        # Load config
        self.config = self.load_account_config(account)
        
        # Get initial balance from config if not provided
        if initial_balance is None:
            initial_balance = self.config.get('backtest', {}).get('initial_balance', 10000)
        self.initial_balance = initial_balance
        self.current_balance = initial_balance
        
        # Tracking variables
        self.current_position = None
        self.current_market_trend = 'BEAR'
        self.signal_analysis = []
        self.last_signal_time = None
        self.last_actual_signal = None  # Track last BUY/SELL signal
        
        # Set up logging
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
    
    def load_account_config(self, account):
        """Load account-specific configuration"""
        import yaml
        
        # Load default config
        with open('src/config.yaml', 'r') as f:
            config = yaml.safe_load(f)
        
        # Try to load account-specific overrides
        account_config_path = f'{account}/config.yaml'
        if os.path.exists(account_config_path):
            with open(account_config_path, 'r') as f:
                account_config = yaml.safe_load(f)
                # Merge configs (account overrides default)
                self._merge_configs(config, account_config)
        
        return config
    
    def _merge_configs(self, base, override):
        """Recursively merge override config into base config"""
        for key, value in override.items():
            if isinstance(value, dict) and key in base:
                self._merge_configs(base[key], value)
            else:
                base[key] = value
    
    def check_market_trend(self, market_data, current_time):
        """Check 3H market trend at current time"""
        market_slice = market_data[market_data.index <= current_time].copy()
        
        if len(market_slice) < 15:
            return 'BEAR'
        
        market_indicators = calculate_pp_supertrend(
            market_slice,
            pivot_period=TradingConfig.pivot_period,
            atr_factor=TradingConfig.atr_factor,
            atr_period=TradingConfig.atr_period
        )
        
        if market_indicators is None or len(market_indicators) == 0:
            return 'BEAR'
        
        last_market_signal = get_current_signal(market_indicators)
        
        # Map signal to market trend
        if last_market_signal['signal'] in ['BUY', 'HOLD_LONG']:
            return 'BULL'
        else:
            return 'BEAR'
    
    def _close_position_at_market(self, close_time, close_price, reason):
        """Close current position at market price"""
        if self.current_position is None:
            return
        
        position = self.current_position
        
        # Calculate P&L
        if position['signal'] == 'BUY':
            pnl = (close_price - position['entry_price']) * position['position_size']
        else:
            pnl = (position['entry_price'] - close_price) * position['position_size']
        
        self.current_balance += pnl
        
        self.logger.info(f"   💰 Position CLOSED: {reason} at {close_price:.5f}, P&L: ${pnl:.2f}")
        self.current_position = None
    
    def get_actual_signal(self, df):
        """Get actual BUY/SELL signal (not HOLD states)"""
        if len(df) < 2:
            return None
        
        last_row = df.iloc[-1]
        
        # Check for actual signal flags
        if last_row['buy_signal']:
            return 'BUY'
        elif last_row['sell_signal']:
            return 'SELL'
        else:
            return None  # No new signal
    
    def run_backtest(self, start_time, end_time, refresh_data=False):
        """Run backtest with corrected signal detection"""
        
        # Parse time range
        if isinstance(start_time, str):
            start_dt = datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S').replace(tzinfo=pytz.UTC)
        else:
            start_dt = start_time
            
        if isinstance(end_time, str):
            end_dt = datetime.strptime(end_time, '%Y-%m-%d %H:%M:%S').replace(tzinfo=pytz.UTC)
        else:
            end_dt = end_time
        
        self.logger.info(f"Running corrected backtest from {start_dt} to {end_dt}")
        
        # Download data
        downloader = BacktestDataDownloader(self.account, cache_dir='backtest/data')
        
        # Get trading data
        days_back = (end_dt - start_dt).days + 10
        trading_data = downloader.download_historical_data(
            self.instrument,
            f'M{self.timeframe[:-1]}' if self.timeframe.endswith('m') else f'H{self.timeframe[:-1]}',
            days_back=days_back,
            force_refresh=refresh_data
        )
        
        # Get market data (3H)
        market_data = downloader.download_historical_data(
            self.instrument,
            'H3',
            days_back=days_back,
            force_refresh=refresh_data
        )
        
        # Filter to backtest period
        trading_data = trading_data[(trading_data.index >= start_dt) & (trading_data.index <= end_dt)]
        
        self.logger.info(f"Filtered to {len(trading_data)} trading candles")
        
        # Calculate indicators
        trading_data_with_indicators = calculate_pp_supertrend(
            trading_data,
            pivot_period=TradingConfig.pivot_period,
            atr_factor=TradingConfig.atr_factor,
            atr_period=TradingConfig.atr_period
        )
        
        if trading_data_with_indicators is None:
            raise ValueError("Failed to calculate indicators")
        
        # Process each candle
        processed = 0
        
        for current_time, row in trading_data_with_indicators.iterrows():
            processed += 1
            
            # Update market trend periodically
            if processed % 12 == 0:
                prev_trend = self.current_market_trend
                self.current_market_trend = self.check_market_trend(market_data, current_time)
                if prev_trend != self.current_market_trend:
                    self.logger.info(f"📊 3H Market Trend UPDATE at {current_time}: {prev_trend} → {self.current_market_trend}")
            
            # Skip until we have enough data
            market_slice = market_data[market_data.index <= current_time]
            if len(market_slice) < 15:
                continue
            
            # Get actual signal (not HOLD states)
            data_slice = trading_data_with_indicators.loc[:current_time].copy()
            current_actual_signal = self.get_actual_signal(data_slice)
            
            # Only process if there's a new actual signal
            if current_actual_signal and current_actual_signal != self.last_actual_signal:
                
                signal_info = get_current_signal(data_slice)
                current_market_trend = self.current_market_trend
                
                self.logger.info(f"\n📍 Signal at {current_time}: {current_actual_signal}")
                self.logger.info(f"   Market Trend: {current_market_trend}")
                self.logger.info(f"   Entry Price: {signal_info['price']:.5f}")
                
                # Close existing position if any
                if self.current_position is not None:
                    self.logger.info(f"   🔄 Closing existing {self.current_position['signal']} position")
                    self._close_position_at_market(current_time, signal_info['price'], "NEW_SIGNAL")
                
                # Check if we should trade
                position_type = 'LONG' if current_actual_signal == 'BUY' else 'SHORT'
                
                should_trade, action, next_action = self.risk_manager.should_trade(
                    signal_info,
                    None,  # No existing position after closure
                    current_time,
                    self.last_signal_time,
                    market_trend=current_market_trend,
                    config=self.config
                )
                
                if should_trade and action in ['OPEN_LONG', 'OPEN_SHORT']:
                    self.logger.info(f"   ✅ Trade ALLOWED: {action}")
                    
                    # Calculate position size
                    position_size, risk_amount = self.risk_manager.calculate_position_size(
                        self.current_balance, signal_info,
                        market_trend=current_market_trend,
                        position_type=position_type,
                        config=self.config
                    )
                    
                    # Calculate stop loss
                    if position_type == 'LONG':
                        stop_loss = signal_info['supertrend'] - 0.00010
                    else:
                        stop_loss = signal_info['supertrend'] + 0.00010
                    
                    # Get take profit ratio
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
                    
                    # Calculate take profit
                    risk = abs(signal_info['price'] - stop_loss)
                    reward = risk * take_profit_ratio
                    
                    if position_type == 'LONG':
                        take_profit_price = signal_info['price'] + reward
                    else:
                        take_profit_price = signal_info['price'] - reward
                    
                    # Find next signal for analysis
                    next_signal_time = None
                    next_actual_signal = current_actual_signal
                    for future_time, future_row in trading_data_with_indicators.loc[current_time:].iterrows():
                        if future_time <= current_time:
                            continue
                        future_data_slice = trading_data_with_indicators.loc[:future_time].copy()
                        future_actual_signal = self.get_actual_signal(future_data_slice)
                        if future_actual_signal and future_actual_signal != next_actual_signal:
                            next_signal_time = future_time
                            break
                        next_actual_signal = future_actual_signal if future_actual_signal else next_actual_signal
                    
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
                            unrealized_pl_max = (max_profit_price - signal_info['price']) * position_size
                            max_profit_ratio = (max_profit_price - signal_info['price']) / risk if risk > 0 else 0
                            
                            take_profit_hit = highest_price >= take_profit_price
                            stop_loss_hit = lowest_price <= stop_loss
                            
                            if take_profit_hit:
                                actual_profit = reward * position_size
                            elif stop_loss_hit:
                                actual_profit = -risk_amount
                            else:
                                actual_profit = 0
                            
                        else:  # SHORT
                            max_profit_price = lowest_price
                            unrealized_pl_max = (signal_info['price'] - max_profit_price) * position_size
                            max_profit_ratio = (signal_info['price'] - max_profit_price) / risk if risk > 0 else 0
                            
                            take_profit_hit = lowest_price <= take_profit_price
                            stop_loss_hit = highest_price >= stop_loss
                            
                            if take_profit_hit:
                                actual_profit = reward * position_size
                            elif stop_loss_hit:
                                actual_profit = -risk_amount
                            else:
                                actual_profit = 0
                    else:
                        unrealized_pl_max = 0
                        max_profit_ratio = 0
                        actual_profit = 0
                        take_profit_hit = False
                        stop_loss_hit = False
                    
                    # Log results
                    position_status = 'CLOSED_TP' if take_profit_hit else ('CLOSED_SL' if stop_loss_hit else 'OPEN')
                    self.logger.info(f"   📈 Max Ratio: {max_profit_ratio:.2f}:1, Potential: ${unrealized_pl_max:.2f}")
                    self.logger.info(f"   💵 Actual P&L: ${actual_profit:.2f} ({position_status})")
                    
                    # Calculate stop distance in pips
                    stop_distance_pips = abs(signal_info['price'] - stop_loss) * 10000
                    
                    # Record for analysis
                    self.signal_analysis.append({
                        'market': current_market_trend,
                        'signal': current_actual_signal,
                        'time': current_time.strftime('%b %d, %I:%M%p'),
                        'entry_price': signal_info['price'],
                        'position_lots': position_size,
                        'risk_amount': f"${risk_amount:.0f}",
                        'stop_distance': f"{stop_distance_pips:.1f} pips",
                        'highest_ratio': f"{max_profit_ratio:.2f}:1",
                        'potential_profit': f"${unrealized_pl_max:.2f}",
                        'take_profit_ratio': f"{take_profit_ratio:.1f}:1",
                        'actual_profit': f"${actual_profit:.2f}",
                        'position_status': position_status,
                        'take_profit_hit': 'YES' if take_profit_hit else 'NO',
                        'stop_loss_hit': 'YES' if stop_loss_hit else 'NO'
                    })
                    
                    # Track position or update balance
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
                    else:
                        self.current_balance += actual_profit
                    
                    self.last_signal_time = current_time
                
                else:
                    self.logger.info(f"   🚫 Trade FILTERED: {current_actual_signal} blocked")
                
                # Update last actual signal
                self.last_actual_signal = current_actual_signal
        
        # Close any remaining position
        if self.current_position is not None:
            final_time = trading_data_with_indicators.index[-1]
            final_price = trading_data_with_indicators.iloc[-1]['close']
            self.logger.info(f"\n⏰ End of backtest period - closing remaining position")
            self._close_position_at_market(final_time, final_price, "END_OF_PERIOD")
        
        return self.generate_results()
    
    def generate_results(self):
        """Generate backtest results"""
        total_trades = len(self.signal_analysis)
        profitable_trades = len([s for s in self.signal_analysis if s['take_profit_hit'] == 'YES'])
        
        total_profit = sum(
            float(s['actual_profit'].replace('$', ''))
            for s in self.signal_analysis if s['take_profit_hit'] == 'YES'
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
    
    def save_results(self, results, output_dir='backtest/results'):
        """Save results to CSV"""
        os.makedirs(output_dir, exist_ok=True)
        
        if not results['signal_analysis']:
            return None
        
        # Create DataFrame
        df = pd.DataFrame(results['signal_analysis'])
        
        # Generate filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{output_dir}/corrected_bt_{self.instrument}_{self.timeframe}_{self.account}_{timestamp}.csv"
        
        # Save CSV
        df.to_csv(filename, index=False)
        self.logger.info(f"\nResults saved to: {filename}")
        
        return filename

def main():
    """Main entry point"""
    # Parse arguments
    args = {}
    for arg in sys.argv[1:]:
        if '=' in arg:
            key, value = arg.split('=', 1)
            args[key] = value
    
    # Extract parameters
    account = args.get('at', 'account1')
    instrument = args.get('fr', 'EUR_USD')
    timeframe = args.get('tf', '5m')
    time_range = args.get('bt', '01/04/2026 16:00:00,01/09/2026 16:00:00')
    # Parse balance if provided, otherwise will use config default
    balance = args.get('balance')
    if balance:
        balance = float(balance)
    else:
        balance = None
    refresh = args.get('refresh', 'false').lower() == 'true'
    
    # Parse time range
    if ',' in time_range:
        start_str, end_str = time_range.split(',')
        start_time = datetime.strptime(start_str.strip(), '%m/%d/%Y %H:%M:%S')
        end_time = datetime.strptime(end_str.strip(), '%m/%d/%Y %H:%M:%S')
    else:
        print("Error: Time range must be in format 'MM/DD/YYYY HH:MM:SS,MM/DD/YYYY HH:MM:SS'")
        sys.exit(1)
    
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(message)s'
    )
    
    print(f"\n{'='*80}")
    print("CORRECTED BACKTEST ENGINE - NO PHANTOM TRADES")
    print(f"{'='*80}")
    print(f"Account: {account}")
    print(f"Instrument: {instrument}")
    print(f"Timeframe: {timeframe}")
    print(f"Period: {start_str} to {end_str}")
    print(f"Initial Balance: ${balance:.2f}")
    print(f"{'='*80}\n")
    
    # Run backtest
    engine = CorrectedBacktestEngine(account, instrument, timeframe, balance)
    results = engine.run_backtest(start_time, end_time, refresh)
    
    # Print summary
    print(f"\n{'='*80}")
    print("BACKTEST RESULTS")
    print(f"{'='*80}")
    print(f"Total Trades: {results['performance']['total_trades']}")
    print(f"Winning Trades: {results['performance']['winning_trades']}")
    print(f"Win Rate: {results['performance']['win_rate']:.1f}%")
    print(f"Total Return: ${results['performance']['total_return']:.2f}")
    print(f"Return %: {results['performance']['total_return_pct']:.2f}%")
    print(f"Final Balance: ${results['backtest_info']['final_balance']:.2f}")
    
    # Save results
    filename = engine.save_results(results)
    
    return results

if __name__ == "__main__":
    main()