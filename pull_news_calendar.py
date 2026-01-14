#!/usr/bin/env python3
"""
News Calendar Fetcher
Fetches economic calendar events and displays/exports them for review.

Usage:
    python3 pull_news_calendar.py                      # Show next 14 days (default)
    python3 pull_news_calendar.py days=30             # Show next 30 days
    python3 pull_news_calendar.py days=7 export       # Export to account1/news_events.json
    python3 pull_news_calendar.py at=account2 export  # Export to specific account
    python3 pull_news_calendar.py source=ff           # Fetch from Forex Factory only
    python3 pull_news_calendar.py source=manual       # Show only manual events file
"""

# Suppress urllib3 warnings
import warnings
warnings.filterwarnings('ignore', message='urllib3')

import sys
import os
import json
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional

# Add src to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.config import OANDAConfig


# Cache directory for storing fetched events
CACHE_DIR = "backtest/data"
CACHE_FILE = f"{CACHE_DIR}/news_calendar_cache.json"


def load_cache() -> List[Dict]:
    """Load cached events from previous fetch."""
    if not os.path.exists(CACHE_FILE):
        return []
    try:
        with open(CACHE_FILE, 'r') as f:
            data = json.load(f)
        events = data.get('events', [])
        cached_time = data.get('cached_at', 'unknown')
        if events:
            print(f"  Loaded {len(events)} cached events (from {cached_time})")
        return events
    except Exception as e:
        return []


def save_cache(events: List[Dict]):
    """Save events to cache file."""
    if not events:
        return
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        cache_data = {
            'events': events,
            'cached_at': datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC'),
            'count': len(events)
        }
        with open(CACHE_FILE, 'w') as f:
            json.dump(cache_data, f, indent=2)
    except Exception as e:
        pass


# High-impact event keywords
HIGH_IMPACT_KEYWORDS = [
    'FOMC', 'Fed', 'Federal Reserve', 'Interest Rate', 'ECB', 'Bank of England', 'BOE',
    'CPI', 'Consumer Price', 'Core CPI', 'PPI', 'Producer Price', 'PCE', 'Inflation',
    'Non-Farm', 'NFP', 'Nonfarm', 'Unemployment', 'Jobless', 'Employment Change', 'ADP',
    'GDP', 'Gross Domestic', 'Retail Sales', 'ISM Manufacturing', 'ISM Services'
]


def fetch_oanda_calendar(days: int = 14) -> List[Dict]:
    """
    Fetch calendar from OANDA ForexLabs API.
    Note: This API may be blocked by Cloudflare in some regions.
    """
    try:
        OANDAConfig.set_account('account1')

        if OANDAConfig.is_practice:
            base_url = "https://api-fxpractice.oanda.com"
        else:
            base_url = "https://api-fxtrade.oanda.com"

        url = f"{base_url}/labs/v1/calendar"
        headers = OANDAConfig.get_headers()
        params = {
            'instrument': 'EUR_USD',
            'period': days * 86400  # Convert days to seconds
        }

        print(f"Fetching from OANDA ForexLabs API...")
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()

        events = response.json()
        print(f"  Fetched {len(events)} events from OANDA")
        return events

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 403:
            print(f"  OANDA Calendar API blocked (403 Forbidden)")
        else:
            print(f"  OANDA API error: {e}")
        return []
    except Exception as e:
        print(f"  Failed to fetch from OANDA: {e}")
        return []


def fetch_forexfactory_calendar(days: int = 14) -> List[Dict]:
    """
    Fetch calendar from Forex Factory XML feed.
    This is a publicly accessible feed.
    """
    import time

    try:
        print(f"Fetching from Forex Factory...")

        # Forex Factory provides weekly XML feeds
        # We'll fetch current week and next weeks as needed
        url = "https://nfs.faireconomy.media/ff_calendar_thisweek.xml"

        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Accept': 'application/xml',
            'Cache-Control': 'no-cache'
        }

        # Retry logic for rate limiting
        max_retries = 2
        for attempt in range(max_retries):
            response = requests.get(url, headers=headers, timeout=15)

            if response.status_code == 200:
                break
            elif response.status_code == 429:
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2
                    print(f"  Rate limited, waiting {wait_time}s...")
                    time.sleep(wait_time)
            else:
                print(f"  Forex Factory returned status {response.status_code}")
                return load_cache()  # Return cached data on error
        else:
            print(f"  Forex Factory rate limited - using cached data")
            return load_cache()  # Return cached data on rate limit

        events = parse_forexfactory_xml(response.text, days)

        # Also try next week's data if looking beyond 7 days
        if days > 7:
            try:
                url_next = "https://nfs.faireconomy.media/ff_calendar_nextweek.xml"
                response_next = requests.get(url_next, headers=headers, timeout=15)
                if response_next.status_code == 200:
                    events_next = parse_forexfactory_xml(response_next.text, days)
                    events.extend(events_next)
            except:
                pass

        print(f"  Fetched {len(events)} high-impact events from Forex Factory")

        # Save to cache for future rate-limit fallback
        if events:
            save_cache(events)

        return events

    except Exception as e:
        print(f"  Failed to fetch from Forex Factory: {e}")
        return load_cache()  # Return cached data on error


