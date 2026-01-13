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


def download_candles_by_date_range(client, instrument, granularity, start_date, end_date, logger):
    """
    Download candles for a specific date range using OANDA's from/to parameters.
    Handles pagination for large date ranges.

    Args:
        client: OANDAClient instance
        instrument: Trading pair (e.g., 'EUR_USD')
        granularity: OANDA granularity (e.g., 'M1', 'M5', 'M15', 'H3')
        start_date: Start datetime (timezone-aware)
        end_date: End datetime (timezone-aware)
        logger: Logger instance

    Returns:
        pd.DataFrame: Historical candle data
    """
    import requests

    all_candles = []
    current_start = start_date

    # OANDA limits to 5000 candles per request
    max_candles_per_request = 5000

    while current_start < end_date:
        # Format dates for OANDA API (RFC3339)
        from_time = current_start.strftime('%Y-%m-%dT%H:%M:%SZ')

        url = f"{client.base_url}/v3/instruments/{instrument}/candles"

        # OANDA API: use either (from + count) OR (from + to), not both
        # We use from + count for pagination control
        params = {
            'granularity': granularity,
            'from': from_time,
            'price': 'M',  # Midpoint candles
            'count': max_candles_per_request
        }

        logger.info(f"Fetching {granularity} candles from {from_time}")

        try:
            response = requests.get(url, headers=client.headers, params=params, timeout=60)
            response.raise_for_status()
            data = response.json()

            if 'candles' not in data or len(data['candles']) == 0:
                logger.info(f"No more candles available")
                break

            candles_in_range = 0
            for candle in data['candles']:
                candle_time = pd.to_datetime(candle['time'])
                # Only include candles within our target range
                if candle_time > end_date:
                    break
                if candle['complete']:
                    all_candles.append({
                        'time': candle_time,
                        'open': float(candle['mid']['o']),
                        'high': float(candle['mid']['h']),
                        'low': float(candle['mid']['l']),
                        'close': float(candle['mid']['c']),
                        'volume': int(candle['volume'])
                    })
                    candles_in_range += 1

            logger.info(f"  Fetched {candles_in_range} candles (total: {len(all_candles)})")

            # Check if we've passed our end date or got fewer candles than requested
            last_candle_time = pd.to_datetime(data['candles'][-1]['time'])
            if last_candle_time >= end_date:
                break
            if len(data['candles']) < max_candles_per_request:
                break

            # Update start time for next batch (last candle time + 1 second)
            current_start = last_candle_time + timedelta(seconds=1)

            # Small delay to avoid rate limiting
            time.sleep(0.5)

        except Exception as e:
            logger.error(f"Error fetching candles: {e}")
            break

    if not all_candles:
        return None

    df = pd.DataFrame(all_candles)
    df.set_index('time', inplace=True)
    df = df.sort_index()

    # Remove duplicates (can happen at pagination boundaries)
    df = df[~df.index.duplicated(keep='first')]

    return df


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

    def download_by_date_range(self, instrument, granularity, start_date, end_date, save_to_cache=True):
        """
        Download candles for a specific date range

        Args:
            instrument: Trading pair (e.g., 'EUR_USD')
            granularity: OANDA granularity (e.g., 'M1', 'M5', 'M15', 'H3')
            start_date: Start datetime (timezone-aware or naive, will be treated as UTC)
            end_date: End datetime (timezone-aware or naive, will be treated as UTC)
            save_to_cache: Whether to save to cache directory

        Returns:
            pd.DataFrame: Historical candle data
        """
        # Ensure dates are timezone-aware (UTC)
        if start_date.tzinfo is None:
            start_date = start_date.replace(tzinfo=pd.Timestamp.now().tz)
        if end_date.tzinfo is None:
            end_date = end_date.replace(tzinfo=pd.Timestamp.now().tz)

        self.logger.info(f"Downloading {instrument} {granularity} data from {start_date} to {end_date}")

        df = download_candles_by_date_range(
            self.client, instrument, granularity, start_date, end_date, self.logger
        )

        if df is not None and save_to_cache:
            # Save to cache
            cache_file = os.path.join(
                self.cache_dir,
                self.get_cache_filename(instrument, granularity, start_date, end_date)
            )
            try:
                df.to_csv(cache_file)
                self.logger.info(f"Data saved to {cache_file}")
            except Exception as e:
                self.logger.warning(f"Failed to save cache: {e}")

        return df

    def download_multiple_by_date_range(self, instrument, timeframes, start_date, end_date):
        """
        Download multiple timeframes for a specific date range

        Args:
            instrument: Trading pair (e.g., 'EUR_USD')
            timeframes: List of granularities (e.g., ['M1', 'M5', 'M15', 'H3'])
            start_date: Start datetime
            end_date: End datetime

        Returns:
            dict: Dictionary of {granularity: DataFrame}
        """
        results = {}

        self.logger.info(f"Downloading {instrument} data for timeframes: {timeframes}")
        self.logger.info(f"Period: {start_date} to {end_date}")

        for granularity in timeframes:
            self.logger.info(f"\n--- Downloading {granularity} data ---")
            df = self.download_by_date_range(
                instrument=instrument,
                granularity=granularity,
                start_date=start_date,
                end_date=end_date
            )

            if df is not None:
                results[granularity] = df
                self.logger.info(f"✓ {granularity}: {len(df)} candles")
            else:
                self.logger.error(f"✗ Failed to download {granularity} data")

        return results


