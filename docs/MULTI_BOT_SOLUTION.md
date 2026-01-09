# Running Multiple Bots Concurrently - Solution

## The Problem You're Experiencing

You're running 4 bots simultaneously:
```bash
./auto_trade.sh EUR_USD tf:5m sl:SuperTrend
./auto_trade.sh EUR_USD tf:15m sl:SuperTrend
./auto_trade.sh EUR_USD tf:5m sl:PPCenterLine
./auto_trade.sh EUR_USD tf:15m sl:PPCenterLine
```

**Only the first one can place orders successfully!** ❌

---

## Why This Happens: OANDA's Netting System

OANDA uses **netting**, which means:
- ✅ You can only have **ONE net position per instrument**
- ❌ Cannot have separate positions for different strategies
- ❌ All bots fight over the same EUR_USD position

### What's Happening:

```
Timeline:
──────────────────────────────────────────
Bot 1 (5m SuperTrend):
  Opens SHORT 1 unit
  ✅ Success - first position created

Bot 2 (15m PPCenterLine):
  Tries to open SHORT 49,640 units
  ✅ OANDA nets: Closes 1 SHORT, Opens 49,640 SHORT
  Result: Net SHORT 49,640 units

Bot 3 (15m SuperTrend):
  Tries to open LONG 100,000 units
  ❌ BLOCKED: Would conflict with existing SHORT 49,640
  OANDA rejects or nets into the existing position

Bot 4 (5m PPCenterLine):
  Tries to open LONG 80,000 units
  ❌ BLOCKED: Would conflict with existing SHORT 49,640
```

**All 4 bots are trying to manage the SAME position!**

---

## Solution Options

### **Option 1: Trade Different Instruments** ⭐ RECOMMENDED

Each bot trades a different currency pair:

```bash
# Run 4 different pairs
./auto_trade.sh EUR_USD tf:5m sl:SuperTrend     # Bot 1
./auto_trade.sh GBP_USD tf:15m sl:SuperTrend    # Bot 2
./auto_trade.sh USD_JPY tf:5m sl:PPCenterLine   # Bot 3
./auto_trade.sh AUD_USD tf:15m sl:PPCenterLine  # Bot 4
```

**Pros:**
- ✅ Simple - no code changes needed
- ✅ Each bot has its own position
- ✅ Diversified across multiple pairs
- ✅ No conflicts

**Cons:**
- ❌ Can't compare strategies on same pair

---

### **Option 2: Position Ownership Tracking**

Modify bots to track which position they opened:

```python
# Bot stores: "I opened position 12345"
# Other bots ignore position 12345
```

**Implementation:**
1. Add position ownership file (JSON)
2. Bots claim positions when opening
3. Bots skip positions owned by others
4. Release ownership when closed

**Pros:**
- ✅ All bots run on EUR_USD
- ✅ Strategies can be compared

**Cons:**
- ❌ Complex to implement
- ❌ Still limited by OANDA netting
- ❌ Only 1 active position at a time

---

### **Option 3: Use OANDA Sub-Accounts**

Create 4 separate OANDA practice accounts:

1. Account A: Bot 1 (5m SuperTrend)
2. Account B: Bot 2 (15m SuperTrend)
3. Account C: Bot 3 (5m PPCenterLine)
4. Account D: Bot 4 (15m PPCenterLine)

**Steps:**
1. Create additional practice accounts on OANDA
2. Modify config.py to support multiple accounts
3. Each bot uses different account

**Pros:**
- ✅ Complete isolation
- ✅ All trade same pair
- ✅ Easy to compare results

**Cons:**
- ❌ Need multiple accounts
- ❌ Code changes required

---

### **Option 4: Master Coordinator Bot**

One bot runs all 4 strategies and picks best signal:

```python
# Master bot evaluates:
signals = {
    '5m_supertrend': 'BUY',
    '15m_supertrend': 'SELL',
    '5m_ppcenterline': 'HOLD',
    '15m_ppcenterline': 'BUY'
}

# Pick based on:
# - Majority vote
# - Highest timeframe wins
# - Strongest signal
# - Your preference
```

**Pros:**
- ✅ One position, best signal
- ✅ No conflicts

**Cons:**
- ❌ Can't test strategies separately
- ❌ Complex logic
- ❌ Defeats comparison purpose

---

## Current Status (With Option B)

Now that you've enabled **Option B** (let stop loss handle exits):

### What Happens with Multiple Bots:

```
Scenario 1: All bots agree on direction
────────────────────────────────────────
Bot 1: SHORT signal
Bot 2: SHORT signal
Bot 3: SHORT signal
Bot 4: SHORT signal
→ First bot opens SHORT
→ Other bots see existing SHORT → HOLD
✅ Works fine

Scenario 2: Bots disagree on direction
────────────────────────────────────────
Bot 1: Opened SHORT position
Bot 2: LONG signal (opposite!)
→ With Option B: Bot 2 HOLDS (doesn't try to close SHORT)
→ Logs warning, waits for SL
✅ No conflicts, but only 1 bot's strategy is active

Scenario 3: First bot exits via SL
────────────────────────────────────────
Bot 1: SHORT hit stop loss → Closed
Bot 2: Now has LONG signal → Can open
→ Bot 2 opens LONG position
✅ Bot 2 gets its turn
```

---

## Recommendation

Since you want to **test all 4 configurations**, use **Option 1**:

### Setup:

```bash
# Terminal 1
./auto_trade.sh EUR_USD tf:5m sl:SuperTrend

# Terminal 2
./auto_trade.sh GBP_USD tf:15m sl:SuperTrend

# Terminal 3
./auto_trade.sh USD_JPY tf:5m sl:PPCenterLine

# Terminal 4
./auto_trade.sh AUD_USD tf:15m sl:PPCenterLine
```

### Or Test Same Strategy on Different Pairs:

```bash
# Compare 5m SuperTrend across pairs
./auto_trade.sh EUR_USD tf:5m sl:SuperTrend
./auto_trade.sh GBP_USD tf:5m sl:SuperTrend
./auto_trade.sh USD_JPY tf:5m sl:SuperTrend
./auto_trade.sh AUD_USD tf:5m sl:SuperTrend
```

---

## Alternative: Sequential Testing

Run one strategy at a time for a period:

**Week 1**: Test 5m SuperTrend on EUR_USD
**Week 2**: Test 15m SuperTrend on EUR_USD
**Week 3**: Test 5m PPCenterLine on EUR_USD
**Week 4**: Test 15m PPCenterLine on EUR_USD

Then compare results!

---

## CSV Logs Show The Problem

Your current CSV files:
- ✅ `EUR_USD_5m_sl-SuperTrend.csv`: 2 trades
- ✅ `EUR_USD_15m_sl-PPCenterLine.csv`: 1 trade (active)
- ❌ `EUR_USD_15m_sl-SuperTrend.csv`: Empty
- ❌ `EUR_USD_5m_sl-PPCenterLine.csv`: Empty

The empty ones couldn't place orders because of the existing position.

---

## Summary

**To run 4 bots successfully:**
1. Trade different instruments (EUR_USD, GBP_USD, USD_JPY, AUD_USD)
2. Or test sequentially (one at a time)
3. Or implement Option 3 (sub-accounts)

**Current setup won't work** because OANDA only allows one position per instrument!

Let me know which solution you'd like me to implement! 🚀
