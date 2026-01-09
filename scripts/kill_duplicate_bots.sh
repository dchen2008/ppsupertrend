#!/bin/bash
# Kill duplicate bot instances
# This script safely terminates all running trading bots

echo "=========================================="
echo "Killing Duplicate Trading Bot Instances"
echo "=========================================="
echo ""

# Find all src.trading_bot_enhanced processes
PIDS=$(ps aux | grep "src.trading_bot_enhanced" | grep -v grep | awk '{print $2}')

if [ -z "$PIDS" ]; then
    echo "No running bot instances found."
    exit 0
fi

echo "Found the following bot instances:"
ps aux | grep "src.trading_bot_enhanced" | grep -v grep
echo ""

# Count instances
COUNT=$(echo "$PIDS" | wc -l | tr -d ' ')
echo "Total instances running: $COUNT"
echo ""

# Ask for confirmation
read -p "Do you want to kill all these instances? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "Cancelled."
    exit 0
fi

# Kill all instances
echo ""
echo "Killing bot instances..."
for PID in $PIDS; do
    echo "  Killing PID $PID..."
    kill $PID
    sleep 0.5
done

echo ""
echo "Waiting 2 seconds for graceful shutdown..."
sleep 2

# Check if any are still running
REMAINING=$(ps aux | grep "src.trading_bot_enhanced" | grep -v grep | awk '{print $2}')

if [ -n "$REMAINING" ]; then
    echo ""
    echo "Some processes didn't terminate gracefully. Force killing..."
    for PID in $REMAINING; do
        echo "  Force killing PID $PID..."
        kill -9 $PID
    done
fi

echo ""
echo "=========================================="
echo "All bot instances have been terminated."
echo "=========================================="
