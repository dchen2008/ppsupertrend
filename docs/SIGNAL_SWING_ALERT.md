# PP Signal Swing Alert Mode

The Signal Swing Alert Mode provides real-time detection when price wick crosses the previous candle's SuperTrend during a candle. When detected, the bot switches to 1-second polling and takes immediate action when the candle closes.

## Overview

During PP signal transitions (e.g., SELL→BUY), timing is critical. This feature:

1. Detects when a candle's wick crosses the previous SuperTrend (potential signal change)
2. Switches to rapid 1-second polling to monitor the candle close
3. At candle close, makes an immediate decision:
   - **Decision A**: Wick-only cross → Resume normal trading
   - **Decision B**: Close crossed → Emergency close + open opposite position

## The Problem It Solves

```
Candle1 (7:15-7:20): PP_signal=SELL, SuperTrend=1.10000 (stable, flat)
Candle2 (7:20-7:25): Price drops, wick/close may cross SuperTrend
Candle3 (7:25-7:30): New PP signal (BUY) - need immediate action
```

Without this feature, the bot might:
- Miss the signal change by 10-60 seconds (depending on check_interval)
- Update stop loss unnecessarily during the transition
- React too slowly to the new signal

## Configuration

### Enable Signal Swing Alert (Default: Enabled)

In `src/config.yaml`:
```yaml
signal_swing_alert:
  enabled: true           # Enable/disable the feature
  alert_poll_interval: 1  # Polling interval in seconds during alert mode
```

### Per-Account Override

In `account1/config.yaml`:
```yaml
signal_swing_alert:
  enabled: false  # Disable for this account only
```

## How It Works

### 1. Trigger Detection

During each normal check cycle, the bot monitors for wick crossover:

| Position | Trigger Condition | Cross Type |
|----------|------------------|------------|
| **LONG** | `candle_low < trailing_up` | `BELOW_SUPPORT` |
| **SHORT** | `candle_high > trailing_down` | `ABOVE_RESISTANCE` |

The bot compares against `last_known_trailing_up` or `last_known_trailing_down` from the previous cycle, ensuring stable reference values.

### 2. Alert Mode Activation

When triggered:
```
================================================================================
⚡ SIGNAL SWING DETECTED: Wick crossed BELOW_SUPPORT
⚡ SIGNAL SWING ALERT MODE ACTIVATED
   Position Side: LONG
   SuperTrend Reference: 1.10000
   Switching to 1-second polling...
================================================================================
```

The bot stores:
- `alert_supertrend_reference`: The SuperTrend value to compare against
- `alert_position_side`: Current position direction (LONG/SHORT)
- `alert_previous_candle_time`: To detect when new candle starts

### 3. Alert Mode Loop

The bot polls every 1 second (configurable) until:
- **New candle detected** → Execute decision
- **Position closed externally** (SL hit) → Deactivate and return to normal
- **Safety timeout** (10 minutes max) → Deactivate and return to normal

### 4. Candle Close Decision

When the candle closes, the bot checks if the **close price** crossed the SuperTrend:

| Position | Close Crossed Condition |
|----------|------------------------|
| **LONG** | `close < alert_supertrend_reference` |
| **SHORT** | `close > alert_supertrend_reference` |

**Decision A - Wick Only (Close Did NOT Cross):**
```
   ✗ Wick-only cross - close did NOT cross SuperTrend
   Resuming normal trading mode
================================================================================
⚡ SIGNAL SWING ALERT MODE DEACTIVATED
   Reason: Wick-only cross
   Returning to normal polling interval
================================================================================
```
→ The price recovered, no action needed.

**Decision B - Close Crossed:**
```
   ✓ CLOSE CROSSED - Emergency close + open opposite
   Closing LONG position...
   ✅ Position closed successfully
   Opening SHORT position...
   ✅ SHORT position opened successfully
================================================================================
⚡ SIGNAL SWING ALERT MODE DEACTIVATED
   Reason: Signal swing executed
   Returning to normal polling interval
================================================================================
```
→ Emergency close current position and open opposite direction.

## Stop Loss Handling

During alert mode:
- **Existing SL is kept** as backup protection
- **SL updates are skipped** to avoid unnecessary modifications during signal transition
- New position after signal swing uses the **new candle's SuperTrend** (supertrend_price3)

## CSV Logging

Signal swing closes are logged to CSV with:
- `close_reason`: `SIGNAL_SWING`
- `take_profit_hit`: `NO`
- `stop_loss_hit`: `NO`

## Edge Cases

