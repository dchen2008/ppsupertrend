#!/bin/bash
#
# Manual Order Tool with Post-Fill TP/SL Adjustment
#
# Places a new order and then adjusts TP/SL based on actual fill price.
#
# Usage:
#   ./tools/manually_new_order_cal_tp_sl_position_size.sh at=account1 fr=EUR_USD tf=5m
#   ./tools/manually_new_order_cal_tp_sl_position_size.sh at=account1 fr=EUR_USD tf=5m risk=100
#
# Parameters:
#   at=   Account (default: account1)
#   fr=   Instrument (default: EUR_USD)
#   tf=   Timeframe: 5m, 15m (default: 5m)
#   risk= Risk amount override (optional, uses config if not specified)
#
# WARNING: This tool places REAL orders! Use with caution.

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Show usage if no arguments provided
if [ "$#" -eq 0 ]; then
    echo "Manual Order Tool with Post-Fill TP/SL Adjustment"
    echo ""
    echo "WARNING: This tool places REAL orders!"
    echo ""
    echo "Usage:"
    echo "  $0 at=<account> fr=<instrument> tf=<timeframe> [risk=<amount>] [limit_max_potential_loss=<amount>]"
    echo "  $0 at=<account> fr=<instrument> tf=<timeframe> close-position"
    echo "  $0 at=<account> fr=<instrument> tf=<timeframe> get-position"
    echo ""
    echo "Parameters:"
    echo "  at=account1|account2|...       - Trading account (required)"
    echo "  fr=EUR_USD|GBP_USD|...         - Currency pair (default: EUR_USD)"
    echo "  tf=5m|15m                      - Trading timeframe (default: 5m)"
    echo "  risk=100                       - Risk amount override (optional)"
    echo "  limit_max_potential_loss=120   - Cap position size to limit max loss (optional)"
    echo "  close-position                 - Close current position instead of opening new"
    echo "  get-position                   - Show current position info"
    echo ""
    echo "Examples:"
    echo "  $0 at=account1 fr=EUR_USD tf=5m"
    echo "  $0 at=account1 fr=EUR_USD tf=5m risk=200"
    echo "  $0 at=account1 fr=EUR_USD tf=5m limit_max_potential_loss=120"
    echo "  $0 at=account1 fr=EUR_USD tf=5m close-position"
    echo "  $0 at=account1 fr=EUR_USD tf=5m get-position"
    exit 0
fi

# Default values
ACCOUNT="account1"
INSTRUMENT="EUR_USD"
TIMEFRAME="5m"
RISK=""
CLOSE_POSITION=""
GET_POSITION=""
MAX_LOSS=""

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
        limit_max_potential_loss=*)
            MAX_LOSS="${arg#*=}"
            ;;
        close-position)
            CLOSE_POSITION="close-position"
            ;;
        get-position)
            GET_POSITION="get-position"
            ;;
        -h|--help)
            echo "Manual Order Tool with Post-Fill TP/SL Adjustment"
            echo ""
            echo "WARNING: This tool places REAL orders!"
            echo ""
            echo "Usage:"
            echo "  $0 at=<account> fr=<instrument> tf=<timeframe> [risk=<amount>] [limit_max_potential_loss=<amount>]"
            echo "  $0 at=<account> fr=<instrument> tf=<timeframe> close-position"
            echo "  $0 at=<account> fr=<instrument> tf=<timeframe> get-position"
            echo ""
            echo "Parameters:"
            echo "  at=account1|account2|...       - Trading account (default: account1)"
            echo "  fr=EUR_USD|GBP_USD|...         - Currency pair (default: EUR_USD)"
            echo "  tf=5m|15m                      - Trading timeframe (default: 5m)"
            echo "  risk=100                       - Risk amount override (optional)"
            echo "  limit_max_potential_loss=120   - Cap position size to limit max loss (optional)"
            echo "  close-position                 - Close current position instead of opening new"
            echo "  get-position                   - Show current position info"
            echo ""
            echo "Examples:"
            echo "  $0 at=account1 fr=EUR_USD tf=5m"
            echo "  $0 at=account1 fr=EUR_USD tf=5m risk=200"
            echo "  $0 at=account1 fr=EUR_USD tf=5m limit_max_potential_loss=120"
            echo "  $0 at=account1 fr=EUR_USD tf=5m close-position"
            echo "  $0 at=account1 fr=EUR_USD tf=5m get-position"
            exit 0
            ;;
    esac
done

# Change to project root
cd "$PROJECT_ROOT"

# Build command
CMD="python3 tools/manually_new_order_cal_tp_sl_position_size.py at=$ACCOUNT fr=$INSTRUMENT tf=$TIMEFRAME"

if [ -n "$RISK" ]; then
    CMD="$CMD risk=$RISK"
fi

if [ -n "$MAX_LOSS" ]; then
    CMD="$CMD limit_max_potential_loss=$MAX_LOSS"
fi

if [ -n "$CLOSE_POSITION" ]; then
    CMD="$CMD close-position"
fi

if [ -n "$GET_POSITION" ]; then
    CMD="$CMD get-position"
fi

# Execute
exec $CMD
