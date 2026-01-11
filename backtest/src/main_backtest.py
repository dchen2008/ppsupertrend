#!/usr/bin/env python3
"""
Main Backtest Runner
Orchestrates data download, backtest execution, and report generation
"""

import os
import sys
import argparse
import json
import time
import logging
from datetime import datetime

# Add parent directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from backtest.src.data_downloader import BacktestDataDownloader
from backtest.src.backtest_engine import BacktestEngine
from backtest.src.report_generator import BacktestReportGenerator


def setup_logging(log_level='INFO'):
    """Setup logging configuration"""
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def parse_timeframe_arg(timeframe_str):
    """Parse timeframe argument (e.g., '30d' -> 30)"""
    if timeframe_str.endswith('d'):
        return int(timeframe_str[:-1])
    elif timeframe_str.endswith('days'):
        return int(timeframe_str[:-4])
    else:
        return int(timeframe_str)


def generate_output_prefix(instrument, timeframe, account, backtest_days):
    """Generate output file prefix"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return f"bt_{instrument}_{timeframe}_{account}_{backtest_days}d_{timestamp}"


def run_full_backtest(instrument, timeframe, account, backtest_days, 
                     initial_balance=10000, force_refresh=False, 
                     output_dir='backtest/results', save_json=True):
    """
    Run complete backtest pipeline
    
    Args:
        instrument: Trading instrument (e.g., 'EUR_USD')
        timeframe: Trading timeframe ('5m' or '15m')
        account: Account name for configuration
        backtest_days: Number of days to backtest
        initial_balance: Starting balance
        force_refresh: Force refresh cached data
        output_dir: Output directory for results
        save_json: Save detailed results to JSON
    
    Returns:
        dict: Backtest results
    """
    logger = logging.getLogger(__name__)
    
    logger.info("="*60)
    logger.info("STARTING COMPREHENSIVE BACKTEST")
    logger.info("="*60)
    logger.info(f"Instrument: {instrument}")
    logger.info(f"Timeframe: {timeframe}")
    logger.info(f"Account: {account}")
    logger.info(f"Backtest Period: {backtest_days} days")
    logger.info(f"Initial Balance: ${initial_balance:,.2f}")
    logger.info(f"Force Refresh: {force_refresh}")
    
    start_time = time.time()
    
    try:
        # Step 1: Download historical data
        logger.info("\n=== STEP 1: DOWNLOADING DATA ===")
        downloader = BacktestDataDownloader(account=account)
        
        granularity = 'M5' if timeframe == '5m' else 'M15'
        
        # Download trading, market, and intrabar timeframes
        data = downloader.get_data_for_backtest(
            instrument=instrument,
            trading_timeframe=granularity,
            market_timeframe='H3',
            days_back=backtest_days,
            include_intrabar=True
        )
        
        required_timeframes = [granularity, 'H3', 'M1']
        for tf in required_timeframes:
            if tf not in data:
                raise ValueError(f"Failed to download {tf} data")
        
        logger.info(f"✓ Downloaded {len(data[granularity])} {granularity} candles")
        logger.info(f"✓ Downloaded {len(data['H3'])} H3 candles") 
        logger.info(f"✓ Downloaded {len(data['M1'])} M1 candles")
        logger.info(f"✓ Data range: {data[granularity].index[0]} to {data[granularity].index[-1]}")
        
        # Step 2: Run backtest
        logger.info("\n=== STEP 2: RUNNING BACKTEST ===")
        engine = BacktestEngine(
            instrument=instrument,
            timeframe=timeframe,
            account=account,
            initial_balance=initial_balance
        )
        
        results = engine.run_backtest(data[granularity], data['H3'], data['M1'])
        
        # Log basic results
        logger.info(f"✓ Backtest completed")
        logger.info(f"  Total trades: {results['performance']['total_trades']}")
        logger.info(f"  Final balance: ${results['backtest_info']['final_balance']:,.2f}")
        logger.info(f"  Total return: ${results['performance']['total_return']:,.2f}")
        logger.info(f"  Return percentage: {results['performance']['total_return_pct']:+.2f}%")
        if results['performance']['total_trades'] > 0:
            logger.info(f"  Win rate: {results['performance']['win_rate']:.1f}%")
            logger.info(f"  Profit factor: {results['performance']['profit_factor']:.2f}")
        
        # Step 3: Generate reports
        logger.info("\n=== STEP 3: GENERATING REPORTS ===")
        
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        
        # Generate file prefix
        output_prefix = generate_output_prefix(instrument, timeframe, account, backtest_days)
        
        # Import and generate comprehensive reports
        report_gen = BacktestReportGenerator(results, output_dir)
        generated_files = report_gen.generate_complete_report(output_prefix)
        
        logger.info(f"✓ Generated {len(generated_files)} report files")
        
        # Save detailed results to JSON if requested
        if save_json:
            json_filename = f"{output_prefix}_detailed_results.json"
            json_filepath = os.path.join(output_dir, json_filename)
            
            # Prepare results for JSON serialization
            json_results = prepare_results_for_json(results)
            
            with open(json_filepath, 'w') as f:
                json.dump(json_results, f, indent=2, default=str)
            
            generated_files.append(json_filename)
            logger.info(f"✓ Saved detailed results: {json_filename}")
        
        # Calculate execution time
        execution_time = time.time() - start_time
        logger.info(f"\n⏱️ Total execution time: {execution_time:.1f} seconds")
        
        # Final summary
        logger.info("\n=== BACKTEST SUMMARY ===")
        logger.info(f"Instrument: {instrument} ({timeframe})")
        logger.info(f"Period: {backtest_days} days")
        logger.info(f"Configuration: {account}")
        
        if results['performance']['total_trades'] > 0:
            logger.info(f"Performance:")
            logger.info(f"  • Total Trades: {results['performance']['total_trades']}")
            logger.info(f"  • Win Rate: {results['performance']['win_rate']:.1f}%")
            logger.info(f"  • Total Return: ${results['performance']['total_return']:,.2f} ({results['performance']['total_return_pct']:+.2f}%)")
            logger.info(f"  • Profit Factor: {results['performance']['profit_factor']:.2f}")
            # Get advanced metrics for drawdown info
            temp_gen = BacktestReportGenerator(results, 'temp')
            advanced_metrics = temp_gen.calculate_advanced_metrics()
            if 'risk_metrics' in advanced_metrics:
                logger.info(f"  • Max Drawdown: {advanced_metrics['risk_metrics']['max_drawdown_pct']:.2f}%")
        else:
            logger.info("No trades executed during backtest period")
        
        logger.info(f"\nReports saved to: {output_dir}/")
        for file in generated_files:
            logger.info(f"  • {file}")
        
        logger.info("\n" + "="*60)
        logger.info("BACKTEST COMPLETED SUCCESSFULLY")
        logger.info("="*60)
        
        return results
        
    except Exception as e:
        logger.error(f"Backtest failed: {str(e)}")
        logger.exception("Full traceback:")
        raise


def prepare_results_for_json(results):
    """Prepare results for JSON serialization by converting trade objects"""
    json_results = results.copy()
    
    # Convert trade objects to dictionaries
    if 'trades' in json_results:
        json_trades = []
        for trade in json_results['trades']:
            trade_dict = {
                'trade_id': trade.trade_id,
                'instrument': trade.instrument,
                'position_type': trade.position_type,
                'units': trade.units,
                'entry_price': trade.entry_price,
                'exit_price': trade.exit_price,
                'entry_time': trade.entry_time.isoformat() if trade.entry_time else None,
                'exit_time': trade.exit_time.isoformat() if trade.exit_time else None,
                'duration_minutes': trade.duration_minutes,
                'realized_pl': trade.realized_pl,
                'highest_pl': trade.highest_pl,
                'lowest_pl': trade.lowest_pl,
                'stop_loss': trade.stop_loss,
                'take_profit': trade.take_profit,
                'exit_reason': trade.exit_reason,
                'market_trend': trade.market_trend,
                'risk_reward_target': trade.risk_reward_target,
                'risk_reward_actual': trade.risk_reward_actual
            }
            json_trades.append(trade_dict)
        
        json_results['trades'] = json_trades
    
    return json_results


def main():
    """Main entry point for CLI"""
    parser = argparse.ArgumentParser(
        description='Run comprehensive backtest with market-aware logic',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m backtest.src.main_backtest at=account1 fr=EUR_USD tf=5m bt=30d
  python -m backtest.src.main_backtest at=account2 fr=GBP_USD tf=15m bt=90d balance=25000
  python -m backtest.src.main_backtest at=account1 fr=EUR_USD tf=5m bt=60d --refresh --parallel
        """
    )
    
    # Required parameters (matching shell script format)
    parser.add_argument('account', help='Account configuration (format: at=account1)')
    parser.add_argument('instrument', help='Trading instrument (format: fr=EUR_USD)')
    parser.add_argument('timeframe', help='Trading timeframe (format: tf=5m or tf=15m)')
    parser.add_argument('backtest_period', help='Backtest period (format: bt=30d)')
    
    # Optional parameters
    parser.add_argument('--balance', type=float, default=10000, 
                       help='Initial balance (default: 10000)')
    parser.add_argument('--refresh', action='store_true',
                       help='Force refresh cached data')
    parser.add_argument('--output-dir', default='backtest/results',
                       help='Output directory (default: backtest/results)')
    parser.add_argument('--log-level', default='INFO',
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       help='Log level (default: INFO)')
    parser.add_argument('--no-json', action='store_true',
                       help='Skip saving detailed JSON results')
    parser.add_argument('--parallel', action='store_true',
                       help='Run in parallel mode (experimental)')
    
    args = parser.parse_args()
    
    # Parse the custom format arguments
    try:
        # Parse account (at=account1)
        if not args.account.startswith('at='):
            raise ValueError("Account must be in format: at=account1")
        account = args.account.split('=')[1]
        
        # Parse instrument (fr=EUR_USD)
        if not args.instrument.startswith('fr='):
            raise ValueError("Instrument must be in format: fr=EUR_USD")
        instrument = args.instrument.split('=')[1]
        
        # Parse timeframe (tf=5m)
        if not args.timeframe.startswith('tf='):
            raise ValueError("Timeframe must be in format: tf=5m or tf=15m")
        timeframe = args.timeframe.split('=')[1]
        if timeframe not in ['5m', '15m']:
            raise ValueError("Timeframe must be 5m or 15m")
        
        # Parse backtest period (bt=30d)
        if not args.backtest_period.startswith('bt='):
            raise ValueError("Backtest period must be in format: bt=30d")
        backtest_days = parse_timeframe_arg(args.backtest_period.split('=')[1])
        
    except (ValueError, IndexError) as e:
        print(f"Error parsing arguments: {e}")
        parser.print_help()
        sys.exit(1)
    
    # Setup logging
    setup_logging(args.log_level)
    
    # Run backtest
    try:
        if args.parallel:
            print("Parallel mode not yet implemented in Python version")
            print("Use the shell script for parallel execution")
            sys.exit(1)
        
        results = run_full_backtest(
            instrument=instrument,
            timeframe=timeframe,
            account=account,
            backtest_days=backtest_days,
            initial_balance=args.balance,
            force_refresh=args.refresh,
            output_dir=args.output_dir,
            save_json=not args.no_json
        )
        
        sys.exit(0)
        
    except KeyboardInterrupt:
        print("\nBacktest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"Backtest failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()