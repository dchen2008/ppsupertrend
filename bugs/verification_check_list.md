
1. 3H PP sign[sell|buy] bear|bull are correct

2. 5min/15min pp signs[sell|buy] change correct

3. new order enter time after the candle close, but still has room to optimize: why wait 56seconds to enter the order.
It should enter the order first second at: 04:56:01

Time: 2026-01-15 05:30:55 Pacific Time (PT)
SCALPING: ACTIVE | Entry #1 | Type: SHORT
Account: account26 | Market: BEAR | Balance: $100054.09 | P/L: $76.58
Trade ID:        358 | [SHORT] 84,158 units | entry_time: 2026-01-15 04:56:56
Entry Price:     1.16230 (bid)
SuperTrend:      1.16395
Init SL:         1.16395 (raw SuperTrend)
Init TP:         1.16169 (Expected TP R:R = 0.9)
Risk Amount:     $100.00
Est. Max Loss:   $154.53 (if SL triggered at 1.16414)
>>> NOW POSITION
Fill Price:      1.16230
Take Profit:     1.16082
Stop Loss:       1.16414 (trailing SuperTrend + 3 pip buffer)
>>> RISK/REWARD estimate
Risk (to SL):    21.6 pips  |  Potential Loss:   $181.46
Reward (to TP):  11.6 pips  |  Potential Profit: $97.62
Actual R:R:      0.54

4. when the SL price is lower than enter price, the position still not reach RR:2.0 close price.
Do we need know why? Seem 2.0 can't be reached at this moment, 
The 2.0

--------------------------------------------------------------------------------
[5m-Market] 2026-01-15 10:00:03 - INFO -   Stop Loss Adjustment (SHORT): 1.16135 → 1.16165 (+3 pips buffer)
--------------------------------------------------------------------------------
Time: 2026-01-15 10:00:07 Pacific Time (PT)
SCALPING: ENABLED=FALSE
Account: account4 | Market: BEAR | Balance: $100071.34 | P/L: $109.41
Trade ID:        483 | [SHORT] 84,158 units | entry_time: 2026-01-15 04:56:52
Entry Price:     1.16229 (bid)
SuperTrend:      1.16135
Init SL:         1.16135 (raw SuperTrend)
Init TP:         1.15897 (Expected TP R:R = 2.0)
Risk Amount:     $100.00
Est. Max Loss:   $-53.86 (if SL triggered at 1.16165)
>>> NOW POSITION
Fill Price:      1.16229
Take Profit:     1.15897 (⚠️ Approaching Take Profit Target: 109.41% --> 200%)
Stop Loss:       1.16165 (trailing SuperTrend + 3 pip buffer)
>>> RISK/REWARD estimate
Risk (to SL):    7.5 pips  |  Potential Loss:   $63.12
Reward (to TP):  19.3 pips  |  Potential Profit: $162.42
Actual R:R:      2.57
--------------------------------------------------------------------------------
[5m-Market] 2026-01-15 10:00:07 - INFO -   Stop Loss Adjustment (SHORT): 1.16135 → 1.16165 (+3 pips buffer)
--------------------------------------------------------------------------------
Time: 2026-01-15 10:00:10 Pacific Time (PT)
SCALPING: ENABLED=FALSE
Account: account4 | Market: BEAR | Balance: $100071.34 | P/L: $109.41
Trade ID:        483 | [SHORT] 84,158 units | entry_time: 2026-01-15 04:56:52
Entry Price:     1.16229 (bid)
SuperTrend:      1.16135
Init SL:         1.16135 (raw SuperTrend)
Init TP:         1.15897 (Expected TP R:R = 2.0)
Risk Amount:     $100.00
Est. Max Loss:   $-53.86 (if SL triggered at 1.16165)
>>> NOW POSITION
Fill Price:      1.16229
Take Profit:     1.15897 (⚠️ Approaching Take Profit Target: 109.41% --> 200%)
Stop Loss:       1.16165 (trailing SuperTrend + 3 pip buffer)
>>> RISK/REWARD estimate
Risk (to SL):    7.5 pips  |  Potential Loss:   $63.12
Reward (to TP):  19.3 pips  |  Potential Profit: $162.42
Actual R:R:      2.57
-------------------------------------------


