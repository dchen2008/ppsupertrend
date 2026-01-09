#!/bin/bash
# Auto Trade Script - Launch trading bot with configurable parameters
# Usage: ./auto_trade.sh EUR_USD tf:5m sl:SuperTrend account1

# Check if correct number of arguments provided
if [ $# -lt 3 ] || [ $# -gt 4 ]; then
    echo "Usage: $0 <INSTRUMENT> <TIMEFRAME> <STOP_LOSS> [ACCOUNT]"
    echo ""
    echo "Examples:"
    echo "  $0 EUR_USD tf:5m sl:SuperTrend"
    echo "  $0 EUR_USD tf:5m sl:SuperTrend account1"
    echo "  $0 EUR_USD tf:15m sl:SuperTrend account2"
    echo "  $0 EUR_USD tf:5m sl:PPCenterLine account1"
    echo "  $0 EUR_USD tf:15m sl:PPCenterLine account2"
    echo ""
    echo "Arguments:"
    echo "  INSTRUMENT  - Trading pair (e.g., EUR_USD)"
    echo "  TIMEFRAME   - tf:5m or tf:15m"
    echo "  STOP_LOSS   - sl:SuperTrend or sl:PPCenterLine"
    echo "  ACCOUNT     - (Optional) Account name (e.g., account1, account2). Default: account1"
    exit 1
fi

INSTRUMENT=$1
TIMEFRAME=$2
STOP_LOSS=$3
ACCOUNT=${4:-account1}  # Default to account1 if not provided

# Validate timeframe format
if [[ ! $TIMEFRAME =~ ^tf:(5m|15m)$ ]]; then
    echo "Error: Timeframe must be tf:5m or tf:15m"
    exit 1
fi

# Validate stop loss format (case insensitive)
STOP_LOSS_LOWER=$(echo "$STOP_LOSS" | tr '[:upper:]' '[:lower:]')
if [[ ! $STOP_LOSS_LOWER =~ ^sl:(supertrend|ppcenterline)$ ]]; then
    echo "Error: Stop loss must be sl:SuperTrend or sl:PPCenterLine (case insensitive)"
    exit 1
fi

# Extract values
TF_VALUE=$(echo $TIMEFRAME | cut -d: -f2)
SL_VALUE=$(echo $STOP_LOSS | cut -d: -f2)

# Get script directory and project root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

# Generate output paths (account-based)
CSV_FILE="${PROJECT_ROOT}/${ACCOUNT}/csv/${INSTRUMENT}_${TF_VALUE}_sl-${SL_VALUE}.csv"
LOG_FILE="${PROJECT_ROOT}/${ACCOUNT}/logs/bot_${INSTRUMENT}_${TF_VALUE}_${SL_VALUE}.log"

# Change to project root
cd "$PROJECT_ROOT"

echo "=========================================="
echo "Starting Auto Trade Bot"
echo "=========================================="
echo "Instrument:  $INSTRUMENT"
echo "Timeframe:   $TIMEFRAME"
echo "Stop Loss:   $STOP_LOSS"
echo "Account:     $ACCOUNT"
echo "CSV Log:     $CSV_FILE"
echo "Bot Log:     $LOG_FILE"
echo "=========================================="
echo ""

# Check if src directory exists
if [ ! -d "src" ]; then
    echo "Error: src directory not found in $PROJECT_ROOT"
    exit 1
fi

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "Error: python3 not found. Please install Python 3."
    exit 1
fi

# Run the trading bot as a module
python3 -m src.trading_bot_enhanced "$INSTRUMENT" "$TIMEFRAME" "$STOP_LOSS" "$ACCOUNT"

# Capture exit code
EXIT_CODE=$?

echo ""
echo "=========================================="
echo "Bot stopped with exit code: $EXIT_CODE"
echo "CSV Log:  $CSV_FILE"
echo "Bot Log:  $LOG_FILE"
echo "=========================================="

exit $EXIT_CODE
