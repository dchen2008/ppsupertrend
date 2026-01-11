#!/bin/bash

# Enhanced Backtest Market-Aware Trading Bot Launcher
# Usage: ./backtest/scripts/bt_enhanced_market.sh at=account1 fr=EUR_USD tf=5m bt=01/04/2026\ 16:00:00,01/09/2026\ 16:00:00

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
ACCOUNT=""
INSTRUMENT=""
TIMEFRAME=""
TIME_RANGE=""
INITIAL_BALANCE=""  # Will use config default if not specified
DATA_REFRESH=false

# Function to display usage
show_usage() {
    echo "Usage: $0 at=<account> fr=<instrument> tf=<timeframe> bt=<time_range> [options]"
    echo ""
    echo "Required Parameters:"
    echo "  at=<account>      Account name (account1, account2, etc.)"
    echo "  fr=<instrument>   Trading instrument (EUR_USD, GBP_USD, etc.)"
    echo "  tf=<timeframe>    Timeframe (5m or 15m)"
    echo "  bt=<time_range>   Time range: MM/DD/YYYY HH:MM:SS,MM/DD/YYYY HH:MM:SS"
    echo ""
    echo "Optional Parameters:"
    echo "  balance=<amount>  Initial balance (default: from config.yaml)"
    echo "  refresh=true      Force refresh cached data"
    echo ""
    echo "Examples:"
    echo "  $0 at=account1 fr=EUR_USD tf=5m bt=\"01/04/2026 16:00:00,01/09/2026 16:00:00\""
    echo "  $0 at=account2 fr=GBP_USD tf=15m bt=\"01/01/2026 00:00:00,01/31/2026 23:59:59\" balance=10000"
    echo ""
    echo "Note: Use quotes around time range if it contains spaces"
    exit 1
}

# Function to log with timestamp
log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

log_error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1"
}

log_info() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')] INFO:${NC} $1"
}

# Parse command line arguments
if [ $# -eq 0 ]; then
    show_usage
fi

for arg in "$@"; do
    case $arg in
        at=*)
            ACCOUNT="${arg#*=}"
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
            INITIAL_BALANCE="${arg#*=}"
            ;;
        refresh=*)
            if [ "${arg#*=}" = "true" ]; then
                DATA_REFRESH=true
            fi
            ;;
        -h|--help)
            show_usage
            ;;
        *)
            log_error "Unknown parameter: $arg"
            show_usage
            ;;
    esac
done

# Validate required parameters
if [ -z "$ACCOUNT" ] || [ -z "$INSTRUMENT" ] || [ -z "$TIMEFRAME" ] || [ -z "$TIME_RANGE" ]; then
    log_error "Missing required parameters"
    show_usage
fi

# Validate timeframe
if [ "$TIMEFRAME" != "5m" ] && [ "$TIMEFRAME" != "15m" ]; then
    log_error "Timeframe must be 5m or 15m"
    exit 1
fi

# Validate time range format
if [[ ! "$TIME_RANGE" =~ ^[0-9]{2}/[0-9]{2}/[0-9]{4}\ [0-9]{2}:[0-9]{2}:[0-9]{2},[0-9]{2}/[0-9]{2}/[0-9]{4}\ [0-9]{2}:[0-9]{2}:[0-9]{2}$ ]]; then
    log_error "Invalid time range format. Use: MM/DD/YYYY HH:MM:SS,MM/DD/YYYY HH:MM:SS"
    exit 1
fi

# Check if fixed_backtest.py exists
if [ ! -f "fixed_backtest.py" ]; then
    log_error "fixed_backtest.py not found. Please ensure it's in the project root."
    exit 1
fi

# Check if backtest directory exists
if [ ! -d "backtest" ]; then
    log_error "Backtest directory not found. Please run from project root."
    exit 1
fi

# Create necessary directories
mkdir -p backtest/{data,results,logs}

# Generate timestamp for file naming
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_DIR="backtest/logs"
RESULTS_DIR="backtest/results"
TIME_RANGE_CLEAN=$(echo "$TIME_RANGE" | sed 's/[\/: ,]//g')
LOG_FILE="${LOG_DIR}/bt_enhanced_${INSTRUMENT}_${TIMEFRAME}_${ACCOUNT}_${TIME_RANGE_CLEAN}_${TIMESTAMP}.log"

log "🎯 Starting Enhanced Backtest (Exact Bot Logic)"
log "=============================================="
log "Account: $ACCOUNT"
log "Instrument: $INSTRUMENT"
log "Timeframe: $TIMEFRAME"
log "Time Range: $TIME_RANGE"
log "Initial Balance: \$$INITIAL_BALANCE"
log "Log File: $LOG_FILE"

# Check Python environment
if ! command -v python3 &> /dev/null; then
    log_error "Python3 is required but not installed"
    exit 1
