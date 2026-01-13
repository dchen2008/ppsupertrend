#!/bin/bash
#
# Batch Backtest Script
# Runs backtests for multiple accounts and generates a summary report
#
# Usage:
#   ./scripts/batch_bt.sh at="account1,account2,account3,account4" fr=EUR_USD tf=5m bt="01/04/2026 16:00:00,01/09/2026 16:00:00"
#   ./scripts/batch_bt.sh at="account1,account2" fr=EUR_USD tf=5m bt="01/04/2026 16:00:00,01/09/2026 16:00:00" balance=10000

set -e

# Get the script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

# Parse arguments
ACCOUNTS=""
INSTRUMENT=""
TIMEFRAME=""
TIME_RANGE=""
BALANCE=10000
MARKET=""

for arg in "$@"; do
    case "$arg" in
        at=*)
            ACCOUNTS="${arg#*=}"
            ;;
        fr=*)
            INSTRUMENT="${arg#*=}"
            ;;
        tf=*)
            TIMEFRAME="${arg#*=}"
            ;;
        bt=*)
            TIME_RANGE="${arg#*=}"
            ;;
        balance=*)
            BALANCE="${arg#*=}"
            ;;
        market=*)
            MARKET="${arg#*=}"
            ;;
    esac
done

# Validate required arguments
if [ -z "$ACCOUNTS" ] || [ -z "$INSTRUMENT" ] || [ -z "$TIMEFRAME" ] || [ -z "$TIME_RANGE" ]; then
    echo "Usage: $0 at=account1,account2,... fr=INSTRUMENT tf=TIMEFRAME bt=\"START,END\" [market=bear|bull]"
    echo ""
    echo "Example:"
    echo "  $0 at=\"account1,account2,account3,account4\" fr=EUR_USD tf=5m bt=\"01/04/2026 16:00:00,01/09/2026 16:00:00\""
    echo "  $0 at=\"account1,account2\" fr=EUR_USD tf=5m bt=\"01/04/2026 16:00:00,01/09/2026 16:00:00\" market=bear"
    echo ""
    echo "Options:"
    echo "  at=       Comma-separated list of accounts"
    echo "  fr=       Instrument (e.g., EUR_USD)"
    echo "  tf=       Timeframe (e.g., 5m, 15m)"
    echo "  bt=       Time range in format: MM/DD/YYYY HH:MM:SS,MM/DD/YYYY HH:MM:SS"
    echo "  balance=  Initial balance (default: 10000)"
    echo "  market=   Override market trend: bear or bull (case insensitive, skips 3H calculation)"
    exit 1
fi

# Convert accounts string to array
IFS=',' read -ra ACCOUNT_ARRAY <<< "$ACCOUNTS"

echo ""
echo "========================================"
echo "BATCH BACKTEST"
echo "========================================"
echo "Accounts: ${ACCOUNT_ARRAY[*]}"
echo "Instrument: $INSTRUMENT"
echo "Timeframe: $TIMEFRAME"
echo "Period: $TIME_RANGE"
echo "Balance: \$$BALANCE"
if [ -n "$MARKET" ]; then
    echo "Market Override: $MARKET"
fi
echo "========================================"
echo ""

# Parse time range for filename generation
# Format: "01/04/2026 16:00:00,01/09/2026 16:00:00"
START_DATE=$(echo "$TIME_RANGE" | cut -d',' -f1)
END_DATE=$(echo "$TIME_RANGE" | cut -d',' -f2)

# Extract month and day for filename (MMDD format)
START_MONTH=$(echo "$START_DATE" | cut -d'/' -f1)
START_DAY=$(echo "$START_DATE" | cut -d'/' -f2)
END_MONTH=$(echo "$END_DATE" | cut -d'/' -f1 | xargs)  # xargs to trim leading space
END_DAY=$(echo "$END_DATE" | cut -d'/' -f2)

# Expand timeframe for filenames
TIMEFRAME_EXPANDED="${TIMEFRAME//m/min}"

# Array to store CSV file paths
declare -a CSV_FILES

