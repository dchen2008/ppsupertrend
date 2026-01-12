# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This is a Python-based automated forex trading bot that uses the Pivot Point SuperTrend indicator to trade EUR/USD (and other currency pairs) via the OANDA API. The bot has two main versions:
1. **Standard Bot** (`trading_bot_enhanced.py`): Original PP SuperTrend strategy with configurable stop losses
2. **Market-Aware Bot** (`trading_bot_market_aware.py`): Enhanced version that uses 3H timeframe for market trend detection and dynamic risk/reward ratios based on bull/bear market conditions

## Directory Structure

```
ppsupertrend/
├── src/                    # Source code (tracked)
│   ├── config.py
│   ├── config.yaml         # Default configuration
│   ├── trading_bot_market_aware.py
│   └── ...
├── scripts/                # Launch scripts (tracked)
├── backtest/
│   ├── data/               # Downloaded OANDA data (ignored)
│   ├── results/            # Backtest output CSVs (ignored)
│   └── logs/               # Backtest logs (ignored)
├── account1/               # Per-account runtime (account1-4)
│   ├── config.yaml         # Account-specific overrides (tracked)
│   ├── csv/                # Trade history CSVs (ignored)
│   ├── logs/               # Bot logs (ignored)
│   └── state/              # Signal state persistence (ignored)
├── .gitignore              # Ignores runtime outputs
└── CLAUDE.md
```

**What's tracked vs ignored:**
- **Tracked**: Source code, configs, scripts, `.gitkeep` files
- **Ignored**: Logs, CSVs, state files, backtest data/results, `.DS_Store`

**`.gitkeep` files**: Empty files in ignored directories ensure the folder structure exists on fresh clone. Runtime files are generated locally but never committed.

## Core Architecture

The repository contains a dual-architecture trading system with two distinct bot implementations:

### Standard Bot (`trading_bot_enhanced.py`) 
- Original PP SuperTrend strategy with configurable stop losses
- Single timeframe analysis using trading timeframe only
- Stop loss options: SuperTrend line or Pivot Point center line
- CSV output with basic trade metrics
- Legacy parameter format for launching

### Market-Aware Bot (`trading_bot_market_aware.py`) - **Recommended**
- **3H Market Trend Detection**: Uses PP SuperTrend on H3 timeframe to determine bull/bear market
- **Dynamic Risk/Reward**: Adjusts take profit based on market trend and position direction
  - Bear market: Short R:R=1.2 (favorable), Long R:R=0.6 (conservative)
  - Bull market: Long R:R=1.2 (favorable), Short R:R=0.6 (conservative)
- **Configuration Hierarchy**: `src/config.yaml` (defaults) → `account/config.yaml` (overrides)
- **Automatic Take Profit**: Sets TP at order placement based on calculated R:R
- **Opposite Trade Filter**: `disable_opposite_trade` parameter prevents trades against 3H market trend

### Key Architectural Patterns

**Spread Adjustment**: Critical for accurate stop loss placement
- OANDA uses BID prices to trigger long stop losses, ASK for short stops
- SuperTrend calculations use MID prices
- `spread_buffer_pips` (default: 3) adds buffer to ensure stops trigger correctly
- Fixed backtest now uses configurable buffer matching live bot behavior

**Signal Detection**: Prevents phantom trades
- PP SuperTrend generates BUY/SELL signals when trend changes
- `get_current_signal()` returns both signals (BUY/SELL) and hold states (HOLD_LONG/HOLD_SHORT)
- Backtest engine tracks only actual BUY/SELL signals to prevent false triggers from hold state changes
- Uses `prev_actual_signal` tracker separate from `prev_signal` to avoid phantom trades

**Multi-Account Support**:
- `OANDAConfig.ACCOUNTS` dictionary stores multiple account credentials
- `OANDAConfig.set_account(account_name)` switches active account
- Runtime outputs organized by account folder

## Common Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Test OANDA connection
python tests/test_connection.py