fi

# Check required Python packages
log_info "Checking Python dependencies..."
python3 -c "import pandas, numpy, yaml" 2>/dev/null
if [ $? -ne 0 ]; then
    log_error "Required Python packages missing. Please install: pandas numpy PyYAML"
    exit 1
fi

# Function to run enhanced backtest
run_enhanced_backtest() {
    log "🔄 Running enhanced backtest with exact bot logic..."
    
    # Create FIXED backtest command (exact live bot logic)
    CMD="python3 fixed_backtest.py at=$ACCOUNT fr=$INSTRUMENT tf=$TIMEFRAME bt=\"$TIME_RANGE\""
    
    # Add optional parameters
    if [ -n "$INITIAL_BALANCE" ]; then
        CMD="$CMD --balance $INITIAL_BALANCE"
    fi
    
    CMD="$CMD --output-dir $RESULTS_DIR"
    
    log_info "Executing: $CMD"
    
    # Run the enhanced backtest
    eval "$CMD" 2>&1 | tee -a "$LOG_FILE"
    
    EXIT_CODE=${PIPESTATUS[0]}
    
    if [ $EXIT_CODE -eq 0 ]; then
        log "✅ Enhanced backtest completed successfully!"
        log "📄 Results saved to: $RESULTS_DIR"
        log "📊 Log file: $LOG_FILE"
        
        # List generated files
        log_info "Generated files:"
        ls -la "$RESULTS_DIR"/bt_*sign_ratio_profit* 2>/dev/null | tail -5 | while read line; do
            echo "  $(echo "$line" | awk '{print $9}')"
        done
        
    else
        log_error "Enhanced backtest failed with exit code: $EXIT_CODE"
        log_error "Check log file for details: $LOG_FILE"
        exit 1
    fi
}

# Function to check for running live bots
check_live_bots() {
    log_info "Checking for running live trading bots..."
    
    # Check for live bot processes
    LIVE_BOTS=$(pgrep -f "trading_bot.*${INSTRUMENT}" | grep -v "backtest\|enhanced" || true)
    
    if [ ! -z "$LIVE_BOTS" ]; then
        log_warn "Found running live bot processes for $INSTRUMENT:"
        ps -p $LIVE_BOTS -o pid,ppid,cmd --no-headers 2>/dev/null || true
        log_warn "Enhanced backtest will run independently without affecting live trading"
    else
        log_info "No live trading bots detected for $INSTRUMENT"
    fi
}

# Main execution
main() {
    # Check for live bots
    check_live_bots
    
    # Check if results directory is writable
    if [ ! -w "$RESULTS_DIR" ]; then
        log_error "Cannot write to $RESULTS_DIR directory"
        exit 1
    fi
    
    # Create lock file to prevent duplicate backtests
    LOCK_FILE="backtest/.lock_enhanced_${INSTRUMENT}_${TIMEFRAME}_${ACCOUNT}"
    if [ -f "$LOCK_FILE" ]; then
        LOCK_PID=$(head -1 "$LOCK_FILE" 2>/dev/null)
        if [ ! -z "$LOCK_PID" ] && kill -0 "$LOCK_PID" 2>/dev/null; then
            log_warn "Another enhanced backtest appears to be running (PID: $LOCK_PID)"
            log_warn "Lock file: $LOCK_FILE"
            log_warn "If this is incorrect, remove the lock file and try again"
            exit 1
        else
            log_info "Removing stale lock file"
            rm -f "$LOCK_FILE"
        fi
    fi
    
    # Create lock file
    echo "$$" > "$LOCK_FILE"
    echo "$(date)" >> "$LOCK_FILE"
    echo "Enhanced backtest for $INSTRUMENT $TIMEFRAME $ACCOUNT" >> "$LOCK_FILE"
    
    # Cleanup function
    cleanup() {
        rm -f "$LOCK_FILE"
        log "Enhanced backtest process cleanup completed"
    }
    
    # Set trap for cleanup
    trap cleanup EXIT INT TERM
    
    log "Lock file created: $LOCK_FILE"
    
    # Run enhanced backtest
    run_enhanced_backtest
    
    log "🎉 Enhanced backtest process completed!"
    
    # Show CSV files generated
    log_info "Signal analysis CSV files:"
    find "$RESULTS_DIR" -name "bt_*sign_ratio_profit*.csv" -newer "$LOCK_FILE" 2>/dev/null | while read csvfile; do
        if [ -f "$csvfile" ]; then
            log "  📄 $(basename "$csvfile")"
            log "     Lines: $(wc -l < "$csvfile") | Size: $(du -h "$csvfile" | awk '{print $1}')"
        fi
    done
}

# Run main function
main

echo ""
log "🎯 Enhanced backtest launcher completed!"
log "Use this tool to get exact bot logic results with detailed signal analysis."