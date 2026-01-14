#!/usr/bin/env python3
"""
Add Custom News Event
Manually add a news event to the calendar (for events not in official calendars).

Usage:
    python3 add_news_event.py title="Supreme Court Tariff Ruling" time="01/15/2026 11:00"
    python3 add_news_event.py title="Fed Chair Speech" time="tomorrow 14:30" currency=USD impact=3
    python3 add_news_event.py title="ECB Press Conference" time="2026-01-20 13:45" currency=EUR
    python3 add_news_event.py at=account2 title="Custom Event" time="01/16/2026 09:00"
    python3 add_news_event.py list                    # List all events
    python3 add_news_event.py delete=2               # Delete event at index 2

Time formats supported:
    - "MM/DD/YYYY HH:MM"      e.g., "01/15/2026 11:00"
    - "YYYY-MM-DD HH:MM"      e.g., "2026-01-15 11:00"
    - "tomorrow HH:MM"        e.g., "tomorrow 14:30"
    - "today HH:MM"           e.g., "today 16:00"
    - "+Xh" or "+Xm"          e.g., "+2h" (2 hours from now), "+30m" (30 minutes)

All times are interpreted as UTC.
"""

import sys
import os
import json
import re
import calendar
from datetime import datetime, timedelta

# Suppress warnings
import warnings
warnings.filterwarnings('ignore')


def parse_time(time_str: str) -> datetime:
    """
    Parse various time formats into a datetime object (UTC).

    Supported formats:
    - "MM/DD/YYYY HH:MM"
    - "YYYY-MM-DD HH:MM"
    - "tomorrow HH:MM"
    - "today HH:MM"
    - "+Xh" or "+Xm" (relative time)
    """
    time_str = time_str.strip()
    now = datetime.utcnow()

    # Relative time: +2h, +30m, +1d
    relative_match = re.match(r'\+(\d+)([hdm])', time_str.lower())
    if relative_match:
        amount = int(relative_match.group(1))
        unit = relative_match.group(2)
        if unit == 'h':
            return now + timedelta(hours=amount)
        elif unit == 'm':
            return now + timedelta(minutes=amount)
        elif unit == 'd':
            return now + timedelta(days=amount)

    # "tomorrow HH:MM" or "today HH:MM"
    if time_str.lower().startswith('tomorrow'):
        time_part = time_str[8:].strip()
        base_date = now + timedelta(days=1)
        try:
            hour, minute = map(int, time_part.split(':'))
            return base_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
        except:
            raise ValueError(f"Invalid time format: {time_str}. Use 'tomorrow HH:MM'")

    if time_str.lower().startswith('today'):
        time_part = time_str[5:].strip()
        base_date = now
        try:
            hour, minute = map(int, time_part.split(':'))
            return base_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
        except:
            raise ValueError(f"Invalid time format: {time_str}. Use 'today HH:MM'")

    # Standard formats
    formats = [
        "%m/%d/%Y %H:%M",      # 01/15/2026 11:00
        "%Y-%m-%d %H:%M",      # 2026-01-15 11:00
        "%m/%d/%Y %H:%M:%S",   # 01/15/2026 11:00:00
        "%Y-%m-%d %H:%M:%S",   # 2026-01-15 11:00:00
        "%m-%d-%Y %H:%M",      # 01-15-2026 11:00
        "%d/%m/%Y %H:%M",      # 15/01/2026 11:00 (European)
    ]

    for fmt in formats:
        try:
            return datetime.strptime(time_str, fmt)
        except ValueError:
            continue

    raise ValueError(f"Could not parse time: '{time_str}'\n"
                    f"Supported formats:\n"
                    f"  - MM/DD/YYYY HH:MM (e.g., 01/15/2026 11:00)\n"
                    f"  - YYYY-MM-DD HH:MM (e.g., 2026-01-15 11:00)\n"
                    f"  - tomorrow HH:MM (e.g., tomorrow 14:30)\n"
                    f"  - today HH:MM (e.g., today 16:00)\n"
                    f"  - +Xh or +Xm (e.g., +2h, +30m)")


def load_events(filepath: str) -> dict:
    """Load existing events from JSON file."""
    if not os.path.exists(filepath):
        return {"events": [], "last_updated": None}

    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except:
        return {"events": [], "last_updated": None}


