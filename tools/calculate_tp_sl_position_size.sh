#!/bin/bash
#
# TP/SL/Position Size Calculator Tool
# Calculates and displays values for verification before trading
#
# Usage:
#   ./tools/calculate_tp_sl_position_size.sh at=account1 fr=EUR_USD tf=5m
#   ./tools/calculate_tp_sl_position_size.sh at=account1 fr=EUR_USD tf=5m risk=100
#
# Parameters:
#   at=   Account (default: account1)
#   fr=   Instrument (default: EUR_USD)
#   tf=   Timeframe: 5m, 15m (default: 5m)
#   risk= Risk amount override (optional, uses config if not specified)

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Default values
ACCOUNT="account1"
INSTRUMENT="EUR_USD"
TIMEFRAME="5m"
RISK=""

# Parse arguments
for arg in "$@"; do
    case "$arg" in
        at=*)
            ACCOUNT="${arg#*=}"
            ;;
        fr=*)
            INSTRUMENT="${arg#*=}"
            ;;
        tf=*)
            TIMEFRAME="${arg#*=}"
            ;;
        risk=*)
            RISK="${arg#*=}"
            ;;
        -h|--help)
            echo "TP/SL/Position Size Calculator"
            echo ""
            echo "Usage:"
            echo "  $0 at=<account> fr=<instrument> tf=<timeframe> [risk=<amount>]"
            echo ""
            echo "Parameters:"
            echo "  at=account1|account2|...  - Trading account (default: account1)"
            echo "  fr=EUR_USD|GBP_USD|...    - Currency pair (default: EUR_USD)"
            echo "  tf=5m|15m                 - Trading timeframe (default: 5m)"
            echo "  risk=100                  - Risk amount override (optional)"
            echo ""
            echo "Examples:"
            echo "  $0 at=account1 fr=EUR_USD tf=5m"
            echo "  $0 at=account1 fr=EUR_USD tf=5m risk=200"
            echo "  $0 at=account2 fr=GBP_USD tf=15m"
            exit 0
            ;;
    esac
done

# Change to project root
cd "$PROJECT_ROOT"

# Build command
CMD="python3 tools/calculate_tp_sl_position_size.py at=$ACCOUNT fr=$INSTRUMENT tf=$TIMEFRAME"

if [ -n "$RISK" ]; then
    CMD="$CMD risk=$RISK"
fi

# Execute
exec $CMD
