"""UFC card segment handling.

Expands UFC events into segment-based channels (Early Prelims, Prelims, Main Card).
Streams are routed to correct segment channel based on detected card_segment.

Segment timing comes from ESPN bout-level data:
- PPV events: 3 segments (early_prelims, prelims, main_card)
- Fight Night: 2 segments (prelims, main_card)
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from teamarr.consumers.matching.classifier import (
    ClassifiedStream,
    StreamCategory,
    detect_card_segment,
    is_ufc_excluded,
)
from teamarr.core.types import Event

logger = logging.getLogger(__name__)

# Display names for segment suffixes in channel names
SEGMENT_DISPLAY_NAMES: dict[str, str] = {
    "early_prelims": "Early Prelims",
    "prelims": "Prelims",
    "main_card": "",  # Main card = no suffix (default channel)
    "combined": "",  # Combined streams go to main card channel
}

# Segment codes ordered from earliest to latest
SEGMENT_ORDER = ["early_prelims", "prelims", "main_card"]


@dataclass
class SegmentInfo:
    """Information about a UFC card segment."""

    code: str  # "early_prelims", "prelims", "main_card"
    display_name: str  # "Early Prelims", "Prelims", ""
    start_time: datetime
    end_time: datetime


def is_ufc_event(event: Event | None) -> bool:
    """Check if event is a UFC/MMA event that should have segment handling."""
    if not event:
        return False
    return event.sport == "mma" and event.league == "ufc"


def get_stream_segment(stream: dict, classified: ClassifiedStream | None = None) -> str | None:
    """Get segment code for a stream.

    Args:
        stream: Stream dict with 'name' key
        classified: Optional pre-classified stream with card_segment

    Returns:
        Segment code or None if no segment detected
    """
    # Use pre-classified segment if available
    if classified and classified.card_segment:
        return classified.card_segment

    # Detect from stream name
    stream_name = stream.get("name", "")
    return detect_card_segment(stream_name)


def should_exclude_stream(stream: dict) -> bool:
    """Check if UFC stream should be excluded (weigh-in, press conference, etc.)."""
    stream_name = stream.get("name", "")
    return is_ufc_excluded(stream_name)


def get_segment_display_suffix(segment: str | None) -> str:
    """Get display suffix for channel name.

    Args:
        segment: Segment code ("early_prelims", "prelims", "main_card")

    Returns:
        Display suffix (e.g., " - Early Prelims") or empty string
    """
    if not segment:
        return ""

    display = SEGMENT_DISPLAY_NAMES.get(segment, "")
    if display:
        return f" - {display}"
    return ""


def estimate_segment_times(
    event: Event,
    segment: str,
    sport_durations: dict[str, float] | None = None,
) -> tuple[datetime, datetime]:
    """Estimate start/end times for a segment.

    Uses event.main_card_start if available, otherwise estimates.

    Args:
        event: UFC Event
        segment: Segment code
        sport_durations: Optional duration settings

    Returns:
        Tuple of (start_time, end_time)
    """
    mma_duration = (sport_durations or {}).get("mma", 5.0)

    # If event has main_card_start, use it for accurate timing
    if event.main_card_start:
        if segment == "early_prelims":
            # Early prelims: event start → prelims start
            # Estimate prelims start as 1.5 hours before main card
            prelims_start = event.main_card_start - timedelta(hours=1.5)
            return event.start_time, prelims_start

        elif segment == "prelims":
            # Prelims: 1.5 hours before main → main card start
            prelims_start = event.main_card_start - timedelta(hours=1.5)
            # If event start is later than our estimate, use event start
            if event.start_time > prelims_start:
                prelims_start = event.start_time
            return prelims_start, event.main_card_start

        else:  # main_card
            # Main card: main_card_start → end of event
            main_duration = timedelta(hours=mma_duration / 2)
            return event.main_card_start, event.main_card_start + main_duration

    # No main_card_start - estimate based on total duration
    if segment == "early_prelims":
        # First third of event
        segment_duration = timedelta(hours=mma_duration / 3)
        return event.start_time, event.start_time + segment_duration

    elif segment == "prelims":
        # Middle third of event
        segment_duration = timedelta(hours=mma_duration / 3)
        prelims_start = event.start_time + segment_duration
        return prelims_start, prelims_start + segment_duration

    else:  # main_card
        # Last third of event
        segment_duration = timedelta(hours=mma_duration / 3)
        main_start = event.start_time + 2 * segment_duration
        return main_start, main_start + segment_duration


def expand_ufc_segments(
    matched_streams: list[dict],
    sport_durations: dict[str, float] | None = None,
) -> list[dict]:
    """Expand UFC matched streams into segment-based channels.

    Groups UFC streams by detected segment and creates separate channel
    entries for each segment. Non-UFC streams pass through unchanged.

    Args:
        matched_streams: List of {'stream': ..., 'event': ...} dicts
        sport_durations: Optional sport duration settings

    Returns:
        Expanded list with UFC streams grouped by segment
    """
    result = []

    # Group UFC streams by event ID and segment
    # {event_id: {segment: [streams]}}
    ufc_by_segment: dict[str, dict[str, list[dict]]] = {}

    for match in matched_streams:
        event = match.get("event")
        stream = match.get("stream", {})

        # Non-UFC events pass through unchanged
        if not is_ufc_event(event):
            result.append(match)
            continue

        # Check for excluded streams (weigh-ins, etc.)
        if should_exclude_stream(stream):
            logger.debug(
                "[UFC_SEGMENTS] Excluding stream '%s' (non-event content)",
                stream.get("name", "")[:50],
            )
            continue

        # Detect segment from stream name
        segment = get_stream_segment(stream)

        # Default to main_card if no segment detected
        if not segment:
            segment = "main_card"

        # Combined streams go to main_card
        if segment == "combined":
            segment = "main_card"

        event_id = event.id
        if event_id not in ufc_by_segment:
            ufc_by_segment[event_id] = {}
        if segment not in ufc_by_segment[event_id]:
            ufc_by_segment[event_id][segment] = []

        ufc_by_segment[event_id][segment].append(match)

    # Create segment entries for each UFC event
    for event_id, segments in ufc_by_segment.items():
        # Get the event from any stream (they all have the same event)
        first_match = next(iter(next(iter(segments.values()))))
        event = first_match.get("event")

        # Create entry for each discovered segment
        for segment in SEGMENT_ORDER:
            if segment not in segments:
                continue

            streams_for_segment = segments[segment]
            if not streams_for_segment:
                continue

            # Calculate segment timing
            start_time, end_time = estimate_segment_times(event, segment, sport_durations)

            # Create segment entry with metadata
            for match in streams_for_segment:
                segment_match = {
                    "stream": match.get("stream"),
                    "event": event,
                    "segment": segment,
                    "segment_display": SEGMENT_DISPLAY_NAMES.get(segment, ""),
                    "segment_start": start_time,
                    "segment_end": end_time,
                }
                result.append(segment_match)

            logger.debug(
                "[UFC_SEGMENTS] Event %s segment '%s': %d streams, %s - %s",
                event_id,
                segment,
                len(streams_for_segment),
                start_time.strftime("%H:%M"),
                end_time.strftime("%H:%M"),
            )

    # Log summary
    ufc_count = sum(len(streams) for segs in ufc_by_segment.values() for streams in segs.values())
    segment_count = sum(len(segs) for segs in ufc_by_segment.values())
    if ufc_count > 0:
        logger.info(
            "[UFC_SEGMENTS] Expanded %d UFC streams into %d segment channels",
            ufc_count,
            segment_count,
        )

    return result
