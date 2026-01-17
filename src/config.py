"""
OANDA API Configuration
"""

class OANDAConfig:
    """OANDA API configuration with multi-account support"""

    # Multiple OANDA accounts configuration
    # Add as many accounts as needed following the same structure
    ACCOUNTS = {
        # email: dchen2008@gmail.com
        'account1': {
            'api_key': 'ce37b575a2ce3880061d11fc05101f11-6e2a20ddd9e21e58e87c50e0ff03190f',
            'account_id': '101-001-35749385-001',
            'is_practice': True
        },
        # email: dongchen168@gmail.com
        'account2': {
            'api_key': 'c28a178a6bd204026e4b029d70ef5664-37cb94eabb6963e88d008d7102e37acf',
            'account_id': '101-001-38143009-001',
            'is_practice': True
        },
                # email:don@aidog.us
        'account3': {
            'api_key': '068b6bc3bd53b0156d2e4811d38c42d9-bed103c8bc1666cb8308ba5267b1d510',
            'account_id': '101-001-38195348-001',
            'is_practice': True
        },
        # email:fastsolarllc@gmail.com
        'account4': {
            'api_key': '97e97cf3987d09e57edbc71c4cac6ad9-196ea977cd536d28e4f7bffe0ba4f9c1',
            'account_id': '101-001-38195467-001',
            'is_practice': True
        },
        # 
        'account21': {
            'api_key': 'ce37b575a2ce3880061d11fc05101f11-6e2a20ddd9e21e58e87c50e0ff03190f',
            'account_id': '101-001-35749385-002',
            'is_practice': True
        },
        # 
        'account22': {
            'api_key': 'ce37b575a2ce3880061d11fc05101f11-6e2a20ddd9e21e58e87c50e0ff03190f',
            'account_id': '101-001-35749385-003',
            'is_practice': True
        },
        # 
        'account23': {
            'api_key': 'ce37b575a2ce3880061d11fc05101f11-6e2a20ddd9e21e58e87c50e0ff03190f',
            'account_id': '101-001-35749385-004',
            'is_practice': True
        },
        # 
        'account24': {
            'api_key': 'ce37b575a2ce3880061d11fc05101f11-6e2a20ddd9e21e58e87c50e0ff03190f',
            'account_id': '101-001-35749385-005',
            'is_practice': True
        },
        # 
        'account25': {
            'api_key': 'ce37b575a2ce3880061d11fc05101f11-6e2a20ddd9e21e58e87c50e0ff03190f',
            'account_id': '101-001-35749385-006',
            'is_practice': True
        },
        'account26': {
            'api_key': 'ce37b575a2ce3880061d11fc05101f11-6e2a20ddd9e21e58e87c50e0ff03190f',
            'account_id': '101-001-35749385-007',
            'is_practice': True
        },
        'test1': {
            'api_key': 'ce37b575a2ce3880061d11fc05101f11-6e2a20ddd9e21e58e87c50e0ff03190f',
            'account_id': '101-001-35749385-008',
            'is_practice': True
        },
        'test2': {
            'api_key': 'ce37b575a2ce3880061d11fc05101f11-6e2a20ddd9e21e58e87c50e0ff03190f',
            'account_id': '101-001-35749385-009',
            'is_practice': True
        },
        'os1': {
            'api_key': '99364824df618d6d42eec0f2ba1daabc-bb6046511043a47eb41559d13fd6bdb5',
            'account_id': '101-001-31676122-001',
            'is_practice': True
        },        
        'os2': {
            'api_key': '99364824df618d6d42eec0f2ba1daabc-bb6046511043a47eb41559d13fd6bdb5',
            'account_id': '101-001-31676122-002',
            'is_practice': True
        },        
        'os3': {
            'api_key': '99364824df618d6d42eec0f2ba1daabc-bb6046511043a47eb41559d13fd6bdb5',
            'account_id': '101-001-31676122-003',
            'is_practice': True
        },        
        'os4': {
            'api_key': '99364824df618d6d42eec0f2ba1daabc-bb6046511043a47eb41559d13fd6bdb5',
            'account_id': '101-001-31676122-004',
            'is_practice': True
        },        
        'os5': {
            'api_key': '99364824df618d6d42eec0f2ba1daabc-bb6046511043a47eb41559d13fd6bdb5',
            'account_id': '101-001-31676122-005',
            'is_practice': True
        },        
        'os6': {
            'api_key': '99364824df618d6d42eec0f2ba1daabc-bb6046511043a47eb41559d13fd6bdb5',
            'account_id': '101-001-31676122-006',
            'is_practice': True
        },        
        'os7': {
            'api_key': '99364824df618d6d42eec0f2ba1daabc-bb6046511043a47eb41559d13fd6bdb5',
            'account_id': '101-001-31676122-007',
            'is_practice': True
        },        
        'os8': {
            'api_key': '99364824df618d6d42eec0f2ba1daabc-bb6046511043a47eb41559d13fd6bdb5',
            'account_id': '101-001-31676122-008',
            'is_practice': True
        },        
        'os9': {
            'api_key': '99364824df618d6d42eec0f2ba1daabc-bb6046511043a47eb41559d13fd6bdb5',
            'account_id': '101-001-31676122-009',
            'is_practice': True
        },        
        'os10': {
            'api_key': '99364824df618d6d42eec0f2ba1daabc-bb6046511043a47eb41559d13fd6bdb5',
            'account_id': '101-001-31676122-010',
            'is_practice': True
        },        
        'os11': {
            'api_key': '99364824df618d6d42eec0f2ba1daabc-bb6046511043a47eb41559d13fd6bdb5',
            'account_id': '101-001-31676122-011',
            'is_practice': True
        },        
        'os12': {
            'api_key': '99364824df618d6d42eec0f2ba1daabc-bb6046511043a47eb41559d13fd6bdb5',
            'account_id': '101-001-31676122-012',
            'is_practice': True
        },        
        'os13': {
            'api_key': '99364824df618d6d42eec0f2ba1daabc-bb6046511043a47eb41559d13fd6bdb5',
            'account_id': '101-001-31676122-013',
            'is_practice': True
        },        
        'os14': {
            'api_key': '99364824df618d6d42eec0f2ba1daabc-bb6046511043a47eb41559d13fd6bdb5',
            'account_id': '101-001-31676122-014',
            'is_practice': True
        },        
        'os15': {
            'api_key': '99364824df618d6d42eec0f2ba1daabc-bb6046511043a47eb41559d13fd6bdb5',
            'account_id': '101-001-31676122-015',
            'is_practice': True
        },        
        'os16': {
            'api_key': '99364824df618d6d42eec0f2ba1daabc-bb6046511043a47eb41559d13fd6bdb5',
            'account_id': '101-001-31676122-016',
            'is_practice': True
        },        
        'os17': {
            'api_key': '99364824df618d6d42eec0f2ba1daabc-bb6046511043a47eb41559d13fd6bdb5',
            'account_id': '101-001-31676122-017',
            'is_practice': True
        },        
        'os18': {
            'api_key': '99364824df618d6d42eec0f2ba1daabc-bb6046511043a47eb41559d13fd6bdb5',
            'account_id': '101-001-31676122-018',
            'is_practice': True
        },        
        'os19': {
            'api_key': '99364824df618d6d42eec0f2ba1daabc-bb6046511043a47eb41559d13fd6bdb5',
            'account_id': '101-001-31676122-019',
            'is_practice': True
        },        
        'os20': {
            'api_key': '99364824df618d6d42eec0f2ba1daabc-bb6046511043a47eb41559d13fd6bdb5',
            'account_id': '101-001-31676122-020',
            'is_practice': True
        }
    }
    }

    # Currently active account (default to first account if not set)
    _active_account = 'account1'

    # Active account credentials (set from ACCOUNTS)
    api_key = ACCOUNTS[_active_account]['api_key']
    account_id = ACCOUNTS[_active_account]['account_id']
    is_practice = ACCOUNTS[_active_account]['is_practice']

    # Base URLs (same for all accounts)
    base_url_practice = "https://api-fxpractice.oanda.com"
    base_url_live = "https://api-fxtrade.oanda.com"

    @classmethod
    def set_account(cls, account_name):
        """
        Set the active account to use

        Args:
            account_name: Name of the account (e.g., 'account1', 'account2')

        Raises:
            ValueError: If account_name doesn't exist in ACCOUNTS
        """
        if account_name not in cls.ACCOUNTS:
            available = ', '.join(cls.ACCOUNTS.keys())
            raise ValueError(f"Account '{account_name}' not found. Available accounts: {available}")

        cls._active_account = account_name
        cls.api_key = cls.ACCOUNTS[account_name]['api_key']
        cls.account_id = cls.ACCOUNTS[account_name]['account_id']
        cls.is_practice = cls.ACCOUNTS[account_name]['is_practice']

    @classmethod
    def get_active_account(cls):
        """Get the name of the currently active account"""
        return cls._active_account

    @classmethod
    def list_accounts(cls):
        """List all available account names"""
        return list(cls.ACCOUNTS.keys())

    @classmethod
    def get_base_url(cls):
        """Get the appropriate base URL based on practice/live mode"""
        return cls.base_url_practice if cls.is_practice else cls.base_url_live

    @classmethod
    def get_headers(cls):
        """Get API headers for requests"""
        return {
            'Authorization': f'Bearer {cls.api_key}',
            'Content-Type': 'application/json'
        }

    # API request settings
    api_timeout = 5  # seconds - default timeout for API calls
    api_max_retries = 3  # maximum number of retry attempts
    api_retry_delay = 1  # seconds - delay between retries


