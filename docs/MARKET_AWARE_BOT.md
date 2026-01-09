# Market-Aware Trading Bot Documentation

## Overview

The Market-Aware Trading Bot enhances the original PP SuperTrend strategy by incorporating market trend analysis using a higher timeframe (3H) PP SuperTrend signal. This allows the bot to adapt its risk/reward ratios based on the overall market direction (bull/bear), optimizing trade outcomes.

## Key Features

### 1. Market Trend Detection
- Uses 3-hour (H3) PP SuperTrend signals to determine market direction
- Classifications:
  - **BULL Market**: 3H PP SuperTrend shows BUY signal
  - **BEAR Market**: 3H PP SuperTrend shows SELL signal  
  - **NEUTRAL Market**: 3H PP SuperTrend shows HOLD signal

### 2. Dynamic Risk/Reward Ratios
The bot adjusts take profit targets based on market trend and position direction:

#### Bear Market Strategy
- **Short Positions**: R:R = 1.2 (favorable direction)
- **Long Positions**: R:R = 0.6 (conservative, quick profits)

#### Bull Market Strategy  
- **Long Positions**: R:R = 1.2 (favorable direction)
- **Short Positions**: R:R = 0.6 (conservative, quick profits)

#### Neutral Market Strategy
- **All Positions**: R:R = 1.0 (balanced approach)

### 3. Account-Specific Configuration
Each account can have its own `config.yaml` file to customize:
- Check intervals
- Market timeframe
- Risk/reward ratios
- Stop loss strategies

## Configuration System

### Configuration Hierarchy
The bot uses a hierarchical configuration system:
1. **Default Configuration** (`src/config.yaml`) - Base settings for all accounts
2. **Account-Specific Configuration** (`account1/config.yaml`, etc.) - Overrides default settings

### Default Configuration File
```yaml
# Default configuration file: src/config.yaml
# This file contains default settings that apply to all accounts

# How often to check signals (seconds)
check_interval: 60

# Market trend detection settings
market:
  indicator: ppsupertrend  # Indicator for market direction
  timeframe: H3            # 3-hour timeframe

# Stop loss configuration
stoploss:
  type: PPSuperTrend      # Trailing stop using PP SuperTrend

# Risk/Reward ratios by market condition
risk_reward:
  bear_market:
    short_rr: 1.2         # Favorable for shorts in bear market
    long_rr: 0.6          # Conservative for longs in bear market
  bull_market:
    short_rr: 0.6         # Conservative for shorts in bull market
    long_rr: 1.2          # Favorable for longs in bull market
```

### Account-Specific Override
```yaml
# Account override file: account2/config.yaml
# Only include settings you want to override from defaults

# More aggressive settings for account2
check_interval: 45

risk_reward:
  bear_market:
    short_rr: 1.5    # More aggressive
    long_rr: 0.5
  bull_market:
    short_rr: 0.5
    long_rr: 1.5     # More aggressive
```

### Configuration Loading Order
1. Bot loads `src/config.yaml` (default configuration)
2. Bot checks for `<account>/config.yaml` 
3. If account config exists, it overrides default values
4. Final configuration = default + account overrides

## Running the Bot

### New Command Format
```bash
./scripts/auto_trade_market.sh at=<account> fr=<instrument> tf=<timeframe>
```

### Parameters
- `at=`: Account to use (account1, account2, account3)
- `fr=`: Currency pair (EUR_USD, GBP_USD, etc.)
- `tf=`: Trading timeframe (5m or 15m)

### Examples
```bash
# Run with account1 configuration
./scripts/auto_trade_market.sh at=account1 fr=EUR_USD tf=5m

# Run with account2 configuration  
./scripts/auto_trade_market.sh at=account2 fr=GBP_USD tf=15m

# Multiple concurrent instances
./scripts/auto_trade_market.sh at=account1 fr=EUR_USD tf=5m &
./scripts/auto_trade_market.sh at=account2 fr=EUR_USD tf=15m &
```

## Trading Logic Flow

1. **Market Check** (every 3 minutes)
   - Fetch 3H candles
   - Calculate 3H PP SuperTrend
   - Determine market trend (BULL/BEAR/NEUTRAL)

2. **Signal Check** (every check_interval seconds)
   - Fetch trading timeframe candles (5m/15m)
   - Calculate PP SuperTrend signals
   - Check for BUY/SELL signals

3. **Position Entry**
   - Calculate position size
   - Set stop loss at PP SuperTrend line
   - Set take profit based on:
     - Current market trend
     - Position direction (long/short)
     - Configured R:R ratios

4. **Position Management**
   - Trail stop loss with PP SuperTrend movement
   - Exit on stop loss hit
   - Exit on take profit hit
   - Exit on trend reversal signal

## CSV Output

The bot logs all trades to CSV with additional columns:

| Column | Description |
|--------|-------------|
| marketTrend | Market trend at trade entry (BULL/BEAR/NEUTRAL) |
| riskRewardTarget | Target R:R ratio used |
| riskRewardActual | Actual R:R achieved |
| takeProfit | Take profit price |
| takeProfitHit | Whether TP was hit (TRUE/FALSE) |

Output location: `<account>/csv/<instrument>_<timeframe>_market_aware.csv`

## Testing

### Configuration Test
```bash
python tests/test_market_aware_bot.py
```

This will:
- Verify configuration loading
- Test risk/reward calculations
- Optionally test live market trend detection

### Dry Run
To test without trading:
1. Use a practice account
2. Monitor the logs: `tail -f account1/logs/bot_*_market_aware.log`
3. Check CSV output for trade records

## Configuration Examples

### Conservative Configuration
```yaml
risk_reward:
  bear_market:
    short_rr: 1.0
    long_rr: 0.5
  bull_market:
    short_rr: 0.5
    long_rr: 1.0
```

### Aggressive Configuration  
```yaml
risk_reward:
  bear_market:
    short_rr: 1.5
    long_rr: 0.5
  bull_market:
    short_rr: 0.5
    long_rr: 1.5
```

### Balanced Configuration
```yaml
risk_reward:
  bear_market:
    short_rr: 1.0
    long_rr: 1.0
  bull_market:
    short_rr: 1.0
    long_rr: 1.0
```

## Advantages

1. **Market Adaptation**: Adjusts strategy based on overall market conditions
2. **Risk Management**: Takes smaller profits against the trend, larger profits with the trend
3. **Flexibility**: Each account can have different risk profiles
4. **Automation**: Fully automated trend detection and trade management

## Important Notes

- The bot checks market trend every 3 minutes to avoid excessive API calls
- Market trend is determined at trade entry and doesn't change during the trade
- Take profit is set at order placement and not modified (only stop loss trails)
- Configuration changes require bot restart to take effect

## Troubleshooting

### Bot doesn't start
- Check OANDA credentials in src/config.py
- Verify default config exists: `src/config.yaml`
- Check Python dependencies: `pip install -r requirements.txt`

### No market trend detected
- Ensure sufficient historical data (100 3H candles)
- Check API connectivity
- Verify instrument is tradeable

### Configuration not loading
- Check YAML syntax in both default and account configs
- Verify file locations:
  - Default: `src/config.yaml`
  - Account: `<account>/config.yaml`
- Review bot logs for configuration messages
- Use test script to verify: `python tests/test_market_aware_bot.py`