"""(fork) DAZN España guide titles for F1 and MotoGP must reach their race.

Production, 2026-10-31: the DAZN guide carried both races, but nothing bound.
- F1: "DIRECTO Carrera T2026 · Mundial F1 - GP de México". The fork's
  ``' - '`` matchup separator (#18a) made it "Mundial F1" vs "GP de México",
  so the racing fallback never saw a RACING_EVENT.
- MotoGP: "DIRECTO Grand Prix MotoGP T2026" names no Grand Prix ("Malaysia
  GP" scores 19), and the single-event timed path only read a time written in
  the stream name, never the programme's own broadcast instant.
"""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from teamarr.consumers.matching.classifier import StreamCategory, classify_stream
from teamarr.consumers.matching.racing_matcher import RacingMatchContext, RacingMatcher
from teamarr.core import Event, EventStatus, RacingSession, Team
from teamarr.services.detection_keywords import DetectionKeywordService
from teamarr.utilities.constants import GAME_SEPARATORS


@pytest.fixture
def dash_separator(monkeypatch):
    """Production carries the fork's ' - ' separator row (#18a)."""
    monkeypatch.setattr(DetectionKeywordService, "_separators", [" - ", *GAME_SEPARATORS])


def _team(name, league):
    return Team(
        id=name,
        provider="test",
        name=name,
        short_name=name,
        abbreviation=name[:3],
        league=league,
        sport="racing",
    )


def _weekend(league, name, sessions):
    first = sessions[0][2]
    return Event(
        id=f"{league}-1",
        provider="test",
        name=name,
        short_name=name,
        start_time=first,
        home_team=_team(name, league),
        away_team=_team(name, league),
        status=EventStatus(state="scheduled"),
        league=league,
        sport="racing",
        sessions=[RacingSession(code=c, name=n, start_time=t) for c, n, t in sessions],
    )


F1_MEXICO = _weekend(
    "f1",
    "Mexico City Grand Prix",
    [
        ("fp3", "Practice 3", datetime(2026, 10, 31, 17, 30, tzinfo=UTC)),
        ("qualifying", "Qualifying", datetime(2026, 10, 31, 21, 0, tzinfo=UTC)),
        ("race", "Race", datetime(2026, 11, 1, 20, 0, tzinfo=UTC)),
    ],
)

MOTOGP_MALAYSIA = _weekend(
    "motogp",
    "Malaysia GP",
    [
        ("sprint", "Sprint", datetime(2026, 10, 31, 7, 0, tzinfo=UTC)),
        ("race", "Race", datetime(2026, 11, 1, 7, 0, tzinfo=UTC)),
    ],
)


def _match(title, event, anchor):
    classified = classify_stream(title, "event", None, None, None)
    assert classified.category is StreamCategory.RACING_EVENT
    ctx = RacingMatchContext(
        stream_name=title,
        stream_id=1,
        group_id=1,
        target_date=anchor.date(),
        generation=1,
        user_tz=ZoneInfo("UTC"),
        classified=classified,
        anchor_dt=anchor,
    )
    return RacingMatcher(service=None, cache=None)._match_to_event(ctx, [event], event.league)


def test_dazn_f1_dash_title_classifies_racing(dash_separator):
    title = "DIRECTO Carrera T2026 · Mundial F1 - GP de México"
    assert classify_stream(title, "event", None, None, None).category is StreamCategory.RACING_EVENT
    # A football dash title stays a matchup.
    football = classify_stream("Real Madrid - Málaga", "event", None, None, None)
    assert football.category is StreamCategory.TEAM_VS_TEAM


def test_dazn_f1_race_programme_matches(dash_separator):
    out = _match(
        "DIRECTO Carrera T2026 · Mundial F1 - GP de México",
        F1_MEXICO,
        datetime(2026, 11, 1, 19, 55, tzinfo=UTC),
    )
    assert out.is_matched and out.event.id == "f1-1"


def test_dazn_motogp_race_programme_matches_on_broadcast_instant():
    out = _match(
        "DIRECTO Grand Prix MotoGP T2026",
        MOTOGP_MALAYSIA,
        datetime(2026, 11, 1, 6, 30, tzinfo=UTC),
    )
    assert out.is_matched and out.event.id == "motogp-1"


def test_motogp_title_far_from_every_session_does_not_match():
    # Same title in a replay slot hours away from any session: no binding.
    out = _match(
        "DIRECTO Grand Prix MotoGP T2026",
        MOTOGP_MALAYSIA,
        datetime(2026, 11, 1, 18, 0, tzinfo=UTC),
    )
    assert not out.is_matched
