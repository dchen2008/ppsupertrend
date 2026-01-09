# Pivot Point SuperTrend Auto Trading Bot

Automated trading bot for EUR/USD using the Pivot Point SuperTrend indicator strategy on OANDA.

## Features

- **Pivot Point SuperTrend Indicator**: Advanced trend-following indicator combining pivot points with SuperTrend methodology
- **Automated Trading**: Fully automated buy/sell signal execution
- **Trailing Stop Loss**: Dynamic stop loss that follows SuperTrend line, locking in profits ⭐ NEW!
- **Risk Management**: Built-in position sizing and profit protection
- **OANDA Integration**: Direct connection to OANDA's REST API
- **Real-time Monitoring**: Continuous market monitoring every 30 seconds
- **Practice/Live Mode**: Safe testing in practice account before going live

## Project Structure

```
ppSuperTrend/
├── config.py              # Configuration settings (OANDA credentials, trading parameters)
├── oanda_client.py        # OANDA API client (market data, order execution)
├── indicators.py          # Pivot Point SuperTrend indicator calculations
├── risk_manager.py        # Risk management and position sizing
├── trading_bot.py         # Main trading bot logic
├── test_connection.py     # Connection test script
├── requirements.txt       # Python dependencies
└── README.md             # This file
```

## Installation

### 1. Install Python Dependencies

```bash
pip install -r requirements.txt
```

Required packages:
- `pandas>=2.0.0` - Data manipulation
- `numpy>=1.24.0` - Numerical computations
- `requests>=2.31.0` - HTTP API requests

### 2. Verify OANDA Credentials

Your OANDA credentials are already configured in `config.py`:
- **Account ID**: 101-001-35749385-001
- **Mode**: Practice (Demo account)
- **API Key**: Configured

## Configuration

### Trading Parameters (config.py)

You can customize the following parameters in `config.py`:

```python
class TradingConfig:
    # Instrument
    instrument = "EUR_USD"

    # Pivot Point SuperTrend parameters
    pivot_period = 2      # Pivot detection sensitivity (1-50)
    atr_factor = 3.0      # ATR multiplier for bands
    atr_period = 10       # ATR calculation period

    # Position sizing
    position_size = 1000  # Units per trade (1000 = 0.01 lot)

    # Timeframe
    granularity = "M15"   # Options: M1, M5, M15, H1, H4, D

    # Bot behavior
    check_interval = 30   # Check every 30 seconds

    # Trailing stop loss
    enable_trailing_stop = True  # Dynamic stop loss that locks in profits
    min_stop_update_distance = 0.00010  # Update every 1 pip movement
```

### Trailing Stop Loss ⭐ NEW!

The bot features an intelligent trailing stop loss that automatically follows the SuperTrend line as it moves in your favor:

**How it works:**
- Every 30 seconds, the bot checks if the SuperTrend line has moved favorably
- If it has (up for longs, down for shorts), the stop loss is updated via OANDA API
- This **locks in profits** as the trend continues
- Protects against giving back gains when price reverses

**Example:**
```
Entry LONG at 1.10250, Stop at 1.10175 (7.5 pips risk)
Price moves to 1.10300, SuperTrend at 1.10220
→ Stop updated to 1.10215 (now protecting 4 pips profit)

Price moves to 1.10350, SuperTrend at 1.10280
→ Stop updated to 1.10275 (now protecting 25 pips profit)

Price reverses and hits stop at 1.10275
→ Exit with +25 pips instead of potential loss! ✅
```

**Configuration:**
```python
# Enable/disable
enable_trailing_stop = True   # Recommended: True

# Update sensitivity (minimum SuperTrend movement to update stop)
min_stop_update_distance = 0.00010  # 1 pip (default)
min_stop_update_distance = 0.00005  # 0.5 pips (aggressive)
min_stop_update_distance = 0.00020  # 2 pips (conservative)
```

See `TRAILING_STOP_LOSS.md` for complete documentation.

### Parameter Tuning Guide

**Pivot Period (default: 2)**
- Lower (1-2): More sensitive, more signals, more false positives
- Higher (3-5): Less sensitive, fewer signals, more reliable

**ATR Factor (default: 3.0)**
- Lower (1-2): Tighter stops, more frequent signals, more whipsaws
- Higher (4-6): Wider stops, fewer signals, stronger trends only

**Timeframe**
- M1/M5: Scalping (high frequency, requires constant monitoring)
- M15/H1: Intraday trading (recommended for beginners)
- H4/D: Swing trading (fewer signals, longer holds)

## Usage

### Test Connection First

Before running the bot, test your OANDA connection:

```bash
python test_connection.py
```

This will:
- Verify API credentials
- Fetch account information
- Display current balance and positions
- Test market data retrieval

### Run the Trading Bot

```bash
python trading_bot.py
```

