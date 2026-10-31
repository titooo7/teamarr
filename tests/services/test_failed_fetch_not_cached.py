"""(fork) A failed provider fetch must never be cached as "no events that day".

Production, 2026-10-31 (v2.25.1 deploy): an ESPN 403 burst made the ESPN
client return None, the provider turned that into [], and the service cached
it — LaLiga and Premier League showed no games for the rest of the day, and
the past five days were cached empty for 30 days. The provider now raises
ESPNFetchError on a failed request and the service skips caching any user-day
whose buckets failed.
"""

import contextlib
from datetime import UTC, date, datetime
from unittest.mock import MagicMock

import pytest

from teamarr.core import Event, EventStatus, Team
from teamarr.providers.espn.client import ESPNFetchError
from teamarr.providers.espn.provider import ESPNProvider
from teamarr.services.sports_data import SportsDataService


class _FakeCache:
    def __init__(self):
        self.store = {}

    def get(self, key):
        return self.store.get(key)

    def set(self, key, value, ttl=None):
        self.store[key] = value

    def delete(self, key):
        self.store.pop(key, None)

    @contextlib.contextmanager
    def lock_key(self, key):
        yield


def _team(name):
    return Team(
        id=name.lower(),
        provider="fake",
        name=name,
        short_name=name,
        abbreviation=name[:3].upper(),
        league="esp.1",
        sport="soccer",
    )


def _event(event_id, start):
    return Event(
        id=event_id,
        provider="fake",
        name=f"{event_id} game",
        short_name=event_id,
        start_time=start,
        home_team=_team("Home"),
        away_team=_team("Away"),
        status=EventStatus(state="scheduled"),
        league="esp.1",
        sport="soccer",
    )


class _FlakyProvider:
    """Day-bucketed provider whose fetch fails until ``healthy`` is set."""

    def __init__(self, events):
        self.events = events
        self.healthy = False
        self.calls = 0

    @property
    def name(self):
        return "fake"

    def supports_league(self, league):
        return True

    def get_events(self, league, target_date):
        self.calls += 1
        if not self.healthy:
            raise ESPNFetchError(f"scoreboard {league} {target_date}")
        return [e for e in self.events if e.start_time.date() == target_date]


def _service(provider):
    service = SportsDataService(providers=[])
    service._cache = _FakeCache()
    service.add_provider(provider)
    return service


def test_failed_fetch_is_not_cached_and_recovers():
    game = _event("rayo-elche", datetime(2026, 10, 31, 15, 0, tzinfo=UTC))
    provider = _FlakyProvider([game])
    service = _service(provider)

    assert service.get_events("esp.1", date(2026, 10, 31)) == []
    assert not [k for k in service._cache.store if k.startswith(("events_v2:", "events_raw:"))]

    provider.healthy = True
    assert [e.id for e in service.get_events("esp.1", date(2026, 10, 31))] == ["rayo-elche"]


def test_successful_empty_day_is_still_cached():
    provider = _FlakyProvider([])
    provider.healthy = True
    service = _service(provider)

    assert service.get_events("esp.1", date(2026, 10, 31)) == []
    assert [k for k in service._cache.store if k.startswith("events_v2:")]
    calls = provider.calls
    service.get_events("esp.1", date(2026, 10, 31))
    assert provider.calls == calls  # served from cache, no refetch


@pytest.fixture
def espn(monkeypatch):
    client = MagicMock()
    provider = ESPNProvider(client=client)
    monkeypatch.setattr(provider, "_scoreboard_groups", lambda league: None)
    return provider, client


def test_espn_scoreboard_failure_raises(espn):
    provider, client = espn
    client.get_scoreboard.return_value = None
    with pytest.raises(ESPNFetchError):
        provider._get_scoreboard_events("esp.1", date(2026, 10, 31), ("soccer", "esp.1"))


def test_espn_scoreboard_with_no_events_is_empty_not_an_error(espn):
    provider, client = espn
    client.get_scoreboard.return_value = {"events": []}
    assert provider._get_scoreboard_events("esp.1", date(2026, 10, 31), ("soccer", "esp.1")) == []
