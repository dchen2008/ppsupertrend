# Trading Bot Test Scenarios

This document lists all major business scenarios covered by the automated test suite.

## Summary

| Category | Tests | Coverage |
|----------|-------|----------|
| One Order Per Signal | 14 | Prevents duplicate trades |
| Disable Opposite Trade Filter | 25 | Market trend filtering |
| Signal Detection | 21 | BUY/SELL vs HOLD distinction |
| Indicator Calculations | 34 | PP SuperTrend accuracy |
| Risk Manager | 34 | Position sizing, SL, TP |
| **Total** | **128** | Core trading logic |

---

## 1. One Order Per Signal (14 tests)

**Purpose:** Prevents phantom trades and duplicate orders on the same signal candle.

| # | Scenario | Expected Behavior |
|---|----------|-------------------|
| 1 | Same signal + same candle time | Reject trade (HOLD) |
| 2 | Same signal + different candle time | Allow trade |
| 3 | Fresh start (no previous signal) | Allow trade |
| 4 | Multiple rapid signals on same candle | Only first executed |
| 5 | SELL signal duplicate prevention | Same as BUY |
| 6 | HOLD_LONG signal | Never triggers trade |
| 7 | HOLD_SHORT signal | Never triggers trade |
| 8 | Trend reversal respects rule | One order per reversal candle |
| 9 | New candle after reversal | Allows new trade |
| 10 | Timestamp string comparison | Handles format correctly |
| 11 | Timestamp microsecond precision | Candle-aligned comparison |
| 12 | Signal after long time gap | Allows trade |
| 13 | Consecutive different signals | Both allowed on different candles |
| 14 | State update timing | Only update after successful trade |

---

## 2. Disable Opposite Trade Filter (25 tests)

**Purpose:** Prevents trades against the 3H market trend when `disable_opposite_trade=True`.

### 2.1 BEAR Market Scenarios (3H trend = SELL)

| # | Scenario | Expected Behavior |
|---|----------|-------------------|
| 1 | BUY signal in BEAR market | **Blocked** (HOLD) |
| 2 | SELL signal in BEAR market | Allowed (OPEN_SHORT) |
| 3 | LONG→SHORT reversal in BEAR | Close LONG + Open SHORT |
| 4 | SHORT→LONG reversal in BEAR | **Close SHORT only** (no LONG) |

### 2.2 BULL Market Scenarios (3H trend = BUY)

| # | Scenario | Expected Behavior |
|---|----------|-------------------|
| 5 | SELL signal in BULL market | **Blocked** (HOLD) |
| 6 | BUY signal in BULL market | Allowed (OPEN_LONG) |
| 7 | SHORT→LONG reversal in BULL | Close SHORT + Open LONG |
| 8 | LONG→SHORT reversal in BULL | **Close LONG only** (no SHORT) |

### 2.3 Filter Disabled Scenarios

| # | Scenario | Expected Behavior |
|---|----------|-------------------|
| 9 | LONG in BEAR (filter OFF) | Allowed |
| 10 | SHORT in BULL (filter OFF) | Allowed |
| 11 | Reversal (filter OFF) | Always opens opposite position |

### 2.4 Neutral/None Market Scenarios

| # | Scenario | Expected Behavior |
|---|----------|-------------------|
| 12 | LONG in NEUTRAL market | Allowed |
| 13 | SHORT in NEUTRAL market | Allowed |
| 14 | LONG with None market_trend | Allowed |
| 15 | SHORT with None market_trend | Allowed |

### 2.5 Config Edge Cases

| # | Scenario | Expected Behavior |
|---|----------|-------------------|
| 16 | Missing config | Allows all trades |
| 17 | Empty position_sizing config | Allows all trades |

### 2.6 Parametrized Matrix (8 combinations)

| Market | Signal | Expected |
|--------|--------|----------|
| BEAR | BUY | HOLD |
| BEAR | SELL | OPEN_SHORT |
| BULL | BUY | OPEN_LONG |
| BULL | SELL | HOLD |
| NEUTRAL | BUY | OPEN_LONG |
| NEUTRAL | SELL | OPEN_SHORT |
| None | BUY | OPEN_LONG |
| None | SELL | OPEN_SHORT |

---

## 3. Signal Detection (21 tests)

**Purpose:** Ensures BUY/SELL only on crossovers, HOLD states don't trigger trades.

### 3.1 BUY Signal Generation

| # | Scenario | Expected Behavior |
|---|----------|-------------------|
| 1 | Trend crossover -1 → +1 | BUY signal generated |
| 2 | Uptrend continuation | **No new BUY** (HOLD_LONG) |
| 3 | BUY signal validation | prev_trend=-1, curr_trend=+1 |

### 3.2 SELL Signal Generation