| Scenario | Behavior |
|----------|----------|
| Bot restart during alert | Alert is transient state; starts fresh |
| Position closed by SL during alert | Detects closure, deactivates alert mode |
| News filter active during alert | News logic takes priority |
| Multiple wicks same candle | Only triggers once per candle |

## Log Output Examples

### Alert Triggered (LONG position, wick breaks support):
```
[5m-Market] WARNING - ⚡ SIGNAL SWING DETECTED: Wick crossed BELOW_SUPPORT
[5m-Market] WARNING - ⚡ SIGNAL SWING ALERT MODE ACTIVATED
[5m-Market] WARNING -    Position Side: LONG
[5m-Market] WARNING -    SuperTrend Reference: 1.10000
[5m-Market] WARNING -    Switching to 1-second polling...
[5m-Market] INFO - 🔴 Entering alert mode loop
[5m-Market] INFO -    🔴 Alert mode: polling... (loop 10, mid=1.09950)
[5m-Market] INFO -    🔴 Alert mode: polling... (loop 20, mid=1.09920)
```

### Decision A (Wick-only, resume normal):
```
[5m-Market] INFO - ⏰ CANDLE CLOSED - Executing signal swing decision
[5m-Market] INFO -    Closed candle close: 1.10050
[5m-Market] INFO -    LONG check: close=1.10050 < ref=1.10000 = False
[5m-Market] INFO -    ✗ Wick-only cross - close did NOT cross SuperTrend
[5m-Market] INFO -    Resuming normal trading mode
[5m-Market] INFO - ⚡ SIGNAL SWING ALERT MODE DEACTIVATED
```

### Decision B (Close crossed, emergency action):
```
[5m-Market] INFO - ⏰ CANDLE CLOSED - Executing signal swing decision
[5m-Market] INFO -    Closed candle close: 1.09850
[5m-Market] INFO -    LONG check: close=1.09850 < ref=1.10000 = True
[5m-Market] WARNING -    ✓ CLOSE CROSSED - Emergency close + open opposite
[5m-Market] INFO -    Closing LONG position...
[5m-Market] INFO -    ✅ Position closed successfully
[5m-Market] INFO -    💾 Updated CSV: Trade #1234 SIGNAL_SWING, P/L=$-25.50
[5m-Market] INFO -    Opening SHORT position...
[5m-Market] INFO -    ✅ SHORT position opened successfully
[5m-Market] INFO - ⚡ SIGNAL SWING ALERT MODE DEACTIVATED
```

## Technical Details

### State Variables

```python
# PP Signal Swing Alert Mode state
self.signal_swing_alert_enabled = True/False
self.signal_swing_alert_poll_interval = 1  # seconds
self.signal_swing_alert_active = False
self.alert_supertrend_reference = None     # SuperTrend to compare against
self.alert_candle_start_time = None
self.alert_position_side = None            # 'LONG' or 'SHORT'
self.alert_previous_candle_time = None     # For candle close detection
self.last_known_trailing_up = None         # Tracking from previous cycle
self.last_known_trailing_down = None       # Tracking from previous cycle
```

### Methods Added

| Method | Purpose |
|--------|---------|
| `_get_realtime_price()` | Fetch current price + candle high/low for wick detection |
| `_check_signal_swing_alert_trigger()` | Detect if wick crosses previous SuperTrend |
| `_activate_signal_swing_alert()` | Enter alert mode, store reference values |
| `_run_alert_mode_loop()` | 1-second polling loop until candle closes |
| `_execute_signal_swing_decision()` | Decision at candle close (A or B) |
| `_log_signal_swing_close()` | Log signal swing close to CSV |
| `_deactivate_signal_swing_alert()` | Cleanup and return to normal |
| `_reset_position_tracking()` | Helper to reset position tracking variables |

### Modified Methods

| Method | Changes |
|--------|---------|
| `fetch_and_calculate_indicators()` | Tracks `last_known_supertrend` values |
| `check_and_trade()` | Adds trigger check, returns `True` when alert activated, skips SL update when alert active |
| `run()` | Checks return value, enters alert mode loop when triggered |

## Comparison with Emergency Close

| Feature | Emergency Close | Signal Swing Alert |
|---------|----------------|-------------------|
| Trigger | Closed candle close crossed SuperTrend | Wick crossed SuperTrend (real-time) |
| Timing | After candle closed, during next check cycle | Immediately when wick crosses |
| Polling | Normal interval (10-60s) | 1-second polling |
| False Positives | None (uses closed candle) | Possible (wick-only crosses filtered) |
| Response Time | 10-60 seconds delay | Sub-second at candle close |

The Signal Swing Alert complements the existing Emergency Close by providing faster detection and response during critical signal transitions.
