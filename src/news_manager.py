"""
News Calendar Manager
Handles economic news event filtering for trading decisions.

Fetches events from OANDA ForexLabs Calendar API and supports
manual event imports via JSON file for backup/override.
"""

import logging
import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import pytz


class NewsEvent:
    """Represents a single economic news event."""

    def __init__(self, title: str, timestamp: int, currency: str,
                 impact: int, region: str = None, source: str = 'oanda'):
        """
        Initialize a news event.

        Args:
            title: Event name (e.g., "US CPI Report")
            timestamp: Unix timestamp of the event
            currency: Currency affected (e.g., "USD", "EUR")
            impact: Impact level (1=low, 2=medium, 3=high)
            region: Geographic region (optional)
            source: Data source ('oanda' or 'manual')
        """
        self.title = title
        self.timestamp = timestamp
        self.currency = currency
        self.impact = impact
        self.region = region
        self.source = source

    @property
    def datetime(self) -> datetime:
        """Get event time as datetime (UTC)."""
        return datetime.utcfromtimestamp(self.timestamp).replace(tzinfo=pytz.UTC)

    def matches_keywords(self, keywords: List[str]) -> bool:
        """
        Check if event title matches any of the filter keywords.

        Args:
            keywords: List of keywords to match (case-insensitive)

        Returns:
            True if any keyword found in title
        """
        if not keywords:
            return True  # No keywords = match all
        title_lower = self.title.lower()
        return any(kw.lower() in title_lower for kw in keywords)

    def __repr__(self):
        return f"NewsEvent('{self.title}', {self.datetime.strftime('%Y-%m-%d %H:%M')} UTC, {self.currency}, impact={self.impact})"

    def __str__(self):
        return f"{self.title} ({self.currency}, impact={self.impact}) at {self.datetime.strftime('%Y-%m-%d %H:%M')} UTC"


