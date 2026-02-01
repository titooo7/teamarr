"""Event status utilities.

Single source of truth for determining event final status.
"""

from datetime import datetime

from teamarr.core import Event


def is_event_final(event: Event) -> bool:
    """Check if an event is final/completed.

    This is the SINGLE SOURCE OF TRUTH for final status detection.
    Use this function everywhere final status needs to be checked.

    Checks multiple indicators because different providers use different values:
    - ESPN: "final", "post" (soccer uses STATUS_FULL_TIME -> "final")
    - TSDB: "final" (from "ft", "aet", "finished")
    - HockeyTech: "final" (from "Final", "Final OT", "Final SO")
    - Cricbuzz: "final" (from "complete", "finished")

    Args:
        event: Event to check

    Returns:
        True if event is final/completed, False otherwise
    """
    if not event or not event.status:
        return False

    status_state = event.status.state.lower() if event.status.state else ""
    status_detail = event.status.detail.lower() if event.status.detail else ""

    # Check state for common final indicators
    if status_state in ("final", "post", "completed"):
        return True

    # Check detail for "final" (e.g., "Final", "Final OT", "Final - 3OT")
    if "final" in status_detail:
        return True

    return False


def find_last_completed_event(
    events: list[Event],
    before_event: Event | None = None,
    before_time: datetime | None = None,
) -> Event | None:
    """Find the most recently completed event from a list.

    This is used for .last template variable resolution to ensure we only
    show scores from games that have actually finished, not scheduled games.

    Args:
        events: List of events (should be sorted by start_time)
        before_event: If provided, only consider events before this one
        before_time: If provided, only consider events before this time

    Returns:
        The most recently completed (final) event, or None if none found
    """
    if not events:
        return None

    # Filter to events before the reference point
    candidates = []
    for event in events:
        # Skip the reference event itself
        if before_event and event.id == before_event.id:
            continue

        # Check time constraint
        if before_event and event.start_time >= before_event.start_time:
            continue
        if before_time and event.start_time >= before_time:
            continue

        # Only include completed events
        if is_event_final(event):
            candidates.append(event)

    if not candidates:
        return None

    # Return the most recent (last in sorted order)
    candidates.sort(key=lambda e: e.start_time)
    return candidates[-1]
