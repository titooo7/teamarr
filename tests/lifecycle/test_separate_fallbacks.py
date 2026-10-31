"""Tests for separate-mode failover backups (fork feature).

Full schema.sql fixture (via the shared `db_factory`/`db_conn` fixtures,
which run the real init_db path) — these are integration-style tests against
real SQLite rows, with a fake ChannelManager standing in for Dispatcharr.
"""

from types import SimpleNamespace
from unittest.mock import patch

from teamarr.consumers.lifecycle.separate_fallbacks import (
    _NO_MATCH_PRIORITY,
    BACKUP_PRIORITY_OFFSET,
    _converge_channel,
    _desired_backups,
    _eligible_groups,
    apply_separate_fallbacks,
)
from teamarr.database.channels import (
    add_stream_to_channel,
    create_managed_channel,
    get_channel_streams,
    get_managed_channel,
    get_ordered_stream_ids,
    mark_channel_deleted,
)
from teamarr.database.settings import update_channel_numbering_settings

# =============================================================================
# Fakes / helpers
# =============================================================================


class _FakeDispChannel:
    def __init__(self, channel_id, streams):
        self.id = channel_id
        self.streams = tuple(streams)


class FakeChannelManager:
    """Minimal stand-in for teamarr.dispatcharr.managers.ChannelManager.

    Tracks every update_channel call and mirrors pushed stream lists so
    get_channel reflects the latest push (needed for the phantom-purge path).
    """

    def __init__(self, channels=None, fail_ids=None):
        self._channels = {cid: list(s) for cid, s in (channels or {}).items()}
        self.fail_ids = set(fail_ids or ())
        self.update_calls: list[tuple[int, dict]] = []

    def get_channel(self, channel_id, use_cache=True):
        if channel_id not in self._channels:
            return None
        return _FakeDispChannel(channel_id, self._channels[channel_id])

    def update_channel(self, channel_id, data):
        self.update_calls.append((channel_id, dict(data)))
        if channel_id in self.fail_ids:
            return SimpleNamespace(success=False, error="boom")
        if "streams" in data:
            self._channels[channel_id] = list(data["streams"])
        return SimpleNamespace(success=True)


def _make_channel(
    conn,
    *,
    event_id,
    primary_stream_id,
    provider="espn",
    exception_keyword=None,
    feed_team_id=None,
    dispatcharr_channel_id=None,
    event_date=None,
    scheduled_delete_at=None,
    attach_at=None,
    detach_at=None,
):
    dispatcharr_channel_id = dispatcharr_channel_id or (10_000 + primary_stream_id)
    cid = create_managed_channel(
        conn,
        None,
        event_id,
        provider,
        f"tvg-{event_id}-{primary_stream_id}",
        f"Ch {primary_stream_id}",
        primary_stream_id=primary_stream_id,
        exception_keyword=exception_keyword,
        feed_team_id=feed_team_id,
        dispatcharr_channel_id=dispatcharr_channel_id,
        event_date=event_date,
        scheduled_delete_at=scheduled_delete_at,
    )
    add_stream_to_channel(
        conn=conn,
        managed_channel_id=cid,
        dispatcharr_stream_id=primary_stream_id,
        stream_name=f"Stream {primary_stream_id}",
        priority=0,
        exception_keyword=exception_keyword,
        feed_team_id=feed_team_id,
        attach_at=attach_at,
        detach_at=detach_at,
        is_backup=0,
    )
    conn.commit()
    return cid


def _enable(conn, count=3, global_mode="separate"):
    update_channel_numbering_settings(
        conn,
        global_consolidation_mode=global_mode,
        separate_fallback_enabled=True,
        separate_fallback_count=count,
    )
    conn.commit()


class FakeM3UManager:
    """Stand-in for M3UManager: the catalog knows every id except ``unknown``.

    ``known=None`` simulates a failed catalog lookup (purge nothing, #1097).
    """

    def __init__(self, unknown=(), fail=False):
        self.unknown = set(unknown)
        self.fail = fail
        self.calls: list[list[int]] = []

    def known_stream_ids(self, stream_ids):
        ids = list(stream_ids)
        self.calls.append(ids)
        if self.fail:
            return None
        return {i for i in ids if i not in self.unknown}


