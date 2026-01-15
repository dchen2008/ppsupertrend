# Pivot Point Confirmation Bar

This document explains how pivot points are detected and why we use the "confirmation bar" to match TradingView's Pine Script behavior.

## Overview

The PP SuperTrend indicator uses pivot highs and pivot lows to calculate a dynamic center line. The timing of when these pivots are "reported" is critical for accurate calculations.

## Pivot Detection Logic

With `pivot_period = 2`, a pivot high requires:
- The bar's high must be **higher** than `period` bars to the LEFT
- The bar's high must be **higher** than `period` bars to the RIGHT

```
Bar Index:    3    4    5    6    7
              ^    ^    ^    ^    ^
             left left PIVOT right right
```

## Why We Need the Confirmation Bar

**The problem:** You cannot know if bar 5 is a pivot until bar 7 closes!

- At bar 5: You don't know yet - bars 6 and 7 haven't formed
- At bar 6: Still don't know - bar 7 hasn't formed
- At bar 7: NOW you can confirm bar 5 was a pivot

### Real-time Trading Example

```
Time:         10:00  10:05  10:10  10:15  10:20
Bar Index:      3      4      5      6      7
High:         1.100  1.102  1.108  1.105  1.103
                            ^^^^
                         Highest!

At 10:10 (bar 5 closes): High is 1.108, but is it a pivot? Unknown yet.
At 10:15 (bar 6 closes): High is 1.105 < 1.108. Need one more bar.
At 10:20 (bar 7 closes): High is 1.103 < 1.108. NOW CONFIRMED!
```

Bar 7 is when you **know for certain** that bar 5 was a pivot high.

## Pine Script Behavior

Pine Script's `pivothigh(prd, prd)` function returns the pivot value at the **confirmation bar**, not the actual pivot bar:

```pine
// Pine Script
float ph = pivothigh(prd, prd)  // Returns value at bar i+prd when pivot detected at bar i
```

This is because in real-time trading, the pivot information only becomes available at the confirmation bar.

## Python Implementation

Our Python code in `src/indicators.py` matches this behavior:

```python
def detect_pivot_highs(df, period=2):
    for i in range(period, len(highs) - period):
        # Check if bar i is a pivot (higher than period bars on each side)
        is_pivot = True

        # Check left side
        for j in range(1, period + 1):
            if highs[i] <= highs[i - j]:
                is_pivot = False
                break

        # Check right side
        if is_pivot:
            for j in range(1, period + 1):
                if highs[i] <= highs[i + j]:
                    is_pivot = False
                    break

        if is_pivot:
            # Place pivot at CONFIRMATION bar (period bars later)
            # This matches Pine Script's pivothigh(prd, prd) behavior
            pivot_highs.iloc[i + period] = highs[i]
```

### Visual Comparison

```
Bar Index:    0   1   2   3   4   5   6   7   8   9
Price High:   H   H   H   H   H  [PH]  H   H   H   H
                                  ^
                              Actual pivot at bar 5

WRONG (pivot at actual bar):
pivot_highs:  -   -   -   -   -  [X]  -   -   -   -
                                  ^
                              Value at bar 5

CORRECT (pivot at confirmation bar):
pivot_highs:  -   -   -   -   -   -   -  [X]  -   -
                                          ^
                              Value at bar 7 (5 + period)
```

## Impact on Calculations

When the pivot is placed at the confirmation bar, it affects the entire calculation chain:

1. **Center Line**: Updates at the correct time (confirmation bar)
2. **Upper/Lower Bands**: `center +/- (ATR_factor * ATR)` calculated correctly
3. **Trailing Stops**: TUp and TDown track the bands correctly
4. **SuperTrend Line**: Final indicator value matches TradingView

## Affected Components

This pivot timing logic in `src/indicators.py` affects:

| Component | File | Impact |
|-----------|------|--------|
| Trading Bot | `src/trading_bot_market_aware.py` | Signal detection, SL placement |
| Backtest | `fixed_backtest.py` | Historical trade simulation |
| Manual Order Tool | `tools/manually_new_order_cal_tp_sl_position_size.py` | TP/SL calculations |
| Risk Manager | `src/risk_manager.py` | Position sizing based on SuperTrend |

## Verification

To verify the Python implementation matches TradingView:

1. Open TradingView with the "Pivot Point SuperTrend" indicator
2. Note the SuperTrend line value at a specific candle
3. Run the manual order tool and compare:
   ```bash
   ./tools/manually_new_order_cal_tp_sl_position_size.sh at=account1 fr=EUR_USD tf=5m get-position
   ```

The SuperTrend values should now match closely (small differences may exist due to candle data timing).

