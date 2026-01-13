# Scalping Trade Strategy

The scalping strategy allows the bot to automatically re-enter trades at the original signal price after take profit (TP) is hit, maximizing profit during trending market conditions within a defined time window.

## Overview

When scalping is enabled:
1. After the initial PP SuperTrend signal triggers a trade
2. If TP is hit, the bot waits for price to return to the original entry price
3. Re-enters the same direction trade with identical parameters
4. Repeats until a new PP signal (trend reversal), stop loss hit, or time window ends

## Configuration

### Enable Scalping (Per Account)

In `account1/config.yaml`:
```yaml
scalping:
  enabled: true
```

### Full Configuration Options

In `src/config.yaml` (defaults):
```yaml
scalping:
  enabled: false  # Default disabled
  time_window:
    start: "20:00"  # 8 PM PT (scalping window start)
    end: "10:00"    # 10 AM PT next day (scalping window end)
    timezone: "America/Los_Angeles"
  re_entry:
    use_limit_orders: true  # Use limit orders for re-entry (recommended)
    price_buffer_pips: 0.5  # Buffer for limit order price execution
  max_entries_per_signal: 0  # 0 = unlimited re-entries within time window
```

## Order Conditions

### Entry Condition (First Trade)

The first trade enters via normal PP SuperTrend signal:
- **BUY Signal**: Opens LONG position
- **SELL Signal**: Opens SHORT position

When scalping is enabled and within the time window, the bot captures:
- `signal_price`: The actual fill price of the first entry
- `supertrend_value`: SuperTrend value at signal time (used for stop loss)
- `market_trend`: BULL or BEAR (from 3H timeframe)
- `rr_ratio`: Risk/reward ratio used for take profit

### Re-Entry Condition

After TP is hit, the bot monitors price for re-entry opportunity:

| Position Type | Re-Entry Condition |
|--------------|-------------------|
| **LONG** | `current_price <= signal_price` (equal or cheaper entry) |
| **SHORT** | `current_price >= signal_price` (equal or higher entry to short) |

## Entry Price

### First Entry
- Uses **market order** at current price when PP signal triggers
- `signal_price` is set to the **actual fill price** (not the signal candle price)

### Re-Entry
- Default: **Limit order** at `signal_price + buffer` (configurable)
- Buffer: `price_buffer_pips` (default 0.5 pips) ensures execution
  - LONG: `signal_price + 0.5 pips`
  - SHORT: `signal_price - 0.5 pips`
- Can use market orders if `use_limit_orders: false`

## Stop Loss (SL)

All entries (first and re-entries) use the **same stop loss** based on the original SuperTrend value:

```
SL = SuperTrend value (at first signal) + spread_buffer_pips
```

| Position | Stop Loss Formula |
|----------|------------------|
| **LONG** | `supertrend_value - spread_buffer_pips` |
| **SHORT** | `supertrend_value + spread_buffer_pips` |

The `spread_buffer_pips` (default: 3 pips) compensates for spread when stop loss triggers.

## Take Profit (TP)

Take profit is calculated from the entry price using the original R:R ratio:

```
TP = entry_price + (stop_loss_distance * rr_ratio)
```

| Position | Take Profit Formula |
|----------|-------------------|
| **LONG** | `entry_price + (entry_price - stop_loss) * rr_ratio` |
| **SHORT** | `entry_price - (stop_loss - entry_price) * rr_ratio` |

R:R ratios are determined by market trend (from account config):
```yaml
risk_reward:
  bear_market:
    short_rr: 0.4  # SHORT trades in bear market
    long_rr: 0.3   # LONG trades in bear market
  bull_market:
    short_rr: 0.3  # SHORT trades in bull market
    long_rr: 0.4   # LONG trades in bull market
```

## Close Conditions

### Scalping Continues When:
- **Take Profit Hit**: Position closes at profit, bot waits for re-entry

### Scalping Stops When:

| Condition | Result |
|-----------|--------|
| **Stop Loss Hit** | Position closes at loss, scalping deactivated |
| **New PP Signal** | Trend reversal detected, scalping deactivated |
| **Time Window Ends** | Outside 8PM-10AM PT, scalping deactivated |
| **Manual Close** | Position manually closed, scalping deactivated |

## Time Window

The scalping time window restricts when the strategy is active:

- **Default**: 8:00 PM - 10:00 AM Pacific Time (overnight/Asian session)
- **Rationale**: Lower volatility periods with more predictable price movements

Time window handles overnight correctly:
- If `start > end` (e.g., 20:00 - 08:00), window spans midnight
- Scalping active if `current_time >= start OR current_time < end`

## Example Trade Flow

```
1. 9:00 PM PT - PP Signal: SELL @ 1.08500
   - Bot opens SHORT 100,000 units
   - SL: 1.08600 (SuperTrend 1.08570 + 3 pips buffer)
   - TP: 1.08460 (R:R 0.4)
   - Scalping mode activated, signal_price = 1.08500

2. 9:45 PM PT - TP Hit @ 1.08460
   - Position closed with +40 pips profit
   - Scalping: Waiting for re-entry at 1.08500

3. 10:30 PM PT - Price returns to 1.08500
   - Re-entry condition met (price >= signal_price)
   - Bot places limit order at 1.08495 (signal - 0.5 pip buffer)

4. 10:31 PM PT - Limit order filled @ 1.08495
   - Scalping entry #2
   - SL: 1.08600 (same as before)
   - TP: 1.08455 (recalculated from new entry)

5. Repeat until SL hit, new signal, or 10:00 AM PT
```

## Log Output

When scalping is active, the bot logs:
```
[5m-Market] SCALPING: ACTIVE | Entry #2 | Type: SHORT
```

When waiting for re-entry:
```
[5m-Market] SCALPING: Waiting for re-entry | Signal Price: 1.08500 | Current: 1.08520 (+2.0 pips) | Type: SHORT
```

## Best Practices

1. **Use with `disable_opposite_trade: true`**: Only trade in direction of 3H trend
2. **Conservative R:R ratios**: Lower R:R (0.3-0.4) increases TP hit probability
3. **Monitor overnight**: Scalping is designed for low-volatility periods
4. **Account risk**: Each re-entry uses the same risk amount as the first trade

## Comparison: Normal vs Scalping Mode

| Aspect | Normal Mode | Scalping Mode |
|--------|-------------|---------------|
| Entries per signal | 1 | Multiple (unlimited by default) |
| After TP hit | Wait for new signal | Re-enter at signal price |
| Time restriction | None | Time window only |
| SL handling | Normal | Deactivates scalping |
| Signal reversal | New trade | Deactivates scalping |