# Run backtest for each account
for account in "${ACCOUNT_ARRAY[@]}"; do
    echo ""
    echo "----------------------------------------"
    echo "Running backtest for: $account"
    echo "----------------------------------------"

    # Run the backtest
    if [ -n "$MARKET" ]; then
        python3 fixed_backtest.py "at=$account" "fr=$INSTRUMENT" "tf=$TIMEFRAME" "bt=$TIME_RANGE" --balance "$BALANCE" --market "$MARKET"
    else
        python3 fixed_backtest.py "at=$account" "fr=$INSTRUMENT" "tf=$TIMEFRAME" "bt=$TIME_RANGE" --balance "$BALANCE"
    fi

    # Find the most recent CSV file for this account
    # Pattern: account1_EUR_USD_5min_0104_0109_XXX.csv
    PATTERN="${account}_${INSTRUMENT}_${TIMEFRAME_EXPANDED}_${START_MONTH}${START_DAY}_${END_MONTH}${END_DAY}_*.csv"
    LATEST_CSV=$(ls -t backtest/results/$PATTERN 2>/dev/null | head -1)

    if [ -n "$LATEST_CSV" ]; then
        CSV_FILES+=("$LATEST_CSV")
        echo "CSV generated: $LATEST_CSV"
    else
        echo "Warning: Could not find CSV file for $account"
    fi
done

echo ""
echo "========================================"
echo "GENERATING SUMMARY REPORT"
echo "========================================"

# Check if we have CSV files
if [ ${#CSV_FILES[@]} -eq 0 ]; then
    echo "Error: No CSV files generated"
    exit 1
fi

# Generate summary filename
# Format: summary_act1-2-3-4_EUR_USD_5min_0104_0109_XXX.csv
ACCOUNT_NUMS=""
for account in "${ACCOUNT_ARRAY[@]}"; do
    NUM="${account//[^0-9]/}"
    if [ -n "$ACCOUNT_NUMS" ]; then
        ACCOUNT_NUMS="${ACCOUNT_NUMS}-${NUM}"
    else
        ACCOUNT_NUMS="$NUM"
    fi
done

RANDOM_NUM=$((RANDOM % 900 + 100))  # Random 3-digit number
SUMMARY_FILENAME="summary_act${ACCOUNT_NUMS}_${INSTRUMENT}_${TIMEFRAME_EXPANDED}_${START_MONTH}${START_DAY}_${END_MONTH}${END_DAY}_${RANDOM_NUM}.csv"
SUMMARY_PATH="backtest/results/$SUMMARY_FILENAME"

# Format dates for display
# Convert MM/DD/YYYY HH:MM:SS to "Mon DD, YYYY HH:MM"
format_date() {
    local date_str="$1"
    local month=$(echo "$date_str" | cut -d'/' -f1)
    local day=$(echo "$date_str" | cut -d'/' -f2)
    local rest=$(echo "$date_str" | cut -d'/' -f3)
    local year=$(echo "$rest" | cut -d' ' -f1)
    local time=$(echo "$rest" | cut -d' ' -f2 | cut -d':' -f1-2)

    local months=("" "Jan" "Feb" "Mar" "Apr" "May" "Jun" "Jul" "Aug" "Sep" "Oct" "Nov" "Dec")
    local month_name="${months[$((10#$month))]}"

    echo "$month_name $((10#$day)), $year $time"
}

START_DATE_FMT=$(format_date "$START_DATE")
END_DATE_FMT=$(format_date "$(echo "$END_DATE" | xargs)")

# Join CSV files with comma
CSV_LIST=$(IFS=','; echo "${CSV_FILES[*]}")

# Run summary generator
if [ -n "$MARKET" ]; then
    python3 generate_bt_summary.py \
        --accounts "$ACCOUNTS" \
        --csv-files "$CSV_LIST" \
        --instrument "$INSTRUMENT" \
        --timeframe "$TIMEFRAME" \
        --start-date "$START_DATE_FMT" \
        --end-date "$END_DATE_FMT" \
        --balance "$BALANCE" \
        --market "$MARKET" \
        --output "$SUMMARY_PATH"
else
    python3 generate_bt_summary.py \
        --accounts "$ACCOUNTS" \
        --csv-files "$CSV_LIST" \
        --instrument "$INSTRUMENT" \
        --timeframe "$TIMEFRAME" \
        --start-date "$START_DATE_FMT" \
        --end-date "$END_DATE_FMT" \
        --balance "$BALANCE" \
        --output "$SUMMARY_PATH"
fi

echo ""
echo "========================================"
echo "BATCH BACKTEST COMPLETE"
echo "========================================"
echo "Individual CSVs:"
for csv in "${CSV_FILES[@]}"; do
    echo "  - $csv"
done
echo ""
echo "Summary: $SUMMARY_PATH"
echo "========================================"
