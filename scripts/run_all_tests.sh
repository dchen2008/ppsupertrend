#!/bin/bash
# Run all test configurations concurrently
# This script launches 4 different bot configurations in parallel

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
cd "$PROJECT_ROOT"

echo "=========================================="
echo "Starting Multiple Trading Bot Instances"
echo "=========================================="
echo "This will run 4 concurrent bot instances:"
echo "  1. EUR_USD 5m  + SuperTrend (account1)"
echo "  2. EUR_USD 15m + SuperTrend (account1)"
echo "  3. EUR_USD 5m  + PPCenterLine (account2)"
echo "  4. EUR_USD 15m + PPCenterLine (account2)"
echo ""
echo "Press Ctrl+C to stop all bots"
echo "=========================================="
echo ""

# Create a PID file to track all background processes
PID_FILE="$PROJECT_ROOT/bot_pids.txt"
rm -f "$PID_FILE"

# Create logs directories for console output
mkdir -p "$PROJECT_ROOT/account1/logs"
mkdir -p "$PROJECT_ROOT/account2/logs"

# Launch each bot configuration in the background
echo "Launching bots..."

# Bot 1: 5m + SuperTrend (account1)
"$SCRIPT_DIR/auto_trade.sh" EUR_USD tf:5m sl:SuperTrend account1 > "$PROJECT_ROOT/account1/logs/console_5m_supertrend.out" 2>&1 &
echo $! >> "$PID_FILE"
echo "✓ Started: EUR_USD 5m SuperTrend account1 (PID: $!)"

# Bot 2: 15m + SuperTrend (account1)
"$SCRIPT_DIR/auto_trade.sh" EUR_USD tf:15m sl:SuperTrend account1 > "$PROJECT_ROOT/account1/logs/console_15m_supertrend.out" 2>&1 &
echo $! >> "$PID_FILE"
echo "✓ Started: EUR_USD 15m SuperTrend account1 (PID: $!)"

# Bot 3: 5m + PPCenterLine (account2)
"$SCRIPT_DIR/auto_trade.sh" EUR_USD tf:5m sl:PPCenterLine account2 > "$PROJECT_ROOT/account2/logs/console_5m_ppcenterline.out" 2>&1 &
echo $! >> "$PID_FILE"
echo "✓ Started: EUR_USD 5m PPCenterLine account2 (PID: $!)"

# Bot 4: 15m + PPCenterLine (account2)
"$SCRIPT_DIR/auto_trade.sh" EUR_USD tf:15m sl:PPCenterLine account2 > "$PROJECT_ROOT/account2/logs/console_15m_ppcenterline.out" 2>&1 &
echo $! >> "$PID_FILE"
echo "✓ Started: EUR_USD 15m PPCenterLine account2 (PID: $!)"

echo ""
echo "All bots launched successfully!"
echo "Process IDs saved to: $PID_FILE"
echo ""
echo "CSV output files:"
echo "  - account1/csv/EUR_USD_5m_sl-SuperTrend.csv"
echo "  - account1/csv/EUR_USD_15m_sl-SuperTrend.csv"
echo "  - account2/csv/EUR_USD_5m_sl-PPCenterLine.csv"
echo "  - account2/csv/EUR_USD_15m_sl-PPCenterLine.csv"
echo ""
echo "Console output files:"
echo "  - account1/logs/console_5m_supertrend.out"
echo "  - account1/logs/console_15m_supertrend.out"
echo "  - account2/logs/console_5m_ppcenterline.out"
echo "  - account2/logs/console_15m_ppcenterline.out"
echo ""
echo "To stop all bots, run: ./scripts/stop_all_bots.sh"
echo ""
echo "Press Enter to view live logs or Ctrl+C to return to shell..."

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "Stopping all bots..."
    if [ -f "$PID_FILE" ]; then
        while read pid; do
            if kill -0 "$pid" 2>/dev/null; then
                kill "$pid"
                echo "Stopped PID: $pid"
            fi
        done < "$PID_FILE"
        rm -f "$PID_FILE"
    fi
    echo "All bots stopped."
    exit 0
}

# Trap Ctrl+C to cleanup
trap cleanup INT TERM

# Wait for user input or all processes to finish
read -t 2
if [ $? -eq 0 ]; then
    # User pressed Enter, show logs
    echo "Showing combined logs (Ctrl+C to exit)..."
    tail -f "$PROJECT_ROOT"/account*/logs/console_*.out
else
    # Just wait for all processes
    wait
fi
