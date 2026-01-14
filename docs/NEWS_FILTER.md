# News Calendar Filter Documentation

## Overview

The News Filter feature automatically pauses trading and closes positions before high-impact economic news events (CPI, NFP, FOMC, etc.) to avoid volatility-related losses.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           NEWS FILTER WORKFLOW                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────────────────┐    │
│  │ Data Sources │     │ NewsManager  │     │ Trading Bot Integration  │    │
│  ├──────────────┤     ├──────────────┤     ├──────────────────────────┤    │
│  │              │     │              │     │                          │    │
│  │ Forex Factory├────►│ Load Events  ├────►│ check_and_trade()        │    │
│  │ (XML Feed)   │     │              │     │   │                      │    │
│  │              │     │ Filter by:   │     │   ├─► should_close?      │    │
│  │ Manual JSON  ├────►│ - Impact     │     │   │   Close position     │    │
│  │ File         │     │ - Keywords   │     │   │                      │    │
│  │              │     │ - Currency   │     │   ├─► is_blocked?        │    │
│  │ Cache File   ├────►│              │     │   │   Skip trading       │    │
│  │ (Fallback)   │     │ Check Time   │     │   │                      │    │
│  │              │     │ Windows      │     │   └─► Normal trading     │    │
│  └──────────────┘     └──────────────┘     └──────────────────────────┘    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Data Sources

### 1. Forex Factory XML Feed (Primary)

**Endpoint:** `https://nfs.faireconomy.media/ff_calendar_thisweek.xml`

**Additional:** `https://nfs.faireconomy.media/ff_calendar_nextweek.xml`

**Response Format (XML):**
```xml
<event>
  <title>Non-Farm Employment Change</title>
  <country>USD</country>
  <date>01-10-2025</date>
  <time>8:30am</time>
  <impact>High</impact>
  <forecast>150K</forecast>
  <previous>227K</previous>
</event>
```

**Rate Limiting:** ~1 request per minute (429 error if exceeded)

**Caching:** On rate limit, falls back to `backtest/data/news_calendar_cache.json`

### 2. OANDA ForexLabs Calendar (Deprecated)

**Endpoint:** `https://api-fxpractice.oanda.com/labs/v1/calendar`

**Status:** Blocked by Cloudflare (403 Forbidden)

**Parameters:**
| Parameter | Description | Example |
|-----------|-------------|---------|
| instrument | Currency pair | EUR_USD |
| period | Lookahead in seconds | 2592000 (30 days) |

**Response Format (JSON):**
```json
[
  {
    "title": "US CPI",
    "timestamp": 1705420800,
    "currency": "USD",
    "impact": 3,
    "region": "americas",
    "forecast": "0.2%",
    "previous": "0.3%"
  }
]
```

### 3. Manual Events File

**Location:** `{account}/news_events.json`

**Format:**
```json
{
  "events": [
    {
      "title": "FOMC Interest Rate Decision",
      "timestamp": 1768455000,
      "currency": "USD",
      "impact": 3
    }
  ],
  "last_updated": "2026-01-14T02:00:00Z"
}
```

**Timestamp:** Unix timestamp in seconds (UTC)
- Convert dates at: https://www.epochconverter.com/

## Business Logic

### Event Filtering

Events are filtered by:

1. **Impact Level** (config: `impact_levels`)
   - 1 = Low impact (ignored)
   - 2 = Medium impact (optional)
   - 3 = High impact (default: filtered)

2. **Currency** (config: `currencies`)
   - Default: `['EUR', 'USD']`
   - Only events affecting these currencies trigger the filter

3. **Keywords** (config: `event_keywords`)
   - Event title must contain at least one keyword
   - Case-insensitive matching

**Default Keywords:**
```
FOMC, Fed, Federal Reserve, Interest Rate, ECB, Bank of England,
CPI, Consumer Price, Core CPI, PPI, Producer Price, PCE, Inflation,
Non-Farm, NFP, Nonfarm, Unemployment, Jobless, Employment, ADP,
GDP, Gross Domestic, Retail Sales, ISM Manufacturing, ISM Services
```

