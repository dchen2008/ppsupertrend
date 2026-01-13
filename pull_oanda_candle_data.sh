#!/bin/bash
#
# OANDA Candle Data Downloader
# Downloads historical candle data for specified timeframes and date range
#
# Usage:
#   ./pull_oanda_candle_data.sh range="01/04/2026 16:00:00,01/09/2026 16:00:00" tf="M1,M5,M15,H3"
#   ./pull_oanda_candle_data.sh range="01/04/2026 16:00:00,01/09/2026 16:00:00" tf="M1,M5,M15,H3" fr=EUR_USD
#   ./pull_oanda_candle_data.sh days=30 tf="M5,M15,H3"
#
# Parameters:
#   range=  Date range in format: "MM/DD/YYYY HH:MM:SS,MM/DD/YYYY HH:MM:SS"
#   tf=     Comma-separated timeframes (M1, M5, M15, H3) - aliases: 1M, 5M, 15M, 3H
#   fr=     Instrument (default: EUR_USD)
#   at=     Account (default: account1)
#   days=   Days back (alternative to range)

set -e

# Get the script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Default values
DATE_RANGE=""
TIMEFRAMES="M1,M5,M15,H3"
INSTRUMENT="EUR_USD"
ACCOUNT="account1"
DAYS=""

# Parse arguments
for arg in "$@"; do
    case "$arg" in
        range=*)
            DATE_RANGE="${arg#*=}"
            ;;
        tf=*)
            TIMEFRAMES="${arg#*=}"
            ;;
        fr=*)
            INSTRUMENT="${arg#*=}"
            ;;
        at=*)
            ACCOUNT="${arg#*=}"
            ;;
        days=*)
            DAYS="${arg#*=}"
            ;;
    esac
done

# Validate that we have either range or days
if [ -z "$DATE_RANGE" ] && [ -z "$DAYS" ]; then
    echo "OANDA Candle Data Downloader"
    echo ""
    echo "Usage:"
    echo "  $0 range=\"MM/DD/YYYY HH:MM:SS,MM/DD/YYYY HH:MM:SS\" tf=\"M1,M5,M15,H3\""
    echo "  $0 days=30 tf=\"M5,M15,H3\""
    echo ""
    echo "Parameters:"
    echo "  range=  Date range (required if no days)"
    echo "  tf=     Timeframes: M1, M5, M15, H3 (default: M1,M5,M15,H3)"
    echo "  fr=     Instrument (default: EUR_USD)"
    echo "  at=     Account for API key (default: account1)"
    echo "  days=   Days back (alternative to range)"
    echo ""
    echo "Examples:"
    echo "  $0 range=\"01/04/2026 16:00:00,01/09/2026 16:00:00\" tf=\"M1,M5,M15,H3\""
    echo "  $0 range=\"12/01/2025 00:00:00,12/31/2025 23:59:59\" tf=\"M5,H3\" fr=GBP_USD"
    echo "  $0 days=30 tf=\"M5,M15,H3\""
    exit 1
fi

echo ""
echo "========================================"
echo "OANDA CANDLE DATA DOWNLOADER"
echo "========================================"
echo "Instrument: $INSTRUMENT"
echo "Timeframes: $TIMEFRAMES"
echo "Account: $ACCOUNT"

# Build command
CMD="python3 backtest/src/data_downloader.py --instrument $INSTRUMENT --timeframes $TIMEFRAMES --account $ACCOUNT"

if [ -n "$DATE_RANGE" ]; then
    echo "Date Range: $DATE_RANGE"
    CMD="$CMD --range \"$DATE_RANGE\""
elif [ -n "$DAYS" ]; then
    echo "Days Back: $DAYS"
    CMD="$CMD --days $DAYS"
fi

echo "========================================"
echo ""

# Execute
eval $CMD

echo ""
echo "Done!"
