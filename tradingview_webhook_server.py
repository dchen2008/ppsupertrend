#!/usr/bin/env python3
"""
TradingView Webhook Server for Signal Reception
Receives signals from TradingView and executes trades via OANDA
"""

from flask import Flask, request, jsonify
import json
import logging
from datetime import datetime
import hmac
import hashlib
import os
import sys

# Add src to path
sys.path.append('src')
from oanda_client import OANDAClient
from config import OANDAConfig

app = Flask(__name__)

# Configuration
WEBHOOK_SECRET = "your_secret_key_here"  # Change this!
LOG_FILE = "tradingview_signals.log"

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Store last signals to prevent duplicates
last_signals = {}

def verify_webhook_signature(payload, signature):
    """Verify TradingView webhook signature"""
    if not signature:
        return False
    
    expected_signature = hmac.new(
        WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(signature, expected_signature)

@app.route('/webhook/tradingview', methods=['POST'])
def tradingview_webhook():
    """
    Receive signals from TradingView
    
    Expected JSON format:
    {
        "signal": "BUY" or "SELL",
        "symbol": "EUR_USD",
        "price": 1.16300,
        "timeframe": "5m",
        "timestamp": "2026-01-09T21:35:00Z",
        "supertrend": 1.16390,
        "atr": 0.00050
    }
    """
    try:
        # Verify signature (optional but recommended)
        signature = request.headers.get('X-TradingView-Signature')
        if WEBHOOK_SECRET and not verify_webhook_signature(request.data, signature):
            logger.error("Invalid webhook signature")
            return jsonify({'error': 'Invalid signature'}), 401
        
        # Parse JSON payload
        data = request.get_json()
        if not data:
            logger.error("No JSON data received")
            return jsonify({'error': 'No JSON data'}), 400
        
        logger.info(f"📡 Received TradingView signal: {data}")
        
        # Validate required fields
        required_fields = ['signal', 'symbol', 'price', 'timestamp']
        for field in required_fields:
            if field not in data:
                logger.error(f"Missing required field: {field}")
                return jsonify({'error': f'Missing field: {field}'}), 400
        
        # Check for duplicate signals
        signal_key = f"{data['symbol']}_{data['signal']}_{data['timestamp']}"
        if signal_key in last_signals:
            logger.warning("Duplicate signal ignored")
            return jsonify({'status': 'ignored', 'reason': 'duplicate'}), 200
        
        # Store signal to prevent duplicates
        last_signals[signal_key] = datetime.now()
        
        # Process the signal
        result = process_tradingview_signal(data)
        
        return jsonify(result), 200
        
    except Exception as e:
        logger.error(f"Error processing webhook: {str(e)}")
        return jsonify({'error': str(e)}), 500

def process_tradingview_signal(signal_data):
    """
    Process TradingView signal and execute trade
    """
    try:
        symbol = signal_data['symbol']
        signal_type = signal_data['signal']
        price = signal_data['price']
        
        logger.info(f"🎯 Processing {signal_type} signal for {symbol} at {price}")
        
        # Initialize OANDA client
        OANDAConfig.set_account('account1')  # Use your preferred account
        client = OANDAClient()
        
        # Check if we have an existing position
        positions = client.get_open_positions()
        existing_position = None
        
        if positions:
            for pos in positions:
                if pos.get('instrument') == symbol:
                    existing_position = pos
                    break
        
        # Execute trade based on signal
        if signal_type == 'BUY':
            if existing_position and float(existing_position.get('units', 0)) < 0:
                # Close short position first
                logger.info("🔄 Closing existing SHORT position")
                client.close_position(symbol, 'short')
            
            # Open long position
            result = execute_buy_order(client, symbol, signal_data)
            
        elif signal_type == 'SELL':
            if existing_position and float(existing_position.get('units', 0)) > 0:
                # Close long position first
                logger.info("🔄 Closing existing LONG position")
                client.close_position(symbol, 'long')
            
            # Open short position
            result = execute_sell_order(client, symbol, signal_data)
        
        else:
            return {'status': 'error', 'message': 'Invalid signal type'}
        
        return result
        
    except Exception as e:
        logger.error(f"Error executing signal: {str(e)}")
        return {'status': 'error', 'message': str(e)}

def execute_buy_order(client, symbol, signal_data):
    """Execute BUY order"""
    try:
        price = signal_data['price']
        
        # Calculate position size (use your existing logic)
        position_size = 10000  # Replace with dynamic calculation
        
        # Calculate stop loss (use SuperTrend value)
        stop_loss = signal_data.get('supertrend', price * 0.998)  # 0.2% fallback
        
        # Calculate take profit
        risk = abs(price - stop_loss)
        take_profit = price + (risk * 1.2)  # 1.2 R:R ratio
        
        order_data = {
            'instrument': symbol,
            'units': position_size,
            'type': 'MARKET',
            'stopLossOnFill': {'price': str(stop_loss)},
            'takeProfitOnFill': {'price': str(take_profit)}
        }
        
        response = client.place_order(order_data)
        
        if response:
            logger.info(f"✅ BUY order placed: {position_size} units at {price}")
            return {
                'status': 'success',
                'action': 'BUY',
                'units': position_size,
                'price': price,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'order_id': response.get('orderFillTransaction', {}).get('id')
            }
        else:
            return {'status': 'error', 'message': 'Failed to place order'}
            
    except Exception as e:
        logger.error(f"Error executing BUY order: {str(e)}")
        return {'status': 'error', 'message': str(e)}

def execute_sell_order(client, symbol, signal_data):
    """Execute SELL order"""
    try:
        price = signal_data['price']
        
        # Calculate position size (use your existing logic)
        position_size = -10000  # Negative for short
        
        # Calculate stop loss (use SuperTrend value)
        stop_loss = signal_data.get('supertrend', price * 1.002)  # 0.2% fallback
        
        # Calculate take profit
        risk = abs(price - stop_loss)
        take_profit = price - (risk * 1.2)  # 1.2 R:R ratio
        
        order_data = {
            'instrument': symbol,
            'units': position_size,
            'type': 'MARKET',
            'stopLossOnFill': {'price': str(stop_loss)},
            'takeProfitOnFill': {'price': str(take_profit)}
        }
        
        response = client.place_order(order_data)
        
        if response:
            logger.info(f"✅ SELL order placed: {position_size} units at {price}")
            return {
                'status': 'success',
                'action': 'SELL',
                'units': position_size,
                'price': price,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'order_id': response.get('orderFillTransaction', {}).get('id')
            }
        else:
            return {'status': 'error', 'message': 'Failed to place order'}
            
    except Exception as e:
        logger.error(f"Error executing SELL order: {str(e)}")
        return {'status': 'error', 'message': str(e)}

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'signals_processed': len(last_signals)
    })

if __name__ == '__main__':
    logger.info("🚀 Starting TradingView Webhook Server")
    logger.info("📡 Listening for TradingView signals...")
    
    # Run the server
    app.run(host='0.0.0.0', port=5000, debug=False)