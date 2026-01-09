"""
Risk Management Module
Handles position sizing and risk calculations
"""

import logging
from .config import TradingConfig


class RiskManager:
    """Manages trading risk and position sizing"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def calculate_position_size(self, account_balance, signal_info):
        """
        Calculate position size based on fixed dollar risk per trade

        Formula for EUR/USD:
        Position Size (units) = Risk Amount ($) / Stop Loss Distance (in price)

        Where:
        - 1 standard lot = 100,000 units
        - 1 pip = 0.0001
        - Risk is fixed in dollars per trade

        Args:
            account_balance: Current account balance
            signal_info: Signal information dict with 'supertrend', 'price', 'atr'

        Returns:
            int: Number of units to trade
        """
        if not TradingConfig.use_dynamic_sizing:
            return TradingConfig.position_size

        # Calculate risk amount (can be fixed or percentage of balance)
        if TradingConfig.risk_per_trade < 1:
            # Interpret as percentage (e.g., 0.02 = 2%)
            risk_amount = account_balance * TradingConfig.risk_per_trade
        else:
            # Interpret as fixed dollar amount (e.g., 100 = $100)
            risk_amount = TradingConfig.risk_per_trade

        # Estimate stop loss distance based on SuperTrend
        if signal_info['supertrend'] and signal_info['price']:
            stop_distance = abs(signal_info['price'] - signal_info['supertrend'])
        elif signal_info['atr']:
            # Fallback to ATR-based stop
            stop_distance = signal_info['atr'] * TradingConfig.atr_factor
        else:
            # Use default small stop if no data
            stop_distance = 0.0020  # 20 pips for EUR/USD

        # Calculate position size using risk-based formula
        # Position Size (units) = Risk Amount ($) / Stop Distance (in price)
        position_size_units = risk_amount / stop_distance
        position_size_units = int(round(position_size_units))

        # Convert to lots for logging
        position_size_lots = position_size_units / 100000

        # Ensure position size is within limits
        position_size_units = max(1000, position_size_units)  # Minimum 1000 units
        position_size_units = min(TradingConfig.max_position_size, position_size_units)

        # Recalculate actual risk after rounding/limits
        actual_risk = position_size_units * stop_distance
        stop_distance_pips = stop_distance / 0.0001

        self.logger.info(f"Calculated position size: {position_size_units} units ({position_size_lots:.3f} lots)")
        self.logger.info(f"  Risk amount: ${risk_amount:.2f}")
        self.logger.info(f"  Actual risk: ${actual_risk:.2f}")
        self.logger.info(f"  Stop distance: {stop_distance:.5f} ({stop_distance_pips:.1f} pips)")

        return position_size_units

    def calculate_stop_loss(self, signal_info, signal_type, client=None, instrument=None):
        """
        Calculate stop loss price based on SuperTrend line with spread adjustment

        Args:
            signal_info: Signal information dict
            signal_type: 'BUY' or 'SELL'
            client: OANDAClient instance (optional, for spread calculation)
            instrument: Trading instrument (optional, for spread calculation)

        Returns:
            float: Stop loss price (adjusted for spread if applicable)
        """
        if signal_info['supertrend'] is None:
            return None

        # For buy signals, stop loss is at the SuperTrend line (below price)
        # For sell signals, stop loss is at the SuperTrend line (above price)
        base_stop_loss = signal_info['supertrend']

        # Apply spread adjustment if enabled and client is provided
        if TradingConfig.use_spread_adjustment and client and instrument:
            spread = client.get_current_spread(instrument)

            if spread:
                from .config import TradingConfig
                # Adjust stop loss so position closes when MIDPOINT touches SuperTrend
                # SuperTrend is calculated from MIDPOINT, but stops trigger on BID/ASK
                spread_adjustment = spread / 2.0

                # Adjust stop loss based on position type
                if signal_type == 'SELL':  # SHORT position
                    # Stop triggered by ASK = MIDPOINT + (spread/2)
                    adjusted_stop_loss = base_stop_loss + spread_adjustment
                    self.logger.info(f"Stop loss (SHORT): {base_stop_loss:.5f} → {adjusted_stop_loss:.5f} (spread adj: +{spread_adjustment:.5f})")
                    return round(adjusted_stop_loss, 5)
                else:  # BUY / LONG position
                    # Stop triggered by BID = MIDPOINT - (spread/2)
                    adjusted_stop_loss = base_stop_loss - spread_adjustment
                    self.logger.info(f"Stop loss (LONG): {base_stop_loss:.5f} → {adjusted_stop_loss:.5f} (spread adj: -{spread_adjustment:.5f})")
                    return round(adjusted_stop_loss, 5)

        self.logger.info(f"Calculated stop loss: {base_stop_loss:.5f} (SuperTrend line)")
        return round(base_stop_loss, 5)

    def calculate_take_profit(self, entry_price, stop_loss, risk_reward_ratio=2.0):
        """
        Calculate take profit based on risk-reward ratio

        Args:
            entry_price: Entry price
            stop_loss: Stop loss price
            risk_reward_ratio: Risk-reward ratio (default: 2.0)

        Returns:
            float: Take profit price or None
        """
        if stop_loss is None or entry_price is None:
            return None

        # Calculate risk (distance to stop loss)
        risk = abs(entry_price - stop_loss)

        # Calculate reward (risk * ratio)
        reward = risk * risk_reward_ratio

        # Calculate take profit
        if entry_price > stop_loss:  # Long position
            take_profit = entry_price + reward
        else:  # Short position
            take_profit = entry_price - reward

        self.logger.info(f"Calculated take profit: {take_profit:.5f} (RR: {risk_reward_ratio})")
        return round(take_profit, 5)

    def should_trade(self, signal_info, current_position, current_candle_time, last_signal_candle_time):
        """
        Determine if we should execute a trade based on current state

        Strategy: Close on opposite signals (matching Pine Script behavior)
        - Close LONG position when SELL signal appears
        - Close SHORT position when BUY signal appears
        - This allows new position to open immediately (OANDA allows only 1 position per instrument)
        - Prevent duplicate trades on the same signal candle
        - Skip stale signals (older than max_signal_age)

        Args:
            signal_info: Signal information dict with 'signal' and 'candle_age_seconds'
            current_position: Current position dict or None
            current_candle_time: Timestamp of the current signal candle
            last_signal_candle_time: Timestamp of the last candle that triggered a trade

        Returns:
            tuple: (bool: should_trade, str: action, str: next_action)
                action: 'OPEN_LONG', 'OPEN_SHORT', 'CLOSE', 'HOLD'
                next_action: Action to take after closing (for trend reversals): 'OPEN_LONG', 'OPEN_SHORT', or None
        """
        signal = signal_info['signal']

        # Check signal age - skip if too old (stale)
        if 'candle_age_seconds' in signal_info:
            signal_age = signal_info['candle_age_seconds']
            if signal_age > TradingConfig.max_signal_age:
                self.logger.warning(f"⏰ Skipping stale {signal} signal: {signal_age:.1f}s old (max: {TradingConfig.max_signal_age}s)")
                return False, 'HOLD', None

        # Check for duplicate signal from same candle
        if last_signal_candle_time is not None and current_candle_time == last_signal_candle_time:
            self.logger.debug(f"Ignoring duplicate {signal} signal from same candle: {current_candle_time}")
            return False, 'HOLD', None

        # If no position, check for entry signals
        if current_position is None or current_position['units'] == 0:
            if signal == 'BUY':
                return True, 'OPEN_LONG', None
            elif signal == 'SELL':
                return True, 'OPEN_SHORT', None
            else:
                return False, 'HOLD', None

        # If we have a position, check for opposite signals (trend reversal)
        current_side = current_position['side']

        # Close on opposite signal and prepare to open opposite position immediately
        if current_side == 'LONG' and signal == 'SELL':
            self.logger.info("🔄 Trend reversal: Closing LONG and opening SHORT")
            return True, 'CLOSE', 'OPEN_SHORT'
        elif current_side == 'SHORT' and signal == 'BUY':
            self.logger.info("🔄 Trend reversal: Closing SHORT and opening LONG")
            return True, 'CLOSE', 'OPEN_LONG'

        # Hold if no action needed
        return False, 'HOLD', None

    def validate_trade(self, account_summary, position_size):
        """
        Validate if trade can be executed based on account state

        Args:
            account_summary: Account summary dict
            position_size: Proposed position size

        Returns:
            tuple: (bool: is_valid, str: reason)
        """
        if account_summary is None:
            return False, "Cannot fetch account summary"

        # Check if sufficient margin available
        margin_available = account_summary['margin_available']
        if margin_available <= 0:
            return False, "Insufficient margin available"

        # Check account balance
        balance = account_summary['balance']
        if balance <= 0:
            return False, "Account balance is zero or negative"

        # Additional checks can be added here

        return True, "Trade validated"