# Run market-aware bot (recommended)
./scripts/auto_trade_market.sh at=account1 fr=EUR_USD tf=5m           # Mac/Linux
scripts\auto_trade_market.bat at=account1 fr=EUR_USD tf=5m            # Windows

# Catch-up mode: Enter position based on current trend (if bot missed a signal)
./scripts/auto_trade_market.sh at=account1 fr=EUR_USD tf=5m catch-up  # Mac/Linux
scripts\auto_trade_market.bat at=account1 fr=EUR_USD tf=5m catch-up   # Windows

# Run enhanced backtest (exact bot logic) - FIXED VERSION
python3 fixed_backtest.py at=account1 fr=EUR_USD tf=5m bt="01/04/2026 16:00:00,01/09/2026 16:00:00"

# Monitor live bot logs
tail -f account1/logs/bot_EUR_USD_5m_market_aware.log

# Check backtest results (no phantom trades)
ls -la backtest/results/bt_*sign_ratio_profit*.csv

# Run signal timing analysis
python3 analyze_signal_timing.py fr=EUR_USD tf=5m start="2026-01-04 16:00:00" end="2026-01-09 16:00:00"

# Debug phantom trades (if they appear)
python3 debug_phantom_trades.py

# Check OANDA position/trades with raw API response (SL, TP, etc.)
python3 check_position.py           # account1 (default)
python3 check_position.py account1  # specify account
python3 check_position.py account2

# View trade details and set/update take profit
python3 set_take_profit.py                              # view only (shows suggested TP)
python3 set_take_profit.py account1                     # view only (specify account)
python3 set_take_profit.py take_profit_price=1.16210    # set TP to exact price
python3 set_take_profit.py rr=1.0                       # auto-calculate & set TP with R:R=1.0
python3 set_take_profit.py account1 rr=2.0              # specify account with R:R
```

## Configuration Hierarchy

1. **Default Configuration** (`src/config.yaml`): Base settings for all accounts
2. **Account Override** (`account1/config.yaml`): Only include settings to override

Key parameters:
- `stoploss.spread_buffer_pips`: Buffer added to stop loss (default: 3 pips)
- `position_sizing.disable_opposite_trade`: Skip trades against 3H trend (default: true)
- `risk_reward.bear_market.short_rr`: Risk/reward for shorts in bear market (default: 1.2)

## Backtest System

### Fixed/Enhanced Backtest (`fixed_backtest.py`) - **CORRECTED VERSION**
Recent fixes to eliminate phantom trades:

**Problem**: Original backtest generated trades that never occurred in TradingView
- Phantom trades at times like 07:10AM when actual signal was at 07:00AM
- Caused by comparing HOLD states with actual signals

**Solution**: 
- Added `prev_actual_signal` tracker separate from `prev_signal`
- Only triggers trades on genuine BUY/SELL signal changes
- Ignores transitions between HOLD_LONG and HOLD_SHORT states

**Verification**:
```bash
# Run backtest and check for phantom trades
python3 fixed_backtest.py at=account1 fr=EUR_USD tf=5m bt="01/04/2026 16:00:00,01/09/2026 16:00:00"

# Verify no "never happen in TradingView" markers in output
grep "never happen" backtest/results/bt_*.csv
```

### Backtest Command Formats

**Time Range Backtest (Enhanced - Exact Bot Logic):**
```bash
# Run with exact live bot logic (no phantom trades)
python3 fixed_backtest.py at=account1 fr=EUR_USD tf=5m bt="MM/DD/YYYY HH:MM:SS,MM/DD/YYYY HH:MM:SS"

