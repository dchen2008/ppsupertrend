# Quick Start Guide

## 1️⃣ Install Dependencies

```bash
pip install -r requirements.txt
```

## 2️⃣ Test Connection

```bash
python test_connection.py
```

Expected output:
- ✅ Connection successful
- ✅ Account balance displayed
- ✅ Current price retrieved
- ✅ Indicator calculations working

## 3️⃣ Run Trading Bot

```bash
python trading_bot.py
```

Press `Ctrl+C` to stop.

## 4️⃣ Monitor Performance

Check `trading_bot.log` for detailed logs:
```bash
tail -f trading_bot.log
```

## Configuration Cheat Sheet

Edit `config.py` to customize:

### Quick Settings
```python
# Change timeframe
granularity = "H1"  # M1, M5, M15, H1, H4, D

# Change position size
position_size = 2000  # Units (1000 = 0.01 lot)

# Adjust sensitivity
pivot_period = 3     # Higher = less sensitive
atr_factor = 2.5     # Lower = tighter stops
```

### Trading Different Pairs
```python
instrument = "GBP_USD"  # EUR_USD, USD_JPY, etc.
```

## Common Commands

| Action | Command |
|--------|---------|
| Install dependencies | `pip install -r requirements.txt` |
| Test connection | `python test_connection.py` |
| Start bot | `python trading_bot.py` |
| Stop bot | Press `Ctrl+C` |
| View logs | `cat trading_bot.log` |
| Monitor live | `tail -f trading_bot.log` |

## Indicator Parameters

| Parameter | Default | Effect |
|-----------|---------|--------|
| pivot_period | 2 | Lower = more signals |
| atr_factor | 3.0 | Higher = wider stops |
| atr_period | 10 | ATR calculation period |

## Signal Types

- **BUY**: Enter long position
- **SELL**: Enter short position
- **HOLD_LONG**: Continue holding long
- **HOLD_SHORT**: Continue holding short
- **HOLD**: No position, waiting

## Timeframes

- **M1, M5**: Scalping (many signals)
- **M15, H1**: Intraday (recommended)
- **H4, D**: Swing trading (few signals)

## Safety Checklist

✅ Running in practice mode
✅ Small position sizes
✅ Tested connection successfully
✅ Understand the strategy
✅ Monitoring regularly

## Troubleshooting

**Connection Error**
→ Check API key and account ID in `config.py`

**No Signals**
→ Lower `pivot_period` or `atr_factor`

**Margin Error**
→ Reduce `position_size`

**Bot Not Trading**
→ Check logs in `trading_bot.log`

## Emergency Stop

1. Press `Ctrl+C` (stops bot)
2. Manually close positions via OANDA web platform if needed

## Support

- Read full documentation: `README.md`
- View strategy details: `pivot-point-supertrend-documentation.html`
- OANDA API docs: https://developer.oanda.com/
