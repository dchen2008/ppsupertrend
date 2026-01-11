"""
OANDA Historical Data Downloader for Backtesting
Downloads historical candle data with optimized API calls
"""

import os
import sys
import pandas as pd
import time
from datetime import datetime, timedelta
import logging

# Add parent directory to path to import from src
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from src.oanda_client import OANDAClient
from src.config import OANDAConfig


class BacktestDataDownloader:
    """Download and cache historical data for backtesting"""
    
    def __init__(self, account='account1', cache_dir='backtest/data'):
        """
        Initialize data downloader
        
        Args:
            account: Account to use for data download
            cache_dir: Directory to cache downloaded data
        """
        # Set the account
        OANDAConfig.set_account(account)
        
        self.client = OANDAClient()
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        
        # Setup logging
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
    
    def get_cache_filename(self, instrument, granularity, start_date, end_date):
        """Generate cache filename for the data"""
        start_str = start_date.strftime('%Y%m%d')
        end_str = end_date.strftime('%Y%m%d')
        return f"{instrument}_{granularity}_{start_str}_{end_str}.csv"
    
    def is_cache_valid(self, cache_file):
        """Check if cached file exists and is recent"""
        if not os.path.exists(cache_file):
            return False
        
        # Check if file is less than 1 hour old (for recent data)
        file_age = time.time() - os.path.getmtime(cache_file)
        return file_age < 3600  # 1 hour
    
    def download_historical_data(self, instrument, granularity, days_back=90, 
                                force_refresh=False):
        """
        Download historical data with caching (simplified for current API)
        
        Args:
            instrument: Trading pair (e.g., 'EUR_USD')
            granularity: OANDA granularity (e.g., 'M5', 'M15', 'H3')
            days_back: Number of days back to download
            force_refresh: Force refresh even if cache exists
            
        Returns:
            pd.DataFrame: Historical candle data
        """
        # Calculate date range for cache naming
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        # Check cache first
        cache_file = os.path.join(self.cache_dir, 
                                 self.get_cache_filename(instrument, granularity, 
                                                       start_date, end_date))
        
        if not force_refresh and self.is_cache_valid(cache_file):
            self.logger.info(f"Loading cached data from {cache_file}")
            try:
                df = pd.read_csv(cache_file, index_col=0, parse_dates=True)
                return df
            except Exception as e:
                self.logger.warning(f"Failed to load cache: {e}. Downloading fresh data.")
        
        # Calculate total candles needed based on granularity and days
        self.logger.info(f"Downloading recent {instrument} {granularity} data...")
        
        # Calculate approximate candles needed
        if granularity == 'M1':
            # 1-minute candles: 1440 per day (24*60)
            total_candles = days_back * 1440
        elif granularity == 'M5':
            # 5-minute candles: 288 per day (24*60/5)
            total_candles = days_back * 288
        elif granularity == 'M15':
            # 15-minute candles: 96 per day (24*60/15)
            total_candles = days_back * 96
        elif granularity == 'H3':
            # 3-hour candles: 8 per day (24/3)
            total_candles = days_back * 8
        else:
            # Default estimate
            total_candles = days_back * 100
        
        # Cap at OANDA's maximum and ensure minimum
        total_candles = min(max(total_candles, 50), 5000)
        
        self.logger.info(f"Requesting {total_candles} recent candles")
        
        # Download data (this will get the most recent data)
        df = self.client.get_candles(
            instrument=instrument,
            granularity=granularity,
            count=total_candles
        )
        
        if df is None or len(df) == 0:
            self.logger.error("No data downloaded")
            return None
        
        self.logger.info(f"Downloaded {len(df)} candles from {df.index[0]} to {df.index[-1]}")
        
        # Cache the data
        try:
            df.to_csv(cache_file)
            self.logger.info(f"Data cached to {cache_file}")
        except Exception as e:
            self.logger.warning(f"Failed to cache data: {e}")
        
        return df
    
    def download_multiple_timeframes(self, instrument, timeframes, days_back=90):
        """
        Download data for multiple timeframes efficiently
        
        Args:
            instrument: Trading pair (e.g., 'EUR_USD')
            timeframes: List of granularities (e.g., ['M5', 'M15', 'H3'])
            days_back: Number of days back to download
            
        Returns:
            dict: Dictionary of {granularity: DataFrame}
        """
        results = {}
        
        self.logger.info(f"Downloading {instrument} data for timeframes: {timeframes}")
        
        for granularity in timeframes:
            self.logger.info(f"\n--- Downloading {granularity} data ---")
            df = self.download_historical_data(
                instrument=instrument,
                granularity=granularity,
                days_back=days_back
            )
            
            if df is not None:
                results[granularity] = df
                self.logger.info(f"✓ {granularity}: {len(df)} candles")
            else:
                self.logger.error(f"✗ Failed to download {granularity} data")
        
        return results
    
    def get_data_for_backtest(self, instrument, trading_timeframe, market_timeframe='H3', 
                            days_back=90, include_intrabar=True):
        """
        Get all required data for a backtest
        
        Args:
            instrument: Trading pair (e.g., 'EUR_USD')
            trading_timeframe: Trading timeframe ('M5' or 'M15')
            market_timeframe: Market trend timeframe (default 'H3')
            days_back: Number of days back to download
            include_intrabar: Include M1 data for intrabar monitoring (default True)
            
        Returns:
            dict: {trading_tf: DataFrame, market_tf: DataFrame, 'M1': DataFrame}
        """
        timeframes = [trading_timeframe]
        if market_timeframe not in timeframes:
            timeframes.append(market_timeframe)
        
        # Add M1 data for intrabar monitoring (take profit checking every 60 seconds)
        if include_intrabar and 'M1' not in timeframes:
            timeframes.append('M1')
        
        return self.download_multiple_timeframes(instrument, timeframes, days_back)


def main():
    """CLI for data downloader"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Download historical data for backtesting')
    parser.add_argument('--instrument', default='EUR_USD', help='Trading instrument')
    parser.add_argument('--timeframes', default='M5,M15,H3', help='Comma-separated timeframes')
    parser.add_argument('--days', type=int, default=90, help='Days back to download')
    parser.add_argument('--account', default='account1', help='Account to use')
    parser.add_argument('--force', action='store_true', help='Force refresh cache')
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Create downloader
    downloader = BacktestDataDownloader(account=args.account)
    
    # Parse timeframes
    timeframes = [tf.strip() for tf in args.timeframes.split(',')]
    
    # Download data
    results = downloader.download_multiple_timeframes(
        instrument=args.instrument,
        timeframes=timeframes,
        days_back=args.days
    )
    
    # Summary
    print("\n" + "="*50)
    print("DOWNLOAD SUMMARY")
    print("="*50)
    for tf, df in results.items():
        print(f"{tf}: {len(df)} candles ({df.index[0]} to {df.index[-1]})")


if __name__ == "__main__":
    main()