5. emergency close: when price crossed SuperTrend, failure log:
--------------------------------------------------------------------------------
[5m-Market] 2026-01-15 10:05:01 - INFO -   Stop Loss Adjustment (SHORT): 1.16135 → 1.16165 (+3 pips buffer)
--------------------------------------------------------------------------------
Time: 2026-01-15 10:05:05 Pacific Time (PT)
SCALPING: ENABLED=FALSE
Account: account4 | Market: BEAR | Balance: $100071.34 | P/L: $68.17
Trade ID:        483 | [SHORT] 84,158 units | entry_time: 2026-01-15 04:56:52
Entry Price:     1.16229 (bid)
SuperTrend:      1.15986
Init SL:         1.15986 (raw SuperTrend)
Init TP:         1.15897 (Expected TP R:R = 2.0)
Risk Amount:     $100.00
Est. Max Loss:   $-53.86 (if SL triggered at 1.16165)
>>> NOW POSITION
Fill Price:      1.16229
Take Profit:     1.15897 (⚠️ Approaching Take Profit Target: 68.17% --> 200%)
Stop Loss:       1.16165 (trailing SuperTrend + 3 pip buffer)
>>> RISK/REWARD estimate
Risk (to SL):    2.1 pips  |  Potential Loss:   $17.67
Reward (to TP):  24.7 pips  |  Potential Profit: $207.87
Actual R:R:      11.76
--------------------------------------------------------------------------------
[5m-Market] 2026-01-15 10:05:05 - WARNING - ================================================================================
[5m-Market] 2026-01-15 10:05:05 - WARNING - ⚠️  EMERGENCY CLOSE: Price crossed SuperTrend!
[5m-Market] 2026-01-15 10:05:05 - WARNING -    Position: SHORT
[5m-Market] 2026-01-15 10:05:05 - WARNING -    Close Price: 1.16144 crossed ABOVE SuperTrend: 1.15986
[5m-Market] 2026-01-15 10:05:05 - WARNING -    Reason: Protecting against sudden reversal (not waiting for confirmation bar)
[5m-Market] 2026-01-15 10:05:05 - WARNING - ================================================================================
🚨 API REQUEST ERROR (1/3): close_position()
   Error: 400 Client Error: Bad Request for url: https://api-fxpractice.oanda.com/v3/accounts/101-001-38195467-001/positions/EUR_USD/close
   Status Code: 400
   Response: {"longOrderRejectTransaction":{"id":"510","accountID":"101-001-38195467-001","userID":38195467,"batchID":"510","requestID":"79475221941878190","time":"2026-01-15T18:05:05.571703674Z","type":"MARKET_ORDER_REJECT","rejectReason":"CLOSEOUT_POSITION_DOESNT_EXIST","instrument":"EUR_USD","timeInForce":"FOK","positionFill":"REDUCE_ONLY","reason":"POSITION_CLOSEOUT","longPositionCloseout":{"instrument":"EUR_USD","units":"ALL"}},"shortOrderRejectTransaction":{"id":"511","accountID":"101-001-38195467-001","userID":38195467,"batchID":"510","requestID":"79475221941878190","time":"2026-01-15T18:05:05.571703674Z","type":"MARKET_ORDER_REJECT","rejectReason":"CLOSEOUT_POSITION_REJECT","instrument":"EUR_USD","units":"84158","timeInForce":"FOK","positionFill":"REDUCE_ONLY","reason":"POSITION_CLOSEOUT","shortPositionCloseout":{"instrument":"EUR_USD","units":"ALL"}},"relatedTransactionIDs":["510","511"],"lastTransactionID":"511","errorMessage":"The Position requested to be closed out does not exist","errorCode":"CLOSEOUT_POSITION_DOESNT_EXIST"}
   Retrying in 1s...
🚨 API REQUEST ERROR (2/3): close_position()
   Error: 400 Client Error: Bad Request for url: https://api-fxpractice.oanda.com/v3/accounts/101-001-38195467-001/positions/EUR_USD/close
   Status Code: 400
   Response: {"longOrderRejectTransaction":{"id":"512","accountID":"101-001-38195467-001","userID":38195467,"batchID":"512","requestID":"97489620455782104","time":"2026-01-15T18:05:06.719402329Z","type":"MARKET_ORDER_REJECT","rejectReason":"CLOSEOUT_POSITION_DOESNT_EXIST","instrument":"EUR_USD","timeInForce":"FOK","positionFill":"REDUCE_ONLY","reason":"POSITION_CLOSEOUT","longPositionCloseout":{"instrument":"EUR_USD","units":"ALL"}},"shortOrderRejectTransaction":{"id":"513","accountID":"101-001-38195467-001","userID":38195467,"batchID":"512","requestID":"97489620455782104","time":"2026-01-15T18:05:06.719402329Z","type":"MARKET_ORDER_REJECT","rejectReason":"CLOSEOUT_POSITION_REJECT","instrument":"EUR_USD","units":"84158","timeInForce":"FOK","positionFill":"REDUCE_ONLY","reason":"POSITION_CLOSEOUT","shortPositionCloseout":{"instrument":"EUR_USD","units":"ALL"}},"relatedTransactionIDs":["512","513"],"lastTransactionID":"513","errorMessage":"The Position requested to be closed out does not exist","errorCode":"CLOSEOUT_POSITION_DOESNT_EXIST"}
   Retrying in 1s...
