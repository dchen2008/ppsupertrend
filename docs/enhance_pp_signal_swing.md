
Whe PP Signal Changing, timing and logic is very critical.
Here are my requirements:

when 5min/15min/30mins pp signal change. The bot will be into very critical momnents:
Below example use 5mins, time range candles:0-5min, 5m-10, 10m-15, 20m-25, 25m-30
I attached one picture as real example, it's 3 candle(5m):
7:15:01 to 7:20:00, candle1, pp_signal:sell, supertrend_price1
                    the instrument current price ran on peak, current supertrend price(supertrend_price1) is flat.

7:20:01 to 7:25:00, candle2, pp_signal:sell, supertrend_price2
                    the instrument current price suddenly drop huge, it's wick price or close price crossed previous supertrend(supertrend_price1). The current superTrend price(supertrend_price2) could be very stranger, can't be used.
                    as long as the bot detected above one of price crossed, the bot should stop SL update, and must keep check instrument current price in very second(can't use check_interval(10s) to void missing task in the next candle's), be prepared to take action in next candle's first second.

7:25:01 to 7:30:00, candle3, pp_signal:buy, supertrend_price3
                    The pp signal change or not.
                    after previous candle2 be closed, in first second we need follow below sequence to do below tasks:
                    A. if the candle2's just wick price crossed supertrend_price1 but the close price not, the bot back to normal.
                    B. if the candle2's close price crossed candle1's superTrend price(supertrend_price1). 
                      In the candle's first second (7:25:01), the bot to do:
                      a. confirm the pp signal change from sell to buy
                      b. emergency close position if existing position is opposite with new pp signal[buy]]
                      c. make a new order[LONG]

First pls confirm my below understanding correct or not:
--What's current the bot's pp signal confirm bar definitions?
--What's SuperTrend price during 3 candles windows:supertrend_price1, supertrend_price2, supertrend_price3 ?
--When pp signal:sell,the supertrend price only keep down or flat, can't going up. Am I unstanding right?
--Above ongoing supertrend_price2 change huge, very stranger, can't be used.  Am I unstanding right?
--When pp signal:sell,the supertrend price only keep up or flat, can't going down. Am I unstanding right?
