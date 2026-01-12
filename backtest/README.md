# Comprehensive Backtest System

This backtest system replicates the exact trading logic of the market-aware trading bot for historical simulation and strategy analysis.

## Features

- 🔄 **Exact Bot Logic Replication**: Uses the same PP SuperTrend indicators, market trend detection, and risk management
- 📊 **Market-Aware Strategy**: Implements dynamic risk/reward ratios based on 3H market trend (bull/bear)
- 📈 **Comprehensive Reports**: Industry-standard metrics, visualizations, and detailed analysis
- ⚡ **Optimized Data Download**: Efficient OANDA API usage with caching
- 🎯 **Multiple Output Formats**: CSV trades log, summary reports, JSON data, and charts
- 🔧 **Configurable**: Supports all account configurations and trading parameters

## Quick Setup

```bash
# From project root directory
./setup_backtest.sh

# Or manually install dependencies:
pip install -r requirements_backtest.txt
```

## Usage Examples

### Command Line Options

Both Python and shell script versions support the same command format:

**Required Parameters:**
- `at=<account>` - Account configuration (account1, account2, etc.)
- `fr=<instrument>` - Trading instrument (EUR_USD, GBP_USD, etc.)
- `tf=<timeframe>` - Trading timeframe (5m or 15m)
- `bt=<days>` - Backtest period (30d, 90d, etc.)

**Optional Parameters:**
- `--balance=<amount>` - Initial balance (default: 10000)
- `--refresh` - Force refresh cached data
- `--parallel` - Run in background (shell script only)

### Python Version (Recommended)

```bash
# Basic backtest
python3 backtest/src/main_backtest.py at=account1 fr=EUR_USD tf=5m bt=30d

# With custom balance
python3 backtest/src/main_backtest.py at=account2 fr=GBP_USD tf=15m bt=90d --balance=25000

# Force refresh data
python3 backtest/src/main_backtest.py at=account1 fr=EUR_USD tf=5m bt=60d --refresh
```

### Shell Script Version

```bash
# Basic backtest
./backtest/scripts/bt_auto_trade_market.sh at=account1 fr=EUR_USD tf=5m bt=30d

# With custom balance
./backtest/scripts/bt_auto_trade_market.sh at=account2 fr=GBP_USD tf=15m bt=90d balance=25000

# Background execution
./backtest/scripts/bt_auto_trade_market.sh at=account1 fr=EUR_USD tf=5m bt=30d parallel=true
```

## Output Files

All output files use the prefix format: `bt_<instrument>_<timeframe>_<account>_<days>d_<timestamp>`

### Generated Reports

1. **Equity Curve Chart** (`*_equity_curve.png`)
   - Account balance progression over time
   - Visual representation of trading performance

2. **Drawdown Chart** (`*_drawdown.png`)
   - Maximum drawdown periods
   - Risk visualization

3. **P&L Distribution** (`*_pl_distribution.png`)
   - Histogram of trade outcomes
   - Win/loss distribution analysis

4. **Market Analysis Charts** (`*_market_analysis.png`)
   - Performance by market conditions (bull/bear/neutral)
   - Win rates and profitability by trend

5. **Position Analysis** (`*_position_analysis.png`)
   - LONG vs SHORT position performance
   - Direction bias analysis

6. **Detailed Trades CSV** (`*_trades.csv`)
   - Complete trade log with all metrics
   - Entry/exit prices, durations, P&L tracking

7. **Summary Report** (`*_summary.txt`)
   - Comprehensive text-based performance analysis
   - Industry-standard trading metrics

8. **JSON Report** (`*_report.json`)
   - Machine-readable results for further analysis
   - Complete trading statistics and metadata

### Key Metrics Included

**Performance Metrics:**
- Total Return ($ and %)
- Win Rate
- Profit Factor
- Sharpe Ratio
- Expectancy
- Average Win/Loss

**Risk Metrics:**
- Maximum Drawdown
- Recovery Factor
- Consecutive Wins/Losses
- Risk/Reward Analysis