🚨 API REQUEST ERROR (3/3): close_position()
   Error: 400 Client Error: Bad Request for url: https://api-fxpractice.oanda.com/v3/accounts/101-001-38195467-001/positions/EUR_USD/close
   Status Code: 400
   Response: {"longOrderRejectTransaction":{"id":"514","accountID":"101-001-38195467-001","userID":38195467,"batchID":"514","requestID":"97489620459977490","time":"2026-01-15T18:05:07.865417271Z","type":"MARKET_ORDER_REJECT","rejectReason":"CLOSEOUT_POSITION_DOESNT_EXIST","instrument":"EUR_USD","timeInForce":"FOK","positionFill":"REDUCE_ONLY","reason":"POSITION_CLOSEOUT","longPositionCloseout":{"instrument":"EUR_USD","units":"ALL"}},"shortOrderRejectTransaction":{"id":"515","accountID":"101-001-38195467-001","userID":38195467,"batchID":"514","requestID":"97489620459977490","time":"2026-01-15T18:05:07.865417271Z","type":"MARKET_ORDER_REJECT","rejectReason":"CLOSEOUT_POSITION_REJECT","instrument":"EUR_USD","units":"84158","timeInForce":"FOK","positionFill":"REDUCE_ONLY","reason":"POSITION_CLOSEOUT","shortPositionCloseout":{"instrument":"EUR_USD","units":"ALL"}},"relatedTransactionIDs":["514","515"],"lastTransactionID":"515","errorMessage":"The Position requested to be closed out does not exist","errorCode":"CLOSEOUT_POSITION_DOESNT_EXIST"}
   ❌ Max retries reached for close_position(). Giving up.
[5m-Market] 2026-01-15 10:05:07 - ERROR - ❌ Emergency close failed - no result returned
[5m-Market] 2026-01-15 10:05:07 - INFO -   Stop Loss Adjustment (SHORT): 1.15986 → 1.16016 (+3 pips buffer)
[5m-Market] 2026-01-15 10:05:07 - INFO - 🔄 Updating trailing stop: 1.16165 → 1.16016
[5m-Market] 2026-01-15 10:05:08 - INFO -   Refreshed SL Order ID: 509
[5m-Market] 2026-01-15 10:05:08 - INFO - ✅ Stop loss updated
[5m-Market] 2026-01-15 10:05:12 - INFO - 📍 Position closed externally (manual/other): P/L=$0.00 (0.00%)
[5m-Market] 2026-01-15 10:05:12 - INFO -    💾 Logged external close to CSV: Trade #483, P/L=$0.00 (0.00%), TP=FALSE, SL=FALSE


❯ How did you know the bot At 10:05:07 - Bot lowered stop loss from 1.16165 → 1.16016 (trailing with new SuperTrend) ? 

⏺ From the log you provided:

  [5m-Market] 2026-01-15 10:05:07 - INFO -   Stop Loss Adjustment (SHORT): 1.15986 → 1.16016 (+3 pips buffer)
  [5m-Market] 2026-01-15 10:05:07 - INFO - 🔄 Updating trailing stop: 1.16165 → 1.16016
  [5m-Market] 2026-01-15 10:05:08 - INFO -   Refreshed SL Order ID: 509
  [5m-Market] 2026-01-15 10:05:08 - INFO - ✅ Stop loss updated

  This shows:
  1. SuperTrend dropped to 1.15986
  2. Bot calculated new SL: 1.15986 + 3 pips buffer = 1.16016
  3. Bot updated trailing stop from 1.16165 → 1.16016
  4. Stop loss update succeeded

  The problem: The bot lowered the stop loss to 1.16016, but price was already at ~1.16149 (above 1.16016). So when OANDA received the new SL order at 1.16016, price had already crossed it, and OANDA immediately filled the stop loss.

