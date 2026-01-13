#!/bin/bash
#
# Launch Market-Aware Trading Bot with Dynamic Risk/Reward
# Uses 3H PP SuperTrend for market direction (bull/bear)
#
# Usage:
#   ./auto_trade_market.sh at=account1 fr=EUR_USD tf=5m
#   ./auto_trade_market.sh at=account2 fr=EUR_USD tf=15m
#   ./auto_trade_market.sh at=account1 fr=EUR_USD tf=5m catch-up
#   ./auto_trade_market.sh at=account1 fr=EUR_USD tf=5m close-position
#
# Examples:
#   ./auto_trade_market.sh at=account1 fr=EUR_USD tf=5m
#   ./auto_trade_market.sh at=account1 fr=GBP_USD tf=15m
#   ./auto_trade_market.sh at=account2 fr=USD_JPY tf=5m
#   ./auto_trade_market.sh at=account1 fr=EUR_USD tf=5m catch-up        # Enter on current trend
#   ./auto_trade_market.sh at=account1 fr=EUR_USD tf=5m close-position  # Close position immediately

# Check if correct number of arguments (3 required, 1 optional)
if [ "$#" -lt 3 ] || [ "$#" -gt 4 ]; then
    echo "❌ Error: Invalid number of arguments"
    echo ""
    echo "Usage: $0 at=<account> fr=<instrument> tf=<timeframe> [catch-up|close-position]"
    echo ""
    echo "Examples:"
    echo "  $0 at=account1 fr=EUR_USD tf=5m"
    echo "  $0 at=account2 fr=EUR_USD tf=15m"
    echo "  $0 at=account1 fr=GBP_USD tf=5m"
    echo "  $0 at=account1 fr=EUR_USD tf=5m catch-up        # Enter on current trend"
    echo "  $0 at=account1 fr=EUR_USD tf=5m close-position  # Close position immediately"
    echo ""
    echo "Parameters:"
    echo "  at=account1|account2|account3  - Trading account to use"
    echo "  fr=EUR_USD|GBP_USD|USD_JPY...  - Currency pair to trade"
    echo "  tf=5m|15m                      - Trading timeframe"
    echo "  catch-up                       - (Optional) Enter position on current trend"
    echo "  close-position                 - (Optional) Close position immediately"
    echo ""
    echo "Note: Account-specific configuration will be loaded from:"
    echo "      <account>/config.yaml"
    exit 1
fi

# Parse arguments
ACCOUNT_ARG=$1
INSTRUMENT_ARG=$2
TIMEFRAME_ARG=$3
CATCHUP_ARG=$4

# Validate account argument format
if [[ ! $ACCOUNT_ARG =~ ^at= ]]; then
    echo "❌ Error: Account must be in format at=account1, at=account2, etc."
    exit 1
