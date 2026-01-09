# Stop Loss Strategy Explanation

## Current Implementation: Static Stop Loss

### How It Works Now:

1. **Position Opens** (e.g., BUY signal at 1.10250)
   - SuperTrend line: 1.10180
   - Stop Loss set: 1.10175 (SuperTrend - 0.5 pips)
   - Stop loss order sent to OANDA

2. **After Position Opens**
   - Stop loss REMAINS at 1.10175
   - **NOT updated** even as SuperTrend line moves
   - Bot checks market every 60 seconds
   - SuperTrend line may move to 1.10200, 1.10220, etc.
   - But stop loss stays at original 1.10175

3. **Position Exits in One of Two Ways:**
   - **Option A:** Opposite signal detected → Bot closes position manually
   - **Option B:** Price hits stop loss → OANDA closes position automatically

## Visual Example

```
Time: 10:00 AM - ENTRY
Price: 1.10250
SuperTrend: 1.10180
Stop Loss: 1.10175 ← Set once here
─────────────────────────────────

Time: 10:15 AM - Price moving up
Price: 1.10300
SuperTrend: 1.10200 ← Moved up
Stop Loss: 1.10175 ← Still at original level (NOT updated)
─────────────────────────────────

Time: 10:30 AM - Price still up
Price: 1.10350
SuperTrend: 1.10220 ← Moved up more
Stop Loss: 1.10175 ← Still at original level (NOT updated)
─────────────────────────────────

Time: 10:45 AM - Trend reverses
Price: 1.10280
SuperTrend: 1.10290 ← Now ABOVE price
Signal: SELL ← Opposite signal!
Action: Bot closes position (doesn't wait for stop loss)
```

## Why Static Stop Loss?

### Strategy Design:
- **Primary Exit:** Opposite signal (trend reversal)
- **Backup Exit:** Stop loss (protects against sudden moves)

The stop loss acts as a **safety net**, not a trailing stop.

## API Call Frequency

### Current Behavior:
- **Stop Loss Set:** Once when position opens
- **Stop Loss Updates:** ZERO (never updated)
- **OANDA API Calls for Stop Loss:** 1 per trade (at entry only)

### Market Check Frequency:
- **Every 60 seconds:** Bot checks for new signals
- **If opposite signal:** Bot closes position via API
- **Stop loss monitoring:** Continuous by OANDA servers (not bot)

## What Happens Each 60-Second Cycle

```python
Every 60 seconds:
├─ Fetch latest candles from OANDA
├─ Calculate SuperTrend indicator
├─ Check for signal change
│  ├─ If SELL signal while holding LONG → Close position
│  ├─ If BUY signal while holding SHORT → Close position
│  └─ Otherwise → Do nothing, let position run
└─ Sleep 60 seconds
```

**Note:** The bot does NOT call OANDA to update stop loss during these checks.

## Trade Lifecycle API Calls

```
1. Open Position
   └─ API Call: POST /v3/accounts/{id}/orders
      └─ Creates position + stop loss order (1 API call)

2. Hold Position (60 second checks)
   └─ API Call: GET /v3/accounts/{id}/positions/{instrument}
      └─ Check if position still exists (read only, no stop loss update)

3. Close Position
   Option A: Opposite Signal Detected
   └─ API Call: PUT /v3/accounts/{id}/positions/{instrument}/close
      └─ Closes position, OANDA auto-cancels stop loss

   Option B: Stop Loss Hit
   └─ No API call from bot
      └─ OANDA automatically closes position (server-side)
```

## Key Points

✅ **Stop loss is set once** at position entry
✅ **Stop loss never updated** by the bot
✅ **Primary exit is opposite signal**, not stop loss
✅ **Stop loss is backup protection** for sudden moves
✅ **Bot checks market every 60 seconds** for signals
✅ **OANDA monitors stop loss 24/7** (server-side, continuous)

## If You Want Trailing Stop Loss

If you want the stop loss to "trail" the price (move up for longs, down for shorts),
the bot would need to be modified to:

1. Every 60 seconds (or when SuperTrend moves favorably)
2. Calculate new stop loss based on current SuperTrend line
3. If new stop is better than old stop:
   - Call OANDA API to update stop loss order
   - API: PUT /v3/accounts/{id}/orders/{stopLossOrderId}

This would add 1+ API call per minute when position is open and moving favorably.

**Current design avoids this** to:
- Minimize API calls
- Reduce complexity
- Rely on signal-based exits (more aligned with trend-following strategy)