# Example with custom balance
python3 fixed_backtest.py at=account1 fr=EUR_USD tf=5m bt="01/06/2026 00:00:00,01/10/2026 23:59:59" balance=10000
```

**Output Format** (enhanced CSV with spread buffer):
```csv
market,signal,time,entry_price,stop_loss_price,take_profit_price,position_lots,
risk_amount,original_stop_pips,buffer_pips,adjusted_stop_pips,take_profit_ratio,
highest_ratio,potential_profit,actual_profit,position_status,take_profit_hit,stop_loss_hit
```

## PP SuperTrend Signal Logic

### Signal Generation Rules
1. **Actual Signals**: Only BUY or SELL when trend changes
2. **Hold States**: HOLD_LONG or HOLD_SHORT between signals
3. **Trade Triggers**: Only on actual signal changes, not hold state changes

### Critical Implementation Details

**One Order Per Signal Rule**: 
- Bot must NEVER place more than one order between consecutive PP SuperTrend signals
- Implemented via `last_signal_time` tracking in both live bot and backtest
- Prevents duplicate trades even after stop loss hits

**Signal Detection in Backtest**:
```python
# Extract actual signal (BUY/SELL) from current signal (which could be HOLD_LONG/HOLD_SHORT)
if current_signal == 'BUY':
    current_actual_signal = 'BUY'
elif current_signal == 'SELL':
    current_actual_signal = 'SELL'
else:
    current_actual_signal = prev_actual_signal  # Keep previous actual signal

# Check for actual signal change (not HOLD state changes)
if current_actual_signal != prev_actual_signal and current_actual_signal in ['BUY', 'SELL']:
    # Process trade...
```

**Opposite Trade Filtering** (`disable_opposite_trade`):
- BEAR market (3H = SELL): Blocks LONG/BUY trades, allows SHORT/SELL
- BULL market (3H = BUY): Blocks SHORT/SELL trades, allows LONG/BUY
- Closes existing position but skips opening filtered opposite trade

## Risk Manager Integration

The `RiskManager` class (`src/risk_manager.py`) serves as the central decision engine:
- **Position Sizing**: Dynamic sizing based on market trend and position direction
- **Trade Validation**: `should_trade()` method with duplicate signal prevention
- **Stop Loss Calculation**: Includes spread adjustment buffer

Key methods:
- `should_trade()`: Validates trades, prevents duplicates, enforces opposite trade filter
- `calculate_position_size()`: Market-aware position sizing
- `calculate_stop_loss()`: Adds spread buffer for accurate execution

## CSV Output Schema

**Market-Aware Bot** fields:
```
tradeID, name, orderTime, closeTime, duration, superTrend, pivotPoint, signal,
type, positionSize, enterPrice, stopLoss, closePrice, highestPrice, lowestPrice,
highestProfit, lowestLoss, stopLossHit, takeProfit, takeProfitHit, 
marketTrend, riskRewardTarget, riskRewardActual
```

**Enhanced Backtest** fields (with buffer details):
```
market, signal, time, entry_price, stop_loss_price, take_profit_price,
position_lots, risk_amount, original_stop_pips, buffer_pips, adjusted_stop_pips,
take_profit_ratio, highest_ratio, potential_profit, actual_profit,
position_status, take_profit_hit, stop_loss_hit
```

## Analysis Tools

### Signal Timing Analysis (`analyze_signal_timing.py`)
Compares different signal detection methods:
- Method 1: Current implementation (check last row's signal flags)
- Method 2: Direct trend change detection
- Method 3: Lookback detection (finds missed signals)

Useful for identifying phantom trades and signal timing issues.

### Phantom Trade Debugger (`debug_phantom_trades.py`)
Analyzes specific timestamps where phantom trades occur:
- Shows signal progression around phantom trade times
- Compares what backtest would trigger vs actual signals
- Helps identify logic errors in signal detection

## OANDA Account Tools

### Check Position (`check_position.py`)
Fetches raw OANDA API response to verify account state:
```bash
python3 check_position.py           # account1 (default)
python3 check_position.py account2  # specify account
```
Shows: Open trades (with SL/TP), positions, current price, account summary, recent transactions.

### Set Take Profit (`set_take_profit.py`)
View trade details and set/update take profit price:
```bash
# View current trades (shows suggested TP if not set)
python3 set_take_profit.py
python3 set_take_profit.py account1

