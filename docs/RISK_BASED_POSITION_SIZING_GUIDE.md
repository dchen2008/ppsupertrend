# Risk-Based Position Sizing Guide

## Overview

Your trading bot now supports **proper risk management** with dynamic position sizing based on stop loss distance. This ensures you risk a consistent dollar amount on every trade, regardless of where the SuperTrend stop loss is located.

---

## How It Works

### The Formula
```
Position Size (units) = Risk Amount ($) / Stop Loss Distance (in price)
```

### For EUR/USD:
- **1 standard lot** = 100,000 units
- **1 pip** = 0.0001
- **Value per pip per standard lot** = $10

### Example Calculation

```
Entry Price:    1.17300
Stop Loss:      1.17200 (10 pips away)
Risk Amount:    $100

Stop Distance = 1.17300 - 1.17200 = 0.00100
Position Size = $100 / 0.00100 = 100,000 units (1.0 standard lot)

If stopped out:
Loss = 100,000 units × 0.00100 = $100 ✓
```

---

## Configuration in `config.py`

### Option 1: Fixed Dollar Risk (Recommended)
```python
use_dynamic_sizing = True
risk_per_trade = 100  # Risk $100 per trade
```

Every trade risks exactly **$100**, regardless of stop loss distance:
- **Tight 5-pip stop** → 200,000 units (2.0 lots)
- **Normal 10-pip stop** → 100,000 units (1.0 lot)
- **Wide 20-pip stop** → 50,000 units (0.5 lots)

### Option 2: Percentage Risk
```python
use_dynamic_sizing = True
risk_per_trade = 0.02  # Risk 2% of account per trade
```

With $500,000 account:
- **2% risk** = $10,000 per trade
- Position size adjusts based on stop loss

### Option 3: Fixed Position Size (Simple, Not Recommended)
```python
use_dynamic_sizing = False
position_size = 85  # Always trade 85 units
```

Risk varies with stop loss distance:
- **10-pip stop** → Risk $8.50
- **50-pip stop** → Risk $42.50 ⚠️ Inconsistent!

---

## Position Size Examples

### With $100 Risk per Trade:

| Stop Loss | Units | Lots | Notional Value | Value/Pip | Actual Risk |
|-----------|-------|------|----------------|-----------|-------------|
| 5 pips    | 200,000 | 2.000 | $234,600 | $20.00 | $100.00 |
| 10 pips   | 100,000 | 1.000 | $117,300 | $10.00 | $100.00 |
| 20 pips   | 50,000  | 0.500 | $58,650  | $5.00  | $100.00 |
| 50 pips   | 20,000  | 0.200 | $23,460  | $2.00  | $100.00 |

**Notice:** Risk is always $100, but position size adjusts!

---

## Tools Available

### 1. Position Size Calculator
```bash
python3 position_size_calculator.py
```

Shows:
- How many units needed for different stop losses
- Risk/reward calculations
- Comparison tables

### 2. Dynamic Sizing Test
```bash
python3 test_dynamic_sizing.py
```

Verifies:
- Risk management is working correctly
- Position sizes are calculated properly
- Compares fixed vs. dynamic sizing

### 3. Quick Reference
```bash
python3 calculate_position_size.py
```

Calculates position size for specific dollar exposure.

---

## Current Bot Configuration

✅ **Enabled:** `use_dynamic_sizing = True`
✅ **Risk per trade:** `$100 fixed`
✅ **Max position:** `1,000,000 units (safety limit)`
✅ **Timeframe:** `M15 (15-minute candles)`
✅ **Check interval:** `60 seconds`

---

## Why This Matters

### Without Dynamic Sizing (Bad):
```
Trade 1: 1000 units, 10-pip stop → Risk $1.00
Trade 2: 1000 units, 50-pip stop → Risk $5.00  ⚠️ 5x more risk!
Trade 3: 1000 units, 100-pip stop → Risk $10.00  ⚠️ 10x more risk!
```

### With Dynamic Sizing (Good):
```
Trade 1: 100,000 units, 10-pip stop → Risk $100.00
Trade 2: 20,000 units, 50-pip stop → Risk $100.00  ✓ Consistent
Trade 3: 10,000 units, 100-pip stop → Risk $100.00  ✓ Consistent
```

---

## Margin Requirements

With typical 30:1 leverage on OANDA:

| Position Size | Notional Value | Required Margin (3.33%) |
|--------------|----------------|-------------------------|
| 20,000 units | $23,460 | $781 |
| 50,000 units | $58,650 | $1,953 |
| 100,000 units | $117,300 | $3,906 |
| 200,000 units | $234,600 | $7,813 |

Your $500,000 account can easily handle these positions.

---

## Recommended Settings

For **conservative trading**:
```python
use_dynamic_sizing = True
risk_per_trade = 50  # Risk $50 per trade
```

For **moderate trading**:
```python
use_dynamic_sizing = True
risk_per_trade = 100  # Risk $100 per trade (current)
```

For **aggressive trading**:
```python
use_dynamic_sizing = True
risk_per_trade = 0.01  # Risk 1% per trade ($5,000 on $500k account)
```

---

## How Stop Loss is Determined

The bot automatically sets stop loss at the **SuperTrend line**:
- **Long positions:** Stop loss = SuperTrend value (below price)
- **Short positions:** Stop loss = SuperTrend value (above price)
- **Dynamic:** Adjusts with each candle as SuperTrend moves

This is why position sizing must be dynamic - the stop loss distance varies!

---

## Summary

✅ **Current setup is optimal** for risk-based trading
✅ **Risk $100 per trade** regardless of stop loss distance
✅ **Position size calculated automatically** for each trade
✅ **Better capital preservation** than fixed position sizing

**No manual calculation needed** - the bot handles everything!

---

## Quick Start

1. **Set your risk amount** in `config.py`:
   ```python
   risk_per_trade = 100  # Change to your preference
   ```

2. **Run the bot**:
   ```bash
   python3 trading_bot.py
   ```

3. **Monitor logs** - you'll see:
   ```
   Calculated position size: 100,000 units (1.000 lots)
     Risk amount: $100.00
     Actual risk: $100.00
     Stop distance: 0.00100 (10.0 pips)
   ```

Done! The bot now manages position sizing for you.