def parse_forexfactory_xml(xml_text: str, days: int = 14) -> List[Dict]:
    """
    Parse Forex Factory XML calendar feed.
    Returns list of high-impact events for USD/EUR.
    """
    import re
    import xml.etree.ElementTree as ET

    events = []
    now = datetime.utcnow()
    end_time = now + timedelta(days=days)

    try:
        root = ET.fromstring(xml_text)

        for event_elem in root.findall('.//event'):
            try:
                title = event_elem.find('title')
                currency = event_elem.find('country')
                impact = event_elem.find('impact')
                date_elem = event_elem.find('date')
                time_elem = event_elem.find('time')

                if title is None or currency is None or impact is None:
                    continue

                title_text = title.text or ''
                currency_text = currency.text or ''
                impact_text = (impact.text or '').lower()

                # Only high impact events
                if impact_text != 'high':
                    continue

                # Only USD and EUR
                if currency_text not in ['USD', 'EUR']:
                    continue

                # Parse date and time
                date_text = date_elem.text if date_elem is not None else ''
                time_text = time_elem.text if time_elem is not None else ''

                if not date_text:
                    continue

                # Handle "All Day" events
                if not time_text or time_text.lower() == 'all day':
                    time_text = '12:00am'

                # Parse datetime (format: "01-15-2026" and "8:30am")
                try:
                    # Clean up time format
                    time_text = time_text.replace(' ', '').lower()
                    datetime_str = f"{date_text} {time_text}"

                    # Try different formats
                    for fmt in ['%m-%d-%Y %I:%M%p', '%m-%d-%Y %H:%M']:
                        try:
                            dt = datetime.strptime(datetime_str, fmt)
                            break
                        except:
                            continue
                    else:
                        # If no format worked, try just the date
                        dt = datetime.strptime(date_text, '%m-%d-%Y')

                    # Check if within range
                    if dt < now or dt > end_time:
                        continue

                    timestamp = int(dt.timestamp())

                    events.append({
                        'title': title_text,
                        'timestamp': timestamp,
                        'currency': currency_text,
                        'impact': 3,
                        'source': 'forexfactory'
                    })

                except Exception as e:
                    continue

            except Exception as e:
                continue

    except ET.ParseError as e:
        print(f"  XML parse error: {e}")

    return events


def load_manual_events(account: str = 'account1') -> List[Dict]:
    """Load events from manual JSON file."""
    filepath = f"{account}/news_events.json"

    if not os.path.exists(filepath):
        print(f"  No manual events file found at {filepath}")
        return []

    try:
        with open(filepath, 'r') as f:
            data = json.load(f)

        events = data.get('events', [])
        # Add source marker
        for event in events:
            event['source'] = 'manual'

        print(f"  Loaded {len(events)} events from {filepath}")
        return events

    except Exception as e:
        print(f"  Failed to load manual events: {e}")
        return []


def filter_events(events: List[Dict], days: int = 14) -> List[Dict]:
    """
    Filter events to high-impact only within date range.
    """
    now = datetime.utcnow()
    end_time = now + timedelta(days=days)

    filtered = []
    for event in events:
        try:
            # Check timestamp is in range
            timestamp = event.get('timestamp', 0)
            event_time = datetime.utcfromtimestamp(timestamp)

            if now <= event_time <= end_time:
                # Check impact level
                impact = event.get('impact', 0)
                if impact >= 2:  # Medium and High impact
                    filtered.append(event)
        except:
            continue

    # Sort by timestamp
    filtered.sort(key=lambda x: x.get('timestamp', 0))
    return filtered


def display_events(events: List[Dict], title: str = "Economic Calendar"):
    """Display events in a formatted table."""
    try:
        import pytz
        pt_tz = pytz.timezone('America/Los_Angeles')
    except ImportError:
        pt_tz = None

    print("\n" + "=" * 90)
    print(f"  {title}")
    print("=" * 90)

    if not events:
        print("  No events found.")
        print("=" * 90)
        return

    # Header
    print(f"{'Date/Time (PT)':<18} {'Currency':<8} {'Impact':<8} {'Event':<50}")
    print("-" * 90)

    for event in events:
        try:
            timestamp = event.get('timestamp', 0)
            dt_utc = datetime.utcfromtimestamp(timestamp)

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
            event_title = event.get('title', 'Unknown')[:48]
            source = event.get('source', '')

            # Highlight high impact
            if impact == 3:
                print(f"{date_str:<18} {currency:<8} {impact_str:<8} ** {event_title} **")
            else:
                print(f"{date_str:<18} {currency:<8} {impact_str:<8} {event_title}")

        except Exception as e:
            continue

    print("=" * 90)
    print(f"  Total: {len(events)} events")
    print("=" * 90)