| # | Scenario | Expected Behavior |
|---|----------|-------------------|
| 4 | Trend crossover +1 → -1 | SELL signal generated |
| 5 | Downtrend continuation | **No new SELL** (HOLD_SHORT) |
| 6 | SELL signal validation | prev_trend=+1, curr_trend=-1 |

### 3.3 HOLD State Verification

| # | Scenario | Expected Behavior |
|---|----------|-------------------|
| 7 | Uptrend without crossover | Returns HOLD_LONG |
| 8 | Downtrend without crossover | Returns HOLD_SHORT |
| 9 | HOLD_LONG ≠ BUY | Distinct signal states |
| 10 | HOLD_SHORT ≠ SELL | Distinct signal states |

### 3.4 Signal Info Structure

| # | Scenario | Expected Behavior |
|---|----------|-------------------|
| 11 | Required fields present | signal, trend, supertrend, price, etc. |
| 12 | Trend matches indicator | signal['trend'] == df['trend'].iloc[-1] |
| 13 | SuperTrend value accuracy | Matches indicator value |

### 3.5 Edge Cases

| # | Scenario | Expected Behavior |
|---|----------|-------------------|
| 14 | Empty DataFrame | Returns None |
| 15 | Minimal candles (20) | Still produces signal |
| 16 | Ranging market | BUY and SELL mutually exclusive |

### 3.6 Trend Determination

| # | Scenario | Expected Behavior |
|---|----------|-------------------|
| 17 | Valid trend values | Only 0, 1, or -1 |
| 18 | Strong uptrend | Ends with trend=+1 |
| 19 | Strong downtrend | Ends with trend=-1 |
| 20 | Trend persistence | No random flips in strong trend |

### 3.7 Debug Info

| # | Scenario | Expected Behavior |
|---|----------|-------------------|
| 21 | Debug info included | prev_trend, curr_trend, trend_changed |

---

## 4. Indicator Calculations (34 tests)

**Purpose:** Validates PP SuperTrend mathematical accuracy.

### 4.1 ATR Calculation (4 tests)

| # | Scenario | Expected Behavior |
|---|----------|-------------------|
| 1 | Basic ATR calculation | First N-1 values NaN, rest valid |
| 2 | ATR values positive | All valid ATR > 0 |
| 3 | Period affects result | Different periods → different values |
| 4 | Gap candles handling | Calculates correctly with gaps |

### 4.2 Pivot Detection (6 tests)

| # | Scenario | Expected Behavior |
|---|----------|-------------------|
| 5 | Detect pivot highs | Finds peaks in data |
| 6 | Detect pivot lows | Finds troughs in data |
| 7 | Period=1 detection | More pivots detected |
| 8 | Period=2 detection | Fewer pivots detected |
| 9 | Period=3 detection | Even fewer pivots |
| 10 | Period=5 detection | Fewest, most significant |
| 11 | Pivot high values | Match actual high prices |
| 12 | Pivot low values | Match actual low prices |

### 4.3 Pivot Center (2 tests)

| # | Scenario | Expected Behavior |
|---|----------|-------------------|
| 13 | Center line calculated | Has valid values |
| 14 | Center updates on pivot | Changes when new pivot detected |

### 4.4 PP SuperTrend (12 tests)

| # | Scenario | Expected Behavior |
|---|----------|-------------------|
| 15 | All columns calculated | atr, trend, supertrend, signals, etc. |
| 16 | Valid trend values | Only 0, 1, -1 |
| 17 | Uptrend → trend=+1 | Strong uptrend produces positive |
| 18 | Downtrend → trend=-1 | Strong downtrend produces negative |
| 19 | BUY on trend change up | buy_signal when -1 → +1 |
| 20 | SELL on trend change down | sell_signal when +1 → -1 |
| 21 | Mutually exclusive signals | Never both BUY and SELL |
| 22 | ATR factor=1.0 bands | Narrow bands |
| 23 | ATR factor=2.0 bands | Medium bands |
| 24 | ATR factor=3.0 bands | Wide bands |
| 25 | ATR factor=5.0 bands | Widest bands |
| 26 | SuperTrend follows trend | Uses trailing_up or trailing_down |

### 4.5 Get Current Signal (8 tests)

| # | Scenario | Expected Behavior |
|---|----------|-------------------|
| 27 | Correct structure | All expected keys present |
| 28 | Valid signal values | BUY, SELL, HOLD_LONG, HOLD_SHORT |
| 29 | Trend matches | signal['trend'] == indicator trend |
| 30 | Price is close | signal['price'] == last close |
| 31 | Empty DataFrame | Returns None |
| 32 | HOLD_LONG in uptrend | When no crossover |
| 33 | HOLD_SHORT in downtrend | When no crossover |
| 34 | Debug info included | Has prev_trend, curr_trend |

---

