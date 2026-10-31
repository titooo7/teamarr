"""Separate-mode failover backups (fork-owned).

Teamarr's "Separate" consolidation mode gives each matched stream its own
channel holding exactly one stream — if that stream dies, the channel is
dead, with nothing to fail over to. This module adds an opt-in pass that
gives each separate-mode channel up to N same-exception-keyword-group
sibling streams as Dispatcharr failover backups, run once per EPG
generation (``apply_separate_fallbacks``, wired into
``teamarr.consumers.generation`` as its own stage right after the
stream-ordering stage).

Design (see the fork's CUSTOMIZATIONS.md for the full writeup):

- **Fallback pool = same exception-keyword group only.** A group is keyed by
  ``(event_id, event_provider, exception_keyword, feed_team_id)`` — the
  ``idx_mc_unique_event_v2`` tuple minus ``primary_stream_id``. No
  cross-group fallbacks: an ``(Español)`` channel only falls back to other
  ``Español`` streams, a plain channel only to other plain streams. This is
  load-bearing, not just a preference: ``KeywordEnforcer`` moves any stream
  row whose recomputed keyword differs from its channel's, so same-keyword
  backups make it a no-op — cross-group backups would get ripped off every
  channel on every run.
- **The channel's own stream always stays at slot #0.** Backups are given
  priority = the source stream's rule priority + ``BACKUP_PRIORITY_OFFSET``
  (an offset far above the maximum rule priority), so ``ORDER BY priority``
  (``get_ordered_stream_ids``) always sorts the primary first and backups
  keep their relative rule order behind it.
- **Effective mode** is re-derived exactly as
  ``teamarr.consumers.lifecycle.creator`` does when placing a stream:
  per-keyword ``behavior`` wins over the global consolidation mode. Only
  groups of >= 2 sibling channels are eligible — a lone channel has no one
  to fail over to.
- **Window intersection.** A backup's attach/detach window is clamped to the
  intersection of its own window and the *primary's* window (dropping the
  candidate if that intersection is empty) so a channel whose primary is
  currently out-of-window never pushes a lone backup as its only slot.
- **Convergence, every run.** Desired backups are diffed against the current
  ``is_backup`` rows; add/remove/window-refresh reduce every trigger (cap
  shrink, sibling deletion, mode flip, feature toggle-off) to the same
  ``desired = {}`` path — see ``_teardown_all``.
- **Push safety mirrors the consolidate path** in
  ``teamarr.consumers.lifecycle.creator`` (catalog-checked phantom purge
  (#1097), the live-event #1 pin, rollback of the DB insert on a failed
  Dispatcharr call). Steady state issues zero Dispatcharr calls — a channel is
  only fetched/pushed when it is actually being mutated.
- **Scope = event channels only.** Managed team channels (#810) live in their
  own tables and are never read here; plugin-owned channels are skipped
  (``core_only``).
- **Ordering owns the priority afterwards.** ``apply_stream_ordering``
  (``generation_pipeline/channel_steps.py``) adds ``BACKUP_PRIORITY_OFFSET`` to
  every ``is_backup`` row it re-scores, as does ``reorder_channel_streams``;
  the value written here is only the insert-time priority and converges to the
  same number on the next ordering pass, so nothing oscillates.

``is_backup`` rows must NEVER affect channel lifetime — that guard lives in
``teamarr.consumers.lifecycle.cleanup``, not here.
"""

import logging
from sqlite3 import Connection
from typing import Any

from teamarr.database.channels.types import ManagedChannel, ManagedChannelStream

logger = logging.getLogger(__name__)

# Above the maximum stream-ordering rule priority (~999_499_999) so a backup
# never outranks its channel's own (primary) stream, regardless of rules.
BACKUP_PRIORITY_OFFSET = 1_000_000_000

# Mirrors teamarr.services.stream_ordering.NO_MATCH_PRIORITY — used as the
# base priority for a backup candidate when no ordering rules are configured
# at all (compute_stream_priority_from_rules returns None in that case).
_NO_MATCH_PRIORITY = 999


