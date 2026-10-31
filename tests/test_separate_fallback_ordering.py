"""Tests for the offset-aware stream-ordering reorder loop (fork feature).

``teamarr.consumers.generation._apply_stream_ordering`` is the only site that
rewrites stream priorities from ordering rules; without the offset-aware
tweak it would flatten separate-fallback backups back into the same priority
band as their channel's primary stream, breaking "primary always at slot 0".
"""

from teamarr.consumers.generation import _apply_stream_ordering
from teamarr.consumers.lifecycle.separate_fallbacks import BACKUP_PRIORITY_OFFSET
from teamarr.database.channels import (
    add_stream_to_channel,
    create_managed_channel,
    get_channel_streams,
    get_ordered_stream_ids,
)
from teamarr.database.settings.update import update_stream_ordering_rules


def _progress(*args, **kwargs):
    pass


def _make_channel_with_backup(conn, event_id, primary_id, backup_id):
    ch_id = create_managed_channel(
        conn,
        None,
        event_id,
        "espn",
        f"tvg-{event_id}",
        f"Ch {event_id}",
        primary_stream_id=primary_id,
    )
    add_stream_to_channel(
        conn=conn,
        managed_channel_id=ch_id,
        dispatcharr_stream_id=primary_id,
        stream_name="Primary Feed",
        priority=0,
        is_backup=0,
    )
    add_stream_to_channel(
        conn=conn,
        managed_channel_id=ch_id,
        dispatcharr_stream_id=backup_id,
        stream_name="Backup Feed",
        priority=0,
        is_backup=1,
    )
    conn.commit()
    return ch_id


def test_offset_applied_to_backup_but_not_primary(db_conn, db_factory):
    update_stream_ordering_rules(
        db_conn,
        [{"type": "catch_all", "value": "", "priority": 50, "mode": "priority", "points": 0}],
    )
    db_conn.commit()

    ch_id = _make_channel_with_backup(db_conn, "evt-ord-1", 700, 701)

    _apply_stream_ordering(db_factory, None, _progress)

    streams = {s.dispatcharr_stream_id: s for s in get_channel_streams(db_conn, ch_id)}
    assert streams[700].priority < BACKUP_PRIORITY_OFFSET
    assert streams[701].priority >= BACKUP_PRIORITY_OFFSET
    assert streams[701].priority == streams[700].priority + BACKUP_PRIORITY_OFFSET

    ordered = get_ordered_stream_ids(db_conn, ch_id)
    assert ordered[0] == 700


def test_offset_does_not_oscillate_across_two_runs(db_conn, db_factory):
    update_stream_ordering_rules(
        db_conn,
        [{"type": "catch_all", "value": "", "priority": 50, "mode": "priority", "points": 0}],
    )
    db_conn.commit()

    ch_id = _make_channel_with_backup(db_conn, "evt-ord-2", 710, 711)

    _apply_stream_ordering(db_factory, None, _progress)
    first = {s.dispatcharr_stream_id: s.priority for s in get_channel_streams(db_conn, ch_id)}

    result2 = _apply_stream_ordering(db_factory, None, _progress)
    second = {s.dispatcharr_stream_id: s.priority for s in get_channel_streams(db_conn, ch_id)}

    # compute_priority is memoryless (recomputed from stream fields, never
    # from the stored priority) — a regression that re-added the offset on
    # top of an already-offset value would double it here.
    assert second == first
    assert result2["streams_reordered"] == 0


def test_no_ordering_rules_still_leaves_primary_first(db_conn, db_factory):
    """No rules configured at all: the reorder loop skips priority writes
    entirely (ordering_service is None) — the default priority=0/priority>0
    from attach time must already keep the primary ahead of its backup."""
    ch_id = _make_channel_with_backup(db_conn, "evt-ord-3", 720, 721)

    result = _apply_stream_ordering(db_factory, None, _progress)

    assert result["streams_reordered"] == 0
    ordered = get_ordered_stream_ids(db_conn, ch_id)
    assert ordered[0] == 720