def _run(db_factory, fake_mgr=None, dispatcharr_client=None, fake_m3u=None):
    fake_mgr = fake_mgr if fake_mgr is not None else FakeChannelManager()
    fake_m3u = fake_m3u if fake_m3u is not None else FakeM3UManager()
    client = dispatcharr_client if dispatcharr_client is not None else object()
    with (
        patch("teamarr.dispatcharr.managers.ChannelManager", return_value=fake_mgr),
        patch("teamarr.dispatcharr.managers.M3UManager", return_value=fake_m3u),
    ):
        result = apply_separate_fallbacks(db_factory, client)
    assert result["errors"] == []
    return result, fake_mgr


def _backup_ids(conn, channel_id):
    return {s.dispatcharr_stream_id for s in get_channel_streams(conn, channel_id) if s.is_backup}


# =============================================================================
# Mutual attach / cap / isolation
# =============================================================================


def test_mutual_backup_attach(db_conn, db_factory):
    _enable(db_conn)
    ch_a = _make_channel(db_conn, event_id="evt1", primary_stream_id=1)
    ch_b = _make_channel(db_conn, event_id="evt1", primary_stream_id=2)

    result, fake_mgr = _run(db_factory)

    assert result["enabled"] is True
    assert _backup_ids(db_conn, ch_a) == {2}
    assert _backup_ids(db_conn, ch_b) == {1}

    a_backup = next(s for s in get_channel_streams(db_conn, ch_a) if s.is_backup)
    assert a_backup.priority == _NO_MATCH_PRIORITY + BACKUP_PRIORITY_OFFSET


def test_cap_selects_lowest_ids_deterministically(db_conn, db_factory):
    _enable(db_conn, count=3)
    primary = _make_channel(db_conn, event_id="evt2", primary_stream_id=100)
    sibling_ids = [201, 206, 203, 202, 205, 204]  # unsorted on purpose
    for sid in sibling_ids:
        _make_channel(db_conn, event_id="evt2", primary_stream_id=sid)

    result, _ = _run(db_factory)

    # Every channel in the 7-member group converges its own backup set
    # (mutual attach) — assert on the specific primary channel under test,
    # not the group-wide total.
    assert result["backups_added"] > 0
    assert _backup_ids(db_conn, primary) == {201, 202, 203}

    # Re-running must not reshuffle the deterministic cap selection.
    result2, fake_mgr2 = _run(db_factory)
    assert result2["backups_added"] == 0
    assert _backup_ids(db_conn, primary) == {201, 202, 203}


def test_keyword_isolation_both_ways(db_conn, db_factory):
    _enable(db_conn)
    # Per-keyword behavior wins over the global mode (creator.py:256) — the
    # seeded 'Español' keyword defaults to behavior='consolidate' (fork
    # CUSTOMIZATIONS.md #6: seeds stay 'consolidate', only a live prod DB is
    # patched to 'separate'), so flip it explicitly to exercise separate mode
    # here, exactly like the fork's real deployment does.
    db_conn.execute(
        "UPDATE consolidation_exception_keywords SET behavior = 'separate' WHERE label = ?",
        ("Español",),
    )
    db_conn.commit()
    es_a = _make_channel(
        db_conn, event_id="evt3", primary_stream_id=10, exception_keyword="Español"
    )
    es_b = _make_channel(
        db_conn, event_id="evt3", primary_stream_id=11, exception_keyword="Español"
    )
    plain_a = _make_channel(db_conn, event_id="evt3", primary_stream_id=12)
    plain_b = _make_channel(db_conn, event_id="evt3", primary_stream_id=13)

    _run(db_factory)

    assert _backup_ids(db_conn, es_a) == {11}
    assert _backup_ids(db_conn, es_b) == {10}
    assert _backup_ids(db_conn, plain_a) == {13}
    assert _backup_ids(db_conn, plain_b) == {12}


