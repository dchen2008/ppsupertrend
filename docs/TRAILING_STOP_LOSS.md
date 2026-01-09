# Trailing Stop Loss Implementation

## 🎯 Overview

The bot now features a **dynamic trailing stop loss** that automatically updates as the SuperTrend line moves in your favor, locking in profits and protecting against reversals.

## 🚨 Why This Was Necessary

### The Problem with Static Stop Loss

As you correctly identified, the Pivot Point SuperTrend indicator has **lag** (it's a lagging indicator). With a static stop loss:

```
Example Trade:
Entry LONG: 1.10250
Initial Stop: 1.10175 (7.5 pips risk)

Price moves up to 1.10350 (100 pips profit!)
SuperTrend trails to 1.10280
But stop is STILL at 1.10175 (original)

Price reverses down to 1.10200
Opposite signal appears at 1.10200
Exit at 1.10200 = -5 pips LOSS

Result: Had 100 pips profit, ended with 5 pip loss
```

**With static stop:** Most trades that show profit eventually give it all back before exit signal.

### The Solution: Trailing Stop Loss

```
Same Trade with Trailing Stop:
Entry LONG: 1.10250
Initial Stop: 1.10175 (7.5 pips risk)

Price moves up to 1.10300
SuperTrend: 1.10220
Stop updated to: 1.10215 (protecting 4 pips profit)

Price moves up to 1.10350
SuperTrend: 1.10280
Stop updated to: 1.10275 (protecting 25 pips profit)

Price reverses down
Hits stop at 1.10275
Exit at 1.10275 = +25 pips PROFIT

Result: Locked in profit before reversal
```

## ⚙️ How It Works

### Update Frequency
- **Check interval:** Every 30 seconds (changed from 60)
- **Faster response** to SuperTrend movements
- **More protection** during volatile moves

### Update Logic

```python
Every 30 seconds:
1. Fetch latest market data
2. Calculate current SuperTrend value
3. Calculate new stop loss (SuperTrend ± 0.5 pips)
4. Compare with current stop loss

For LONG positions:
   If new_stop > current_stop:  # Stop moved UP (closer to price)
      If movement >= 1 pip:      # Minimum distance check
         Update stop loss via API

For SHORT positions:
   If new_stop < current_stop:  # Stop moved DOWN (closer to price)
      If movement >= 1 pip:      # Minimum distance check
         Update stop loss via API
```

### Key Features

✅ **One-Way Movement:** Stop only moves in favorable direction (never widens)
✅ **Minimum Distance:** Only updates if SuperTrend moved at least 1 pip (avoids excessive API calls)
✅ **Profit Protection:** Automatically locks in gains as trend continues
✅ **Server-Side:** Stop loss still managed by OANDA (works even if bot offline)
✅ **Recovery:** If bot restarts, it recovers stop loss tracking from open positions

## 📊 Configuration

### In `config.py`:

```python
# Bot behavior
check_interval = 30  # Check every 30 seconds (faster updates)

# Trailing stop loss settings
enable_trailing_stop = True  # Enable/disable trailing
min_stop_update_distance = 0.00010  # Min 1 pip movement to update
```

### Enable/Disable Trailing Stop

```python
# Disable trailing stop (use static stop)
enable_trailing_stop = False

# Enable trailing stop (default)
enable_trailing_stop = True
```

### Adjust Update Sensitivity

```python
# Very sensitive (update every 0.5 pip movement)
min_stop_update_distance = 0.00005

# Default (update every 1 pip movement)
min_stop_update_distance = 0.00010

# Less sensitive (update every 2 pip movement)
min_stop_update_distance = 0.00020
```

## 📈 Example Scenarios

### Scenario 1: Profitable Long Trade

```
10:00 - Entry
  Price: 1.10250 LONG
  SuperTrend: 1.10180
  Stop Loss: 1.10175

10:30 - Price moving up (Check #1)
  Price: 1.10300
  SuperTrend: 1.10220 (moved up 4 pips)
  Stop Loss: 1.10215 (updated! +4 pips)
  Unrealized P/L: +50 pips
  Protected: +4 pips

11:00 - Price continuing up (Check #2)
  Price: 1.10350
  SuperTrend: 1.10280 (moved up 6 pips)
  Stop Loss: 1.10275 (updated! +6 pips)
  Unrealized P/L: +100 pips
  Protected: +10 pips total

11:30 - Price reverses
  Price: 1.10270
  Price hits stop at 1.10275
  OANDA closes position automatically
  Realized P/L: +25 pips ✅

Outcome: Protected 25 pips of the 100 pip move
```

### Scenario 2: Whipsaw Protection

```
14:00 - Entry
  Price: 1.10200 LONG
  SuperTrend: 1.10130
  Stop Loss: 1.10125

14:30 - Small move up
  Price: 1.10215
  SuperTrend: 1.10135 (moved up 0.5 pips)
  Stop Loss: 1.10125 (NO UPDATE - below 1 pip threshold)

15:00 - Price drops
  Price: 1.10180
  Opposite signal appears
  Bot closes at 1.10180
  Realized P/L: -20 pips

Outcome: Stop didn't chase small moves, avoided worse loss
```

### Scenario 3: Major Trend

```
09:00 - Entry
  Price: 1.10100 LONG
  SuperTrend: 1.10030
  Stop Loss: 1.10025

09:30 - Update #1
  SuperTrend: 1.10080
  Stop: 1.10075 (+5 pips protected)

10:00 - Update #2
  SuperTrend: 1.10130
  Stop: 1.10125 (+10 pips protected)

10:30 - Update #3
  SuperTrend: 1.10180
  Stop: 1.10175 (+15 pips protected)

11:00 - Update #4
  SuperTrend: 1.10230
  Stop: 1.10225 (+20 pips protected)

11:30 - Update #5
  SuperTrend: 1.10280
  Stop: 1.10275 (+25 pips protected)

12:00 - Price reverses, hits stop
  Exit: 1.10275
  Profit: +175 pips ✅

Outcome: Captured majority of 200+ pip trend
```

## 🔧 API Calls

### Frequency
- **Without trailing:** 0 stop loss updates per trade
- **With trailing (30s checks):** 0-20 updates per trade (depends on trend length)
- **Average:** ~2-5 updates per profitable trade

### API Call Breakdown

```
Position Open:
└─ 1 API call (create position + stop loss)

During Position (every 30 seconds):
├─ 1 API call (fetch candles)
├─ 1 API call (get position)
└─ 0-1 API calls (update stop if SuperTrend moved)

Position Close:
└─ 1 API call (close position)

Total per trade: 5-15 API calls (depending on trade duration)
```

### OANDA API Limits
- **Practice Account:** 120 requests/second
- **Live Account:** 120 requests/second
- **Bot usage:** ~2-4 requests/30s = well within limits

## 📝 Logging

### When Stop Loss Updates

```
🔄 UPDATING TRAILING STOP LOSS
  Position: LONG
  Old Stop: 1.10175
  New Stop: 1.10215
  Movement: 4.0 pips closer
  SuperTrend: 1.10220
  Current Price: 1.10300
✅ Stop loss updated successfully
🛡️  Protecting additional 4.0 pips of profit
--------------------------------------------------------------------------------
```

### When Position Opens

```
🛑 STOP LOSS ORDER CREATED:
  Stop Loss Price: 1.10175
  Stop Loss ID: 12346
  Trailing Stop: ENABLED (updates every 30s)
```

### Regular Status (Every 30s)

```
--------------------------------------------------------------------------------
Time: 2026-01-04 10:30:15
Balance: $100005.66 | Unrealized P/L: $5.00 | NAV: $100010.66
Position: LONG 100 units | P/L: $5.00
Signal: HOLD_LONG | Price: 1.10300 | SuperTrend: 1.10220 | Trend: UP
📊 No trade action: HOLD
🔄 UPDATING TRAILING STOP LOSS
  [update details...]
```

## ⚠️ Important Notes

### When Stop WILL Update

✅ SuperTrend moves favorably (up for LONG, down for SHORT)
✅ Movement is at least 1 pip (configurable)
✅ Position is open
✅ No opposite signal present

### When Stop WON'T Update

❌ SuperTrend moves unfavorably (would widen stop)
❌ Movement is less than 1 pip
❌ No position open
❌ Opposite signal detected (position will close instead)

### Recovery on Restart

If bot crashes and restarts:
1. Bot checks for open positions on startup
2. Retrieves stop loss order ID from OANDA
3. Continues trailing from current stop level
4. No manual intervention needed

## 💡 Best Practices

### For Volatile Markets
```python
check_interval = 20  # More frequent checks
min_stop_update_distance = 0.00005  # More sensitive (0.5 pips)
```

### For Trending Markets
```python
check_interval = 30  # Standard
min_stop_update_distance = 0.00010  # Standard (1 pip)
```

### For Conservative Trading
```python
check_interval = 60  # Less frequent
min_stop_update_distance = 0.00020  # Less sensitive (2 pips)
```

## 📊 Performance Impact

### Benefits
- **Higher win rate:** Locks in profits before reversals
- **Better R:R ratio:** Protects gains while letting winners run
- **Psychological:** Less stressful knowing profits are protected
- **Automatic:** No manual intervention needed

### Trade-offs
- **Earlier exits:** May exit before trend fully exhausts
- **More API calls:** 2-5 extra calls per profitable trade
- **Slightly complex:** More moving parts to monitor

## 🎯 Recommended Settings

### Default (Balanced)
```python
check_interval = 30
enable_trailing_stop = True
min_stop_update_distance = 0.00010  # 1 pip
```

### Aggressive (Maximum Protection)
```python
check_interval = 20
enable_trailing_stop = True
min_stop_update_distance = 0.00005  # 0.5 pips
```

### Conservative (Fewer Updates)
```python
check_interval = 60
enable_trailing_stop = True
min_stop_update_distance = 0.00020  # 2 pips
```

### Disabled (Static Stop)
```python
check_interval = 60
enable_trailing_stop = False
```

## 🔬 Testing

Monitor these metrics to evaluate trailing stop performance:

1. **Win Rate:** Should increase
2. **Average Win:** May decrease slightly (earlier exits)
3. **Average Loss:** Should decrease (tighter stops)
4. **Profit Factor:** Should increase overall
5. **Max Drawdown:** Should decrease

Compare results with `enable_trailing_stop = False` vs `True` over 20+ trades.

## Summary

The trailing stop loss solves the critical problem of giving back profits in a lagging indicator system. By automatically tightening the stop as the SuperTrend moves favorably, the bot now:

✅ **Protects profits** as trend continues
✅ **Exits with gains** instead of losses after reversals
✅ **Responds faster** with 30-second checks
✅ **Stays aligned** with SuperTrend structure
✅ **Maintains safety** via server-side stops

This enhancement transforms the bot from a signal-only system to a true profit-protection system.
