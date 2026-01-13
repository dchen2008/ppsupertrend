Here's the complete Stop Loss flow explained with a concrete example:

  ---
  Example Scenario: SHORT Position

  Entry Price:     1.16778
  SuperTrend:      1.16870  (above entry for SHORT = stop loss level)
  Buffer:          3 pips (0.0003)

  ---
  Step 1: Initial Stop Loss Calculation (at trade open)

  calculate_stop_loss() is called:

  1. base_stop_loss = SuperTrend = 1.16870

  2. For SHORT position, add buffer (price goes UP to trigger SL):
     adjusted_stop_loss = 1.16870 + 0.0003 = 1.16900

  3. This SL is sent to OANDA when opening the trade

  Result: Stop Loss set at 1.16900 (above entry price 1.16778)

  ---
  Step 2: Price Moves in Your Favor (Profit)

  As time passes, price drops (good for SHORT):
  Time T1: Price = 1.16700, SuperTrend = 1.16800
  Time T2: Price = 1.16650, SuperTrend = 1.16700
  Time T3: Price = 1.16600, SuperTrend = 1.16560  ← The problematic case

  ---
  Step 3: Trailing Stop Update Logic

  Each cycle, update_trailing_stop_loss() is called:

  # Step 3a: Calculate new SL from current SuperTrend
  new_stop_loss = SuperTrend + buffer

  # Step 3b: For SHORT, only update if new SL is LOWER (trailing down)
  if new_stop_loss < current_stop_loss:
      should_update = True

  At Time T2:
  Current SL:    1.16900
  SuperTrend:    1.16700
  new_stop_loss: 1.16700 + 0.0003 = 1.16730

  1.16730 < 1.16900? YES → Update SL to 1.16730 ✓

  ---
  Step 4: The Bug (Before Fix)

  At Time T3:
  Current Price: 1.16646
  SuperTrend:    1.16560
  new_stop_loss: 1.16560 + 0.0003 = 1.16590

  Old Logic:
    1.16590 < 1.16730? YES → Update SL to 1.16590

  BUT PROBLEM:
    For SHORT, SL triggers when ASK price >= SL price
    Current ASK ≈ 1.16663
    New SL = 1.16590

    1.16663 >= 1.16590? YES → SL TRIGGERS IMMEDIATELY! 💥

  ---
  Step 5: The Fix (After Fix)

  # NEW: Safety validation before updating
  safety_buffer = 0.0002  # 2 pips

  # For SHORT: new SL must be ABOVE current price + safety buffer
  if new_stop_loss <= current_price + safety_buffer:
      # SKIP update - would trigger immediately!
      return

  # Check: 1.16590 <= 1.16646 + 0.0002 = 1.16666?
  # YES! 1.16590 <= 1.16666 → SKIP UPDATE ✓

  ---
  Visual Summary

                       PRICE CHART (SHORT Position)

      1.16900 ─────────── Initial SL ──────────────────────
      1.16870 ─────────── Initial SuperTrend ──────────────
      1.16778 ─────────── Entry Price ─────────────────────
      1.16730 ─────────── Trailed SL (T2) ─────────────────
      1.16700 ─────────── SuperTrend at T2 ────────────────

      1.16666 ─ ─ ─ ─ ─ ─ Safety boundary (price + 2 pips) ─
      1.16663 ─────────── Current ASK price ───────────────  ← Market here
      1.16646 ─────────── Current MID price ───────────────

      1.16590 ─────────── Proposed new SL ─────────────────  ← DANGER ZONE!
      1.16560 ─────────── SuperTrend at T3 ────────────────


      ❌ OLD LOGIC: Would set SL to 1.16590 → Immediate trigger!
      ✅ NEW LOGIC: 1.16590 < 1.16666 → Skip update, keep SL at 1.16730

  ---
  Key Rules
  ┌──────────┬──────────────────────┬───────────────────────┬─────────────────────────┐
  │ Position │ SL Relative to Price │  Trailing Direction   │      Safety Check       │
  ├──────────┼──────────────────────┼───────────────────────┼─────────────────────────┤
  │ LONG     │ SL below price       │ Trail UP (raise SL)   │ new_SL < price - 2 pips │
  ├──────────┼──────────────────────┼───────────────────────┼─────────────────────────┤
  │ SHORT    │ SL above price       │ Trail DOWN (lower SL) │ new_SL > price + 2 pips │
  └──────────┴──────────────────────┴───────────────────────┴─────────────────────────┘

✻ Brewed for 32s