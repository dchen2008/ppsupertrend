#!/bin/bash

# Backtest Market-Aware Trading Bot Launcher
# Usage: ./scripts/bt_auto_trade_market.sh at=account1 fr=EUR_USD tf=5m bt=30d

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
BACKTEST_DAYS=""
INITIAL_BALANCE=10000
DATA_REFRESH=false
PARALLEL_MODE=false

# Function to display usage
show_usage() {
    echo "Usage: $0 at=<account> fr=<instrument> tf=<timeframe> bt=<days> [options]"
    echo ""
    echo "Required Parameters:"
    echo "  at=<account>      Account name (account1, account2, etc.)"
    echo "  fr=<instrument>   Trading instrument (EUR_USD, GBP_USD, etc.)"
    echo "  tf=<timeframe>    Timeframe (5m or 15m)"
    echo "  bt=<days>         Backtest period in days (e.g., 30d, 90d)"
    echo ""
    echo "Optional Parameters:"
    echo "  balance=<amount>  Initial balance (default: 10000)"
    echo "  refresh=true      Force refresh cached data"
    echo "  parallel=true     Run in parallel mode (experimental)"
    echo ""
    echo "Examples:"
    echo "  $0 at=account1 fr=EUR_USD tf=5m bt=30d"
    echo "  $0 at=account2 fr=GBP_USD tf=15m bt=90d balance=25000"
    echo "  $0 at=account1 fr=EUR_USD tf=5m bt=60d refresh=true"
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
            BACKTEST_PERIOD="${arg#*=}"
            # Extract number of days from format like "30d"
            BACKTEST_DAYS=$(echo "$BACKTEST_PERIOD" | sed 's/[^0-9]*//g')
            ;;
        balance=*)
            INITIAL_BALANCE="${arg#*=}"
            ;;
        refresh=*)
            if [ "${arg#*=}" = "true" ]; then
                DATA_REFRESH=true
            fi
            ;;
        parallel=*)
            if [ "${arg#*=}" = "true" ]; then
                PARALLEL_MODE=true
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
if [ -z "$ACCOUNT" ] || [ -z "$INSTRUMENT" ] || [ -z "$TIMEFRAME" ] || [ -z "$BACKTEST_DAYS" ]; then
    log_error "Missing required parameters"
    show_usage
fi

# Validate timeframe
if [ "$TIMEFRAME" != "5m" ] && [ "$TIMEFRAME" != "15m" ]; then
    log_error "Timeframe must be 5m or 15m"
    exit 1
fi

# Validate backtest days
if ! [[ "$BACKTEST_DAYS" =~ ^[0-9]+$ ]]; then
    log_error "Backtest days must be a number"
    exit 1
fi

# Check if backtest directory exists
if [ ! -d "backtest" ]; then
    log_error "Backtest directory not found. Please run from project root."
    exit 1
fi

# Create necessary directories
mkdir -p backtest/{data,results,logs}

# Set up file paths with bt_ prefix
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_DIR="backtest/logs"
RESULTS_DIR="backtest/results"
LOG_FILE="${LOG_DIR}/bt_${INSTRUMENT}_${TIMEFRAME}_${ACCOUNT}_${BACKTEST_DAYS}d_${TIMESTAMP}.log"
RESULTS_PREFIX="bt_${INSTRUMENT}_${TIMEFRAME}_${ACCOUNT}_${BACKTEST_DAYS}d_${TIMESTAMP}"

log "Starting Backtest for Market-Aware Trading Bot"
log "=============================================="
log "Account: $ACCOUNT"
log "Instrument: $INSTRUMENT"
log "Timeframe: $TIMEFRAME"
log "Backtest Period: $BACKTEST_DAYS days"
log "Initial Balance: \$$INITIAL_BALANCE"
log "Data Refresh: $DATA_REFRESH"
log "Log File: $LOG_FILE"
log "Results Prefix: $RESULTS_PREFIX"

# Check Python environment
if ! command -v python3 &> /dev/null; then
    log_error "Python3 is required but not installed"
    exit 1
fi

# Check required Python packages
log_info "Checking Python dependencies..."
python3 -c "import pandas, numpy, matplotlib, seaborn, yaml" 2>/dev/null
if [ $? -ne 0 ]; then
    log_error "Required Python packages missing. Please install: pandas numpy matplotlib seaborn PyYAML"
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    log_info "Creating virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    pip install -r requirements_backtest.txt
else
    source venv/bin/activate
    # Check if backtest dependencies are installed
    python3 -c "import matplotlib, seaborn" 2>/dev/null
    if [ $? -ne 0 ]; then
        log_info "Installing backtest dependencies..."
        pip install -r requirements_backtest.txt
    fi
