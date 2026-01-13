# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

Python-based automated forex trading bot using the Pivot Point SuperTrend indicator to trade EUR/USD via OANDA API. Two bot versions exist:
1. **Standard Bot** (`src/trading_bot_enhanced.py`): Single timeframe PP SuperTrend strategy
2. **Market-Aware Bot** (`src/trading_bot_market_aware.py`): Uses 3H timeframe for market trend detection with dynamic R:R ratios (recommended)

## Common Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Test OANDA connection
python tests/test_connection.py

# Run market-aware bot (recommended)
./scripts/auto_trade_market.sh at=account1 fr=EUR_USD tf=5m
./scripts/auto_trade_market.sh at=account1 fr=EUR_USD tf=5m catch-up        # Enter on current trend
./scripts/auto_trade_market.sh at=account1 fr=EUR_USD tf=5m close-position  # Close position immediately

# Run backtest (single account)
python3 fixed_backtest.py at=account1 fr=EUR_USD tf=5m bt="01/04/2026 16:00:00,01/09/2026 16:00:00"
python3 fixed_backtest.py at=account1 fr=EUR_USD tf=5m bt="01/06/2026 00:00:00,01/10/2026 23:59:59" balance=10000

# Run batch backtest (multiple accounts with summary report)
./scripts/batch_bt.sh at="account1,account2,account3,account4" fr=EUR_USD tf=5m bt="01/04/2026 16:00:00,01/09/2026 16:00:00"

# Download OANDA candle data
## 2025's data
./pull_oanda_candle_data.sh range="11/01/2025 16:00:00,11/30/2025 16:00:00" tf="M1,M5,M15,H3"
./pull_oanda_candle_data.sh range="12/01/2025 16:00:00,11/31/2025 16:00:00" tf="M1,M5,M15,H3"
## 2026's data
./pull_oanda_candle_data.sh range="01/01/2026 16:00:00,01/09/2026 16:00:00" tf="M1,M5,M15,H3"

./scripts/batch_bt.sh at="account1,account2,account3,account4" fr=EUR_USD tf=5m bt="11/30/2025 16:00:00,12/04/2025 16:00:00"

# other usage cmd:
./pull_oanda_candle_data.sh range="01/04/2026 16:00:00,01/09/2026 16:00:00" tf="M1,M5,M15,H3" fr=EUR_USD
./pull_oanda_candle_data.sh days=30 tf="M5,M15,H3"

# Account utilities
python3 check_position.py account1                   # View open trades/positions
python3 check_position.py account1 tradeid=802    # View open trades/positions
python3 set_take_profit.py account1 rr=1.0  # Set TP with R:R ratio
python3 check_balance.py                     # Check account balance

# Monitor logs
tail -f account1/logs/bot_EUR_USD_5m_market_aware.log

# Run tests
python tests/test_connection.py
python tests/test_market_aware_bot.py

# Debug tools
python3 analyze_signal_timing.py fr=EUR_USD tf=5m start="2026-01-04 16:00:00" end="2026-01-09 16:00:00"
python3 debug_phantom_trades.py
```

## Core Architecture

### Directory Structure
```
ppsupertrend/
├── src/                    # Source code
│   ├── config.py           # OANDA credentials + TradingConfig
│   ├── config.yaml         # Default bot configuration
│   ├── oanda_client.py     # OANDA API client
│   ├── indicators.py       # PP SuperTrend calculations
│   ├── risk_manager.py     # Position sizing, trade validation
│   └── trading_bot_market_aware.py
├── scripts/                # Launch scripts (.sh/.bat)
├── account1-4/             # Per-account runtime
│   ├── config.yaml         # Account-specific overrides
│   ├── csv/                # Trade history (gitignored)
│   ├── logs/               # Bot logs (gitignored)
│   └── state/              # Signal persistence (gitignored)
├── backtest/
│   ├── data/               # Downloaded OANDA data (gitignored)
│   └── results/            # Backtest outputs (gitignored)
└── fixed_backtest.py       # Main backtest script
```

### Configuration Hierarchy
1. `src/config.yaml` - Default settings
2. `account1/config.yaml` - Account-specific overrides (only include settings to change)

Key parameters:
- `stoploss.spread_buffer_pips`: Buffer added to stop loss (default: 3 pips)
- `position_sizing.disable_opposite_trade`: Skip trades against 3H trend
- `risk_reward.{bear,bull}_market.{short,long}_rr`: Dynamic R:R ratios

### Multi-Account Support
```python
OANDAConfig.set_account('account1')  # Switch active account
OANDAConfig.ACCOUNTS                  # Dictionary of all accounts
```

## Critical Implementation Details

### Signal Detection (Prevents Phantom Trades)
PP SuperTrend generates signals (BUY/SELL) and hold states (HOLD_LONG/HOLD_SHORT). Critical distinction:
```python
# Only trigger trades on actual signal changes, not hold state changes
if current_signal == 'BUY':
    current_actual_signal = 'BUY'
