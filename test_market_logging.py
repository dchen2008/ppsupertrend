#!/usr/bin/env python3
"""
Test market-aware bot logging with R:R display
"""

import time
from src.config import OANDAConfig, TradingConfig
from src.trading_bot_market_aware import MarketAwareTradingBot

def test_bot_logging():
    """Run bot for a short time to test logging"""
    
    # Set account
    OANDAConfig.set_account('account1')
    print(f"✓ Using account: {OANDAConfig.account_id}")
    
    # Create bot instance
    bot = MarketAwareTradingBot('EUR_USD', '5m', 'account1')
    
    print("\nTesting bot logging for 10 seconds...")
    print("Check the log file for market trend and R:R info")
    print(f"Log file: {bot.log_filename}")
    print("-" * 60)
    
    # Run one check cycle
    try:
        bot.check_and_trade()
        print("\n✅ Check completed. Review the log for:")
        print("  - OVERALL Market: BEAR/BULL/NEUTRAL")
        print("  - Expected Take Profit R:R")
        print("  - Current R:R Reached")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    print("\nTo view the log:")
    print(f"  tail -f {bot.log_filename}")

if __name__ == "__main__":
    test_bot_logging()