class NewsManager:
    """
    Manages economic news calendar and trading filters.

    Responsibilities:
    - Fetch events from OANDA Calendar API
    - Load manual events from JSON file
    - Cache events to avoid excessive API calls
    - Determine if trading should be paused for upcoming news
    - Provide news status for logging/display
    """

    def __init__(self, client, config: Dict, account: str):
        """
        Initialize NewsManager.

        Args:
            client: OANDAClient instance for API calls
            config: Bot configuration dict with 'news_filter' section
            account: Account name for manual events file path
        """
        self.client = client
        self.account = account
        self.logger = logging.getLogger(__name__)

        # Load config with defaults
        self.config = config.get('news_filter', {})
        self.enabled = self.config.get('enabled', False)

        # Timing buffers
        self.pre_news_buffer = timedelta(
            minutes=self.config.get('pre_news_buffer_minutes', 10)
        )
        self.post_news_buffer = timedelta(
            minutes=self.config.get('post_news_buffer_minutes', 15)
        )

        # Filtering settings
        self.impact_levels = self.config.get('impact_levels', [3])
        self.keywords = self.config.get('event_keywords', [])
        self.currencies = self.config.get('currencies', ['EUR', 'USD'])

        # OANDA calendar settings
        oanda_config = self.config.get('oanda_calendar', {})
        self.oanda_calendar_enabled = oanda_config.get('enabled', True)
        self.oanda_instrument = oanda_config.get('instrument', 'EUR_USD')
        self.oanda_period = oanda_config.get('period', 2592000)  # 30 days

        # Action settings
        self.close_before_news = self.config.get('close_positions_before_news', True)

        # Cache
        self._event_cache: List[NewsEvent] = []
        self._cache_updated: Optional[datetime] = None
        self._cache_ttl = timedelta(
            seconds=oanda_config.get('cache_ttl', 3600)  # 1 hour default
        )

        # Manual events file path
        manual_file = self.config.get('manual_events_file')
        if manual_file:
            # Support {account} placeholder in path
            self.manual_events_file = manual_file.replace('{account}', account)
        else:
            self.manual_events_file = None

        if self.enabled:
            self.logger.info(f"NewsManager initialized: pre={int(self.pre_news_buffer.total_seconds()//60)}m, "
                           f"post={int(self.post_news_buffer.total_seconds()//60)}m, "
                           f"impacts={self.impact_levels}")
            if self.manual_events_file:
                self.logger.info(f"  Manual events file: {self.manual_events_file}")

    def is_enabled(self) -> bool:
        """Check if news filtering is enabled."""
        return self.enabled

    def refresh_events(self, force: bool = False) -> List[NewsEvent]:
        """
        Refresh event cache from OANDA API and manual file.

        Args:
            force: Force refresh even if cache is valid

        Returns:
            List of NewsEvent objects
        """
        if not self.enabled:
            return []

        now = datetime.utcnow().replace(tzinfo=pytz.UTC)

        # Check if cache is still valid
        if not force and self._cache_updated:
            cache_age = now - self._cache_updated
            if cache_age < self._cache_ttl:
                return self._event_cache

        events = []

        # Fetch from OANDA Calendar API
        if self.oanda_calendar_enabled:
            oanda_events = self._fetch_oanda_events()
            events.extend(oanda_events)

        # Load manual events
        if self.manual_events_file and os.path.exists(self.manual_events_file):
            manual_events = self._load_manual_events()
            events.extend(manual_events)

        # Filter events
        filtered_events = self._filter_events(events)

        # Sort by timestamp
        filtered_events.sort(key=lambda e: e.timestamp)

        # Update cache
        self._event_cache = filtered_events
        self._cache_updated = now

        self.logger.debug(f"News cache refreshed: {len(filtered_events)} relevant events found")
        return filtered_events

    def _fetch_oanda_events(self) -> List[NewsEvent]:
        """Fetch events from OANDA Calendar API."""
        try:
            calendar_data = self.client.get_calendar_events(
                instrument=self.oanda_instrument,
                period=self.oanda_period
            )

            if not calendar_data:
                self.logger.warning("No events returned from OANDA Calendar API")
                return []

            events = []
            for item in calendar_data:
                try:
                    event = NewsEvent(
                        title=item.get('title', 'Unknown Event'),
                        timestamp=int(item.get('timestamp', 0)),
                        currency=item.get('currency', ''),
                        impact=int(item.get('impact', 0)),
                        region=item.get('region', ''),
                        source='oanda'
                    )
                    events.append(event)
                except (ValueError, TypeError) as e:
                    self.logger.warning(f"Failed to parse event: {item}, error: {e}")
                    continue

            self.logger.debug(f"Fetched {len(events)} events from OANDA Calendar")
            return events

        except Exception as e:
            self.logger.error(f"Failed to fetch OANDA calendar: {e}")
            return []

    def _load_manual_events(self) -> List[NewsEvent]:
        """Load events from manual JSON file."""
        try:
            with open(self.manual_events_file, 'r') as f:
                data = json.load(f)

            events = []
            for item in data.get('events', []):
                try:
                    event = NewsEvent(
                        title=item.get('title', 'Manual Event'),
                        timestamp=int(item.get('timestamp', 0)),
                        currency=item.get('currency', 'USD'),
                        impact=int(item.get('impact', 3)),
                        source='manual'
                    )
                    events.append(event)
                except (ValueError, TypeError) as e:
                    self.logger.warning(f"Failed to parse manual event: {item}, error: {e}")
                    continue

            self.logger.debug(f"Loaded {len(events)} manual events from {self.manual_events_file}")
            return events

        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in manual events file: {e}")
            return []
        except Exception as e:
            self.logger.error(f"Failed to load manual events: {e}")
            return []

    def _filter_events(self, events: List[NewsEvent]) -> List[NewsEvent]:
        """
        Filter events by impact, keywords, and currency.

        Args:
            events: List of raw NewsEvent objects

        Returns:
            Filtered list of events matching criteria
        """
        filtered = []
        now = datetime.utcnow().replace(tzinfo=pytz.UTC)

        for event in events:
            # Skip events in the past (beyond post-news buffer)
            event_end = event.datetime + self.post_news_buffer
            if event_end < now:
                continue

            # Filter by impact level
            if event.impact not in self.impact_levels:
                continue

            # Filter by currency
            if self.currencies and event.currency not in self.currencies:
                continue

            # Filter by keywords (if configured) - skip for manual events
            if self.keywords and event.source != 'manual' and not event.matches_keywords(self.keywords):
                continue

            filtered.append(event)

        return filtered

    def get_upcoming_event(self, within_minutes: int = 60) -> Optional[NewsEvent]:
        """
        Get the next upcoming event within the specified time window.

        Args:
            within_minutes: Look ahead window in minutes

        Returns:
            Next NewsEvent or None
        """
        if not self.enabled:
            return None

        now = datetime.utcnow().replace(tzinfo=pytz.UTC)
        window_end = now + timedelta(minutes=within_minutes)

        events = self.refresh_events()

        for event in events:
            if now <= event.datetime <= window_end:
                return event

        return None

    def is_news_blocked(self) -> Tuple[bool, Optional[str], Optional[NewsEvent]]:
        """
        Check if trading should be blocked due to upcoming or recent news.

        Returns:
            Tuple of (is_blocked, reason, event)
            - is_blocked: True if trading should be paused
            - reason: Human-readable reason string
            - event: The NewsEvent causing the block
        """
        if not self.enabled:
            return False, None, None

        now = datetime.utcnow().replace(tzinfo=pytz.UTC)
        events = self.refresh_events()

        for event in events:
            event_time = event.datetime

            # Check pre-news buffer (upcoming event)
            pre_window_start = event_time - self.pre_news_buffer
            if pre_window_start <= now < event_time:
                mins_until = int((event_time - now).total_seconds() / 60)
                reason = f"Pre-news block: {event.title} in {mins_until}m"
                return True, reason, event

            # Check post-news buffer (recent event)
            post_window_end = event_time + self.post_news_buffer
            if event_time <= now < post_window_end:
                mins_since = int((now - event_time).total_seconds() / 60)
                reason = f"Post-news block: {event.title} was {mins_since}m ago"
                return True, reason, event

        return False, None, None

    def should_close_position(self) -> Tuple[bool, Optional[str], Optional[NewsEvent]]:
        """
        Check if positions should be closed due to imminent news.
        Only returns True during the pre-news buffer window.

        Returns:
            Tuple of (should_close, reason, event)
            - should_close: True if positions should be closed
            - reason: Human-readable reason string
            - event: The NewsEvent causing the close
        """
        if not self.enabled or not self.close_before_news:
            return False, None, None

        now = datetime.utcnow().replace(tzinfo=pytz.UTC)
        events = self.refresh_events()

        for event in events:
            event_time = event.datetime

            # Only check pre-news buffer
            pre_window_start = event_time - self.pre_news_buffer
            if pre_window_start <= now < event_time:
                mins_until = int((event_time - now).total_seconds() / 60)
                reason = f"Close before news: {event.title} in {mins_until}m"
                return True, reason, event

        return False, None, None

    def get_status(self) -> Dict:
        """
        Get current news filter status for logging/display.

        Returns:
            Status dict with enabled, blocked, next_event info
        """
        if not self.enabled:
            return {
                'enabled': False,
                'is_blocked': False,
                'block_reason': None,
                'blocking_event': None,
                'next_event': None,
                'cache_age_seconds': None,
                'cached_event_count': 0
            }

        is_blocked, reason, blocking_event = self.is_news_blocked()
        next_event = self.get_upcoming_event(within_minutes=120)

        cache_age = None
        if self._cache_updated:
            cache_age = int((datetime.utcnow().replace(tzinfo=pytz.UTC) - self._cache_updated).total_seconds())

        return {
            'enabled': self.enabled,
            'is_blocked': is_blocked,
            'block_reason': reason,
            'blocking_event': str(blocking_event) if blocking_event else None,
            'next_event': str(next_event) if next_event else None,
            'cache_age_seconds': cache_age,
            'cached_event_count': len(self._event_cache)
        }

    def get_next_event_info(self) -> Optional[str]:
        """
        Get a formatted string about the next upcoming event.
        Useful for status logging.

        Returns:
            Formatted string or None if no upcoming events
        """
        event = self.get_upcoming_event(within_minutes=240)  # 4 hours
        if event:
            now = datetime.utcnow().replace(tzinfo=pytz.UTC)
            mins_until = int((event.datetime - now).total_seconds() / 60)
            if mins_until > 60:
                hours = mins_until // 60
                mins = mins_until % 60
                time_str = f"{hours}h {mins}m"
            else:
                time_str = f"{mins_until}m"
            return f"{event.title} ({event.currency}) in {time_str}"
        return None

    def get_events_during_period(self, start_time: datetime, end_time: datetime) -> List[NewsEvent]:
        """
        Get all news events that occurred during a specific time period.
        Used for logging news events that happened during a trade.

        Args:
            start_time: Start of period (timezone-aware datetime)
            end_time: End of period (timezone-aware datetime)

        Returns:
            List of NewsEvent objects that occurred during the period
        """
        # Ensure times are timezone-aware
        if start_time.tzinfo is None:
            start_time = pytz.UTC.localize(start_time)
        if end_time.tzinfo is None:
            end_time = pytz.UTC.localize(end_time)

        # Load all events (including manual events)
        events = []

        # Load manual events if configured
        if self.manual_events_file and os.path.exists(self.manual_events_file):
            events.extend(self._load_manual_events())

        # Fetch OANDA events if enabled
        if self.oanda_calendar_enabled:
            events.extend(self._fetch_oanda_events())

        # Filter events by impact and currency (but not keywords for logging purposes)
        filtered = []
        for event in events:
            # Filter by impact level
            if event.impact not in self.impact_levels:
                continue
            # Filter by currency
            if self.currencies and event.currency not in self.currencies:
                continue
            # Check if event occurred during the period
            if start_time <= event.datetime <= end_time:
                filtered.append(event)

        # Sort by timestamp
        filtered.sort(key=lambda e: e.timestamp)
        return filtered

    def format_events_for_csv(self, events: List[NewsEvent], timezone_str: str = 'US/Pacific') -> str:
        """
        Format news events for CSV column output.
        Format: {event1-name},{event1-time};{event2-name},{event2-time};...

        Args:
            events: List of NewsEvent objects
            timezone_str: Timezone for formatting times (default: Pacific)

        Returns:
            Formatted string for CSV column
        """
        if not events:
            return ''

        tz = pytz.timezone(timezone_str)
        parts = []
        for event in events:
            event_time_local = event.datetime.astimezone(tz)
            time_str = event_time_local.strftime('%Y-%m-%d %H:%M')
            parts.append(f"{event.title},{time_str}")

        return ';'.join(parts)