class TradingConfig:
    """Trading bot configuration"""
    # Instrument to trade
    instrument = "EUR_USD"

    # Pivot Point SuperTrend parameters (matching Pine Script defaults)
    pivot_period = 2  # Pivot Point Period
    atr_factor = 3.0  # ATR Factor
    atr_period = 10   # ATR Period

    # Trading parameters
    position_size = 1  # Units to trade if use_dynamic_sizing = False
    max_position_size = 10000000  # Maximum position size (safety limit)

    # Risk management (IMPORTANT: Read carefully!)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # Option 1: Fixed Position Size (Simple)
    #   use_dynamic_sizing = False
    #   position_size = 85  (≈$100 notional value at current prices)
    #
    # Option 2: Risk-Based Position Sizing (Recommended)
    #   use_dynamic_sizing = True
    #   risk_per_trade = 100  (risk $100 per trade)
    #   OR
    #   risk_per_trade = 0.02  (risk 2% of account per trade)
    #
    # How it works:
    #   - If risk_per_trade >= 1: Treated as fixed dollar amount
    #     Example: risk_per_trade = 100 → risk $100 per trade
    #   - If risk_per_trade < 1: Treated as percentage of balance
    #     Example: risk_per_trade = 0.02 → risk 2% per trade
    #
    # Position size is calculated automatically based on stop loss distance:
    #   Position Size = Risk Amount / Stop Loss Distance
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    use_dynamic_sizing = True  # Enable risk-based position sizing
    risk_per_trade = 100  # Risk $100 per trade (change this to your preference)

    # Timeframe
    granularity = "M15"  # 15-minute candles (options: M1, M5, M15, H1, H4, D)

    # Bot behavior
    check_interval = 60  # Check for new signals every 60 seconds (faster trailing stop updates)
    lookback_candles = 100  # Number of candles to fetch for calculation

    # Trailing stop loss settings
    enable_trailing_stop = True  # Enable trailing stop loss that follows SuperTrend
    min_stop_update_distance = 0.00010  # Minimum 1 pip movement to update stop (avoids excessive API calls)

    # Spread adjustment settings
    # IMPORTANT: Stop losses are triggered by BID (for LONG) or ASK (for SHORT) prices
    # The bot uses MIDPOINT prices for SuperTrend calculation, but stops trigger on BID/ASK
    # This adjustment ensures the position closes when MIDPOINT touches SuperTrend line
    use_spread_adjustment = True  # Enable spread adjustment for stop loss calculation

    # Logging
    log_level = "INFO"  # DEBUG, INFO, WARNING, ERROR
    log_file = "trading_bot.log"