# Set/update take profit to specific price
python3 set_take_profit.py take_profit_price=1.16210
python3 set_take_profit.py account1 take_profit_price=1.16210

# Auto-calculate and SET take profit based on R:R ratio
python3 set_take_profit.py rr=1.0                       # set TP with R:R=1.0
python3 set_take_profit.py rr=2.0                       # set TP with R:R=2.0
python3 set_take_profit.py account1 rr=1.5             # specify account
```

**Features:**
- Displays: Trade ID, instrument, position type, entry price, P/L, SL, TP
- Shows suggested TP based on R:R ratio from `account/config.yaml` (when viewing only)
- `rr=X` auto-calculates TP from stop loss distance and **sets it immediately**
- `take_profit_price=X` sets TP to exact price
- Creates new TP order if none exists, or updates existing TP order

**Example output when TP not set:**
```
Trade ID:        769
Position:        SHORT (-127,565 units)
Entry Price:     1.16300
Stop Loss:       1.16454
Take Profit:     NOT SET

************************************************************
SUGGESTED Take Profit:
  For your SHORT position with entry 1.16300
  and R:R=1.0, TP should be around 1.16146
  (15.4 pips below entry, matching 15.4 pips SL risk)

  To set this TP, run:
  python3 set_take_profit.py account1 take_profit_price=1.16146
************************************************************
```

## Important Implementation Notes

1. **API Retry Logic**: All OANDA API calls use `@api_retry_handler` decorator (3 retries)
2. **Stop Loss Updates**: Use trade ID, not stop loss order ID for modifications
3. **Signal State Persistence**: `last_signal_candle_time` is persisted to `{account}/state/{instrument}_{timeframe}_state.json` and survives bot restarts
4. **Spread Simulation**: Fixed backtest uses typical spread of 1.5 pips for EUR/USD
5. **Time Zone**: Backtest outputs use UTC-8 for readability

## Catch-Up Mode

When the bot misses a signal (e.g., due to restart or network issues), use the `catch-up` parameter to enter a position based on the current trend:

```bash
# Enter position based on current trend (HOLD_SHORT → SHORT, HOLD_LONG → LONG)
./scripts/auto_trade_market.sh at=account1 fr=EUR_USD tf=5m catch-up
```

**How it works:**
1. Checks if there's an existing position (skips if position exists)
2. Reads current signal state:
   - `HOLD_SHORT` or `SELL` → Opens SHORT position
   - `HOLD_LONG` or `BUY` → Opens LONG position
3. Respects `disable_opposite_trade` setting (won't open LONG in BEAR market, etc.)
4. Saves state after catch-up to prevent duplicate trades on next restart

**Use case:** Bot was offline when a SELL signal occurred. Signal has transitioned to HOLD_SHORT. Running with `catch-up` will open a SHORT position based on the current trend.

## Signal State Persistence

The bot persists `last_signal_candle_time` to prevent duplicate trades across restarts:

**State file location:** `{account}/state/{instrument}_{timeframe}_state.json`

**Example:** `account1/state/EUR_USD_5m_state.json`

```json
{
  "last_signal_candle_time": "2026-01-12T14:25:00+00:00",
  "updated_at": "2026-01-12T06:30:07.123456"
}
```

**Behavior:**
- On startup: Bot loads saved state and won't re-trade the same signal
- After trade: State is saved immediately
- After position close (TP/SL hit): State is reset to `null` allowing next signal

**To force a new trade on current signal:** Delete the state file:
```bash
rm account1/state/EUR_USD_5m_state.json
```

## Testing Recommendations

1. **Verify No Phantom Trades**: Run backtest and check for trades that don't match TradingView
2. **Test Spread Buffer**: Compare stop loss distances with and without buffer
3. **Validate Signal Detection**: Use `analyze_signal_timing.py` to verify signals
4. **Check Opposite Trade Filter**: Ensure trades align with 3H market trend when enabled
5. **Monitor Win Rates**: Compare backtest results with live trading performance