**Market Analysis:**
- Performance by market trend (Bull/Bear/Neutral)
- Position type effectiveness (LONG vs SHORT)
- Exit reason analysis (Stop Loss, Take Profit, Signal Reversal)

## Architecture

```
backtest/
├── src/
│   ├── data_downloader.py      # Historical data fetching with caching
│   ├── backtest_engine.py      # Core backtest simulation engine  
│   ├── report_generator.py     # Comprehensive report generation
│   └── main_backtest.py        # Main orchestration script
├── scripts/
│   └── bt_auto_trade_market.sh # Shell wrapper script
├── data/                       # Cached historical data
├── results/                    # Generated reports and outputs
└── logs/                       # Execution logs
```

## Key Features

### Market-Aware Logic
- **3H Trend Detection**: Uses PP SuperTrend on H3 timeframe for market direction
- **Dynamic Risk/Reward**: 
  - Bull market: Long R:R = 1.2, Short R:R = 0.6
  - Bear market: Short R:R = 1.2, Long R:R = 0.6
  - Neutral market: R:R = 1.0

### Risk Management
- **Position Sizing**: Dynamic sizing based on market trend and risk per trade
- **Stop Loss**: SuperTrend or Pivot Point center line based
- **Take Profit**: Automatically calculated based on R:R ratio
- **Spread Adjustment**: Accounts for bid/ask spread in stop loss placement

### Data Management  
- **Smart Caching**: Avoids redundant API calls
- **Rate Limiting**: Respects OANDA API limits
- **Error Handling**: Robust retry logic and fallback mechanisms

## Configuration

The backtest system uses the same configuration hierarchy as the live trading bot:

1. **Default Configuration**: `src/config.yaml`
2. **Account-Specific Overrides**: `<account>/config.yaml`

Example account-specific configuration:
```yaml
# account2/config.yaml - More aggressive settings
check_interval: 45
risk_reward:
  bear_market:
    short_rr: 1.5  # More aggressive than default 1.2
    long_rr: 0.5
  bull_market:
    short_rr: 0.5  
    long_rr: 1.5   # More aggressive than default 1.2
```

## Validation & Accuracy

The backtest engine replicates the live trading bot logic with high fidelity:

- ✅ Same PP SuperTrend calculation
- ✅ Identical signal generation logic
- ✅ Market trend detection matching live bot
- ✅ Risk/reward calculations
- ✅ Position sizing algorithms
- ✅ Stop loss and take profit placement

## Performance Optimization

- **Vectorized Calculations**: Uses pandas for efficient indicator computation
- **Minimal API Calls**: Smart data download with chunking and caching
- **Memory Efficient**: Processes data in optimized batches
- **Parallel Execution**: Shell script supports background execution

## Troubleshooting

### Common Issues

1. **Import Errors**: Make sure to run from project root directory
2. **Missing Dependencies**: Run `pip install -r requirements_backtest.txt`
3. **API Connection**: Verify OANDA credentials in `src/config.py`
4. **Data Download**: Check internet connection and API limits

### Debug Mode

Add `--log-level=DEBUG` for detailed execution information:
```bash
python3 backtest/src/main_backtest.py at=account1 fr=EUR_USD tf=5m bt=30d --log-level=DEBUG
```

## Integration with Live Trading

The backtest system is designed to run independently without affecting live trading:

- ✅ Separate execution environment
- ✅ No impact on live bot processes
- ✅ Uses same account configurations safely
- ✅ Parallel execution support

## Example Results

A typical 30-day backtest might show:
```
BACKTEST RESULTS
================
Instrument: EUR_USD (5m)
Period: 30 days
Total Trades: 127
Win Rate: 45.7%
Total Return: $387.42 (+3.87%)
Profit Factor: 1.23
Max Drawdown: -2.45%
```

## Support

For issues or questions:
1. Check the logs in `backtest/logs/`
2. Review the generated reports in `backtest/results/`
3. Verify configuration in account-specific YAML files
4. Ensure all dependencies are installed correctly