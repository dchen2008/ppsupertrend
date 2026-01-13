# Stop Loss Calculation & Trailing Stop Logic

This document explains how Stop Loss (SL) is calculated and updated in the trading bot.

## Overview

The bot uses **SuperTrend** as the stop loss level. The SuperTrend line acts as dynamic support/resistance:
- For **LONG**: SuperTrend is below price (support) → SL placed at SuperTrend
- For **SHORT**: SuperTrend is above price (resistance) → SL placed at SuperTrend

---

## Step 1: Initial Stop Loss Calculation

When opening a new position, `calculate_stop_loss()` is called.

### Formula

```
base_stop_loss = SuperTrend value

For SHORT position:
  adjusted_stop_loss = base_stop_loss + spread_buffer_pips
  (Add buffer because OANDA triggers SHORT SL on ASK price, which is higher than MID)

For LONG position:
  adjusted_stop_loss = base_stop_loss - spread_buffer_pips
  (Subtract buffer because OANDA triggers LONG SL on BID price, which is lower than MID)
```

### Example: Opening a SHORT Position

```
Entry Price:        1.16778
SuperTrend:         1.16870  (above entry = resistance for SHORT)
spread_buffer_pips: 3 pips (configurable in config.yaml)

Calculation:
  base_stop_loss     = 1.16870
  buffer             = 3 pips = 0.0003
  adjusted_stop_loss = 1.16870 + 0.0003 = 1.16900

Result: Stop Loss order placed at 1.16900
```

### Why the Buffer?

OANDA uses different prices to trigger stop losses:
- **LONG SL**: Triggered when BID price <= SL price
- **SHORT SL**: Triggered when ASK price >= SL price

The SuperTrend is calculated using MID prices. The buffer accounts for the spread difference to ensure the SL triggers at the intended SuperTrend level.

---

## Step 2: Trailing Stop Loss Logic

The bot trails the stop loss as price moves in your favor, locking in profits.

### When Trailing Stop Updates

`update_trailing_stop_loss()` is called every cycle when:
1. `enable_trailing_stop = True` (in TradingConfig)
2. Position is open
3. No new trade signal detected

### Update Rules

| Position | Trail Direction | Condition to Update |
|----------|----------------|---------------------|
| LONG | Move SL **UP** | `new_SL > current_SL` |
| SHORT | Move SL **DOWN** | `new_SL < current_SL` |

The stop loss only moves in the profitable direction - never backwards.

### Minimum Update Distance

Updates only occur if the distance exceeds `min_stop_update_distance` (default: 0.0001 = 1 pip) to avoid excessive API calls.

---

## Step 3: Trailing Stop Example (SHORT Position)

### Initial State
```
Entry Price:  1.16778
SuperTrend:   1.16870
Stop Loss:    1.16900 (SuperTrend + 3 pips buffer)
```

### Price Moves Down (Profitable for SHORT)

```
Time T1:
  Price:      1.16700
  SuperTrend: 1.16800
  New SL:     1.16800 + 0.0003 = 1.16830

  Check: 1.16830 < 1.16900? YES
  Action: Update SL from 1.16900 → 1.16830 ✓
  (Locking in ~7 pips of profit)

Time T2:
  Price:      1.16600
  SuperTrend: 1.16700
  New SL:     1.16700 + 0.0003 = 1.16730

  Check: 1.16730 < 1.16830? YES
  Action: Update SL from 1.16830 → 1.16730 ✓
  (Locking in ~17 pips of profit)
```

### Price Reverses Up

```
Time T3:
  Price:      1.16750
  SuperTrend: 1.16700 (hasn't changed yet)
  New SL:     1.16700 + 0.0003 = 1.16730

  Check: 1.16730 < 1.16730? NO (equal)
  Action: No update (SL stays at 1.16730)
```

### Price Crosses SuperTrend (Trend Reversal)

```
Time T4:
  Price:      1.16780 (crossed above SuperTrend!)
  SuperTrend: 1.16560 (flipped to below price)

  This generates a BUY signal (trend reversal).
  Bot will attempt to CLOSE the SHORT position.

  If close succeeds: Position closed by market order
  If close fails: Trailing stop may trigger at next update
```

---

## Step 4: Visual Flow Diagram

```
                    SHORT Position Price Movement

Price
  ^
  |
1.16900 ──●───────────────────────────────────── Initial SL
1.16870 ──│─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─  Initial SuperTrend
1.16830 ──│───────●───────────────────────────── SL after T1
1.16800 ──│───────│─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─  SuperTrend at T1
1.16778 ──│───────│───────────────────────────── Entry Price
1.16730 ──│───────│───────●───────●───────────── SL after T2 (stays)
1.16700 ──│───────│───────│─ ─ ─ ─│─ ─ ─ ─ ─ ─  SuperTrend at T2/T3
          │       │       │       │
          │       │       │       └── T3: Price bounces, SL holds
          │       │       └────────── T2: Price drops, SL trails down
          │       └────────────────── T1: Price drops, SL trails down
          └────────────────────────── T0: Position opened

                    Time ───────────────────────>
```

---

## Step 5: Code Flow Summary

```
┌─────────────────────────────────────────────────────────────────┐
│                     check_and_trade() - Each Cycle              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. Fetch latest candle data                                    │
│  2. Calculate SuperTrend indicator                              │
│  3. Get current signal (BUY/SELL/HOLD_LONG/HOLD_SHORT)          │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ if should_trade (new signal detected):                  │    │
│  │   └─→ execute_trade(CLOSE/OPEN_LONG/OPEN_SHORT)         │    │
│  │       └─→ calculate_stop_loss() for new position        │    │
│  │       └─→ Place order with SL to OANDA                  │    │
│  │       └─→ If success: save signal state                 │    │
│  │       └─→ If fail: DO NOT save (retry next cycle)       │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ else (no new signal, position open):                    │    │
│  │   └─→ update_trailing_stop_loss()                       │    │
│  │       └─→ calculate_stop_loss() with current SuperTrend │    │
│  │       └─→ Compare with current SL                       │    │
│  │       └─→ If improved: update SL in OANDA               │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Configuration Reference

In `config.yaml`:

```yaml
stoploss:
  type: supertrend           # Use SuperTrend as SL level
  spread_buffer_pips: 3      # Buffer added to SL (default: 3 pips)

# In TradingConfig (src/config.py):
enable_trailing_stop: True          # Enable/disable trailing
min_stop_update_distance: 0.0001    # Minimum distance to trigger update (1 pip)
use_spread_adjustment: True         # Apply spread buffer
```

---

## Key Points

1. **Stop Loss = SuperTrend + Buffer**: The SuperTrend line IS your stop loss level

2. **Buffer protects against spread**: The 3-pip buffer ensures SL triggers at the intended level despite bid/ask spread

3. **Trailing only moves favorably**: SL moves UP for LONG (locking profit), DOWN for SHORT (locking profit), never backwards

4. **If SL triggers, it's by design**: When price crosses SuperTrend, the trend is reversing - the SL protects you from further losses

5. **Failed trades retry**: If a close/open trade fails, the signal state is NOT saved, so the bot will retry on the next cycle