def test_feed_team_id_isolation(db_conn, db_factory):
    _enable(db_conn)
    home_a = _make_channel(db_conn, event_id="evt4", primary_stream_id=20, feed_team_id="home-team")
    home_b = _make_channel(db_conn, event_id="evt4", primary_stream_id=21, feed_team_id="home-team")
    away_a = _make_channel(db_conn, event_id="evt4", primary_stream_id=22, feed_team_id="away-team")
    away_b = _make_channel(db_conn, event_id="evt4", primary_stream_id=23, feed_team_id="away-team")

    _run(db_factory)

    assert _backup_ids(db_conn, home_a) == {21}
    assert _backup_ids(db_conn, home_b) == {20}
    assert _backup_ids(db_conn, away_a) == {23}
    assert _backup_ids(db_conn, away_b) == {22}


def test_lone_channel_ineligible(db_conn, db_factory):
    """A group with only one channel has no one to fail over to."""
    _enable(db_conn)
    solo = _make_channel(db_conn, event_id="evt5", primary_stream_id=30)

    result, _ = _run(db_factory)

    assert result["backups_added"] == 0
    assert _backup_ids(db_conn, solo) == set()


# =============================================================================
# Primary always at slot 0
# =============================================================================


def test_primary_always_at_slot_zero(db_conn, db_factory):
    _enable(db_conn, count=5)
    primary = _make_channel(db_conn, event_id="evt6", primary_stream_id=40)
    for sid in (41, 42, 43, 44, 45):
        _make_channel(db_conn, event_id="evt6", primary_stream_id=sid)

    _run(db_factory)

    ordered = get_ordered_stream_ids(db_conn, primary)
    assert ordered[0] == 40
    assert ordered[1:] == sorted(ordered[1:])  # backups keep priority order behind it


# =============================================================================
# Idempotence
# =============================================================================


def test_idempotent_second_run_pushes_nothing(db_conn, db_factory):
    _enable(db_conn)
    _make_channel(db_conn, event_id="evt7", primary_stream_id=50)
    _make_channel(db_conn, event_id="evt7", primary_stream_id=51)

    result1, fake_mgr = _run(db_factory)
    assert result1["backups_added"] == 2  # mutual: one each way

    calls_after_first = len(fake_mgr.update_calls)
    assert calls_after_first > 0

    result2, fake_mgr2 = _run(db_factory, fake_mgr=fake_mgr)
    assert result2["backups_added"] == 0
    assert result2["backups_removed"] == 0
    assert len(fake_mgr2.update_calls) == calls_after_first  # zero new Dispatcharr calls


# =============================================================================
# Convergence: cap shrink, sibling deletion, teardown
# =============================================================================


def test_convergence_on_cap_shrink(db_conn, db_factory):
    _enable(db_conn, count=3)
    primary = _make_channel(db_conn, event_id="evt8", primary_stream_id=60)
    for sid in (61, 62, 63, 64):
        _make_channel(db_conn, event_id="evt8", primary_stream_id=sid)

    _run(db_factory)
    assert len(_backup_ids(db_conn, primary)) == 3

    _enable(db_conn, count=1)
    result, fake_mgr = _run(db_factory)

    assert _backup_ids(db_conn, primary) == {61}
    assert result["backups_removed"] >= 2


def test_convergence_on_sibling_deletion(db_conn, db_factory):
    _enable(db_conn, count=3)
    primary = _make_channel(db_conn, event_id="evt9", primary_stream_id=70)
    sib_channels = {}
    for sid in (71, 72, 73):
        sib_channels[sid] = _make_channel(db_conn, event_id="evt9", primary_stream_id=sid)

    _run(db_factory)
    assert _backup_ids(db_conn, primary) == {71, 72, 73}

    # Delete the sibling that supplied stream 71.
    mark_channel_deleted(db_conn, sib_channels[71], "test")
    db_conn.commit()

    _run(db_factory)
    assert 71 not in _backup_ids(db_conn, primary)
    assert _backup_ids(db_conn, primary) == {72, 73}


