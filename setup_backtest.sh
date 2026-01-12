#!/bin/bash

# Setup script for backtest environment
echo "Setting up backtest environment..."

# Check if we're in the right directory
if [ ! -f "requirements_backtest.txt" ]; then
    echo "Error: Please run this script from the project root directory"
    exit 1
fi

# Install Python dependencies for backtest
echo "Installing Python dependencies..."
pip install -r requirements_backtest.txt

# Create necessary directories
mkdir -p backtest/{data,results,logs}

# Make scripts executable
chmod +x backtest/scripts/bt_auto_trade_market.sh
chmod +x backtest/src/main_backtest.py

echo ""
echo "✅ Backtest environment setup complete!"
echo ""
echo "Usage examples:"
echo "  # Run backtest with Python:"
echo "  python3 backtest/src/main_backtest.py at=account1 fr=EUR_USD tf=5m bt=30d"
echo ""
echo "  # Run backtest with shell script:"
echo "  ./backtest/scripts/bt_auto_trade_market.sh at=account1 fr=EUR_USD tf=5m bt=30d"
echo ""
echo "  # Run backtest with different balance:"
echo "  python3 backtest/src/main_backtest.py at=account2 fr=GBP_USD tf=15m bt=90d --balance=25000"
echo ""
echo "Results will be saved in: backtest/results/"
echo "Logs will be saved in: backtest/logs/"