### Time Windows

```
        Pre-News Buffer              Post-News Buffer
        (default: 10 min)            (default: 15 min)
              │                            │
              ▼                            ▼
    ──────────┼────────────────────────────┼──────────►
              │      NEWS EVENT            │           time
              │          │                 │
              │◄────────►│◄───────────────►│
              │  CLOSE   │    BLOCKED      │
              │ POSITION │   (no trades)   │
```

**Pre-News Buffer (`pre_news_buffer_minutes`):**
- Default: 10 minutes before event
- Actions: Close open positions + block new trades

**Post-News Buffer (`post_news_buffer_minutes`):**
- Default: 15 minutes after event
- Actions: Block new trades only

### Decision Flow

```python
# In check_and_trade() - runs every check_interval (60s)

1. Check should_close_position()
   └── If within pre-news buffer AND has open position:
       └── Close position immediately
       └── Log to CSV with position_status='NEWS_CLOSE'
       └── Return (skip rest of cycle)

2. Check is_news_blocked()
   └── If within pre-news OR post-news buffer:
       └── Log "Trading paused: {reason}"
       └── Continue to position monitoring (no new trades)

3. In should_trade() - additional check:
   └── If news_manager.is_news_blocked():
       └── Return (False, 'HOLD_NEWS', None)
```

## Configuration

### Default Config (`src/config.yaml`)

```yaml
news_filter:
  enabled: false                    # Enable per-account

  # Time buffers
  pre_news_buffer_minutes: 10       # Close positions X mins before
  post_news_buffer_minutes: 15      # Resume trading X mins after

  # Data sources
  oanda_calendar:
    enabled: false                  # OANDA API (currently blocked)
    instrument: EUR_USD
    period: 2592000                 # 30 days
    cache_ttl: 3600                 # 1 hour cache

  manual_events_file: "{account}/news_events.json"

  # Filtering
  impact_levels: [3]                # High impact only
  currencies: [EUR, USD]

  event_keywords:
    - "FOMC"
    - "CPI"
    - "NFP"
    - "GDP"
    # ... (see full list in config.yaml)

  # Actions
  close_positions_before_news: true
  log_blocked_trades: true
```

### Account Override (`account1/config.yaml`)

```yaml
news_filter:
  enabled: true
  pre_news_buffer_minutes: 5        # Override: only 5 mins
  close_positions_before_news: false # Don't auto-close
```

## File Structure

```
ppsupertrend/
├── src/
│   ├── news_manager.py          # NewsManager class
│   ├── config.yaml              # Default news_filter config
│   └── trading_bot_market_aware.py  # Integration
│
├── account1/
│   ├── config.yaml              # Account-specific overrides
│   └── news_events.json         # Manual events file
│
├── backtest/
│   └── data/
│       └── news_calendar_cache.json  # Forex Factory cache
│
└── pull_news_calendar.py        # CLI tool for fetching events
```

## CLI Tools

### add_news_event.py (Add Custom Events)

Manually add events not in official calendars (e.g., court rulings, political speeches, emergency meetings).

**Use Cases:**
- Supreme Court rulings on tariffs/trade
- Presidential speeches or press conferences
- Emergency Fed meetings
- Political events affecting markets
- Any custom event you want to pause trading for

#### Basic Usage

```bash
# Add a custom event (required: title and time)
python3 add_news_event.py title="Supreme Court Tariff Ruling" time="01/15/2026 11:00"

# Output:
# ======================================================================
#   Event Added Successfully!
# ======================================================================
#   Title:     Supreme Court Tariff Ruling
#   Time:      2026-01-15 11:00 UTC
#   Timestamp: 1768503600
#   Currency:  USD
#   Impact:    HIGH
#   Saved to:  account1/news_events.json
# ======================================================================
```

#### Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `title=`  | Yes | - | Event name |
| `time=`   | Yes | - | Event time (see formats below) |
| `currency=` | No | USD | Affected currency (USD, EUR) |
| `impact=` | No | 3 | Impact level (1=Low, 2=Medium, 3=High) |
| `at=` | No | account1 | Target account |

#### Time Formats

| Format | Example | Description |
|--------|---------|-------------|
| MM/DD/YYYY HH:MM | `01/15/2026 11:00` | Standard US format |
| YYYY-MM-DD HH:MM | `2026-01-15 11:00` | ISO format |
| tomorrow HH:MM | `tomorrow 14:30` | Tomorrow at specified time |
| today HH:MM | `today 16:00` | Today at specified time |
| +Xh | `+2h` | X hours from now |
| +Xm | `+30m` | X minutes from now |
| +Xd | `+1d` | X days from now |

**Note:** All times are interpreted as **UTC**.

#### Examples

```bash
# Political event
python3 add_news_event.py title="Trump Tariff Announcement" time="01/15/2026 14:00"

# Tomorrow's event
python3 add_news_event.py title="Fed Chair Powell Speech" time="tomorrow 18:00" impact=3

# Urgent event (2 hours from now)
python3 add_news_event.py title="Emergency Press Conference" time="+2h"

# European event
python3 add_news_event.py title="ECB President Speech" time="01/16/2026 13:00" currency=EUR

# Medium impact event
python3 add_news_event.py title="Treasury Secretary Interview" time="today 20:00" impact=2

# Add to different account
python3 add_news_event.py at=account2 title="Custom Event" time="01/17/2026 09:00"
```

#### List Events

```bash
python3 add_news_event.py list

# Output:
# ======================================================================
#   News Events in account1/news_events.json
# ======================================================================
# #    Date/Time (UTC)      Currency Impact   Title
# ----------------------------------------------------------------------
# 0    2026-01-15 05:30     USD      HIGH     Core PPI m/m
# 1    2026-01-15 05:30     USD      HIGH     Retail Sales m/m
# 2    2026-01-15 11:00     USD      HIGH     Supreme Court Tariff Ruling
# 3    2026-01-16 05:30     USD      HIGH     Unemployment Claims
# ======================================================================
#   Total: 4 events
# ======================================================================
```

#### Delete Events

```bash
# First list to see indices
python3 add_news_event.py list

# Delete by index number
python3 add_news_event.py delete=2

# Output:
#   Deleted event: Supreme Court Tariff Ruling
```

#### Workflow Example

```bash
# 1. Check current events
python3 add_news_event.py list

# 2. Add custom event for tomorrow's Supreme Court ruling
python3 add_news_event.py title="Supreme Court Tariff Decision" time="tomorrow 11:00"

# 3. Verify it was added
python3 add_news_event.py list

# 4. Bot will automatically:
#    - Close positions 10 minutes before (10:50 UTC)
#    - Block trading until 15 minutes after (11:15 UTC)
```

### pull_news_calendar.py (Fetch Official Calendar)

```bash
# Show next 14 days (default)
python3 pull_news_calendar.py

# Show next 30 days
python3 pull_news_calendar.py days=30

# Fetch from Forex Factory only
python3 pull_news_calendar.py source=ff

# Show manual events only
python3 pull_news_calendar.py source=manual

# Export to account's news_events.json
python3 pull_news_calendar.py days=14 source=ff export

# Export to specific account
python3 pull_news_calendar.py at=account2 days=14 export
```

### Output Example

```
==========================================================================================
  Economic Calendar - Next 14 Days
==========================================================================================
Date/Time (UTC)      Currency Impact   Event
------------------------------------------------------------------------------------------
2026-01-14 21:30     USD      HIGH     ** Core PPI m/m **
2026-01-14 21:30     USD      HIGH     ** Retail Sales m/m **
2026-01-15 21:30     USD      HIGH     ** Unemployment Claims **
==========================================================================================
  Total: 3 events
==========================================================================================
```