def test_teardown_on_toggle_off(db_conn, db_factory):
    _enable(db_conn)
    a = _make_channel(db_conn, event_id="evt10", primary_stream_id=80)
    b = _make_channel(db_conn, event_id="evt10", primary_stream_id=81)

    _run(db_factory)
    assert _backup_ids(db_conn, a) and _backup_ids(db_conn, b)

    update_channel_numbering_settings(db_conn, separate_fallback_enabled=False)
    db_conn.commit()

    result, fake_mgr = _run(db_factory)
    assert result["enabled"] is False
    assert result["backups_torn_down"] == 2
    assert _backup_ids(db_conn, a) == set()
    assert _backup_ids(db_conn, b) == set()

    # And a further run is a true no-op (nothing left to tear down) — reuse
    # the same fake_mgr (so its cached channel state carries over) and check
    # the call count didn't grow rather than that it's empty.
    calls_before = len(fake_mgr.update_calls)
    result2, fake_mgr2 = _run(db_factory, fake_mgr=fake_mgr)
    assert result2["backups_torn_down"] == 0
    assert len(fake_mgr2.update_calls) == calls_before


# =============================================================================
# Window intersection
# =============================================================================


def test_window_both_full_life_intersects_fully(db_conn, db_factory):
    _enable(db_conn)
    a = _make_channel(db_conn, event_id="evt11", primary_stream_id=90)
    _make_channel(db_conn, event_id="evt11", primary_stream_id=91)

    _run(db_factory)

    backup = next(s for s in get_channel_streams(db_conn, a) if s.is_backup)
    assert backup.attach_at is None
    assert backup.detach_at is None


def test_window_no_overlap_excludes_candidate(db_conn, db_factory):
    _enable(db_conn)
    a = _make_channel(
        db_conn,
        event_id="evt12",
        primary_stream_id=92,
        attach_at="2026-06-01 10:00:00",
        detach_at="2026-06-01 12:00:00",
    )
    _make_channel(
        db_conn,
        event_id="evt12",
        primary_stream_id=93,
        attach_at="2026-06-01 13:00:00",
        detach_at="2026-06-01 15:00:00",
    )

    _run(db_factory)

    assert _backup_ids(db_conn, a) == set()


def test_window_partial_overlap_clamps_to_intersection(db_conn, db_factory):
    _enable(db_conn)
    a = _make_channel(
        db_conn,
        event_id="evt13",
        primary_stream_id=94,
        attach_at="2026-06-01 10:00:00",
        detach_at="2026-06-01 12:00:00",
    )
    _make_channel(
        db_conn,
        event_id="evt13",
        primary_stream_id=95,
        attach_at="2026-06-01 11:00:00",
        detach_at="2026-06-01 13:00:00",
    )

    _run(db_factory)

    backup = next(s for s in get_channel_streams(db_conn, a) if s.is_backup)
    assert backup.attach_at == "2026-06-01 11:00:00"
    assert backup.detach_at == "2026-06-01 12:00:00"


# =============================================================================
# Rollback on Dispatcharr failure
# =============================================================================


def test_rollback_on_update_channel_failure(db_conn, db_factory):
    _enable(db_conn)
    a = _make_channel(db_conn, event_id="evt14", primary_stream_id=96, dispatcharr_channel_id=50096)
    _make_channel(db_conn, event_id="evt14", primary_stream_id=97, dispatcharr_channel_id=50097)

    channel_a = get_managed_channel(db_conn, a)
    fake_mgr = FakeChannelManager(
        channels={
            channel_a.dispatcharr_channel_id: [96],
            50097: [97],
        },
        fail_ids={channel_a.dispatcharr_channel_id},
    )

    _run(db_factory, fake_mgr=fake_mgr)

    # Channel A's push failed -> its DB insert must be rolled back.
    assert _backup_ids(db_conn, a) == set()


# =============================================================================
# Internal helpers exercised directly
# =============================================================================


def test_eligible_groups_filters_non_separate_mode(db_conn):
    _make_channel(db_conn, event_id="evt15", primary_stream_id=98)
    _make_channel(db_conn, event_id="evt15", primary_stream_id=99)

    groups = _eligible_groups(db_conn, keyword_behaviors={}, global_mode="consolidate")
    assert groups == {}

    groups = _eligible_groups(db_conn, keyword_behaviors={}, global_mode="separate")
    assert len(groups) == 1


