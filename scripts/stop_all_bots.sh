#!/bin/bash
# Stop all running trading bot instances

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

PID_FILE="$PROJECT_ROOT/bot_pids.txt"

if [ ! -f "$PID_FILE" ]; then
    echo "No running bots found (PID file not found)"
    exit 0
fi

echo "Stopping all trading bots..."

while read pid; do
    if kill -0 "$pid" 2>/dev/null; then
        kill "$pid"
        echo "✓ Stopped bot (PID: $pid)"
    else
        echo "- Bot already stopped (PID: $pid)"
    fi
done < "$PID_FILE"

rm -f "$PID_FILE"

echo ""
echo "All bots stopped successfully!"