The bot will:
1. Connect to OANDA API
2. Fetch historical candle data
3. Calculate Pivot Point SuperTrend indicator
4. Monitor for buy/sell signals
5. Execute trades automatically
6. Log all activities to `trading_bot.log`

### Stop the Bot

Press `Ctrl+C` to gracefully stop the bot.

## Trading Strategy

### Entry Signals

**BUY Signal (Long Entry)**
- Triggered when price crosses above the SuperTrend line
- Trend changes from downtrend (-1) to uptrend (1)
- Stop loss placed at SuperTrend line

**SELL Signal (Short Entry)**
- Triggered when price crosses below the SuperTrend line
- Trend changes from uptrend (1) to downtrend (-1)
- Stop loss placed at SuperTrend line

### Exit Signals

**Exit Long Position**
- When SELL signal occurs (trend reversal)
- Or when stop loss is hit

**Exit Short Position**
- When BUY signal occurs (trend reversal)
- Or when stop loss is hit

### Risk Management

The bot includes several risk management features:

1. **Stop Loss**: Automatically placed at SuperTrend line with small buffer
2. **Position Sizing**: Fixed position size (configurable)
3. **Dynamic Sizing**: Optional risk-based position sizing (2% risk per trade)
4. **Margin Validation**: Checks available margin before placing orders
5. **Trade Validation**: Validates account state before execution

## Monitoring

### Console Output

The bot displays real-time information:
```
2026-01-04 10:30:15 - INFO - Balance: $10000.00 | Unrealized P/L: $0.00 | NAV: $10000.00
2026-01-04 10:30:15 - INFO - Position: None
2026-01-04 10:30:15 - INFO - Signal: HOLD | Price: 1.10250 | SuperTrend: 1.10180 | Trend: UP
```

### Log File

All activities are logged to `trading_bot.log`:
- Trade executions
- Signal changes
- Errors and warnings
- Detailed market data

## Safety Features

### Practice Mode

The bot is configured to run on OANDA's practice (demo) account:
- **No real money at risk**
- Same market data as live
- Test strategies safely

To switch to live mode (NOT RECOMMENDED until thoroughly tested):
```python
# In config.py
class OANDAConfig:
    is_practice = False  # ⚠️ USE WITH EXTREME CAUTION
```

### Risk Warnings

⚠️ **Important Warnings:**
- This is algorithmic trading software
- Past performance does not guarantee future results
- Trading involves substantial risk of loss
- Only trade with capital you can afford to lose
- Test thoroughly in practice mode before considering live trading
- Market conditions can change rapidly
- No strategy wins 100% of the time

## Troubleshooting

### Connection Errors

If you get connection errors:
1. Verify your API key is correct
2. Check your internet connection
3. Ensure OANDA API is accessible (not blocked by firewall)
4. Verify account ID is correct

### No Signals Generated

If the bot isn't generating signals:
1. Check if enough candles are available (need 100+ candles)
2. Verify pivot points are being detected
3. Try adjusting `pivot_period` parameter
4. Check market volatility (low volatility = fewer signals)

### Margin Errors

If trades fail due to margin:
1. Reduce `position_size` in config
2. Check account balance
3. Close existing positions if needed

## Performance Monitoring

Track the following metrics:
- **Win Rate**: % of profitable trades
- **Profit Factor**: Gross profit / Gross loss
- **Max Drawdown**: Largest peak-to-trough decline
- **Sharpe Ratio**: Risk-adjusted returns

Use OANDA's web interface to view detailed trade history and analytics.

## Advanced Customization

### Modify Indicator Parameters

Edit `config.py` to adjust strategy parameters:
```python
pivot_period = 3    # More conservative pivot detection
atr_factor = 2.5    # Tighter stops
atr_period = 14     # Standard ATR period
```

### Add Take Profit

In `trading_bot.py`, uncomment take profit logic:
```python
# Line ~195 in execute_trade()
take_profit = self.risk_manager.calculate_take_profit(
    current_price,
    stop_loss,
    risk_reward_ratio=2.0  # 2:1 reward-risk ratio
)

result = self.client.place_market_order(
    instrument=instrument,
    units=units,
    stop_loss=stop_loss,
    take_profit=take_profit  # Enable take profit
)
```

### Change Instruments

To trade other currency pairs, update `config.py`:
```python
instrument = "GBP_USD"  # Or USD_JPY, AUD_USD, etc.
```

## Support

For OANDA API documentation:
- https://developer.oanda.com/rest-live-v20/introduction/

For strategy questions:
- Review the HTML documentation: `pivot-point-supertrend-documentation.html`

## License

This software is for educational and research purposes only. Use at your own risk.

## Disclaimer

This trading bot is provided "as is" without warranty of any kind. The authors are not responsible for any financial losses incurred through the use of this software. Always test thoroughly in a practice environment and understand the risks before trading with real money.
