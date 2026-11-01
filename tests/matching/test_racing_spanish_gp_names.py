"""(fork #23) Spanish Grand Prix names must reach their English-named race.

Production, 2026-11-01: ``MOTOGP EVENTO 01 | GP de Malasia 01/11 03:35`` (group
``ES| MOTOGP PPV``) failed with no_racing_match. TheSportsDB names the weekend
"Malaysia GP"; "Malasia" scored 40 against it, below the single-event floor of
50. The time could not rescue it: 03:35 Madrid is the start of the provider's
all-day feed, hours before the only Sunday session TheSportsDB lists (the race).
The racing matcher now also scores the country-translated name.
"""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from teamarr.consumers.matching.classifier import StreamCategory, classify_stream
from teamarr.consumers.matching.racing_matcher import RacingMatchContext, RacingMatcher
from teamarr.core import Event, EventStatus, RacingSession, Team, Venue


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


def _weekend(league, eid, name, sessions, country=None):
    return Event(
        id=eid,
        provider="test",
        name=name,
        short_name=name,
        start_time=sessions[0][2],
        home_team=_team(name, league),
        away_team=_team(name, league),
        status=EventStatus(state="scheduled"),
        league=league,
        sport="racing",
        venue=Venue(name=f"{name} circuit", country=country) if country else None,
        sessions=[RacingSession(code=c, name=n, start_time=t) for c, n, t in sessions],
    )


MALAYSIA = _weekend(
    "motogp",
    "motogp-my",
    "Malaysia GP",
    [
        ("sprint", "Sprint", datetime(2026, 10, 31, 7, 0, tzinfo=UTC)),
        ("race", "Race", datetime(2026, 11, 1, 7, 0, tzinfo=UTC)),
    ],
)

JAPAN = _weekend(
    "motogp",
    "motogp-jp",
    "Japan GP",
    [("race", "Race", datetime(2026, 11, 1, 5, 0, tzinfo=UTC))],
)


def _match(title, events):
    classified = classify_stream(title, "event", None, None, None)
    assert classified.category is StreamCategory.RACING_EVENT
    ctx = RacingMatchContext(
        stream_name=title,
        stream_id=1,
        group_id=1,
        target_date=datetime(2026, 11, 1).date(),
        generation=1,
        user_tz=ZoneInfo("Europe/Madrid"),
        classified=classified,
    )
    return RacingMatcher(service=None, cache=None)._match_to_event(ctx, events, "motogp")


def test_spanish_country_name_matches_single_event():
    out = _match("MOTOGP EVENTO 01 | GP de Malasia 01/11 03:35", [MALAYSIA])
    assert out.is_matched and out.event.id == "motogp-my"


def test_spanish_country_name_picks_right_event_among_two():
    # Strategy 2 (fuzzy among several): the translated name selects Malaysia.
    out = _match("MOTOGP EVENTO 01 | GP de Malasia 01/11 03:35", [JAPAN, MALAYSIA])
    assert out.is_matched and out.event.id == "motogp-my"
    out = _match("MOTOGP EVENTO 01 | GP de Japón 01/11 03:35", [MALAYSIA, JAPAN])
    assert out.is_matched and out.event.id == "motogp-jp"


def test_translated_venue_country_counts():
    # Venue-country fallback reads the translated name too.
    event = _weekend(
        "motogp",
        "motogp-x",
        "Petronas Grand Prix",
        [("race", "Race", datetime(2026, 11, 1, 7, 0, tzinfo=UTC))],
        country="Malaysia",
    )
    other = _weekend(
        "motogp",
        "motogp-y",
        "Other Grand Prix",
        [("race", "Race", datetime(2026, 11, 1, 9, 0, tzinfo=UTC))],
        country="Japan",
    )
    out = _match("MOTOGP | Malasia", [other, event])
    assert out.is_matched and out.event.id == "motogp-x"


def test_unrelated_stream_still_fails():
    # Names the series but a different country with no event this weekend.
    out = _match("MOTOGP EVENTO 01 | GP de Brasil 01/11 03:35", [MALAYSIA, JAPAN])
    assert not out.is_matched