## 5. Risk Manager (34 tests)

**Purpose:** Validates position sizing, stop loss, take profit, and trade validation.

### 5.1 Position Sizing (6 tests)

| # | Scenario | Expected Behavior |
|---|----------|-------------------|
| 1 | Dynamic sizing with fixed risk | Position scales with stop |
| 2 | Wider stop → smaller position | Inverse relationship |
| 3 | BEAR + SHORT | Risk = $300 |
| 4 | BEAR + LONG | Risk = $100 |
| 5 | BULL + LONG | Risk = $300 |
| 6 | BULL + SHORT | Risk = $100 |
| 7 | Min position size | At least 1000 units |
| 8 | Neutral market | Uses default risk |

### 5.2 Stop Loss Calculation (4 tests)

| # | Scenario | Expected Behavior |
|---|----------|-------------------|
| 9 | BUY → SL at SuperTrend | Below entry price |
| 10 | SELL → SL at SuperTrend | Above entry price |
| 11 | None SuperTrend | Returns None |
| 12 | Rounded to 5 decimals | Proper OANDA format |

### 5.3 Take Profit Calculation (5 tests)

| # | Scenario | Expected Behavior |
|---|----------|-------------------|
| 13 | LONG, 10 pip risk, 2 RR | TP = entry + 20 pips |
| 14 | LONG, 10 pip risk, 1 RR | TP = entry + 10 pips |
| 15 | SHORT, 10 pip risk, 2 RR | TP = entry - 20 pips |
| 16 | SHORT, 10 pip risk, 0.5 RR | TP = entry - 5 pips |
| 17 | None stop | Returns None |
| 18 | None entry | Returns None |
| 19 | Rounded to 5 decimals | Proper OANDA format |

### 5.4 Should Trade Decision (9 tests)

| # | Scenario | Expected Behavior |
|---|----------|-------------------|
| 20 | BUY + no position | OPEN_LONG |
| 21 | SELL + no position | OPEN_SHORT |
| 22 | HOLD_LONG signal | No action (HOLD) |
| 23 | HOLD_SHORT signal | No action (HOLD) |
| 24 | SELL + LONG position | CLOSE + OPEN_SHORT |
| 25 | BUY + SHORT position | CLOSE + OPEN_LONG |
| 26 | Zero units = no position | Treated as no position |

### 5.5 Trade Validation (5 tests)

| # | Scenario | Expected Behavior |
|---|----------|-------------------|
| 27 | Valid account | Trade validated |
| 28 | None account | Fails - cannot fetch |
| 29 | Zero margin | Fails - insufficient |
| 30 | Zero balance | Fails - zero balance |
| 31 | Negative margin | Fails |

### 5.6 Risk Amount Selection (6 tests)

| # | Scenario | Expected Behavior |
|---|----------|-------------------|
| 32 | BEAR + SHORT | $300 higher risk |
| 33 | BEAR + LONG | $100 lower risk |
| 34 | BULL + LONG | $300 higher risk |
| 35 | BULL + SHORT | $100 lower risk |
| 36 | NEUTRAL | Default $100 |
| 37 | None config | Uses TradingConfig |

---

## Test Commands

```bash
# Run all tests
python3 -m pytest tests/unit/ tests/integration/ -v

# Run critical path tests only (One Order + Opposite Trade + Signal)
python3 -m pytest tests/integration/ -v

# Run with coverage
python3 -m pytest tests/ --ignore=tests/live/ --cov=src --cov-report=term-missing

# Run specific category
python3 -m pytest tests/integration/test_one_order_per_signal.py -v
python3 -m pytest tests/integration/test_opposite_trade_filter.py -v
python3 -m pytest tests/integration/test_signal_detection.py -v
python3 -m pytest tests/unit/test_indicators.py -v
python3 -m pytest tests/unit/test_risk_manager.py -v
```

---

## Coverage Summary

| Module | Coverage | Description |
|--------|----------|-------------|
| `indicators.py` | 98% | PP SuperTrend calculations |
| `risk_manager.py` | 86% | Trade decisions, sizing |
| `config.py` | 94% | Configuration loading |
| `oanda_client.py` | 37% | API calls (mocked) |

---

## Critical Business Rules Tested

1. **One Order Per Signal**: Bot NEVER places more than one order per PP SuperTrend signal candle
2. **Phantom Trade Prevention**: HOLD_LONG/HOLD_SHORT states do NOT trigger new trades
3. **Market Trend Filter**: Trades against 3H trend are blocked when `disable_opposite_trade=True`
4. **Signal vs Hold Distinction**: BUY/SELL only on crossovers, not trend continuation
5. **Dynamic Position Sizing**: Risk amount varies by market trend + position direction
6. **Spread Adjustment**: Stop loss adjusted for BID/ASK vs MID price difference
