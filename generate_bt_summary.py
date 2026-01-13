#!/usr/bin/env python3
"""
Batch Backtest Summary Generator
Reads multiple backtest CSV files and generates a summary report
"""

import os
import sys
import pandas as pd
import yaml
import argparse
from datetime import datetime


def load_account_config(account):
    """Load account configuration to get R:R settings"""
    # Default config
    default_config = {
        'stoploss': {'spread_buffer_pips': 3},
        'position_sizing': {'disable_opposite_trade': True},
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
            deep_merge(default_config, loaded_default)

    # Load account-specific overrides
    account_config_file = f"{account}/config.yaml"
    if os.path.exists(account_config_file):
        with open(account_config_file, 'r') as f:
            account_config = yaml.safe_load(f) or {}
        deep_merge(default_config, account_config)

    return default_config


def deep_merge(base_dict, override_dict):
    """Deep merge override_dict into base_dict"""
    for key, value in override_dict.items():
        if key in base_dict and isinstance(base_dict[key], dict) and isinstance(value, dict):
            deep_merge(base_dict[key], value)
        else:
            base_dict[key] = value


def analyze_backtest_csv(csv_path):
    """Analyze a backtest CSV file and return results"""
    df = pd.read_csv(csv_path)

    total_trades = len(df)
    tp_hits = len(df[df['take_profit_hit'] == 'YES'])
    sl_hits = len(df[df['stop_loss_hit'] == 'YES'])
    win_rate = (tp_hits / total_trades * 100) if total_trades > 0 else 0

    # Calculate total P/L
    total_pl = df['actual_profit'].apply(lambda x: float(x.replace('$', ''))).sum()

    # BUY/SELL breakdown
    buy_trades = df[df['signal'] == 'BUY']
    sell_trades = df[df['signal'] == 'SELL']

    buy_count = len(buy_trades)
    buy_wins = len(buy_trades[buy_trades['take_profit_hit'] == 'YES'])
    buy_win_rate = (buy_wins / buy_count * 100) if buy_count > 0 else 0

    sell_count = len(sell_trades)
    sell_wins = len(sell_trades[sell_trades['take_profit_hit'] == 'YES'])
    sell_win_rate = (sell_wins / sell_count * 100) if sell_count > 0 else 0

    return {
        'total_trades': total_trades,
        'tp_hits': tp_hits,
        'sl_hits': sl_hits,
        'win_rate': win_rate,
        'total_pl': total_pl,
        'buy_count': buy_count,
        'buy_wins': buy_wins,
        'buy_win_rate': buy_win_rate,
        'sell_count': sell_count,
        'sell_wins': sell_wins,
        'sell_win_rate': sell_win_rate
    }


def format_rr(value):
    """Format R:R value as string"""
    return f"{value:.1f}:1"


def generate_summary_report(accounts, csv_files, instrument, timeframe, start_date, end_date, initial_balance=10000, market_override=None):
    """Generate summary report from multiple backtest results"""
    results = []

    for account, csv_file in zip(accounts, csv_files):
        config = load_account_config(account)
        analysis = analyze_backtest_csv(csv_file)

        # Extract account number for display
        account_num = account.replace('account', '')

        results.append({
            'account': account,
            'account_num': account_num,
            'config': config,
            'analysis': analysis,
            'final_balance': initial_balance + analysis['total_pl']
        })

    # Generate report content
    report_lines = []
    report_lines.append("Backtest Summary Report")
    report_lines.append(f"Period: {start_date} - {end_date} ({instrument.replace('_', '/')} {timeframe})")
    if market_override:
        report_lines.append(f"Market Override: {market_override.upper()} (3H calculation disabled)")
    report_lines.append("")

    # Key Settings Info (at top of report)
    report_lines.append("Key Settings")
    for r in results:
        cfg = r['config']
        disable_opposite = cfg.get('position_sizing', {}).get('disable_opposite_trade', False)
        disable_str = "YES" if disable_opposite else "NO"
        report_lines.append(f"Account {r['account_num']}: disable_opposite_trade={disable_str}")
    report_lines.append("")

    # Configuration Settings Table
    report_lines.append("Configuration Settings (R:R Ratios)")
    report_lines.append("Account,Bear Short,Bear Long,Bull Short,Bull Long,Buffer")
    for r in results:
        cfg = r['config']
        bear_short = format_rr(cfg['risk_reward']['bear_market']['short_rr'])
        bear_long = format_rr(cfg['risk_reward']['bear_market']['long_rr'])
        bull_short = format_rr(cfg['risk_reward']['bull_market']['short_rr'])
        bull_long = format_rr(cfg['risk_reward']['bull_market']['long_rr'])
        buffer = f"{cfg['stoploss']['spread_buffer_pips']} pips"
        report_lines.append(f"{r['account_num']},{bear_short},{bear_long},{bull_short},{bull_long},{buffer}")

    report_lines.append("")

    # Results Table
    report_lines.append("Results")
    report_lines.append("Account,Trades,TP Hits,Win Rate,Total P/L,Final Balance")
    for r in results:
        a = r['analysis']
        pl_str = f"+${a['total_pl']:.0f}" if a['total_pl'] >= 0 else f"-${abs(a['total_pl']):.0f}"
        report_lines.append(f"{r['account_num']},{a['total_trades']},{a['tp_hits']},{a['win_rate']:.1f}%,{pl_str},${r['final_balance']:.0f}")

    report_lines.append("")

    # Trade Breakdown by Direction
    report_lines.append("Trade Breakdown by Direction")
    report_lines.append("Account,BUY Trades,BUY Win %,SELL Trades,SELL Win %")
    for r in results:
        a = r['analysis']
        report_lines.append(f"{r['account_num']},{a['buy_count']},{a['buy_win_rate']:.1f}%,{a['sell_count']},{a['sell_win_rate']:.1f}%")

    return "\n".join(report_lines), results


def generate_summary_csv(accounts, csv_files, output_path, instrument, timeframe, start_date, end_date, initial_balance=10000, market_override=None):
    """Generate summary CSV from multiple backtest results"""
    report_content, results = generate_summary_report(
        accounts, csv_files, instrument, timeframe, start_date, end_date, initial_balance, market_override
    )

    # Write to CSV file
    with open(output_path, 'w') as f:
        f.write(report_content)

    return output_path, results


def print_summary_table(results, instrument, timeframe, start_date, end_date, initial_balance, market_override=None):
    """Print formatted summary tables to console"""
    print(f"\n{'='*80}")
    print(f"BACKTEST SUMMARY REPORT")
    print(f"Period: {start_date} - {end_date} ({instrument.replace('_', '/')} {timeframe})")
    if market_override:
        print(f"Market Override: {market_override.upper()} (3H calculation disabled)")
    print(f"Initial Balance: ${initial_balance:,.0f}")
    print(f"{'='*80}")

    # Key Settings Info
    print(f"\n{'Key Settings':^80}")
    print("-" * 80)
    for r in results:
        cfg = r['config']
        disable_opposite = cfg.get('position_sizing', {}).get('disable_opposite_trade', False)
        disable_str = "YES" if disable_opposite else "NO"
        print(f"Account {r['account_num']}: disable_opposite_trade={disable_str}")
    print("-" * 80)

    # Configuration Table
    print(f"\n{'Configuration Settings (R:R Ratios)':^80}")
    print("-" * 80)
    print(f"{'Account':^10} {'Bear Short':^12} {'Bear Long':^12} {'Bull Short':^12} {'Bull Long':^12} {'Buffer':^10}")
    print("-" * 80)

    for r in results:
        cfg = r['config']
        bear_short = format_rr(cfg['risk_reward']['bear_market']['short_rr'])
        bear_long = format_rr(cfg['risk_reward']['bear_market']['long_rr'])
        bull_short = format_rr(cfg['risk_reward']['bull_market']['short_rr'])
        bull_long = format_rr(cfg['risk_reward']['bull_market']['long_rr'])
        buffer = f"{cfg['stoploss']['spread_buffer_pips']} pips"
        print(f"{r['account_num']:^10} {bear_short:^12} {bear_long:^12} {bull_short:^12} {bull_long:^12} {buffer:^10}")

    # Results Table
    print(f"\n{'Results':^80}")
    print("-" * 80)
    print(f"{'Account':^10} {'Trades':^10} {'TP Hits':^10} {'Win Rate':^12} {'Total P/L':^14} {'Final Balance':^14}")
    print("-" * 80)

    for r in results:
        a = r['analysis']
        pl_str = f"+${a['total_pl']:.0f}" if a['total_pl'] >= 0 else f"-${abs(a['total_pl']):.0f}"
        print(f"{r['account_num']:^10} {a['total_trades']:^10} {a['tp_hits']:^10} {a['win_rate']:.1f}%{'':<6} {pl_str:^14} ${r['final_balance']:,.0f}{'':<4}")

    # Trade Breakdown
    print(f"\n{'Trade Breakdown by Direction':^80}")
    print("-" * 80)
    print(f"{'Account':^10} {'BUY Trades':^14} {'BUY Win %':^14} {'SELL Trades':^14} {'SELL Win %':^14}")
    print("-" * 80)

    for r in results:
        a = r['analysis']
        print(f"{r['account_num']:^10} {a['buy_count']:^14} {a['buy_win_rate']:.1f}%{'':<9} {a['sell_count']:^14} {a['sell_win_rate']:.1f}%{'':<9}")

    print(f"\n{'='*80}")


def main():
    parser = argparse.ArgumentParser(description='Generate backtest summary from multiple CSV files')
    parser.add_argument('--accounts', required=True, help='Comma-separated list of accounts (e.g., account1,account2)')
    parser.add_argument('--csv-files', required=True, help='Comma-separated list of CSV file paths')
    parser.add_argument('--instrument', required=True, help='Instrument (e.g., EUR_USD)')
    parser.add_argument('--timeframe', required=True, help='Timeframe (e.g., 5m)')
    parser.add_argument('--start-date', required=True, help='Start date (e.g., "Jan 04, 2026 16:00")')
    parser.add_argument('--end-date', required=True, help='End date (e.g., "Jan 09, 2026 16:00")')
    parser.add_argument('--balance', type=float, default=10000, help='Initial balance')
    parser.add_argument('--market', type=str, default=None, help='Market override: bear or bull')
    parser.add_argument('--output', required=True, help='Output summary CSV file path')

    args = parser.parse_args()

    accounts = args.accounts.split(',')
    csv_files = args.csv_files.split(',')

    if len(accounts) != len(csv_files):
        print("Error: Number of accounts must match number of CSV files")
        return 1

    # Verify CSV files exist
    for csv_file in csv_files:
        if not os.path.exists(csv_file):
            print(f"Error: CSV file not found: {csv_file}")
            return 1

    # Generate summary
    output_path, results = generate_summary_csv(
        accounts, csv_files, args.output,
        args.instrument, args.timeframe,
        args.start_date, args.end_date,
        args.balance, args.market
    )

    # Print formatted summary to console
    print_summary_table(results, args.instrument, args.timeframe,
                        args.start_date, args.end_date, args.balance, args.market)

    print(f"\nSummary saved to: {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