fi
ACCOUNT=${ACCOUNT_ARG#at=}

# Validate instrument argument format
if [[ ! $INSTRUMENT_ARG =~ ^fr= ]]; then
    echo "❌ Error: Instrument must be in format fr=EUR_USD, fr=GBP_USD, etc."
    exit 1
fi
INSTRUMENT=${INSTRUMENT_ARG#fr=}

# Validate timeframe argument format
if [[ ! $TIMEFRAME_ARG =~ ^tf= ]]; then
    echo "❌ Error: Timeframe must be in format tf=5m or tf=15m"
    exit 1
fi
TIMEFRAME=${TIMEFRAME_ARG#tf=}

# Validate timeframe value
if [ "$TIMEFRAME" != "5m" ] && [ "$TIMEFRAME" != "15m" ]; then
    echo "❌ Error: Timeframe must be 5m or 15m (got: $TIMEFRAME)"
    exit 1
fi

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Check configuration files
DEFAULT_CONFIG="${PROJECT_ROOT}/src/config.yaml"
ACCOUNT_CONFIG="${PROJECT_ROOT}/${ACCOUNT}/config.yaml"

# Display configuration
echo ""
echo "=" 80
echo "🚀 LAUNCHING MARKET-AWARE TRADING BOT"
echo "=" 80
echo "Account:     $ACCOUNT"
echo "Instrument:  $INSTRUMENT"
echo "Timeframe:   $TIMEFRAME"
echo ""

# Check which config files exist
echo "📋 Configuration:"
if [ -f "$DEFAULT_CONFIG" ]; then
    echo "  Default Config: $DEFAULT_CONFIG ✓"
else
    echo "  Default Config: Not found (using built-in defaults)"
fi

if [ -f "$ACCOUNT_CONFIG" ]; then
    echo "  Account Config: $ACCOUNT_CONFIG ✓ (overrides defaults)"
    CONFIG_TO_DISPLAY="$ACCOUNT_CONFIG"
else
    echo "  Account Config: Not found (using defaults only)"
    CONFIG_TO_DISPLAY="$DEFAULT_CONFIG"
fi

echo ""

# Display configuration summary from the appropriate config
if [ -f "$CONFIG_TO_DISPLAY" ]; then
    echo "Configuration Summary:"
    echo "---"
    
    # Extract and display check_interval
    CHECK_INTERVAL=$(grep -E "^check_interval:" "$CONFIG_TO_DISPLAY" | awk '{print $2}')
    if [ ! -z "$CHECK_INTERVAL" ]; then
        echo "  Check Interval: ${CHECK_INTERVAL}s"
    fi
    
    # Extract and display market timeframe
    MARKET_TF=$(grep -A2 "^market:" "$CONFIG_TO_DISPLAY" | grep "timeframe:" | awk '{print $2}')
    if [ ! -z "$MARKET_TF" ]; then
        echo "  Market Trend Timeframe: $MARKET_TF"
    fi
    
    # Extract and display risk/reward settings
    echo ""
    echo "  Risk/Reward Settings:"
    BEAR_SHORT=$(grep -A2 "bear_market:" "$CONFIG_TO_DISPLAY" | grep "short_rr:" | awk '{print $2}')
    BEAR_LONG=$(grep -A2 "bear_market:" "$CONFIG_TO_DISPLAY" | grep "long_rr:" | awk '{print $2}')
    BULL_SHORT=$(grep -A2 "bull_market:" "$CONFIG_TO_DISPLAY" | grep "short_rr:" | awk '{print $2}')
    BULL_LONG=$(grep -A2 "bull_market:" "$CONFIG_TO_DISPLAY" | grep "long_rr:" | awk '{print $2}')
    
    if [ ! -z "$BEAR_SHORT" ]; then
        echo "    Bear Market: Short R:R=$BEAR_SHORT, Long R:R=$BEAR_LONG"
    fi
    if [ ! -z "$BULL_SHORT" ]; then
        echo "    Bull Market: Short R:R=$BULL_SHORT, Long R:R=$BULL_LONG"
    fi
    echo "---"
fi

# Skip delay for close-position (immediate action)
if [ "$CATCHUP_ARG" != "close-position" ]; then
    echo ""
    echo "Starting bot in 3 seconds..."
    echo "Press Ctrl+C to stop"
    echo ""
    sleep 3
fi

# Change to project root directory
cd "$PROJECT_ROOT"

# Create log and csv directories if they don't exist
mkdir -p "${ACCOUNT}/logs"
mkdir -p "${ACCOUNT}/csv"

# Run the market-aware bot
if [ "$CATCHUP_ARG" == "close-position" ]; then
    echo "🔒 Close-position mode: Closing all positions for $INSTRUMENT immediately"
    python3 -m src.trading_bot_market_aware "$ACCOUNT_ARG" "$INSTRUMENT_ARG" "$TIMEFRAME_ARG" "$CATCHUP_ARG"
elif [ -n "$CATCHUP_ARG" ]; then
    echo "🔄 Catch-up mode enabled: Will enter on current trend if no position"
    python3 -m src.trading_bot_market_aware "$ACCOUNT_ARG" "$INSTRUMENT_ARG" "$TIMEFRAME_ARG" "$CATCHUP_ARG"
else
    python3 -m src.trading_bot_market_aware "$ACCOUNT_ARG" "$INSTRUMENT_ARG" "$TIMEFRAME_ARG"
fi