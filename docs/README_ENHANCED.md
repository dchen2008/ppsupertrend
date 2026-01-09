# Enhanced Multi-Configuration Trading Bot

This enhanced version of the Pivot Point SuperTrend Trading Bot supports running multiple configurations concurrently with different parameters for testing and comparison.

## Features

- **Multiple Timeframes**: 5-minute (M5) or 15-minute (M15) candles
- **Multiple Stop Loss Strategies**:
  - SuperTrend: Uses SuperTrend line +/- 5 pips
  - PPCenterLine: Uses Pivot Point center line
- **Concurrent Execution**: Run multiple bot instances simultaneously without conflicts
- **CSV Logging**: Each configuration logs trades to separate CSV files
- **Thread-Safe**: Each bot instance manages its own state and logs

## File Structure

```
ppSuperTrend/
├── trading_bot_enhanced.py    # Enhanced bot with CLI arguments
├── auto_trade.sh              # Launch script for single configuration
├── run_all_tests.sh           # Launch all 4 configurations at once
├── stop_all_bots.sh           # Stop all running bot instances
├── logs/                      # Console output logs
├── EUR_USD_5m_sl-SuperTrend.csv
├── EUR_USD_15m_sl-SuperTrend.csv
├── EUR_USD_5m_sl-PPCenterLine.csv
└── EUR_USD_15m_sl-PPCenterLine.csv
```

## Usage

### Single Bot Instance

Run a single bot with specific parameters:

```bash
# 5-minute timeframe with SuperTrend stop loss
./auto_trade.sh EUR_USD tf:5m sl:SuperTrend

# 15-minute timeframe with SuperTrend stop loss
./auto_trade.sh EUR_USD tf:15m sl:SuperTrend

# 5-minute timeframe with PPCenterLine stop loss
./auto_trade.sh EUR_USD tf:5m sl:PPCenterLine

# 15-minute timeframe with PPCenterLine stop loss
./auto_trade.sh EUR_USD tf:15m sl:PPCenterLine
```

**Parameters:**
- `EUR_USD` - Trading instrument (currency pair)
- `tf:5m` or `tf:15m` - Timeframe (5-minute or 15-minute candles)
- `sl:SuperTrend` or `sl:PPCenterLine` - Stop loss strategy (case insensitive)

### Multiple Concurrent Bots

Run all 4 configurations simultaneously:

```bash
./run_all_tests.sh
```

This will launch:
1. EUR_USD 5m + SuperTrend → `EUR_USD_5m_sl-SuperTrend.csv`
2. EUR_USD 15m + SuperTrend → `EUR_USD_15m_sl-SuperTrend.csv`
3. EUR_USD 5m + PPCenterLine → `EUR_USD_5m_sl-PPCenterLine.csv`
4. EUR_USD 15m + PPCenterLine → `EUR_USD_15m_sl-PPCenterLine.csv`

To stop all running bots:

```bash
./stop_all_bots.sh
```

Or press `Ctrl+C` in the terminal running `run_all_tests.sh`.

## CSV Log Format

Each trade is logged to a CSV file with the following columns:

| Column | Description | Example |
|--------|-------------|---------|
| name | Trading instrument | EUR_USD |
| orderTime | Timestamp of order | 2026-01-04 19:37:30 |
| Signal | Position direction | LONG or SHORT |
| Type | Order type | buy, sell, or CLOSE |
| position_size | Number of units | 1 |
| stopLoss | Stop loss price | 1.16500 |
| OrderPrice | Entry/execution price | 1.17146 |
| ClosePrice | Exit price (N/A for opens) | 1.18146 or N/A |
| profit | Profit/Loss amount | $150.00 or -$50.00 |
| accountBalance | Account balance after trade | 100150.50 |

Example CSV content:
```csv
name,orderTime,Signal,Type,position_size,stopLoss,OrderPrice,ClosePrice,profit,accountBalance
EUR_USD,2026-01-04 19:37:30,SHORT,sell,1,1.17500,1.17146,N/A,$0.00,100000.00
EUR_USD,2026-01-04 20:15:45,SHORT,CLOSE,1,1.17500,1.17146,1.16146,$100.00,100100.00
EUR_USD,2026-01-04 21:00:12,LONG,buy,1,1.16500,1.16800,N/A,$0.00,100100.00
EUR_USD,2026-01-04 22:30:20,LONG,CLOSE,1,1.16500,1.16800,1.16300,-$50.00,100050.00
```

