"""Lifecycle-guard regression tests for separate-mode failover backups.

``is_backup`` rows must NEVER affect channel lifetime — a channel whose own
(primary) stream dies must still die even while its backups are perfectly
healthy, and a disabled group's cleanup must not be blocked by a healthy
backup sourced from elsewhere. These two guards live in
``teamarr.consumers.lifecycle.cleanup`` (see the fork's CUSTOMIZATIONS.md).

A third guard lives in ``KeywordEnforcer``: same-keyword-only backups (the
group key includes ``exception_keyword``) make it a structural no-op — a
backup's stream name always re-derives the SAME keyword as the channel it's
attached to, so it's never "misplaced".
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

GROUP_ID = 1


@pytest.fixture
def service():
    from teamarr.consumers.lifecycle.service import ChannelLifecycleService

    svc = ChannelLifecycleService(
        db_factory=MagicMock(),
        sports_service=MagicMock(),
        channel_manager=MagicMock(),
    )
    svc._remove_stream_from_dispatcharr_channel = MagicMock(return_value=True)
    svc.delete_managed_channel = MagicMock(return_value=True)
    return svc


def _channel(cid, event_id, name="Ch"):
    return SimpleNamespace(
        id=cid,
        dispatcharr_channel_id=1000 + cid,
        channel_number=cid,
        channel_name=name,
        event_id=event_id,
        primary_stream_id=None,
    )


def _stream(sid, name, *, source_group_id=GROUP_ID, is_backup=False):
    return SimpleNamespace(
        dispatcharr_stream_id=sid,
        source_group_id=source_group_id,
        stream_name=name,
        is_backup=is_backup,
    )


def _run_cleanup(service, channels, streams_by_channel, current_streams, matched=None, **kwargs):
    with (
        patch(
            "teamarr.database.channels.get_managed_channels_for_group",
            return_value=channels,
        ),
        patch(
            "teamarr.database.channels.get_channel_streams",
            side_effect=lambda conn, cid, include_removed=False: streams_by_channel.get(cid, []),
        ),
        patch("teamarr.database.channels.remove_stream_from_channel") as rm,
        patch("teamarr.database.channels.update_stream_name"),
        patch("teamarr.database.channels.log_channel_history"),
    ):
        result = service.cleanup_deleted_streams(
            GROUP_ID, current_streams, matched_streams=matched or [], **kwargs
        )
    return result, rm


# =============================================================================
# Guard 1: cleanup_deleted_streams (M3U-vanish path)
# =============================================================================


def test_channel_with_dead_primary_still_deleted_despite_healthy_backup(service):
    """Without the guard, the healthy backup makes valid_streams non-empty and
    the channel survives as a zombie pointing at a dead primary."""
    channel = _channel(7, "38659", "Team A vs Team B")
    streams = [
        _stream(100, "Primary Feed"),  # about to vanish from the M3U
        _stream(200, "Backup Feed", is_backup=True),  # perfectly healthy
    ]

    result, rm = _run_cleanup(
        service,
        channels=[channel],
        streams_by_channel={7: streams},
        current_streams={},  # primary (100) no longer in the M3U; backup (200) untouched
    )

    service.delete_managed_channel.assert_called_once()
    assert service.delete_managed_channel.call_args.args[1] == 7
    assert len(result.deleted) == 1
    # The backup itself is never even considered for removal by this path.
    rm.assert_not_called()


def test_channel_with_healthy_primary_survives_regardless_of_backup(service):
    """Sanity check the guard doesn't over-trigger: a live primary + any
    backup state must never delete the channel via this path."""
    channel = _channel(8, "38660", "Team C vs Team D")
    streams = [
        _stream(101, "Primary Feed"),
        _stream(201, "Backup Feed", is_backup=True),
    ]

    result, rm = _run_cleanup(
        service,
        channels=[channel],
        streams_by_channel={8: streams},
        current_streams={101: {"name": "Primary Feed"}},
    )

    service.delete_managed_channel.assert_not_called()
    assert result.deleted == []
    rm.assert_not_called()


def test_backup_never_flagged_missing_even_when_sourced_from_same_group(service):
    """A backup row sourced from the SAME group being scanned, and absent from
    that group's current M3U listing, must not be treated as "missing" —
    backups have their own lifecycle in separate_fallbacks.py, not this one."""
    channel = _channel(9, "38661", "Team E vs Team F")
    streams = [
        _stream(102, "Primary Feed"),
        _stream(202, "Backup Feed", source_group_id=GROUP_ID, is_backup=True),
    ]

    result, rm = _run_cleanup(
        service,
        channels=[channel],
        streams_by_channel={9: streams},
        current_streams={102: {"name": "Primary Feed"}},  # 202 absent from the pool
    )

    service.delete_managed_channel.assert_not_called()
    assert result.deleted == []
    rm.assert_not_called()  # the backup is never touched by this path


# =============================================================================
# Guard 2: cleanup_disabled_groups
# =============================================================================


def _run_disabled_groups(service, groups, channels_for_group, streams_by_channel):
    with (
        patch("teamarr.database.groups.get_all_groups", return_value=groups),
        patch(
            "teamarr.database.channels.get_managed_channels_for_group",
            side_effect=lambda conn, gid, include_deleted=False: channels_for_group.get(gid, []),
        ),
        patch(
            "teamarr.database.channels.get_channel_streams",
            side_effect=lambda conn, cid, include_removed=False: streams_by_channel.get(cid, []),
        ),
        patch("teamarr.database.channels.remove_stream_from_channel") as rm,
    ):
        result = service.cleanup_disabled_groups()
    return result, rm


def test_disabling_primarys_group_still_deletes_channel(service):
    """A healthy backup sourced from a DIFFERENT (still-enabled) group must
    not keep alive a channel whose own stream came from the disabled group."""
    from tests.fakes import FakeGroup

    channel = _channel(10, "38662", "Team G vs Team H")
    streams = [
        _stream(103, "Primary Feed", source_group_id=38),  # from the disabled group
        _stream(203, "Backup Feed", source_group_id=52, is_backup=True),  # enabled group
    ]

    result, rm = _run_disabled_groups(
        service,
        groups=[FakeGroup(id=38, name="Disabled Group", enabled=False)],
        channels_for_group={38: [channel]},
        streams_by_channel={10: streams},
    )

    # The disabled group's own stream (103) is detached...
    rm.assert_called_once()
    assert rm.call_args.args[2] == 103
    # ...and the channel is deleted despite the healthy backup, since a
    # backup never counts toward "remaining" coverage.
    service.delete_managed_channel.assert_called_once()
    assert service.delete_managed_channel.call_args.args[1] == 10


def test_backup_from_disabled_group_is_still_detached(service):
    """'Keep detaching backups sourced from that group' — is_backup does not
    exempt a stream from removal when IT is the one sourced from the group
    being disabled."""
    from tests.fakes import FakeGroup

    channel = _channel(11, "38663", "Team I vs Team J")
    streams = [
        _stream(104, "Primary Feed", source_group_id=52),  # enabled group — keeps channel alive
        _stream(204, "Backup Feed", source_group_id=38, is_backup=True),  # disabled group
    ]

    result, rm = _run_disabled_groups(
        service,
        groups=[FakeGroup(id=38, name="Disabled Group", enabled=False)],
        channels_for_group={38: [channel]},
        streams_by_channel={11: streams},
    )

    rm.assert_called_once()
    assert rm.call_args.args[2] == 204  # the backup itself was detached
    service.delete_managed_channel.assert_not_called()  # primary keeps it alive


def test_multi_group_channel_survives_with_only_backups_left(service):
    """Regular (non-backup) 'remaining' logic is untouched: a channel with no
    backups at all still behaves exactly as before."""
    from tests.fakes import FakeGroup

    channel = _channel(12, "38664", "Team K vs Team L")
    streams = [
        _stream(105, "Feed A", source_group_id=38),
        _stream(106, "Feed B", source_group_id=52),
    ]

    result, rm = _run_disabled_groups(
        service,
        groups=[FakeGroup(id=38, name="Disabled Group", enabled=False)],
        channels_for_group={38: [channel]},
        streams_by_channel={12: streams},
    )

    rm.assert_called_once()
    assert rm.call_args.args[2] == 105
    service.delete_managed_channel.assert_not_called()


# =============================================================================
# Guard 3: KeywordEnforcer no-op on separate-fallback backups
# =============================================================================


def test_keyword_enforcer_no_op_on_same_keyword_backup(db_conn, db_factory):
    """Same-keyword-only backups (the group key includes exception_keyword)
    make KeywordEnforcer a structural no-op: a backup's stream name always
    re-derives the SAME keyword as the channel it's attached to."""
    from teamarr.consumers.enforcement.keywords import KeywordEnforcer
    from teamarr.database.channels import add_stream_to_channel, create_managed_channel

    db_conn.execute(
        "UPDATE consolidation_exception_keywords SET behavior = 'separate' WHERE label = ?",
        ("Español",),
    )

    ch_id = create_managed_channel(
        db_conn,
        None,
        "evt-ke-1",
        "espn",
        "tvg-ke-1",
        "Ch KE",
        primary_stream_id=500,
        exception_keyword="Español",
        dispatcharr_channel_id=99500,
    )
    add_stream_to_channel(
        conn=db_conn,
        managed_channel_id=ch_id,
        dispatcharr_stream_id=500,
        stream_name="Team A vs Team B Español",
        priority=0,
        exception_keyword="Español",
        is_backup=0,
    )
    add_stream_to_channel(
        conn=db_conn,
        managed_channel_id=ch_id,
        dispatcharr_stream_id=501,
        stream_name="Team C vs Team D Español",
        priority=1_000_000_999,
        exception_keyword="Español",
        is_backup=1,
    )
    db_conn.commit()

    enforcer = KeywordEnforcer(db_factory, channel_manager=MagicMock())
    result = enforcer.enforce()

    assert result.streams_moved == []
    assert result.errors == []
    assert result.streams_correct == 2
