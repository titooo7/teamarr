"""Fork customization #17: exception-keyword channels (e.g. "(Español)") sort
before the plain channel for the SAME event only.

This is the last tie-break in the global sort key
(``teamarr.database.channel_numbers.get_all_channels_sorted``), so it must
never move a channel relative to a different event's channels — every test
below that isn't purely about the tie-break itself asserts that constraint
explicitly.
"""

from __future__ import annotations

import sqlite3

import pytest

from teamarr.database.channel_numbers import get_all_channels_sorted
from teamarr.database.priority_teams import add_priority_team
from tests.helpers import SCHEMA_PATH

SCHEMA = SCHEMA_PATH


@pytest.fixture
def conn() -> sqlite3.Connection:
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript(SCHEMA.read_text())
    db.commit()
    return db


def _add_channel(
    conn, *, ch_id, event_id="ev1", sport="soccer", league="eng.1",
    home="Malaga", away="Deportivo", date="2026-08-24T21:30:00Z",
    keyword=None,
):
    conn.execute(
        """
        INSERT INTO managed_channels
        (id, event_id, event_provider, tvg_id, channel_name, sport, league,
         home_team, away_team, event_date, exception_keyword)
        VALUES (?, ?, 'espn', ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (ch_id, event_id, f"tvg{ch_id}", f"chan{ch_id}",
         sport, league, home, away, date, keyword),
    )


def test_keyword_channel_sorts_before_plain_channel(conn):
    _add_channel(conn, ch_id=1, keyword=None)
    _add_channel(conn, ch_id=2, keyword="Español")
    conn.commit()

    assert [c["id"] for c in get_all_channels_sorted(conn)] == [2, 1]


def test_multiple_keywords_sort_alphabetically_before_plain(conn):
    _add_channel(conn, ch_id=1, keyword=None)
    _add_channel(conn, ch_id=2, keyword="Portugués")
    _add_channel(conn, ch_id=3, keyword="Español")
    conn.commit()

    assert [c["id"] for c in get_all_channels_sorted(conn)] == [3, 2, 1]


def test_separate_mode_shape_keeps_keyword_block_first_and_contiguous(conn):
    # Two plain + two keyword channels for one event (fork's "separate" mode).
    _add_channel(conn, ch_id=1, keyword=None)
    _add_channel(conn, ch_id=2, keyword=None)
    _add_channel(conn, ch_id=3, keyword="Español")
    _add_channel(conn, ch_id=4, keyword="Español")
    conn.commit()

    ordered = [c["id"] for c in get_all_channels_sorted(conn)]
    assert set(ordered[:2]) == {3, 4}, "both keyword channels lead"
    assert set(ordered[2:]) == {1, 2}, "both plain channels follow"


def test_keyword_tiebreak_never_reorders_across_events_by_time(conn):
    # Earlier event is plain-only; later event has a keyword channel. The
    # earlier event must still sort entirely first — the tie-break only
    # applies within one event.
    _add_channel(conn, ch_id=1, event_id="ev-early", date="2026-08-24T12:00:00Z", keyword=None)
    _add_channel(conn, ch_id=2, event_id="ev-late", date="2026-08-24T22:00:00Z", keyword="Español")
    conn.commit()

    assert [c["id"] for c in get_all_channels_sorted(conn)] == [1, 2]


def test_keyword_tiebreak_never_overrides_league_priority(conn):
    from teamarr.database.sort_priorities import upsert_sort_priority

    # League A ranked ahead of League B; the event in League B additionally
    # has a keyword channel. League A must still lead.
    upsert_sort_priority(conn, "soccer", "eng.1", 1)
    upsert_sort_priority(conn, "soccer", "esp.1", 2)
    conn.commit()

    _add_channel(conn, ch_id=1, event_id="ev-a", league="eng.1", keyword=None)
    _add_channel(conn, ch_id=2, event_id="ev-b", league="esp.1", keyword="Español")
    conn.commit()

    assert [c["id"] for c in get_all_channels_sorted(conn)] == [1, 2]


def test_keyword_tiebreak_never_overrides_priority_team(conn):
    conn.execute(
        """
        INSERT INTO team_cache
        (team_name, provider, provider_team_id, league, sport, last_seen)
        VALUES ('Liverpool', 'espn', '364', 'eng.1', 'soccer', '2026-01-01T00:00:00Z')
        """
    )
    conn.commit()
    add_priority_team(conn, provider="espn", provider_team_id="364", league="eng.1")
    conn.commit()

    # Priority-team event is plain-only and later; the other event has a
    # keyword channel and is earlier. The priority team must still float to
    # the top, ahead of the keyword tie-break.
    _add_channel(
        conn, ch_id=1, event_id="ev-priority", home="Liverpool", away="Everton",
        date="2026-08-25T12:00:00Z", keyword=None,
    )
    _add_channel(
        conn, ch_id=2, event_id="ev-other", home="Arsenal", away="Chelsea",
        date="2026-08-24T12:00:00Z", keyword="Español",
    )
    conn.commit()

    assert [c["id"] for c in get_all_channels_sorted(conn)][0] == 1
