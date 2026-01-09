# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This is a Python-based automated forex trading bot that uses the Pivot Point SuperTrend indicator to trade EUR/USD (and other currency pairs) via the OANDA API. The bot has two main versions:
1. **Standard Bot** (`trading_bot_enhanced.py`): Original PP SuperTrend strategy with configurable stop losses
2. **Market-Aware Bot** (`trading_bot_market_aware.py`): Enhanced version that uses 3H timeframe for market trend detection and dynamic risk/reward ratios based on bull/bear market conditions

## Project Structure

```
ppsupertrend/
├── src/
│   ├── config.py                 # OANDA credentials, trading parameters
│   ├── config.yaml               # Default configuration for market-aware bot
│   ├── oanda_client.py           # OANDA API wrapper
│   ├── indicators.py             # Pivot Point SuperTrend calculations
│   ├── risk_manager.py           # Position sizing and stop loss logic
│   ├── trading_bot_enhanced.py   # Standard trading bot
│   └── trading_bot_market_aware.py # Market-aware bot with 3H trend detection
│
├── scripts/
│   ├── auto_trade.sh             # Launch standard bot (old format)
│   ├── auto_trade_market.sh      # Launch market-aware bot (new format)
│   ├── run_all_tests.sh          # Launch multiple bots concurrently
│   ├── stop_all_bots.sh          # Stop all running bots
│   └── kill_duplicate_bots.sh    # Kill duplicate processes
│
├── account1/, account2/, account3/
│   ├── logs/                     # Bot log files
│   ├── csv/                      # Trade result CSV files
│   └── config.yaml               # Account-specific config overrides
│
└── tests/, docs/, requirements.txt
```

## Core Architecture

### Market-Aware Bot Enhancement

The market-aware bot (`trading_bot_market_aware.py`) adds:
- **3H Market Trend Detection**: Uses PP SuperTrend on H3 timeframe to determine bull/bear market
- **Dynamic Risk/Reward**: Adjusts take profit based on market trend and position direction
  - Bear market: Short R:R=1.2 (favorable), Long R:R=0.6 (conservative)
  - Bull market: Long R:R=1.2 (favorable), Short R:R=0.6 (conservative)
- **Configuration Hierarchy**: `src/config.yaml` (defaults) → `account/config.yaml` (overrides)
- **Automatic Take Profit**: Sets TP at order placement based on calculated R:R

### Key Architectural Patterns

**Spread Adjustment**: Critical for accurate stop loss placement
- OANDA uses BID prices to trigger long stop losses, ASK for short stops
- SuperTrend calculations use MID prices
- `use_spread_adjustment=True` adds half-spread buffer to ensure stops trigger when MID price touches SuperTrend line

**Trailing Stop Loss**: Dynamic stop management
- Every `check_interval` seconds, bot checks if SuperTrend moved favorably
- If movement > `min_stop_update_distance`, updates stop via `modify_stop_loss()`
- Only updates in profitable direction (never widens stops)

**Multi-Account Support**:
- `OANDAConfig.ACCOUNTS` dictionary stores multiple account credentials
- `OANDAConfig.set_account(account_name)` switches active account
- Runtime outputs organized by account folder

## Common Commands

```bash
# Install dependencies (including PyYAML for market-aware bot)
pip install -r requirements.txt

# Test OANDA connection
python tests/test_connection.py

# Run standard bot (old format)
./scripts/auto_trade.sh EUR_USD tf:5m sl:SuperTrend account1

# Run market-aware bot (new format with 3H trend detection)
./scripts/auto_trade_market.sh at=account1 fr=EUR_USD tf=5m

# Test market-aware configuration
python tests/test_market_aware_bot.py

# Test individual components
python tests/test_dynamic_sizing.py
python tests/test_spread_adjustment.py

# Monitor logs
tail -f account1/logs/bot_EUR_USD_5m_market_aware.log

# Check CSV results
cat account1/csv/EUR_USD_5m_market_aware.csv
```

## Configuration Hierarchy (Market-Aware Bot)

1. **Default Configuration** (`src/config.yaml`): Base settings for all accounts
2. **Account Override** (`account1/config.yaml`): Only include settings to override

Example account override:
```yaml
# account2/config.yaml - Aggressive configuration
check_interval: 45
risk_reward:
  bear_market:
    short_rr: 1.5  # More aggressive than default 1.2
    long_rr: 0.5
  bull_market:
    short_rr: 0.5
    long_rr: 1.5   # More aggressive than default 1.2
```

## Important Implementation Details

### API Retry Logic
All OANDA API calls use `@api_retry_handler` decorator:
- Retries up to 3 times with 1 second delay
- Handles Timeout, ConnectionError, RequestException
- Returns `None` on failure after exhausting retries

### Stop Loss Updates
`modify_stop_loss()` requires the trade ID, NOT the stop loss order ID:
- `current_trade_id`: Used for stop modification
- `current_stop_loss_order_id`: Stored for reference only

### CSV Output Schema

**Standard Bot** fields:
```
tradeID, name, orderTime, closeTime, duration, superTrend, pivotPoint, signal,
type, positionSize, enterPrice, stopLoss, closePrice, highestPrice, lowestPrice,
highestProfit, lowestLoss, stopLossHit, riskRewardRatio, profit, accountBalance
```

**Market-Aware Bot** additional fields:
```
takeProfit, takeProfitHit, marketTrend, riskRewardTarget, riskRewardActual
```

### Indicator Lag
Pivot detection requires `period` bars on both sides, introducing `2 * period` bar lag. Signals only generated after sufficient historical data.

## Strategy Parameters

Key parameters in `src/config.py`:
- `pivot_period` (default: 2): Lower = more sensitive
- `atr_factor` (default: 3.0): ATR band multiplier
- `atr_period` (default: 10): ATR calculation period
- `check_interval` (default: 60): Seconds between checks
- `enable_trailing_stop` (default: True): Dynamic stop management
- `min_stop_update_distance` (default: 0.00010): Minimum movement to update stop

## Multi-Account Testing

1. Add accounts to `src/config.py`:
```python
ACCOUNTS = {
    'account1': {'api_key': '...', 'account_id': '...', 'is_practice': True},
    'account2': {'api_key': '...', 'account_id': '...', 'is_practice': True},
}
```

2. Launch concurrent instances:
```bash
# Standard bot
./scripts/auto_trade.sh EUR_USD tf:5m sl:SuperTrend account1 &
./scripts/auto_trade.sh EUR_USD tf:15m sl:PPCenterLine account2 &

# Market-aware bot
./scripts/auto_trade_market.sh at=account1 fr=EUR_USD tf=5m &
./scripts/auto_trade_market.sh at=account2 fr=GBP_USD tf=15m &
```

Outputs saved to: `{account}/csv/` and `{account}/logs/`