def apply_separate_fallbacks(
    db_factory: Any,
    dispatcharr_client: Any | None,
) -> dict:
    """Run the separate-mode failover-backup pass across all managed channels.

    Reads ``settings.separate_fallback_enabled``/``separate_fallback_count``.
    When disabled, tears down any existing backups (feature toggle-off is
    just convergence to ``desired = {}`` for every channel that currently
    carries backups) and returns. When enabled, converges every eligible
    channel's backup set.

    Returns a summary dict (also suitable as ``GenerationResult.separate_fallbacks``).
    """
    from teamarr.database.channel_numbers import get_global_consolidation_mode
    from teamarr.database.channels import get_exception_keywords
    from teamarr.database.channels.streams import get_all_channel_streams
    from teamarr.database.settings import get_channel_numbering_settings
    from teamarr.dispatcharr.factory import DispatcharrConnection
    from teamarr.dispatcharr.managers import ChannelManager, M3UManager

    result: dict[str, Any] = {
        "enabled": False,
        "channels_converged": 0,
        "backups_added": 0,
        "backups_removed": 0,
        "backups_torn_down": 0,
        "errors": [],
    }

    try:
        with db_factory() as conn:
            settings = get_channel_numbering_settings(conn)

            channel_mgr = None
            m3u_mgr = None
            if dispatcharr_client:
                raw_client = (
                    dispatcharr_client.client
                    if isinstance(dispatcharr_client, DispatcharrConnection)
                    else dispatcharr_client
                )
                channel_mgr = ChannelManager(raw_client)
                m3u_mgr = M3UManager(raw_client)

            if not settings.separate_fallback_enabled:
                result["backups_torn_down"] = _teardown_all(conn, channel_mgr, m3u_mgr)
                conn.commit()
                return result

            result["enabled"] = True
            cap = settings.separate_fallback_count
            global_mode = get_global_consolidation_mode(conn)
            keyword_behaviors = {kw.label: kw.behavior for kw in get_exception_keywords(conn)}

            groups = _eligible_groups(conn, keyword_behaviors, global_mode)
            # One bulk read for the whole pass instead of a query per
            # (channel, sibling) pair. Only non-backup rows are read from it,
            # and converging never touches those, so it stays valid.
            streams_by_channel = get_all_channel_streams(conn)

            for _key, siblings in groups.items():
                for channel in siblings:
                    desired = _desired_backups(conn, channel, siblings, cap, streams_by_channel)
                    added, removed, _pushed = _converge_channel(
                        conn, channel_mgr, channel, desired, m3u_mgr
                    )
                    if added or removed:
                        result["channels_converged"] += 1
                        result["backups_added"] += added
                        result["backups_removed"] += removed

            conn.commit()

    except Exception as e:
        logger.exception("[SEPARATE_FALLBACK] %s", e)
        result["errors"].append({"error": str(e)})

    if result["channels_converged"] or result["backups_torn_down"]:
        logger.info(
            "[SEPARATE_FALLBACK] converged %d channel(s): +%d/-%d backups (torn_down=%d)",
            result["channels_converged"],
            result["backups_added"],
            result["backups_removed"],
            result["backups_torn_down"],
        )

    return result


def _eligible_groups(
    conn: Connection,
    keyword_behaviors: dict[str, str],
    global_mode: str,
) -> dict[tuple, list[ManagedChannel]]:
    """Group active channels by fallback-pool key, keeping only >= 2-member groups.

    Group key = ``(event_id, event_provider, exception_keyword, feed_team_id)``
    — the ``idx_mc_unique_event_v2`` tuple minus ``primary_stream_id``.
    Effective mode = per-keyword ``behavior`` if the channel carries an
    exception keyword with a configured behavior, else the global mode —
    exactly the ``effective_mode = keyword_behavior if keyword_behavior else
    duplicate_mode`` derivation in ``creator.py``. Only "separate" channels
    with at least one sibling are eligible for backups.
    """
    from teamarr.database.channels import get_all_managed_channels

    # core_only: plugin-owned channels are fed from their plan, not by us.
    # Managed team channels (#810) are not in this table at all.
    channels = get_all_managed_channels(conn, include_deleted=False, core_only=True)

    groups: dict[tuple, list[ManagedChannel]] = {}
    for ch in channels:
        kw = ch.exception_keyword or None
        effective_mode = keyword_behaviors.get(kw, global_mode) if kw else global_mode
        if effective_mode != "separate":
            continue
        key = (ch.event_id, ch.event_provider, kw, ch.feed_team_id)
        groups.setdefault(key, []).append(ch)

    return {key: members for key, members in groups.items() if len(members) >= 2}