fi

# Function to run backtest
run_backtest() {
    log "Step 1: Downloading historical data..."
    
    # Download data with optional refresh
    REFRESH_FLAG=""
    if [ "$DATA_REFRESH" = true ]; then
        REFRESH_FLAG="--force"
    fi
    
    python3 -m backtest.src.data_downloader \
        --instrument "$INSTRUMENT" \
        --timeframes "$([ "$TIMEFRAME" = "5m" ] && echo "M5,H3" || echo "M15,H3")" \
        --days "$BACKTEST_DAYS" \
        --account "$ACCOUNT" \
        $REFRESH_FLAG \
        2>&1 | tee -a "$LOG_FILE"
    
    if [ ${PIPESTATUS[0]} -ne 0 ]; then
        log_error "Data download failed"
        exit 1
    fi
    
    log "Step 2: Running backtest engine..."
    
    # Run backtest
    python3 -m backtest.src.backtest_engine \
        --instrument "$INSTRUMENT" \
        --timeframe "$TIMEFRAME" \
        --account "$ACCOUNT" \
        --days "$BACKTEST_DAYS" \
        --balance "$INITIAL_BALANCE" \
        2>&1 | tee -a "$LOG_FILE"
    
    if [ ${PIPESTATUS[0]} -ne 0 ]; then
        log_error "Backtest execution failed"
        exit 1
    fi
    
    log "Step 3: Generating comprehensive reports..."
    
    # Generate reports (this would require saving results to JSON first)
    # For now, we'll create a simple Python script to orchestrate everything
    
    cat > /tmp/run_backtest_${TIMESTAMP}.py << EOF
import sys
import os
sys.path.append('.')

from backtest.src.data_downloader import BacktestDataDownloader
from backtest.src.backtest_engine import BacktestEngine
from backtest.src.report_generator import BacktestReportGenerator
import json

# Configuration
instrument = "$INSTRUMENT"
timeframe = "$TIMEFRAME"
account = "$ACCOUNT"
days_back = $BACKTEST_DAYS
initial_balance = $INITIAL_BALANCE
force_refresh = $([[ "$DATA_REFRESH" == "true" ]] && echo "True" || echo "False")
results_prefix = "$RESULTS_PREFIX"

print(f"Starting comprehensive backtest...")
print(f"Instrument: {instrument}")
print(f"Timeframe: {timeframe}")
print(f"Period: {days_back} days")

# Step 1: Download data
print("\\n=== Downloading Data ===")
downloader = BacktestDataDownloader(account=account)

granularity = 'M5' if timeframe == '5m' else 'M15'
data = downloader.get_data_for_backtest(
    instrument=instrument,
    trading_timeframe=granularity,
    market_timeframe='H3',
    days_back=days_back
)

if granularity not in data or 'H3' not in data:
    print("ERROR: Failed to download required data")
    sys.exit(1)

print(f"Downloaded {len(data[granularity])} {granularity} candles")
print(f"Downloaded {len(data['H3'])} H3 candles")

# Step 2: Run backtest
print("\\n=== Running Backtest ===")
engine = BacktestEngine(
    instrument=instrument,
    timeframe=timeframe,
    account=account,
    initial_balance=initial_balance
)

results = engine.run_backtest(data[granularity], data['H3'])

print(f"Backtest completed: {results['performance']['total_trades']} trades")
print(f"Final balance: \${results['backtest_info']['final_balance']:,.2f}")
print(f"Total return: {results['performance']['total_return_pct']:.2f}%")

# Step 3: Generate reports
print("\\n=== Generating Reports ===")
report_gen = BacktestReportGenerator(results, 'backtest/results')
generated_files = report_gen.generate_complete_report(results_prefix)

print("\\n=== Backtest Summary ===")
print(f"Instrument: {instrument} ({timeframe})")
print(f"Period: {days_back} days")
print(f"Total Trades: {results['performance']['total_trades']}")
print(f"Win Rate: {results['performance']['win_rate']:.1f}%")
print(f"Total Return: \${results['performance']['total_return']:,.2f} ({results['performance']['total_return_pct']:.2f}%)")
print(f"Profit Factor: {results['performance']['profit_factor']:.2f}")

# Calculate advanced metrics for summary
from backtest.src.report_generator import BacktestReportGenerator
temp_gen = BacktestReportGenerator(results, 'temp')
advanced_metrics = temp_gen.calculate_advanced_metrics()
if 'risk_metrics' in advanced_metrics:
    print(f"Max Drawdown: {advanced_metrics['risk_metrics']['max_drawdown_pct']:.2f}%")

print(f"\\nReports saved to: backtest/results/")
for file in generated_files:
    print(f"  - {file}")

print("\\n=== Backtest Complete ===")
EOF
    
    # Run the comprehensive backtest
    python3 /tmp/run_backtest_${TIMESTAMP}.py 2>&1 | tee -a "$LOG_FILE"
    
    if [ ${PIPESTATUS[0]} -ne 0 ]; then
        log_error "Comprehensive backtest failed"
        exit 1
    fi
    
    # Cleanup
    rm /tmp/run_backtest_${TIMESTAMP}.py
}