## API Reference

### NewsManager Class

**Location:** `src/news_manager.py`

```python
class NewsManager:
    def __init__(self, client, config: Dict, account: str)

    def is_enabled(self) -> bool
        """Check if news filtering is enabled."""

    def refresh_events(self, force: bool = False) -> List[NewsEvent]
        """Refresh event cache from all sources."""

    def is_news_blocked(self) -> Tuple[bool, Optional[str], Optional[NewsEvent]]
        """Check if trading should be blocked.
        Returns: (is_blocked, reason, event)
        """

    def should_close_position(self) -> Tuple[bool, Optional[str], Optional[NewsEvent]]
        """Check if positions should be closed (pre-news only).
        Returns: (should_close, reason, event)
        """

    def get_upcoming_event(self, within_minutes: int = 60) -> Optional[NewsEvent]
        """Get next event within time window."""

    def get_status(self) -> Dict
        """Get current filter status for logging."""
```

### NewsEvent Class

```python
class NewsEvent:
    title: str          # Event name
    timestamp: int      # Unix timestamp (UTC)
    currency: str       # Affected currency (USD, EUR)
    impact: int         # 1=Low, 2=Medium, 3=High
    region: str         # Geographic region (optional)
    source: str         # 'oanda', 'forexfactory', 'manual'

    @property
    def datetime(self) -> datetime
        """Event time as UTC datetime."""

    def matches_keywords(self, keywords: List[str]) -> bool
        """Check if title matches any keywords."""
```

### OANDAClient Extension

**Location:** `src/oanda_client.py`

```python
def get_calendar_events(self, instrument='EUR_USD', period=2592000) -> List[Dict]
    """Fetch events from OANDA ForexLabs API.

    Note: Currently blocked (403 Forbidden)

    Returns: List of event dicts or empty list on error
    """
```

## CSV Logging

When a position is closed due to news, it's logged with:

```csv
position_status,take_profit_hit,stop_loss_hit
NEWS_CLOSE,FALSE,FALSE
```

## Log Output Examples

### Bot Startup
```
📰 News Filter: ENABLED
   Pre-news buffer: 10 mins
   Post-news buffer: 15 mins
   Close positions before news: True
```

### Position Close (News)
```
================================================================================
📰 CLOSING POSITION for EUR_USD - NEWS EVENT
Reason: Close before news: US CPI Report in 8m
Position: LONG 50000 units
Unrealized P/L: $45.20
================================================================================
✅ Position closed successfully (news event)
   💾 Logged news close to CSV: P/L=$45.20
```

### Trade Blocked
```
📰 Trading paused: Pre-news block: US CPI Report in 8m
```

```
📰 Trade blocked by news filter: Post-news block: US CPI Report was 5m ago
```

## Troubleshooting

### No Events Showing

1. Check if `news_filter.enabled: true` in config
2. Verify events are within date range: `python3 pull_news_calendar.py source=manual`
3. Check timestamps are in UTC and in the future

### Rate Limited (429)

The tool automatically uses cached data:
```
Forex Factory rate limited - using cached data
Loaded 5 cached events (from 2026-01-14 01:54 UTC)
```

Wait a few minutes before trying again.

### Events Not Triggering Filter

Check that events match ALL criteria:
1. Impact level in `impact_levels` list
2. Currency in `currencies` list
3. Title contains keyword from `event_keywords`

### Manual Timestamp Calculation

1. Go to https://www.epochconverter.com/
2. Enter date/time in UTC (e.g., "Jan 15, 2026 13:30:00")
3. Copy Unix timestamp to `news_events.json`

## Best Practices

1. **Update events weekly:** Run `python3 pull_news_calendar.py source=ff export` each week
2. **Verify major events:** Cross-check with https://www.forexfactory.com/calendar
3. **Adjust buffers:** High-volatility events (NFP, FOMC) may need larger buffers
4. **Test before live:** Enable on practice account first
