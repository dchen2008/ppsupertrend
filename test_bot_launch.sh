#!/bin/bash
# Test script to verify bot launches correctly

echo "Testing Market-Aware Bot Launch..."
echo "================================"
echo ""
echo "This will start the bot and exit after 5 seconds for testing."
echo "Press Ctrl+C to stop earlier if needed."
echo ""

# Launch bot with timeout
timeout 5 ./scripts/auto_trade_market.sh at=account1 fr=EUR_USD tf=5m 2>&1 | head -30

EXIT_CODE=$?

echo ""
if [ $EXIT_CODE -eq 124 ]; then
    echo "✅ Bot launched successfully (timed out after 5 seconds as expected)"
elif [ $EXIT_CODE -eq 0 ]; then
    echo "✅ Bot launched and exited normally"
else
    echo "❌ Bot failed to launch (exit code: $EXIT_CODE)"
fi

echo ""
echo "To run the bot normally, use:"
echo "  ./scripts/auto_trade_market.sh at=account1 fr=EUR_USD tf=5m"