# Function to check for running live bots
check_live_bots() {
    log_info "Checking for running live trading bots..."
    
    # Check for live bot processes
    LIVE_BOTS=$(pgrep -f "trading_bot.*${INSTRUMENT}" | grep -v "backtest" || true)
    
    if [ ! -z "$LIVE_BOTS" ]; then
        log_warn "Found running live bot processes for $INSTRUMENT:"
        ps -p $LIVE_BOTS -o pid,ppid,cmd --no-headers
        log_warn "Backtest will run independently without affecting live trading"
    else
        log_info "No live trading bots detected for $INSTRUMENT"
    fi
}

# Function to run in parallel mode (experimental)
run_parallel() {
    log_info "Running in parallel mode (experimental)"
    
    # Create a unique temporary script for this backtest
    TEMP_SCRIPT="/tmp/bt_parallel_${TIMESTAMP}.sh"
    
    cat > "$TEMP_SCRIPT" << 'PARALLEL_EOF'
#!/bin/bash
# This script runs independently in parallel
PARALLEL_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PARALLEL_SCRIPT_DIR"/../..
PARALLEL_EOF
    
    # Append the main backtest function to the parallel script
    echo "run_backtest() {" >> "$TEMP_SCRIPT"
    declare -f run_backtest | tail -n +2 >> "$TEMP_SCRIPT"
    
    # Append variables and execution
    cat >> "$TEMP_SCRIPT" << PARALLEL_EOF2

# Set variables for parallel execution
ACCOUNT="$ACCOUNT"
INSTRUMENT="$INSTRUMENT"
TIMEFRAME="$TIMEFRAME"
BACKTEST_DAYS="$BACKTEST_DAYS"
INITIAL_BALANCE="$INITIAL_BALANCE"
DATA_REFRESH="$DATA_REFRESH"
LOG_FILE="$LOG_FILE"
RESULTS_PREFIX="$RESULTS_PREFIX"

# Run the backtest
run_backtest
PARALLEL_EOF2
    
    chmod +x "$TEMP_SCRIPT"
    
    # Start parallel execution
    nohup "$TEMP_SCRIPT" > "${LOG_FILE}.parallel" 2>&1 &
    PARALLEL_PID=$!
    
    log "Backtest started in parallel mode"
    log "Process ID: $PARALLEL_PID"
    log "Log file: ${LOG_FILE}.parallel"
    log "You can monitor progress with: tail -f ${LOG_FILE}.parallel"
    
    # Clean up temp script after a delay
    (sleep 5 && rm -f "$TEMP_SCRIPT") &
}

# Main execution
main() {
    # Check for live bots
    check_live_bots
    
    # Check if results directory is writable
    if [ ! -w "backtest/results" ]; then
        log_error "Cannot write to backtest/results directory"
        exit 1
    fi
    
    # Create lock file to prevent duplicate backtests
    LOCK_FILE="backtest/.lock_${INSTRUMENT}_${TIMEFRAME}_${ACCOUNT}"
    if [ -f "$LOCK_FILE" ]; then
        log_warn "Another backtest appears to be running for this configuration"
        log_warn "Lock file: $LOCK_FILE"
        log_warn "If this is incorrect, remove the lock file and try again"
        exit 1
    fi
    
    # Create lock file
    echo "$$" > "$LOCK_FILE"
    echo "$(date)" >> "$LOCK_FILE"
    
    # Cleanup function
    cleanup() {
        rm -f "$LOCK_FILE"
        log "Backtest process cleanup completed"
    }
    
    # Set trap for cleanup
    trap cleanup EXIT INT TERM
    
    log "Lock file created: $LOCK_FILE"
    
    # Run backtest (parallel or sequential)
    if [ "$PARALLEL_MODE" = true ]; then
        run_parallel
    else
        run_backtest
        log "Backtest completed successfully!"
        log "Check results in: $RESULTS_DIR"
        log "Log file: $LOG_FILE"
    fi
}

# Run main function
main