elif current_signal == 'SELL':
    current_actual_signal = 'SELL'
else:
    current_actual_signal = prev_actual_signal  # Keep previous

if current_actual_signal != prev_actual_signal and current_actual_signal in ['BUY', 'SELL']:
    # Process trade...
```

### One Order Per Signal Rule
Bot must NEVER place more than one order between consecutive PP SuperTrend signals. Implemented via `last_signal_time` tracking.

### Spread Adjustment
OANDA uses BID prices to trigger long stop losses, ASK for short stops. SuperTrend uses MID prices. `spread_buffer_pips` adds buffer to ensure stops trigger correctly.

### Opposite Trade Filtering (`disable_opposite_trade`)
- BEAR market (3H = SELL): Blocks LONG trades, allows SHORT
- BULL market (3H = BUY): Blocks SHORT trades, allows LONG

### Signal State Persistence
State persisted to `{account}/state/{instrument}_{timeframe}_state.json`:
```json
{"last_signal_candle_time": "2026-01-12T14:25:00+00:00", "updated_at": "..."}
```
Delete state file to force re-trade on current signal.

### Catch-Up Mode
When bot misses a signal, use `catch-up` parameter:
- `HOLD_SHORT` or `SELL` -> Opens SHORT
- `HOLD_LONG` or `BUY` -> Opens LONG
- Respects `disable_opposite_trade` setting

## Risk Manager (`src/risk_manager.py`)

Central decision engine with key methods:
- `should_trade()`: Validates trades, prevents duplicates, enforces opposite trade filter
- `calculate_position_size()`: Market-aware dynamic sizing
- `calculate_stop_loss()`: Adds spread buffer for accurate execution

## Backtest System

The `fixed_backtest.py` corrects phantom trade issues by tracking `prev_actual_signal` separate from `prev_signal`.

**Time format**: `MM/DD/YYYY HH:MM:SS`

**Output file naming**:
- CSV: `account1_EUR_USD_5min_0104_0109_752.csv` (in `backtest/results/`)
- Log: `account1_EUR_USD_5min_0104_0109_752.log` (in `logs/`)

**Output CSV columns**:
```
market, signal, time, entry_price, stop_loss_price, take_profit_price,
position_lots, risk_amount, original_stop_pips, buffer_pips, adjusted_stop_pips,
take_profit_ratio, highest_ratio, potential_profit, actual_profit,
position_status, take_profit_hit, stop_loss_hit
```

### Batch Backtest (`scripts/batch_bt.sh`)

Run backtests across multiple accounts and generate a summary report:
```bash
You can overwrite market trend data as:market=bear|bull, because 3H PP data easy be split by below bt time range with wrong data.
./scripts/batch_bt.sh at="account1,account2,account3,account4" fr=EUR_USD tf=5m bt="01/04/2026 16:00:00,01/09/2026 16:00:00" market=bear|bull
```

**Summary output**: `backtest/results/summary_act1-2-3-4_EUR_USD_5min_0104_0109_XXX.csv`

Contains:
- Configuration table (R:R ratios per account)
- Results table (trades, TP hits, win rate, P/L, final balance)
- Trade breakdown by direction (BUY vs SELL performance)

### OANDA Data Downloader (`pull_oanda_candle_data.sh`)

Download historical candle data for backtesting:
```bash
./pull_oanda_candle_data.sh range="01/04/2026 16:00:00,01/09/2026 16:00:00" tf="M1,M5,M15,H3"
./pull_oanda_candle_data.sh days=30 tf="M5,M15,H3" fr=EUR_USD
```

| Parameter | Description | Default |
|-----------|-------------|---------|
| `range=` | Date range: "MM/DD/YYYY HH:MM:SS,MM/DD/YYYY HH:MM:SS" | - |
| `tf=` | Timeframes: M1, M5, M15, H3 | M1,M5,M15,H3 |
| `fr=` | Instrument | EUR_USD |
| `at=` | Account (for API key) | account1 |
| `days=` | Days back (alternative to range) | - |

**Data saved to**: `backtest/data/EUR_USD_M5_20260104_20260109.csv`

## Important Notes

1. **API Retry Logic**: All OANDA calls use `@api_retry_handler` decorator (3 retries)
2. **Stop Loss Updates**: Use trade ID, not stop loss order ID for modifications
3. **Spread Simulation**: Backtest uses 1.5 pips typical spread for EUR/USD
4. **Time Zone**: Backtest outputs use UTC-8
5. **Config contains API keys**: `src/config.py` has OANDA credentials - do not commit changes to this file