def parse_date_range(range_str):
    """Parse date range string like '01/04/2026 16:00:00,01/09/2026 16:00:00'"""
    start_str, end_str = range_str.split(',')
    start_date = pd.to_datetime(start_str.strip(), format='%m/%d/%Y %H:%M:%S')
    end_date = pd.to_datetime(end_str.strip(), format='%m/%d/%Y %H:%M:%S')

    # Make timezone aware (UTC)
    start_date = start_date.tz_localize('UTC')
    end_date = end_date.tz_localize('UTC')

    return start_date, end_date


def main():
    """CLI for data downloader"""
    import argparse

    parser = argparse.ArgumentParser(description='Download historical data for backtesting')
    parser.add_argument('--instrument', default='EUR_USD', help='Trading instrument')
    parser.add_argument('--timeframes', default='M5,M15,H3', help='Comma-separated timeframes (M1,M5,M15,H3)')
    parser.add_argument('--days', type=int, default=None, help='Days back to download (use if no --range)')
    parser.add_argument('--range', dest='date_range', default=None,
                        help='Date range: "MM/DD/YYYY HH:MM:SS,MM/DD/YYYY HH:MM:SS"')
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
    timeframes = [tf.strip().upper() for tf in args.timeframes.split(',')]

    # Normalize timeframe names (1M -> M1, 5M -> M5, etc.)
    normalized_timeframes = []
    for tf in timeframes:
        if tf == '1M':
            normalized_timeframes.append('M1')
        elif tf == '5M':
            normalized_timeframes.append('M5')
        elif tf == '15M':
            normalized_timeframes.append('M15')
        elif tf == '3H':
            normalized_timeframes.append('H3')
        else:
            normalized_timeframes.append(tf)
    timeframes = normalized_timeframes

    print("\n" + "="*60)
    print("OANDA CANDLE DATA DOWNLOADER")
    print("="*60)
    print(f"Instrument: {args.instrument}")
    print(f"Timeframes: {', '.join(timeframes)}")
    print(f"Account: {args.account}")

    # Download data
    if args.date_range:
        # Use date range mode
        start_date, end_date = parse_date_range(args.date_range)
        print(f"Mode: Date Range")
        print(f"Period: {start_date} to {end_date}")
        print("="*60)

        results = downloader.download_multiple_by_date_range(
            instrument=args.instrument,
            timeframes=timeframes,
            start_date=start_date,
            end_date=end_date
        )
    else:
        # Use days back mode
        days = args.days if args.days else 90
        print(f"Mode: Days Back")
        print(f"Days: {days}")
        print("="*60)

        results = downloader.download_multiple_timeframes(
            instrument=args.instrument,
            timeframes=timeframes,
            days_back=days
        )

    # Summary
    print("\n" + "="*60)
    print("DOWNLOAD SUMMARY")
    print("="*60)
    for tf, df in results.items():
        if df is not None and len(df) > 0:
            print(f"  {tf}: {len(df):,} candles")
            print(f"       From: {df.index[0]}")
            print(f"       To:   {df.index[-1]}")
        else:
            print(f"  {tf}: No data")
    print("="*60)
    print(f"Data saved to: {downloader.cache_dir}/")
    print("="*60)


if __name__ == "__main__":
    main()