def export_events(events: List[Dict], account: str = 'account1'):
    """Export events to manual events JSON file."""
    filepath = f"{account}/news_events.json"

    # Ensure directory exists
    os.makedirs(account, exist_ok=True)

    # Prepare export data
    export_data = {
        'events': [],
        'last_updated': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
        '_generated_by': 'pull_news_calendar.py'
    }

    for event in events:
        export_event = {
            'title': event.get('title', 'Unknown'),
            'timestamp': event.get('timestamp', 0),
            'currency': event.get('currency', 'USD'),
            'impact': event.get('impact', 3)
        }
        export_data['events'].append(export_event)

    # Write to file
    with open(filepath, 'w') as f:
        json.dump(export_data, f, indent=2)

    print(f"\n  Exported {len(events)} events to {filepath}")


def generate_sample_events(days: int = 14) -> List[Dict]:
    """
    Generate sample high-impact events for demonstration.
    These are typical recurring events - user should verify actual dates!
    """
    print(f"  Generating sample events (verify dates manually!)")

    events = []
    now = datetime.utcnow()

    # Sample recurring events (dates are approximate - user must verify!)
    sample_events = [
        ("US CPI (Consumer Price Index)", "USD", 3),
        ("US Core CPI", "USD", 3),
        ("US Non-Farm Payrolls", "USD", 3),
        ("FOMC Interest Rate Decision", "USD", 3),
        ("US GDP (Quarterly)", "USD", 3),
        ("US Unemployment Rate", "USD", 3),
        ("ECB Interest Rate Decision", "EUR", 3),
        ("Eurozone CPI", "EUR", 3),
    ]

    # Add events spread over the period
    for i, (title, currency, impact) in enumerate(sample_events):
        # Spread events throughout the period
        event_time = now + timedelta(days=(i * 2) + 1, hours=13, minutes=30)
        events.append({
            'title': f"{title} (SAMPLE - VERIFY DATE!)",
            'timestamp': int(event_time.timestamp()),
            'currency': currency,
            'impact': impact,
            'source': 'sample'
        })

    return events


def main():
    """Main entry point."""
    # Parse arguments
    days = 14
    account = 'account1'
    source = 'all'  # 'oanda', 'investing', 'manual', 'sample', 'all'
    do_export = False

    for arg in sys.argv[1:]:
        if arg.startswith('days='):
            days = int(arg.split('=')[1])
        elif arg.startswith('at='):
            account = arg.split('=')[1]
        elif arg.startswith('source='):
            source = arg.split('=')[1].lower()
        elif arg == 'export':
            do_export = True

    print(f"\n{'='*60}")
    print(f"  News Calendar Fetcher")
    print(f"  Period: Next {days} days")
    print(f"  Account: {account}")
    print(f"  Source: {source}")
    print(f"{'='*60}\n")

    all_events = []

    # Fetch from sources based on selection
    if source in ['all', 'oanda']:
        oanda_events = fetch_oanda_calendar(days)
        all_events.extend(oanda_events)

    if source in ['all', 'forexfactory', 'ff']:
        ff_events = fetch_forexfactory_calendar(days)
        all_events.extend(ff_events)

    if source in ['all', 'manual']:
        manual_events = load_manual_events(account)
        all_events.extend(manual_events)

    if source == 'sample':
        sample_events = generate_sample_events(days)
        all_events.extend(sample_events)

    # If no events found, offer sample generation
    if not all_events and source == 'all':
        print("\n  No events found from any source.")
        print("  Generating sample events for demonstration...")
        all_events = generate_sample_events(days)

    # Filter and deduplicate events
    filtered_events = filter_events(all_events, days)

    # Remove duplicates based on title + timestamp
    seen = set()
    unique_events = []
    for event in filtered_events:
        key = (event.get('title', ''), event.get('timestamp', 0))
        if key not in seen:
            seen.add(key)
            unique_events.append(event)

    # Display events
    display_events(unique_events, f"Economic Calendar - Next {days} Days")

    # Export if requested
    if do_export and unique_events:
        export_events(unique_events, account)
        print(f"\n  To enable news filtering, add to {account}/config.yaml:")
        print(f"    news_filter:")
        print(f"      enabled: true")

    # Usage hint
    if not do_export:
        print(f"\n  To export these events, run:")
        print(f"    python3 pull_news_calendar.py days={days} export")

    print()


if __name__ == '__main__':
    main()