def test_converge_channel_no_op_when_nothing_current_or_desired(db_conn):
    ch_id = _make_channel(db_conn, event_id="evt16", primary_stream_id=200)
    channel = get_managed_channel(db_conn, ch_id)
    fake_mgr = FakeChannelManager()

    added, removed, pushed = _converge_channel(db_conn, fake_mgr, channel, {})
    assert (added, removed, pushed) == (0, 0, False)
    assert fake_mgr.update_calls == []


def test_desired_backups_returns_empty_without_active_primary(db_conn):
    ch_id = _make_channel(db_conn, event_id="evt17", primary_stream_id=300)
    sib_id = _make_channel(db_conn, event_id="evt17", primary_stream_id=301)

    from teamarr.database.channels import remove_stream_from_channel

    remove_stream_from_channel(db_conn, ch_id, 300, reason="test: primary gone")
    db_conn.commit()

    channel = get_managed_channel(db_conn, ch_id)
    sibling = get_managed_channel(db_conn, sib_id)
    desired = _desired_backups(db_conn, channel, [channel, sibling], cap=3)
    assert desired == {}


# =============================================================================
# v2.25.1 interactions: phantom purge (#1097), windowed rows, plugin/team scope
# =============================================================================


def test_phantom_backup_unknown_to_catalog_is_purged_not_pushed(db_conn, db_factory):
    """A backup candidate the Dispatcharr catalog does not know is purged."""
    _enable(db_conn, count=1)
    a = _make_channel(db_conn, event_id="evt30", primary_stream_id=300, dispatcharr_channel_id=5300)
    _make_channel(db_conn, event_id="evt30", primary_stream_id=301, dispatcharr_channel_id=5301)

    fake_mgr = FakeChannelManager(channels={5300: [300], 5301: [301]})
    _run(db_factory, fake_mgr=fake_mgr, fake_m3u=FakeM3UManager(unknown={301}))

    # 301 is a phantom: never reaches the push on channel A and is not kept.
    assert _backup_ids(db_conn, a) == set()
    assert all(301 not in data["streams"] for cid, data in fake_mgr.update_calls if cid == 5300)


def test_failed_catalog_lookup_purges_nothing(db_conn, db_factory):
    _enable(db_conn, count=1)
    a = _make_channel(db_conn, event_id="evt31", primary_stream_id=310, dispatcharr_channel_id=5310)
    _make_channel(db_conn, event_id="evt31", primary_stream_id=311, dispatcharr_channel_id=5311)

    fake_mgr = FakeChannelManager(channels={5310: [310], 5311: [311]})
    _run(db_factory, fake_mgr=fake_mgr, fake_m3u=FakeM3UManager(fail=True))

    assert _backup_ids(db_conn, a) == {311}
    assert fake_mgr._channels[5310] == [310, 311]


def test_windowed_backup_is_not_catalog_checked_as_phantom(db_conn, db_factory):
    """Windowed rows are held back from the purge candidates (#1097)."""
    _enable(db_conn, count=1)
    # Both primaries windowed (far future) so the backup inherits a window.
    a = _make_channel(
        db_conn,
        event_id="evt32",
        primary_stream_id=320,
        dispatcharr_channel_id=5320,
        attach_at="2099-01-01 10:00:00",
        detach_at="2099-01-01 14:00:00",
    )
    _make_channel(
        db_conn,
        event_id="evt32",
        primary_stream_id=321,
        dispatcharr_channel_id=5321,
        attach_at="2099-01-01 11:00:00",
        detach_at="2099-01-01 13:00:00",
    )

    fake_m3u = FakeM3UManager(unknown={321})
    fake_mgr = FakeChannelManager(channels={5320: [], 5321: []})
    _run(db_factory, fake_mgr=fake_mgr, fake_m3u=fake_m3u)

    # The windowed backup survives even though the (fake) catalog denies it,
    # and the catalog was never asked about it.
    backup = next(s for s in get_channel_streams(db_conn, a) if s.is_backup)
    assert backup.dispatcharr_stream_id == 321
    assert (backup.attach_at, backup.detach_at) == ("2099-01-01 11:00:00", "2099-01-01 13:00:00")
    assert all(321 not in ids for ids in fake_m3u.calls)


