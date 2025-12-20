"""Single-league stream matcher.

Uses Events → Streams approach for a single known league.
Generates patterns from events, scans stream names for matches.
Uses fuzzy matching for better tolerance of name variations.
Supports user-defined team aliases for edge cases.
"""

import logging
from dataclasses import dataclass
from datetime import date
from typing import Any, Callable

from teamarr.core import Event
from teamarr.services import SportsDataService
from teamarr.utilities.fuzzy_match import FuzzyMatcher, get_matcher

logger = logging.getLogger(__name__)


@dataclass
class MatchResult:
    """Result of a stream-to-event match."""

    stream_name: str
    event: Event | None
    league: str
    matched: bool
    exception_keyword: str | None = None
    matched_via_alias: bool = False  # True if alias was used for match

    @property
    def is_exception(self) -> bool:
        return self.exception_keyword is not None


class SingleLeagueMatcher:
    """Matches streams to events for a single known league.

    Supports user-defined team aliases that map stream text to provider team IDs.
    Aliases are checked before fuzzy matching for higher precision.
    """

    def __init__(
        self,
        service: SportsDataService,
        league: str,
        exception_keywords: list[str] | None = None,
        fuzzy_matcher: FuzzyMatcher | None = None,
        get_connection: Callable[[], Any] | None = None,
    ):
        self._service = service
        self._league = league
        self._exception_keywords = [kw.lower() for kw in (exception_keywords or [])]
        self._fuzzy = fuzzy_matcher or get_matcher()
        self._get_connection = get_connection

        # Built during match
        self._events: list[Event] = []
        self._event_patterns: list[tuple[Event, list[str], list[str], list[str]]] = []
        self._cache_date: date | None = None

        # Alias cache (loaded once per matcher instance)
        self._aliases: dict[str, tuple[str, str]] | None = None  # alias -> (team_id, team_name)

    def match(self, stream_name: str, target_date: date) -> MatchResult:
        """Match a stream name to an event in the configured league."""
        stream_lower = stream_name.lower()

        # Check for exception keyword
        for keyword in self._exception_keywords:
            if keyword in stream_lower:
                return MatchResult(
                    stream_name=stream_name,
                    event=None,
                    league=self._league,
                    matched=False,
                    exception_keyword=keyword,
                )

        # Build patterns if needed
        self._build_patterns(target_date)

        # Find matching event (may use aliases)
        event, matched_via_alias = self._find_matching_event(stream_lower)

        return MatchResult(
            stream_name=stream_name,
            event=event,
            league=self._league,
            matched=event is not None,
            matched_via_alias=matched_via_alias,
        )

    def match_batch(self, stream_names: list[str], target_date: date) -> list[MatchResult]:
        """Match multiple streams efficiently."""
        self._build_patterns(target_date)
        return [self.match(name, target_date) for name in stream_names]

    def _build_patterns(self, target_date: date) -> None:
        """Build search patterns from events using fuzzy matcher."""
        if self._cache_date == target_date:
            return

        self._events = self._service.get_events(self._league, target_date)
        self._event_patterns = []

        for event in self._events:
            # Use fuzzy matcher to generate patterns (includes mascot stripping)
            home_patterns = self._fuzzy.generate_team_patterns(event.home_team)
            away_patterns = self._fuzzy.generate_team_patterns(event.away_team)
            event_patterns = self._unique([event.name, event.short_name])
            self._event_patterns.append((event, home_patterns, away_patterns, event_patterns))

        self._cache_date = target_date

    def _unique(self, values: list[str]) -> list[str]:
        """Normalize and dedupe patterns.

        Also generates truncated patterns for names with ":"
        (e.g., "UFC Fight Night: Royval vs. Kape" -> also adds "UFC Fight Night")
        """
        seen = set()
        result = []

        for v in values:
            if not v:
                continue
            lower = v.lower()
            if lower not in seen and len(lower) >= 2:
                seen.add(lower)
                result.append(lower)

            # For names with ":", also add the prefix as a pattern
            # Handles "UFC Fight Night: Royval vs. Kape" -> "ufc fight night"
            if ":" in lower:
                prefix = lower.split(":")[0].strip()
                if prefix not in seen and len(prefix) >= 2:
                    seen.add(prefix)
                    result.append(prefix)

        return result

    def _load_aliases(self) -> None:
        """Load user-defined aliases for this league from the database."""
        if self._aliases is not None:
            return  # Already loaded

        self._aliases = {}

        if not self._get_connection:
            return

        try:
            from teamarr.database.aliases import list_aliases

            with self._get_connection() as conn:
                aliases = list_aliases(conn, league=self._league)
                for alias in aliases:
                    # Store normalized alias -> (team_id, team_name)
                    self._aliases[alias.alias.lower()] = (alias.team_id, alias.team_name)

            if self._aliases:
                logger.debug(
                    f"Loaded {len(self._aliases)} aliases for league {self._league}"
                )
        except Exception as e:
            logger.warning(f"Failed to load aliases for {self._league}: {e}")
            self._aliases = {}

    def _find_alias_team_ids(self, stream_lower: str) -> set[str]:
        """Find team IDs from aliases that appear in the stream name.

        Args:
            stream_lower: Lowercased stream name

        Returns:
            Set of team IDs found via aliases
        """
        self._load_aliases()

        found_team_ids = set()
        for alias_text, (team_id, team_name) in self._aliases.items():
            # Check if alias appears as a word in stream name
            # Use word boundary check to avoid partial matches
            if f" {alias_text} " in f" {stream_lower} ":
                found_team_ids.add(team_id)
                logger.debug(f"Alias match: '{alias_text}' -> {team_name} ({team_id})")

        return found_team_ids

    def _find_matching_event(self, stream_lower: str) -> tuple[Event | None, bool]:
        """Find event that matches the stream name.

        Returns:
            Tuple of (event, matched_via_alias)
        """
        # First, check for aliases
        alias_team_ids = self._find_alias_team_ids(stream_lower)

        # Try alias-based matching first (if we found aliases)
        if alias_team_ids:
            for event, home_patterns, away_patterns, _ in self._event_patterns:
                home_id = event.home_team.id
                away_id = event.away_team.id

                # Check if both teams match via aliases
                home_alias = home_id in alias_team_ids
                away_alias = away_id in alias_team_ids

                if home_alias and away_alias:
                    return event, True

                # Check if one team matches via alias and other via patterns
                if home_alias:
                    away_match = self._fuzzy.matches_any(away_patterns, stream_lower)
                    if away_match.matched:
                        return event, True

                if away_alias:
                    home_match = self._fuzzy.matches_any(home_patterns, stream_lower)
                    if home_match.matched:
                        return event, True

        # Standard pattern matching (need BOTH teams)
        for event, home_patterns, away_patterns, _ in self._event_patterns:
            home_match = self._fuzzy.matches_any(home_patterns, stream_lower)
            away_match = self._fuzzy.matches_any(away_patterns, stream_lower)
            if home_match.matched and away_match.matched:
                return event, False

        # Fallback: event name matching
        for event, _, _, event_patterns in self._event_patterns:
            event_match = self._fuzzy.matches_any(event_patterns, stream_lower)
            if event_match.matched:
                return event, False

        return None, False