---

# Signal Repainting (Appearing/Disappearing Signals)

## The Problem

In TradingView, you may observe signals appearing briefly (within 20 seconds) and then disappearing. This is called **"repainting"**.

## What Causes Repainting

TradingView recalculates the indicator on **every tick** while a candle is still forming:

```
Timeline during ONE 5-minute candle (10:00 - 10:05):

10:00:00  Candle opens at 1.1650
          SuperTrend line at 1.1645
          No signal (price above SuperTrend)

10:02:30  Price wick drops to 1.1640 (below SuperTrend!)
          ⚡ SELL SIGNAL APPEARS (price < SuperTrend)

10:02:50  Price bounces back to 1.1652
          ❌ SELL SIGNAL DISAPPEARS (price > SuperTrend again)

10:05:00  Candle CLOSES at 1.1655
          Final: No signal (close > SuperTrend)
```

The signal is based on the **current price**, not the **closed candle price**. During candle formation, the signal can flip back and forth.

## Two Separate Issues

| Issue | What It Is | Solution |
|-------|------------|----------|
| **Pivot Confirmation Bar** | When pivots are "reported" for center line calculation | Fixed: place pivot at `i + period` |
| **Signal Repainting** | Signals appear/disappear during unclosed candle | Config: `use_closed_candles_only` |

## The Solution: `use_closed_candles_only`

We added a configuration option in `src/config.yaml`:

```yaml
signal:
  # Use only closed candles for signal detection (recommended for live trading)
  # true  = Use second-to-last candle (last CLOSED candle) - no repainting, consistent signals
  # false = Use last candle (might be incomplete) - faster signals but may repaint/disappear
  use_closed_candles_only: true
```

## How It Works

When fetching candles from OANDA API, the last candle might be incomplete (still forming):

```
Candles from API:
Index:    -5   -4   -3   -2   -1
Status: [CLOSED][CLOSED][CLOSED][CLOSED][FORMING...]
                                         ^^^^^^^^
                                    This candle is not done yet!
```

### When `use_closed_candles_only: false` (default for backtest)

```python
last_row = df.iloc[-1]   # Uses the forming candle
prev_row = df.iloc[-2]   # Uses last closed candle
```

- Faster signal detection
- Signal may disappear if price moves back before candle closes

### When `use_closed_candles_only: true` (recommended for live trading)

```python
last_row = df.iloc[-2]   # Uses last CLOSED candle
prev_row = df.iloc[-3]   # Uses second-to-last closed candle
```

- Consistent signals that won't disappear
- Signal is delayed by up to 1 candle (max 5 minutes for 5m timeframe)

## Trade-off Summary

| Setting | Pros | Cons |
|---------|------|------|
| `false` (use incomplete) | Faster entry, earlier signal | Signal might repaint/disappear |
| `true` (closed only) | Consistent, no repainting | Up to 1 candle delay |

## Implementation in `src/indicators.py`

```python
def get_current_signal(df, use_closed_candles_only=False):
    """
    Args:
        use_closed_candles_only: If True, use the last CLOSED candle for SIGNAL detection
                                 to avoid repainting. SuperTrend price always uses the
                                 current (latest) candle for real-time SL placement.
    """
    # Current row always points to latest candle (for real-time SuperTrend price)
    current_row = df.iloc[-1]

    if use_closed_candles_only:
        if len(df) < 2:
            return None
        signal_row = df.iloc[-2]  # Last CLOSED candle for SIGNAL
        prev_row = df.iloc[-3] if len(df) > 2 else None
    else:
        signal_row = df.iloc[-1]
        prev_row = df.iloc[-2] if len(df) > 1 else None

    # Signal from confirmed candle
    signal = determine_signal(signal_row)

    return {
        'signal': signal,                           # From signal_row (confirmed)
        'trend': int(signal_row['trend']),          # From signal_row (confirmed)
        'supertrend': float(current_row['supertrend']),  # From current_row (real-time!)
        'price': float(current_row['close']),       # From current_row (real-time)
        ...
    }
```

## Important: Signal vs SuperTrend Price

| Data | Source | Reason |
|------|--------|--------|
| **Signal (BUY/SELL)** | Closed candle (`signal_row`) | Confirm signal is real, avoid repainting |
| **SuperTrend price** | Current candle (`current_row`) | Real-time SL for accurate protection |

This distinction ensures:
1. We don't enter trades based on signals that might disappear
2. We use the most current SuperTrend value for stop loss placement

## Recommendation

- **Live Trading**: Use `use_closed_candles_only: true` to avoid false signals
- **Backtest**: Use `false` (default) since all historical candles are already closed