def test_plugin_owned_channels_are_not_eligible(db_conn):
    a = _make_channel(db_conn, event_id="evt33", primary_stream_id=330)
    _make_channel(db_conn, event_id="evt33", primary_stream_id=331)
    db_conn.execute("UPDATE managed_channels SET plugin_id = 'p' WHERE id = ?", (a,))
    db_conn.commit()

    # One core channel left in the group -> below the 2-member threshold.
    assert _eligible_groups(db_conn, {}, "separate") == {}


def test_backup_carries_keyword_evidence_and_channel_source_fields(db_conn, db_factory):
    _enable(db_conn, count=1)
    a = _make_channel(db_conn, event_id="evt34", primary_stream_id=340)
    b = _make_channel(db_conn, event_id="evt34", primary_stream_id=341)
    db_conn.execute(
        "UPDATE managed_channel_streams SET epg_program_title = 'Guide Title', m3u_group_id = 7,"
        " m3u_group_name = 'Grp', dispatcharr_source_channel_id = 99"
        " WHERE managed_channel_id = ?",
        (b,),
    )
    db_conn.commit()

    _run(db_factory)

    backup = next(s for s in get_channel_streams(db_conn, a) if s.is_backup)
    assert backup.epg_program_title == "Guide Title"
    assert (backup.m3u_group_id, backup.m3u_group_name) == (7, "Grp")
    assert backup.dispatcharr_source_channel_id == 99


def test_ordering_pass_after_fallbacks_is_a_steady_state(db_conn, db_factory):
    """End to end: fallback pass, then the real ordering pass finds nothing to do.

    The ordering pass reads Dispatcharr's order (#712) and pushes on any drift,
    so a backup priority the pass disagrees with would push every run.
    """
    from teamarr.consumers.generation import _apply_stream_ordering
    from teamarr.database.settings.update import update_stream_ordering_rules

    update_stream_ordering_rules(
        db_conn,
        [{"type": "catch_all", "value": "", "priority": 50, "mode": "priority", "points": 0}],
    )
    _enable(db_conn, count=1)
    a = _make_channel(db_conn, event_id="evt35", primary_stream_id=350, dispatcharr_channel_id=5350)
    _make_channel(db_conn, event_id="evt35", primary_stream_id=351, dispatcharr_channel_id=5351)
    db_conn.commit()

    fake_mgr = FakeChannelManager(channels={5350: [350], 5351: [351]})
    fake_mgr.get_channels = lambda: [
        _FakeDispChannel(cid, ids) for cid, ids in fake_mgr._channels.items()
    ]

    def ordering():
        with patch("teamarr.consumers.generation.ChannelManager", return_value=fake_mgr):
            return _apply_stream_ordering(db_factory, object(), lambda *a, **k: None)

    ordering()  # settle the primaries' rule priorities (the fixture stores 0)
    _run(db_factory, fake_mgr=fake_mgr)
    assert fake_mgr._channels[5350] == [350, 351]

    # The next ordering pass sees Dispatcharr exactly as fallbacks left it.
    fake_mgr.update_calls.clear()
    result = ordering()

    assert fake_mgr.update_calls == []
    assert result["order_drift_synced"] == 0
    streams = {s.dispatcharr_stream_id: s for s in get_channel_streams(db_conn, a)}
    assert streams[351].priority == streams[350].priority + BACKUP_PRIORITY_OFFSET


def test_reorder_channel_streams_keeps_backup_offset(db_conn):
    from teamarr.database.channels import reorder_channel_streams
    from teamarr.database.settings.update import update_stream_ordering_rules

    update_stream_ordering_rules(
        db_conn,
        [{"type": "catch_all", "value": "", "priority": 50, "mode": "priority", "points": 0}],
    )
    a = _make_channel(db_conn, event_id="evt36", primary_stream_id=360)
    add_stream_to_channel(
        conn=db_conn,
        managed_channel_id=a,
        dispatcharr_stream_id=361,
        stream_name="Backup",
        priority=5,
        is_backup=1,
    )
    db_conn.commit()

    reorder_channel_streams(db_conn, a)

    streams = {s.dispatcharr_stream_id: s for s in get_channel_streams(db_conn, a)}
    assert streams[361].priority == streams[360].priority + BACKUP_PRIORITY_OFFSET
    assert get_ordered_stream_ids(db_conn, a)[0] == 360
