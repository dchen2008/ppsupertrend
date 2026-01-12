"""
Comprehensive Backtest Report Generator
Follows industry best practices for trading strategy analysis
"""

import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import json
from collections import defaultdict


class BacktestReportGenerator:
    """Generate comprehensive backtest reports with industry-standard metrics"""
    
    def __init__(self, results, output_dir='backtest/results'):
        """
        Initialize report generator
        
        Args:
            results: Backtest results dictionary from BacktestEngine
            output_dir: Directory to save reports
        """
        self.results = results
        self.trades = results['trades']
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        
        # Convert trades to DataFrame for analysis
        self.trades_df = self._trades_to_dataframe()
        
        # Setup plotting style
        plt.style.use('seaborn-v0_8-whitegrid')
        sns.set_palette("husl")
    
    def _trades_to_dataframe(self):
        """Convert trades list to pandas DataFrame"""
        if not self.trades:
            return pd.DataFrame()
        
        trade_data = []
        for trade in self.trades:
            trade_data.append({
                'trade_id': trade.trade_id,
                'instrument': trade.instrument,
                'position_type': trade.position_type,
                'units': trade.units,
                'entry_price': trade.entry_price,
                'exit_price': trade.exit_price,
                'entry_time': trade.entry_time,
                'exit_time': trade.exit_time,
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
            })
        
        df = pd.DataFrame(trade_data)
        df['entry_time'] = pd.to_datetime(df['entry_time'])
        df['exit_time'] = pd.to_datetime(df['exit_time'])
        df['duration_hours'] = df['duration_minutes'] / 60
        df['is_winning'] = df['realized_pl'] > 0
        
        return df
    
    def calculate_advanced_metrics(self):
        """Calculate advanced trading metrics"""
        if self.trades_df.empty:
            return {}
        
        # Basic metrics
        total_trades = len(self.trades_df)
        winning_trades = self.trades_df[self.trades_df['is_winning']]
        losing_trades = self.trades_df[~self.trades_df['is_winning']]
        
        win_rate = len(winning_trades) / total_trades * 100 if total_trades > 0 else 0
        
        # Profit/Loss metrics
        total_profit = self.trades_df['realized_pl'].sum()
        avg_win = winning_trades['realized_pl'].mean() if len(winning_trades) > 0 else 0
        avg_loss = losing_trades['realized_pl'].mean() if len(losing_trades) > 0 else 0
        
        # Risk metrics
        max_win = self.trades_df['realized_pl'].max()
        max_loss = self.trades_df['realized_pl'].min()
        
        # Consecutive wins/losses
        consecutive_wins = self._calculate_consecutive_runs(self.trades_df['is_winning'], True)
        consecutive_losses = self._calculate_consecutive_runs(self.trades_df['is_winning'], False)
        
        # Profit factor
        total_wins = winning_trades['realized_pl'].sum() if len(winning_trades) > 0 else 0
        total_losses = abs(losing_trades['realized_pl'].sum()) if len(losing_trades) > 0 else 1
        profit_factor = total_wins / total_losses if total_losses > 0 else float('inf')
        
        # Sharpe-like ratio (simplified)
        returns = self.trades_df['realized_pl']
        sharpe_ratio = returns.mean() / returns.std() if returns.std() > 0 else 0
        
        # Maximum drawdown
        cumulative_pl = returns.cumsum()
        running_max = cumulative_pl.expanding().max()
        drawdown = cumulative_pl - running_max
        max_drawdown = drawdown.min()
        max_drawdown_pct = (max_drawdown / self.results['backtest_info']['initial_balance']) * 100
        
        # Recovery factor
        recovery_factor = total_profit / abs(max_drawdown) if max_drawdown != 0 else float('inf')
        
        # Average duration
        avg_duration_hours = self.trades_df['duration_hours'].mean()
        
        # Expectancy
        expectancy = (win_rate / 100 * avg_win) + ((100 - win_rate) / 100 * avg_loss)
        
        return {
            'basic_metrics': {
                'total_trades': total_trades,
                'winning_trades': len(winning_trades),
                'losing_trades': len(losing_trades),
                'win_rate': win_rate,
                'avg_win': avg_win,
                'avg_loss': avg_loss,
                'max_win': max_win,
                'max_loss': max_loss,
                'avg_duration_hours': avg_duration_hours
            },
            'performance_metrics': {
                'total_return': total_profit,
                'total_return_pct': (total_profit / self.results['backtest_info']['initial_balance']) * 100,
                'profit_factor': profit_factor,
                'sharpe_ratio': sharpe_ratio,
                'expectancy': expectancy,
                'recovery_factor': recovery_factor
            },
            'risk_metrics': {
                'max_drawdown': max_drawdown,
                'max_drawdown_pct': max_drawdown_pct,
                'max_consecutive_wins': max(consecutive_wins) if consecutive_wins else 0,
                'max_consecutive_losses': max(consecutive_losses) if consecutive_losses else 0
            }
        }
    
    def _calculate_consecutive_runs(self, series, value):
        """Calculate consecutive runs of a specific value"""
        runs = []
        current_run = 0
        
        for val in series:
            if val == value:
                current_run += 1
            else:
                if current_run > 0:
                    runs.append(current_run)
                current_run = 0
        
        if current_run > 0:
            runs.append(current_run)
        
        return runs
    
    def analyze_by_market_conditions(self):
        """Analyze performance by market conditions"""
        if self.trades_df.empty:
            return {}
        
        analysis = {}
        
        for market_trend in ['BULL', 'BEAR', 'NEUTRAL']:
            subset = self.trades_df[self.trades_df['market_trend'] == market_trend]
            
            if len(subset) > 0:
                total_trades = len(subset)
                winning_trades = len(subset[subset['is_winning']])
                win_rate = (winning_trades / total_trades) * 100
                total_pl = subset['realized_pl'].sum()
                avg_pl = subset['realized_pl'].mean()
                
                analysis[market_trend] = {
                    'trades': total_trades,
                    'win_rate': win_rate,
                    'total_pl': total_pl,
                    'avg_pl': avg_pl,
                    'best_trade': subset['realized_pl'].max(),
                    'worst_trade': subset['realized_pl'].min()
                }
            else:
                analysis[market_trend] = {
                    'trades': 0,
                    'win_rate': 0,
                    'total_pl': 0,
                    'avg_pl': 0,
                    'best_trade': 0,
                    'worst_trade': 0
                }
        
        return analysis
    
    def analyze_by_position_type(self):
        """Analyze performance by position type (LONG vs SHORT)"""
        if self.trades_df.empty:
            return {}
        
        analysis = {}
        
        for position_type in ['LONG', 'SHORT']:
            subset = self.trades_df[self.trades_df['position_type'] == position_type]
            
            if len(subset) > 0:
                total_trades = len(subset)
                winning_trades = len(subset[subset['is_winning']])
                win_rate = (winning_trades / total_trades) * 100
                total_pl = subset['realized_pl'].sum()
                avg_pl = subset['realized_pl'].mean()
                
                analysis[position_type] = {
                    'trades': total_trades,
                    'win_rate': win_rate,
                    'total_pl': total_pl,
                    'avg_pl': avg_pl,
                    'best_trade': subset['realized_pl'].max(),
                    'worst_trade': subset['realized_pl'].min()
                }
            else:
                analysis[position_type] = {
                    'trades': 0,
                    'win_rate': 0,
                    'total_pl': 0,
                    'avg_pl': 0,
                    'best_trade': 0,
                    'worst_trade': 0
                }
        
        return analysis
    
    def analyze_exit_reasons(self):
        """Analyze performance by exit reason"""
        if self.trades_df.empty:
            return {}
        
        analysis = {}
        
        for exit_reason in self.trades_df['exit_reason'].unique():
            subset = self.trades_df[self.trades_df['exit_reason'] == exit_reason]
            
            total_trades = len(subset)
            winning_trades = len(subset[subset['is_winning']])
            win_rate = (winning_trades / total_trades) * 100
            total_pl = subset['realized_pl'].sum()
            avg_pl = subset['realized_pl'].mean()
            
            analysis[exit_reason] = {
                'trades': total_trades,
                'percentage': (total_trades / len(self.trades_df)) * 100,
                'win_rate': win_rate,
                'total_pl': total_pl,
                'avg_pl': avg_pl
            }
        
        return analysis
    
    def generate_plots(self, prefix='bt'):
        """Generate visualization plots"""
        if self.trades_df.empty:
            return []
        
        plot_files = []
        
        # 1. Equity Curve
        plt.figure(figsize=(12, 6))
        cumulative_pl = self.trades_df['realized_pl'].cumsum()
        equity_curve = self.results['backtest_info']['initial_balance'] + cumulative_pl
        
        plt.plot(self.trades_df['exit_time'], equity_curve, linewidth=2)
        plt.title('Equity Curve')
        plt.xlabel('Date')
        plt.ylabel('Account Balance ($)')
        plt.grid(True)
        plt.xticks(rotation=45)
        plt.tight_layout()
        
        filename = f'{prefix}_equity_curve.png'
        filepath = os.path.join(self.output_dir, filename)
        plt.savefig(filepath, dpi=300, bbox_inches='tight')
        plt.close()
        plot_files.append(filename)
        
        # 2. Drawdown Chart
        plt.figure(figsize=(12, 6))
        running_max = equity_curve.expanding().max()
        drawdown = equity_curve - running_max
        
        plt.fill_between(self.trades_df['exit_time'], drawdown, 0, alpha=0.7, color='red')
        plt.title('Drawdown Chart')
        plt.xlabel('Date')
        plt.ylabel('Drawdown ($)')
        plt.grid(True)
        plt.xticks(rotation=45)
        plt.tight_layout()
        
        filename = f'{prefix}_drawdown.png'
        filepath = os.path.join(self.output_dir, filename)
        plt.savefig(filepath, dpi=300, bbox_inches='tight')
        plt.close()
        plot_files.append(filename)
        
        # 3. Trade P&L Distribution
        plt.figure(figsize=(10, 6))
        plt.hist(self.trades_df['realized_pl'], bins=20, alpha=0.7, edgecolor='black')
        plt.axvline(x=0, color='red', linestyle='--', linewidth=2)
        plt.title('Trade P&L Distribution')
        plt.xlabel('P&L ($)')
        plt.ylabel('Frequency')
        plt.grid(True)
        plt.tight_layout()
        
        filename = f'{prefix}_pl_distribution.png'
        filepath = os.path.join(self.output_dir, filename)
        plt.savefig(filepath, dpi=300, bbox_inches='tight')
        plt.close()
        plot_files.append(filename)
        
        # 4. Win/Loss by Market Condition
        market_analysis = self.analyze_by_market_conditions()
        if market_analysis:
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
            
            # Win rates
            markets = list(market_analysis.keys())
            win_rates = [market_analysis[m]['win_rate'] for m in markets]
            trades_count = [market_analysis[m]['trades'] for m in markets]
            
            ax1.bar(markets, win_rates, alpha=0.7)
            ax1.set_title('Win Rate by Market Condition')
            ax1.set_ylabel('Win Rate (%)')
            ax1.set_ylim(0, 100)
            
            # Add trade count labels
            for i, (market, count) in enumerate(zip(markets, trades_count)):
                ax1.text(i, win_rates[i] + 2, f'n={count}', ha='center')
            
            # Total P&L
            total_pls = [market_analysis[m]['total_pl'] for m in markets]
            colors = ['green' if pl > 0 else 'red' for pl in total_pls]
            ax2.bar(markets, total_pls, alpha=0.7, color=colors)
            ax2.set_title('Total P&L by Market Condition')
            ax2.set_ylabel('Total P&L ($)')
            ax2.axhline(y=0, color='black', linestyle='-', linewidth=1)
            
            plt.tight_layout()
            
            filename = f'{prefix}_market_analysis.png'
            filepath = os.path.join(self.output_dir, filename)
            plt.savefig(filepath, dpi=300, bbox_inches='tight')
            plt.close()
            plot_files.append(filename)
        
        # 5. Position Type Analysis
        position_analysis = self.analyze_by_position_type()
        if position_analysis:
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 6))
            
            positions = list(position_analysis.keys())
            win_rates = [position_analysis[p]['win_rate'] for p in positions]
            total_pls = [position_analysis[p]['total_pl'] for p in positions]
            trades_count = [position_analysis[p]['trades'] for p in positions]
            
            # Win rates
            ax1.bar(positions, win_rates, alpha=0.7, color=['blue', 'orange'])
            ax1.set_title('Win Rate by Position Type')
            ax1.set_ylabel('Win Rate (%)')
            ax1.set_ylim(0, 100)
            
            # Add trade count labels
            for i, (pos, count) in enumerate(zip(positions, trades_count)):
                ax1.text(i, win_rates[i] + 2, f'n={count}', ha='center')
            
            # Total P&L
            colors = ['green' if pl > 0 else 'red' for pl in total_pls]
            ax2.bar(positions, total_pls, alpha=0.7, color=colors)
            ax2.set_title('Total P&L by Position Type')
            ax2.set_ylabel('Total P&L ($)')
            ax2.axhline(y=0, color='black', linestyle='-', linewidth=1)
            
            plt.tight_layout()
            
            filename = f'{prefix}_position_analysis.png'
            filepath = os.path.join(self.output_dir, filename)
            plt.savefig(filepath, dpi=300, bbox_inches='tight')
            plt.close()
            plot_files.append(filename)
        
        return plot_files
    
    def generate_csv_report(self, prefix='bt'):
        """Generate CSV report of all trades"""
        if self.trades_df.empty:
            return None
        
        # Enhanced CSV with additional calculated fields
        csv_df = self.trades_df.copy()
        csv_df['cumulative_pl'] = csv_df['realized_pl'].cumsum()
        csv_df['running_balance'] = self.results['backtest_info']['initial_balance'] + csv_df['cumulative_pl']
        
        # Add percentage returns
        csv_df['return_pct'] = (csv_df['realized_pl'] / self.results['backtest_info']['initial_balance']) * 100
        csv_df['cumulative_return_pct'] = (csv_df['cumulative_pl'] / self.results['backtest_info']['initial_balance']) * 100
        
        filename = f'{prefix}_{self.results["backtest_info"]["instrument"]}_{self.results["backtest_info"]["timeframe"]}_trades.csv'
        filepath = os.path.join(self.output_dir, filename)
        csv_df.to_csv(filepath, index=False)
        
        return filename
    
    def generate_summary_report(self, prefix='bt'):
        """Generate comprehensive text summary report"""
        advanced_metrics = self.calculate_advanced_metrics()
        market_analysis = self.analyze_by_market_conditions()
        position_analysis = self.analyze_by_position_type()
        exit_analysis = self.analyze_exit_reasons()
        
        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append("COMPREHENSIVE BACKTEST REPORT")
        report_lines.append("=" * 80)
        
        # Backtest Information
        info = self.results['backtest_info']
        report_lines.append(f"Instrument: {info['instrument']}")
        report_lines.append(f"Timeframe: {info['timeframe']}")
        report_lines.append(f"Account Config: {info['account']}")
        report_lines.append(f"Initial Balance: ${info['initial_balance']:,.2f}")
        report_lines.append(f"Final Balance: ${info['final_balance']:,.2f}")
        
        if self.trades_df.empty:
            report_lines.append("\nNo trades executed during backtest period.")
            report_text = "\n".join(report_lines)
            filename = f'{prefix}_{info["instrument"]}_{info["timeframe"]}_summary.txt'
            filepath = os.path.join(self.output_dir, filename)
            with open(filepath, 'w') as f:
                f.write(report_text)
            return filename
        
        report_lines.append(f"Backtest Period: {self.trades_df['entry_time'].min()} to {self.trades_df['exit_time'].max()}")
        report_lines.append("")
        
        # Performance Summary
        report_lines.append("PERFORMANCE SUMMARY")
        report_lines.append("-" * 40)
        perf = advanced_metrics['performance_metrics']
        basic = advanced_metrics['basic_metrics']
        
        report_lines.append(f"Total Return: ${perf['total_return']:,.2f} ({perf['total_return_pct']:+.2f}%)")
        report_lines.append(f"Total Trades: {basic['total_trades']}")
        report_lines.append(f"Winning Trades: {basic['winning_trades']} ({basic['win_rate']:.1f}%)")
        report_lines.append(f"Losing Trades: {basic['losing_trades']} ({100 - basic['win_rate']:.1f}%)")
        report_lines.append(f"Average Win: ${basic['avg_win']:,.2f}")
        report_lines.append(f"Average Loss: ${basic['avg_loss']:,.2f}")
        report_lines.append(f"Best Trade: ${basic['max_win']:,.2f}")
        report_lines.append(f"Worst Trade: ${basic['max_loss']:,.2f}")
        report_lines.append(f"Profit Factor: {perf['profit_factor']:.2f}")
        report_lines.append(f"Expectancy: ${perf['expectancy']:,.2f}")
        report_lines.append("")
        
        # Risk Metrics
        report_lines.append("RISK ANALYSIS")
        report_lines.append("-" * 40)
        risk = advanced_metrics['risk_metrics']
        
        report_lines.append(f"Maximum Drawdown: ${risk['max_drawdown']:,.2f} ({risk['max_drawdown_pct']:.2f}%)")
        report_lines.append(f"Recovery Factor: {perf['recovery_factor']:.2f}")
        report_lines.append(f"Sharpe Ratio: {perf['sharpe_ratio']:.2f}")
        report_lines.append(f"Max Consecutive Wins: {risk['max_consecutive_wins']}")
        report_lines.append(f"Max Consecutive Losses: {risk['max_consecutive_losses']}")
        report_lines.append("")
        
        # Market Conditions Analysis
        report_lines.append("MARKET CONDITIONS ANALYSIS")
        report_lines.append("-" * 40)
        for market, data in market_analysis.items():
            if data['trades'] > 0:
                report_lines.append(f"{market} Market:")
                report_lines.append(f"  Trades: {data['trades']}")
                report_lines.append(f"  Win Rate: {data['win_rate']:.1f}%")
                report_lines.append(f"  Total P&L: ${data['total_pl']:,.2f}")
                report_lines.append(f"  Avg P&L: ${data['avg_pl']:,.2f}")
                report_lines.append("")
        
        # Position Type Analysis
        report_lines.append("POSITION TYPE ANALYSIS")
        report_lines.append("-" * 40)
        for position, data in position_analysis.items():
            if data['trades'] > 0:
                report_lines.append(f"{position} Positions:")
                report_lines.append(f"  Trades: {data['trades']}")
                report_lines.append(f"  Win Rate: {data['win_rate']:.1f}%")
                report_lines.append(f"  Total P&L: ${data['total_pl']:,.2f}")
                report_lines.append(f"  Avg P&L: ${data['avg_pl']:,.2f}")
                report_lines.append("")
        
        # Exit Reasons Analysis
        report_lines.append("EXIT REASONS ANALYSIS")
        report_lines.append("-" * 40)
        for reason, data in exit_analysis.items():
            report_lines.append(f"{reason}:")
            report_lines.append(f"  Trades: {data['trades']} ({data['percentage']:.1f}%)")
            report_lines.append(f"  Win Rate: {data['win_rate']:.1f}%")
            report_lines.append(f"  Avg P&L: ${data['avg_pl']:,.2f}")
            report_lines.append("")
        
        # Trade Duration Analysis
        report_lines.append("TRADE DURATION ANALYSIS")
        report_lines.append("-" * 40)
        report_lines.append(f"Average Duration: {basic['avg_duration_hours']:.1f} hours")
        report_lines.append(f"Shortest Trade: {self.trades_df['duration_hours'].min():.1f} hours")
        report_lines.append(f"Longest Trade: {self.trades_df['duration_hours'].max():.1f} hours")
        report_lines.append("")
        
        # Monthly/Weekly Performance (if data spans multiple periods)
        if len(self.trades_df) > 10:
            report_lines.append("TEMPORAL ANALYSIS")
            report_lines.append("-" * 40)
            
            # Group by month
            monthly_df = self.trades_df.copy()
            monthly_df['month'] = monthly_df['exit_time'].dt.to_period('M')
            monthly_stats = monthly_df.groupby('month').agg({
                'realized_pl': ['count', 'sum', 'mean'],
                'is_winning': 'mean'
            }).round(2)
            
            report_lines.append("Monthly Performance:")
            for month, stats in monthly_stats.iterrows():
                trades = int(stats[('realized_pl', 'count')])
                total_pl = stats[('realized_pl', 'sum')]
                win_rate = stats[('is_winning', 'mean')] * 100
                report_lines.append(f"  {month}: {trades} trades, ${total_pl:+.2f}, {win_rate:.1f}% win rate")
            
        report_lines.append("")
        report_lines.append("=" * 80)
        report_lines.append(f"Report Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append("=" * 80)
        
        # Save report
        report_text = "\n".join(report_lines)
        filename = f'{prefix}_{info["instrument"]}_{info["timeframe"]}_summary.txt'
        filepath = os.path.join(self.output_dir, filename)
        
        with open(filepath, 'w') as f:
            f.write(report_text)
        
        return filename
    
    def generate_json_report(self, prefix='bt'):
        """Generate machine-readable JSON report"""
        advanced_metrics = self.calculate_advanced_metrics()
        market_analysis = self.analyze_by_market_conditions()
        position_analysis = self.analyze_by_position_type()
        exit_analysis = self.analyze_exit_reasons()
        
        json_report = {
            'backtest_info': self.results['backtest_info'],
            'advanced_metrics': advanced_metrics,
            'market_analysis': market_analysis,
            'position_analysis': position_analysis,
            'exit_analysis': exit_analysis,
            'generation_time': datetime.now().isoformat()
        }
        
        filename = f'{prefix}_{self.results["backtest_info"]["instrument"]}_{self.results["backtest_info"]["timeframe"]}_report.json'
        filepath = os.path.join(self.output_dir, filename)
        
        with open(filepath, 'w') as f:
            json.dump(json_report, f, indent=2, default=str)
        
        return filename
    
    def generate_complete_report(self, prefix='bt'):
        """Generate all report formats"""
        print(f"Generating comprehensive backtest reports with prefix '{prefix}'...")
        
        generated_files = []
        
        # Generate plots
        try:
            plot_files = self.generate_plots(prefix)
            generated_files.extend(plot_files)
            print(f"✓ Generated {len(plot_files)} visualization plots")
        except Exception as e:
            print(f"⚠ Warning: Failed to generate plots: {e}")
        
        # Generate CSV report
        try:
            csv_file = self.generate_csv_report(prefix)
            if csv_file:
                generated_files.append(csv_file)
                print("✓ Generated detailed CSV trades report")
        except Exception as e:
            print(f"⚠ Warning: Failed to generate CSV report: {e}")
        
        # Generate text summary
        try:
            summary_file = self.generate_summary_report(prefix)
            if summary_file:
                generated_files.append(summary_file)
                print("✓ Generated comprehensive text summary")
        except Exception as e:
            print(f"⚠ Warning: Failed to generate text summary: {e}")
        
        # Generate JSON report
        try:
            json_file = self.generate_json_report(prefix)
            if json_file:
                generated_files.append(json_file)
                print("✓ Generated machine-readable JSON report")
        except Exception as e:
            print(f"⚠ Warning: Failed to generate JSON report: {e}")
        
        print(f"\nReport generation completed. {len(generated_files)} files generated in {self.output_dir}/")
        print("Files generated:")
        for file in generated_files:
            print(f"  - {file}")
        
        return generated_files


def main():
    """CLI for report generator"""
    import argparse
    import json
    
    parser = argparse.ArgumentParser(description='Generate comprehensive backtest reports')
    parser.add_argument('results_file', help='JSON file containing backtest results')
    parser.add_argument('--prefix', default='bt', help='Prefix for output files')
    parser.add_argument('--output-dir', default='backtest/results', help='Output directory')
    
    args = parser.parse_args()
    
    # Load results
    with open(args.results_file, 'r') as f:
        results = json.load(f)
    
    # Convert trade dictionaries back to objects (simplified for this example)
    # In practice, you might want to pickle/unpickle the full objects
    
    # Generate reports
    generator = BacktestReportGenerator(results, args.output_dir)
    generator.generate_complete_report(args.prefix)


if __name__ == "__main__":
    main()