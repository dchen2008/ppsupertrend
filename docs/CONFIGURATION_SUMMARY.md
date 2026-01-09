# Configuration Summary for Market-Aware Trading Bot

## Configuration Hierarchy

The bot uses a two-level configuration system:

1. **Default Configuration** (`src/config.yaml`)
   - Base settings that apply to all accounts
   - Contains standard risk/reward ratios

2. **Account Overrides** (`account{n}/config.yaml`)
   - Account-specific settings that override defaults
   - Only include settings you want to change

## Current Account Configurations

### Account1 - Conservative
- **Profile**: Conservative risk management
- **Check Interval**: 60 seconds
- **Risk/Reward Ratios**:
  - Bear Market: Short R:R=1.0, Long R:R=0.5
  - Bull Market: Short R:R=0.5, Long R:R=1.0
- **Strategy**: Takes smaller profits (0.5-1.0x risk)

### Account2 - Standard (Default)
- **Profile**: Standard configuration matching defaults
- **Check Interval**: 60 seconds
- **Risk/Reward Ratios**:
  - Bear Market: Short R:R=1.2, Long R:R=0.6
  - Bull Market: Short R:R=0.6, Long R:R=1.2
- **Strategy**: Balanced approach (0.6-1.2x risk)

### Account3 - Aggressive
- **Profile**: Aggressive risk/reward targeting
- **Check Interval**: 45 seconds (more frequent checks)
- **Risk/Reward Ratios**:
  - Bear Market: Short R:R=1.5, Long R:R=0.5
  - Bull Market: Short R:R=0.5, Long R:R=1.5
- **Strategy**: Larger profits when trading with trend (1.5x risk)

## Risk/Reward Logic Explained

The bot adjusts take profit targets based on:

1. **Market Trend** (detected via 3H PP SuperTrend)
   - BULL: 3H signal shows BUY
   - BEAR: 3H signal shows SELL

2. **Position Direction**
   - Trading WITH trend: Higher R:R (favorable)
   - Trading AGAINST trend: Lower R:R (conservative)

### Examples

**In BEAR Market:**
- Short positions are favorable → Higher R:R
- Long positions are counter-trend → Lower R:R (quick exit)

**In BULL Market:**
- Long positions are favorable → Higher R:R
- Short positions are counter-trend → Lower R:R (quick exit)

## Running Different Configurations

```bash
# Conservative (Account1)
./scripts/auto_trade_market.sh at=account1 fr=EUR_USD tf=5m

# Standard (Account2)
./scripts/auto_trade_market.sh at=account2 fr=EUR_USD tf=5m

# Aggressive (Account3)
./scripts/auto_trade_market.sh at=account3 fr=EUR_USD tf=5m

# Run all three concurrently for comparison
./scripts/auto_trade_market.sh at=account1 fr=EUR_USD tf=5m &
./scripts/auto_trade_market.sh at=account2 fr=EUR_USD tf=5m &
./scripts/auto_trade_market.sh at=account3 fr=EUR_USD tf=5m &
```

## Configuration Testing

To verify configuration loading:
```bash
python3 tests/test_market_aware_bot.py
```

This will show:
- Default config loading
- Account-specific overrides
- Final merged configuration for each account
- Risk/reward calculation examples

## Customizing Configuration

To create your own configuration:

1. Copy an existing account config:
```bash
cp account2/config.yaml account4/config.yaml
```

2. Edit the risk/reward ratios:
```yaml
risk_reward:
  bear_market:
    short_rr: 2.0    # Your custom value
    long_rr: 0.3     # Your custom value
  bull_market:
    short_rr: 0.3    # Your custom value
    long_rr: 2.0     # Your custom value
```

3. Add account credentials to `src/config.py`:
```python
ACCOUNTS = {
    'account4': {
        'api_key': 'your-api-key',
        'account_id': 'your-account-id',
        'is_practice': True
    }
}
```

## Performance Comparison

Use different configurations to test which performs best:

| Account | Strategy | Best For |
|---------|----------|----------|
| account1 | Conservative | Low volatility, risk-averse trading |
| account2 | Standard | Balanced market conditions |
| account3 | Aggressive | Strong trending markets |

Monitor performance via CSV files:
```bash
# Compare results
ls -la account*/csv/*.csv
tail account*/csv/*market_aware.csv
```