def _intersect_window(
    a1: str | None, d1: str | None, a2: str | None, d2: str | None
) -> tuple[str | None, str | None] | None:
    """Intersect two attach/detach windows (None = unbounded on that side).

    Returns ``(attach_at, detach_at)`` for the intersection, or ``None`` if
    the intersection is empty.
    """
    lo = a1 if a2 is None else (a2 if a1 is None else max(a1, a2))
    hi = d1 if d2 is None else (d2 if d1 is None else min(d1, d2))
    if lo is not None and hi is not None and lo >= hi:
        return None
    return lo, hi


def _desired_backups(
    conn: Connection,
    channel: ManagedChannel,
    siblings: list[ManagedChannel],
    cap: int,
    streams_by_channel: dict[int, list[ManagedChannelStream]] | None = None,
) -> dict[int, dict]:
    """Compute the desired backup set for one channel within its fallback group.

    Candidates are every *other* sibling's own (non-backup) active stream —
    never another sibling's backups, which would build backup-of-backup
    chains. Candidates whose window doesn't intersect this channel's own
    primary window are dropped. The cap keeps the lowest-priority (i.e.
    highest-ranked by ordering rules) candidates, ties broken by
    ``dispatcharr_stream_id`` for determinism.
    """
    from teamarr.database.channels import compute_stream_priority_from_rules
    from teamarr.services.stream_ordering import GameContext

    if cap <= 0:
        return {}

    # Siblings share the event, so the channel's game facts (season type, local
    # broadcast) are the right "Only when" context for every candidate (#539).
    game = GameContext.from_channel(channel)

    from teamarr.database.channels import get_channel_streams

    def streams_of(channel_id: int) -> list[ManagedChannelStream]:
        if streams_by_channel is not None:
            return streams_by_channel.get(channel_id, [])
        return get_channel_streams(conn, channel_id)

    own_streams = streams_of(channel.id)
    primary_row = next((s for s in own_streams if not s.is_backup), None)
    if primary_row is None:
        # No active primary stream on this channel right now (about to be
        # cleaned up) — no backups to compute.
        return {}

    candidates: list[tuple[int, int, dict]] = []
    for sib in siblings:
        if sib.id == channel.id:
            continue

        sib_streams = streams_of(sib.id)
        sib_primary = next((s for s in sib_streams if not s.is_backup), None)
        if sib_primary is None:
            continue
        if sib_primary.dispatcharr_stream_id == primary_row.dispatcharr_stream_id:
            # Same stream is primary on multiple channels (happens today,
            # see CUSTOMIZATIONS.md) — never a backup of itself.
            continue

        window = _intersect_window(
            primary_row.attach_at,
            primary_row.detach_at,
            sib_primary.attach_at,
            sib_primary.detach_at,
        )
        if window is None:
            continue
        attach_at, detach_at = window

        rule_priority = compute_stream_priority_from_rules(
            conn,
            sib_primary.stream_name,
            sib_primary.m3u_account_name,
            sib_primary.source_group_id,
            match_type=sib_primary.match_type,
            match_method=sib_primary.match_method,
            dispatcharr_channel_group=sib_primary.dispatcharr_channel_group,
            feed_team_id=sib_primary.feed_team_id,
            feed_side=sib_primary.feed_side,
            sport=channel.sport,
            league=channel.league,
            dispatcharr_source_channel_id=sib_primary.dispatcharr_source_channel_id,
            season_type=game.season_type,
            has_local_broadcast=game.has_local_broadcast,
        )
        if rule_priority is None:
            rule_priority = _NO_MATCH_PRIORITY
        priority = rule_priority + BACKUP_PRIORITY_OFFSET

        candidates.append(
            (
                priority,
                sib_primary.dispatcharr_stream_id,
                {
                    "priority": priority,
                    "stream_name": sib_primary.stream_name,
                    "source_group_id": sib_primary.source_group_id,
                    "source_group_type": sib_primary.source_group_type,
                    "m3u_account_id": sib_primary.m3u_account_id,
                    "m3u_account_name": sib_primary.m3u_account_name,
                    "exception_keyword": sib_primary.exception_keyword,
                    "match_type": sib_primary.match_type,
                    "match_method": sib_primary.match_method,
                    "feed_team_id": sib_primary.feed_team_id,
                    "feed_side": sib_primary.feed_side,
                    "dispatcharr_channel_group": sib_primary.dispatcharr_channel_group,
                    "dispatcharr_channel_group_id": sib_primary.dispatcharr_channel_group_id,
                    "dispatcharr_source_channel_id": sib_primary.dispatcharr_source_channel_id,
                    # Keyword evidence, copied so KeywordEnforcer re-derives the
                    # sibling's keyword for the backup (a structural no-op).
                    "epg_program_title": sib_primary.epg_program_title,
                    "m3u_group_id": sib_primary.m3u_group_id,
                    "m3u_group_name": sib_primary.m3u_group_name,
                    "attach_at": attach_at,
                    "detach_at": detach_at,
                },
            )
        )

    # Deterministic cap: lowest (priority, stream_id) wins ties consistently
    # across runs.
    candidates.sort(key=lambda c: (c[0], c[1]))
    selected = candidates[:cap]
    return {stream_id: spec for _, stream_id, spec in selected}