## Stop Loss Strategies

### SuperTrend Strategy
- **For Buy (Long) Positions**: Stop loss = SuperTrend line - 5 pips
- **For Sell (Short) Positions**: Stop loss = SuperTrend line + 5 pips
- Provides a buffer below/above the SuperTrend line

### PPCenterLine Strategy
- **For All Positions**: Stop loss = Pivot Point center line
- Uses the dynamic center line calculated from pivot points
- Center line adapts to market structure

## Configuration

Edit `config.py` to adjust:

```python
class TradingConfig:
    # Position size per trade
    position_size = 1  # Units (keep small for testing)

    # Risk management
    risk_per_trade = 0.02  # 2% risk per trade
    use_dynamic_sizing = False  # Enable to calculate size based on balance

    # Pivot Point SuperTrend parameters
    pivot_period = 2
    atr_factor = 3.0
    atr_period = 10

    # Trailing stop
    enable_trailing_stop = True
    min_stop_update_distance = 0.00010  # 1 pip minimum movement

    # Bot behavior
    check_interval = 30  # Check every 30 seconds
    lookback_candles = 100  # History for calculations
```

## Process Isolation

Each bot instance is fully isolated:

- **Separate CSV files**: Named by configuration (e.g., `EUR_USD_5m_sl-SuperTrend.csv`)
- **Separate log files**: Named by configuration (e.g., `bot_EUR_USD_5m_SuperTrend.log`)
- **Separate loggers**: Each instance has a unique logger to avoid conflicts
- **Thread-safe CSV writing**: File locking prevents concurrent write conflicts
- **Independent state tracking**: Each bot maintains its own position state

## Monitoring

### View Live Logs

To monitor a specific bot:
```bash
tail -f bot_EUR_USD_5m_SuperTrend.log
```

To monitor console output of all bots:
```bash
tail -f logs/*.out
```

### Check CSV Results

View trades from a specific configuration:
```bash
cat EUR_USD_5m_sl-SuperTrend.csv
```

Calculate win rate:
```bash
# Count wins and losses
python3 -c "
import pandas as pd
df = pd.read_csv('EUR_USD_5m_sl-SuperTrend.csv')
closes = df[df['Type'] == 'CLOSE']
wins = len(closes[closes['profit'].str.contains('-') == False])
losses = len(closes[closes['profit'].str.contains('-')])
total = wins + losses
print(f'Win Rate: {wins}/{total} ({100*wins/total:.1f}%)')
"
```

## Testing Workflow

1. **Start all configurations**:
   ```bash
   ./run_all_tests.sh
   ```

2. **Let them run** for a period (hours/days) to collect data

3. **Stop all bots**:
   ```bash
   ./stop_all_bots.sh
   ```

4. **Analyze CSV files** to compare:
   - Win/loss rates across configurations
   - Total profit/loss per configuration
   - Number of trades per timeframe
   - Stop loss strategy effectiveness

5. **Compare results** to determine optimal configuration

## Important Notes

- **Practice Mode**: Set `OANDAConfig.is_practice = True` for testing
- **Position Size**: Keep `position_size = 1` for minimal risk during testing
- **API Limits**: OANDA has rate limits; running many instances may hit limits
- **Resource Usage**: Each bot consumes CPU/memory; monitor system resources
- **Data Freshness**: 5m bots update more frequently than 15m bots

## Troubleshooting

**Issue**: Bot exits immediately
- Check log files in `logs/` directory
- Verify OANDA API credentials in `config.py`
- Ensure Python dependencies are installed

**Issue**: CSV file has no data
- Bot may not have opened any trades yet
- Check log file for trade signals
- Verify market conditions (may be in consolidation)

**Issue**: "Process ID not found"
- Bots may have crashed; check `logs/*.out` for errors
- Remove `bot_pids.txt` and restart

**Issue**: Stop loss update errors
- Ensure `current_trade_id` is being tracked correctly
- Check OANDA API response in detailed logs

## Python Direct Usage

You can also run the enhanced bot directly with Python:

```bash
python3 trading_bot_enhanced.py EUR_USD tf:5m sl:SuperTrend
```

This is equivalent to using `auto_trade.sh` but gives you more direct control.

## License

For educational and testing purposes only. Use at your own risk.
