1. Initial position sizing (raw):
    Calculate the raw position size using $100 risk, with the current PP SuperTrend price as the stop-loss (SL).

2. Fetch market price:
    Call the OANDA API to get the instrument’s current_price.

3. Initial take-profit (raw):
    Calculate the raw TP (take-profit) price using:
        preconfigured risk/reward (RR) = 0.6
        current PP SuperTrend price as the SL
        current_price from step 2 as the entry reference
    This produces the initial TP price to place on the order.

4. Place the order:
    Submit the new order. The bot confirms the order is created successfully.

5. Post-fill adjustment (TP + SL):
    As long as step 4 succcesfully place the order, 
    Immediately call the OANDA API to fetch the position’s fill and risk values. From the API response, we need:
        fill_price
        current_SL_price
    Then perform two updates:
        Must first adjusted TP: Recalculate TP using the preconfigured RR = 0.6, based on fill_price and current_SL_price.
        Must Second calculate the New SL: Set SL to current PP SuperTrend price + 5 pips buffer.
Finally, call the API to modify the open position with the new TP and new SL.
The bot don't need change the TP again until people manually set a new SL.

6. Ongoing trailing stop management:
    On every check_interval, the bot monitors the latest PP SuperTrend price and continuously updates SL:
        SL = current PP SuperTrend price + 5 pips buffer
        Call the OANDA API to update the SL accordingly.

Pls come up a tool first under:./tools/
./tools/calculate_tp_sl_posistions_size.sh at=account1 fr=EUR_USD risk=$100 tf=5m
-- at=account1, using account1/config.yaml's risk/reward ratio, 3H PP market[BEAR,BULL]
-- tf=5m means using 5min PP superTrend price
 
 ./tools/calculate_tp_sl_position_size.sh --help

 ./tools/calculate_tp_sl_position_size.sh at=account1 fr=EUR_USD tf=5m