def _converge_channel(
    conn: Connection,
    channel_mgr: Any,
    channel: ManagedChannel,
    desired: dict[int, dict],
    m3u_mgr: Any = None,
) -> tuple[int, int, bool]:
    """Diff a channel's current ``is_backup`` rows against ``desired`` and converge.

    Returns ``(added, removed, pushed)``. Issues zero Dispatcharr calls when
    nothing changed (steady state) — a channel is only fetched/pushed when it
    is actually being mutated.
    """
    from teamarr.consumers.lifecycle.timing import is_channel_event_live
    from teamarr.database.channels import (
        add_stream_to_channel,
        get_channel_streams,
        get_ordered_stream_ids,
        log_channel_history,
        remove_stream_from_channel,
        update_stream_window,
    )

    current = {
        s.dispatcharr_stream_id: s for s in get_channel_streams(conn, channel.id) if s.is_backup
    }
    to_remove = set(current) - set(desired)
    to_add = set(desired) - set(current)
    survivors = set(current) & set(desired)

    for sid in to_remove:
        remove_stream_from_channel(
            conn, channel.id, sid, reason="separate_fallback: no longer eligible"
        )

    for sid in to_add:
        spec = desired[sid]
        add_stream_to_channel(
            conn=conn,
            managed_channel_id=channel.id,
            dispatcharr_stream_id=sid,
            stream_name=spec.get("stream_name"),
            priority=spec["priority"],
            source_group_id=spec.get("source_group_id"),
            source_group_type=spec.get("source_group_type"),
            m3u_account_id=spec.get("m3u_account_id"),
            m3u_account_name=spec.get("m3u_account_name"),
            exception_keyword=spec.get("exception_keyword"),
            match_type=spec.get("match_type") or "event",
            match_method=spec.get("match_method"),
            feed_team_id=spec.get("feed_team_id"),
            feed_side=spec.get("feed_side"),
            dispatcharr_channel_group=spec.get("dispatcharr_channel_group"),
            dispatcharr_channel_group_id=spec.get("dispatcharr_channel_group_id"),
            dispatcharr_source_channel_id=spec.get("dispatcharr_source_channel_id"),
            epg_program_title=spec.get("epg_program_title"),
            m3u_group_id=spec.get("m3u_group_id"),
            m3u_group_name=spec.get("m3u_group_name"),
            attach_at=spec.get("attach_at"),
            detach_at=spec.get("detach_at"),
            is_backup=1,
        )

    for sid in survivors:
        spec = desired[sid]
        update_stream_window(conn, channel.id, sid, spec.get("attach_at"), spec.get("detach_at"))

    pushed = False
    if (to_add or to_remove) and channel_mgr and channel.dispatcharr_channel_id:
        disp_channel = channel_mgr.get_channel(channel.dispatcharr_channel_id)
        ordered_streams = get_ordered_stream_ids(conn, channel.id)

        # Purge phantom streams (#1097): a stream the Dispatcharr *catalog*
        # does not know (e.g. after an M3U re-import). Sending one gets
        # "Invalid pk" and blocks ALL updates to the channel. Mirrors
        # creator.py::_purge_phantom_streams: a stream merely missing from the
        # channel's list is not a phantom (the push below restores it), and a
        # windowed row is held back unconditionally (pending window sync).
        # Without a catalog answer nothing is purged.
        if disp_channel and m3u_mgr:
            windowed = {
                s.dispatcharr_stream_id
                for s in get_channel_streams(conn, channel.id)
                if s.attach_at is not None
            }
            candidates = [
                s for s in ordered_streams if s not in disp_channel.streams and s not in windowed
            ]
            known = m3u_mgr.known_stream_ids(candidates) if candidates else set()
            phantoms = [s for s in candidates if known is not None and s not in known]
            if phantoms:
                for pid in phantoms:
                    remove_stream_from_channel(
                        conn, channel.id, pid, reason="phantom: not in Dispatcharr"
                    )
                logger.warning(
                    "[STREAM_AUDIT] separate_fallback purged %d phantom stream(s) "
                    "from ch='%s' (db_id=%d): %s",
                    len(phantoms),
                    channel.channel_name,
                    channel.id,
                    phantoms,
                )
                ordered_streams = [s for s in ordered_streams if s not in phantoms]
                to_add = to_add - set(phantoms)

        # Live-event #1 pin (#232), mirrored from the consolidate path: the
        # priority-offset design already keeps the primary at slot #0, but
        # this guard defends that invariant defensively and, if it ever did
        # fire, would only ever name the *primary* stream — never a backup.
        if (
            len(ordered_streams) > 1
            and ordered_streams[0] != channel.primary_stream_id
            and channel.primary_stream_id in ordered_streams
            and is_channel_event_live(channel.event_date, channel.scheduled_delete_at)
        ):
            idx = ordered_streams.index(channel.primary_stream_id)
            ordered_streams[0], ordered_streams[idx] = ordered_streams[idx], ordered_streams[0]
            logger.info(
                "[STREAM_AUDIT] pin: ch='%s' live event — kept primary %d at #1 "
                "(separate_fallback)",
                channel.channel_name,
                channel.primary_stream_id,
            )

        logger.info(
            "[STREAM_AUDIT] separate_fallback sync: ch='%s' (db_id=%d, d_id=%s) "
            "added=%d removed=%d db_ordered=%s",
            channel.channel_name,
            channel.id,
            channel.dispatcharr_channel_id,
            len(to_add),
            len(to_remove),
            ordered_streams,
        )
        update_result = channel_mgr.update_channel(
            channel.dispatcharr_channel_id, {"streams": ordered_streams}
        )
        if update_result and update_result.success:
            pushed = True
        else:
            # Roll back the DB inserts so drift is retried next run — mirrors
            # the consolidate path (creator.py). Removals are left in place:
            # reconciliation catches the resulting drift and the next run's
            # convergence keeps trying.
            for sid in to_add:
                remove_stream_from_channel(conn, channel.id, sid)

    if to_add or to_remove:
        # change_source is CHECK-constrained in schema.sql to a fixed value
        # set (no "separate_fallback" member — adding one would need a real
        # migration, which this fork-owned feature deliberately avoids, see
        # the module docstring). "lifecycle" is the closest existing value;
        # the notes text carries the actual origin.
        log_channel_history(
            conn=conn,
            managed_channel_id=channel.id,
            change_type="stream_added" if to_add else "stream_removed",
            change_source="lifecycle",
            notes=f"[separate_fallback] backups: +{len(to_add)} -{len(to_remove)}",
        )

    return len(to_add), len(to_remove), pushed


def _teardown_all(conn: Connection, channel_mgr: Any, m3u_mgr: Any = None) -> int:
    """Remove every ``is_backup`` row across all channels (feature toggle-off).

    Reduces to the same ``_converge_channel(..., desired={})`` path as cap
    shrink / sibling deletion / mode flip. Costs one indexed query that
    returns nothing in the steady off state.

    Returns the total number of backup rows removed.
    """
    from teamarr.database.channels import get_managed_channel

    rows = conn.execute(
        "SELECT DISTINCT managed_channel_id FROM managed_channel_streams "
        "WHERE is_backup = 1 AND removed_at IS NULL"
    ).fetchall()

    removed_total = 0
    for row in rows:
        channel = get_managed_channel(conn, row[0])
        if channel is None:
            continue
        _added, removed, _pushed = _converge_channel(conn, channel_mgr, channel, {}, m3u_mgr)
        removed_total += removed

    return removed_total