def save_events(filepath: str, data: dict):
    """Save events to JSON file."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    data['last_updated'] = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)


def list_events(filepath: str):
    """Display all events in the calendar."""
    try:
        import pytz
        pt_tz = pytz.timezone('America/Los_Angeles')
    except ImportError:
        pt_tz = None

    data = load_events(filepath)
    events = data.get('events', [])

    print(f"\n{'='*80}")
    print(f"  News Events in {filepath}")
    print(f"{'='*80}")

    if not events:
        print("  No events found.")
        print(f"{'='*80}\n")
        return

    print(f"{'#':<4} {'Date/Time (PT)':<18} {'Currency':<8} {'Impact':<8} {'Title'}")
    print(f"{'-'*80}")

    now = datetime.utcnow()
    for i, event in enumerate(events):
        try:
            ts = event.get('timestamp', 0)
            dt_utc = datetime.utcfromtimestamp(ts)

            # Convert to Pacific Time
            if pt_tz:
                import pytz
                dt_utc_tz = dt_utc.replace(tzinfo=pytz.UTC)
                dt_pt = dt_utc_tz.astimezone(pt_tz)
                date_str = dt_pt.strftime('%m/%d %H:%M PT')
            else:
                date_str = dt_utc.strftime('%Y-%m-%d %H:%M')

            currency = event.get('currency', 'N/A')
            impact = event.get('impact', 0)
            impact_str = ['', 'Low', 'Med', 'HIGH'][min(impact, 3)]
            title = event.get('title', 'Unknown')[:40]

            # Mark past events
            status = " (PAST)" if dt_utc < now else ""

            print(f"{i:<4} {date_str:<18} {currency:<8} {impact_str:<8} {title}{status}")
        except:
            continue

    print(f"{'='*80}")
    print(f"  Total: {len(events)} events")
    print(f"{'='*80}\n")


def add_event(filepath: str, title: str, time_str: str, currency: str = 'USD', impact: int = 3):
    """Add a new event to the calendar."""
    # Parse time
    try:
        dt = parse_time(time_str)
    except ValueError as e:
        print(f"\n  ERROR: {e}\n")
        return False

    # Use calendar.timegm() since dt is in UTC (from datetime.utcnow())
    # .timestamp() would incorrectly interpret naive datetime as local time
    timestamp = int(calendar.timegm(dt.timetuple()))

    # Load existing events
    data = load_events(filepath)

    # Create new event
    new_event = {
        'title': title,
        'timestamp': timestamp,
        'currency': currency.upper(),
        'impact': impact,
        'source': 'manual'
    }

    # Add to list
    data['events'].append(new_event)

    # Sort by timestamp
    data['events'].sort(key=lambda x: x.get('timestamp', 0))

    # Save
    save_events(filepath, data)

    # Convert to Pacific Time for display
    try:
        import pytz
        pt_tz = pytz.timezone('America/Los_Angeles')
        dt_utc = dt.replace(tzinfo=pytz.UTC)
        dt_pt = dt_utc.astimezone(pt_tz)
        time_str_pt = dt_pt.strftime('%m/%d/%Y %H:%M PT')
    except ImportError:
        time_str_pt = dt.strftime('%Y-%m-%d %H:%M') + ' UTC'

    print(f"\n{'='*70}")
    print(f"  Event Added Successfully!")
    print(f"{'='*70}")
    print(f"  Title:     {title}")
    print(f"  Time:      {time_str_pt}")
    print(f"  Currency:  {currency.upper()}")
    print(f"  Impact:    {['', 'Low', 'Medium', 'HIGH'][min(impact, 3)]}")
    print(f"  Saved to:  {filepath}")
    print(f"{'='*70}\n")

    return True


def delete_event(filepath: str, index: int):
    """Delete an event by index."""
    data = load_events(filepath)
    events = data.get('events', [])

    if index < 0 or index >= len(events):
        print(f"\n  ERROR: Invalid index {index}. Use 'list' to see event indices.\n")
        return False

    removed = events.pop(index)
    save_events(filepath, data)

    print(f"\n  Deleted event: {removed.get('title', 'Unknown')}\n")
    return True


def print_usage():
    """Print usage instructions."""
    print("""
Usage:
    python3 add_news_event.py title="Event Name" time="MM/DD/YYYY HH:MM"

Required:
    title=     Event title (e.g., "Supreme Court Tariff Ruling")
    time=      Event time in UTC (see formats below)

Optional:
    currency=  Currency affected (default: USD)
    impact=    Impact level 1-3 (default: 3 = HIGH)
    at=        Account name (default: account1)

Time formats:
    "01/15/2026 11:00"     MM/DD/YYYY HH:MM
    "2026-01-15 11:00"     YYYY-MM-DD HH:MM
    "tomorrow 14:30"       Tomorrow at specified time
    "today 16:00"          Today at specified time
    "+2h"                  2 hours from now
    "+30m"                 30 minutes from now

Commands:
    list                   Show all events
    delete=N               Delete event at index N

Examples:
    python3 add_news_event.py title="Supreme Court Tariff Ruling" time="01/15/2026 11:00"
    python3 add_news_event.py title="Fed Chair Speech" time="tomorrow 14:30" impact=3
    python3 add_news_event.py title="ECB Meeting" time="+2h" currency=EUR
    python3 add_news_event.py list
    python3 add_news_event.py delete=0
""")


def main():
    # Parse arguments
    account = 'account1'
    title = None
    time_str = None
    currency = 'USD'
    impact = 3
    action = 'add'
    delete_index = None

    for arg in sys.argv[1:]:
        if arg.startswith('at='):
            account = arg.split('=', 1)[1]
        elif arg.startswith('title='):
            title = arg.split('=', 1)[1]
        elif arg.startswith('time='):
            time_str = arg.split('=', 1)[1]
        elif arg.startswith('currency='):
            currency = arg.split('=', 1)[1]
        elif arg.startswith('impact='):
            impact = int(arg.split('=', 1)[1])
        elif arg == 'list':
            action = 'list'
        elif arg.startswith('delete='):
            action = 'delete'
            delete_index = int(arg.split('=', 1)[1])
        elif arg in ['-h', '--help', 'help']:
            print_usage()
            return

    filepath = f"{account}/news_events.json"

    # Execute action
    if action == 'list':
        list_events(filepath)
    elif action == 'delete':
        if delete_index is not None:
            delete_event(filepath, delete_index)
        else:
            print("\n  ERROR: Please specify index to delete (e.g., delete=0)\n")
    elif action == 'add':
        if not title or not time_str:
            print("\n  ERROR: Both 'title=' and 'time=' are required.\n")
            print_usage()
            return
        add_event(filepath, title, time_str, currency, impact)


if __name__ == '__main__':
    main()
