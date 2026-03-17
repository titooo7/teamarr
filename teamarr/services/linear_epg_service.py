"""Linear EPG Discovery Service.

Handles daily pre-filtering of linear channel schedules from external XMLTV sources.
Populates linear_epg_cache for fast discovery during EPG generation.
"""

import logging
import sqlite3
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import requests
from dateutil import parser

from teamarr.utilities.constants import TEAM_ALIASES

logger = logging.getLogger(__name__)

class LinearEpgService:
    """Service for monitoring linear channels via Dispatcharr EPG."""

    def __init__(self, db_factory=None):
        from teamarr.database import get_db
        self.db_factory = db_factory or get_db

    def _get_connection(self):
        return self.db_factory()

    def _apply_team_aliases(self, text: str) -> str:
        """Apply TEAM_ALIASES to expand shortened team names before matching.

        This improves fuzzy matching scores by expanding common abbreviations.
        E.g., "PAOK - Celta" → "PAOK Salonika PAOK - Celta Vigo Celta"

        Args:
            text: The EPG title or subtitle to expand

        Returns:
            Text with team aliases appended for better fuzzy matching
        """
        if not text:
            return text

        words = text.lower().split()
        expanded = []

        for word in words:
            # Always include the original word
            expanded.append(word)
            # Also add the canonical name if there's an alias match
            canonical = TEAM_ALIASES.get(word)
            if canonical:
                expanded.append(canonical)

        return ' '.join(expanded)

    def refresh_cache(self):
        """Perform refresh of all linear channels from Dispatcharr."""
        from teamarr.dispatcharr import get_dispatcharr_connection
        from teamarr.database.settings import get_dispatcharr_settings

        with self._get_connection() as conn:
            settings = get_dispatcharr_settings(conn)
            if not settings.enabled or not settings.url:
                logger.info("[LINEAR_EPG] Dispatcharr not configured. Skipping.")
                return

            dispatcharr = get_dispatcharr_connection(self.db_factory)
            if not dispatcharr:
                logger.warning("[LINEAR_EPG] Could not connect to Dispatcharr.")
                return

            logger.info("[LINEAR_EPG] Fetching channels from Dispatcharr...")
            all_channels = dispatcharr.channels.get_channels()
            
            # Map tvg_id -> list[channel_id] (for final storage)
            tvg_id_map: Dict[str, List[int]] = {}
            # Map XML channel ID -> tvg_id (for XML parsing)
            # Dispatcharr uses channel_number as XML ID in /output/epg
            xml_id_to_tvg_map: Dict[str, str] = {}
            
            for ch in all_channels:
                if ch.tvg_id:
                    if ch.tvg_id not in tvg_id_map:
                        tvg_id_map[ch.tvg_id] = []
                    tvg_id_map[ch.tvg_id].append(ch.id)
                    
                    # Store both internal ID and channel number as potential XML IDs
                    xml_id_to_tvg_map[str(ch.id)] = ch.tvg_id
                    if ch.channel_number is not None:
                        # Some APIs return channel_number as float or string float, convert properly
                        try:
                            num_str = str(int(float(ch.channel_number)))
                            xml_id_to_tvg_map[num_str] = ch.tvg_id
                        except (ValueError, TypeError):
                            xml_id_to_tvg_map[str(ch.channel_number)] = ch.tvg_id

            logger.info(f"[LINEAR_EPG] Built mapping for {len(xml_id_to_tvg_map)} potential XML IDs")
            if xml_id_to_tvg_map:
                # Log first 5 for debugging
                sample = list(xml_id_to_tvg_map.items())[:5]
                logger.info(f"[LINEAR_EPG] Sample mappings: {sample}")

            if not tvg_id_map:
                logger.info("[LINEAR_EPG] No channels with tvg_id found in Dispatcharr.")
                return

            # Construct XMLTV path (standard Dispatcharr endpoint)
            xmltv_path = "/output/epg"
            
            # Use discovery_channels filter if configured
            discovery_filter = settings.discovery_channels
            
            try:
                self._process_dispatcharr_xmltv(conn, dispatcharr, xmltv_path, tvg_id_map, xml_id_to_tvg_map, discovery_filter)
            except Exception as e:
                logger.error(f"[LINEAR_EPG] Failed to process Dispatcharr XMLTV at {xmltv_path}: {e}")
                
                # Fallback to legacy /xmltv.php if /output/epg failed
                legacy_path = "/xmltv.php"
                logger.info(f"[LINEAR_EPG] Attempting fallback to legacy endpoint {legacy_path}...")
                try:
                    self._process_dispatcharr_xmltv(conn, dispatcharr, legacy_path, tvg_id_map, xml_id_to_tvg_map, discovery_filter)
                except Exception as e2:
                    logger.error(f"[LINEAR_EPG] Fallback also failed: {e2}")

        logger.info("[LINEAR_EPG] Refresh complete.")

    def _parse_xmltv_datetime(self, dt_str: str) -> datetime:
        # ... [rest of helper same] ...
        """Parse XMLTV datetime string like '20260314113500 +0100' to aware datetime."""
        from datetime import timedelta, timezone
        
        # Format: YYYYMMDDHHmmss +HHMM (or -HHMM)
        dt_str = dt_str.strip()
        if " " in dt_str:
            time_part, tz_part = dt_str.rsplit(" ", 1)
        else:
            time_part = dt_str
            tz_part = "+0000"

        # Parse base datetime (naively first)
        try:
            dt = datetime.strptime(time_part, "%Y%m%d%H%M%S")
        except ValueError:
            # Fallback for shorter formats if they exist
            try:
                dt = datetime.strptime(time_part[:12], "%Y%m%d%H%M")
            except ValueError:
                return parser.parse(dt_str) # Last resort

        # Parse timezone offset
        tz_sign = 1 if tz_part.startswith("+") else -1
        tz_digits = tz_part.lstrip("+-")
        tz_hours = int(tz_digits[:2])
        tz_minutes = int(tz_digits[2:4]) if len(tz_digits) >= 4 else 0
        tz_offset = timedelta(hours=tz_hours, minutes=tz_minutes) * tz_sign

        return dt.replace(tzinfo=timezone(tz_offset))

    def _process_dispatcharr_xmltv(self, conn, dispatcharr, path: str, tvg_id_map: Dict[str, List[int]], xml_id_to_tvg_map: Dict[str, str], discovery_filter: list[str] = None):
        """Download and parse Dispatcharr XMLTV."""
        logger.info(f"[LINEAR_EPG] Fetching XMLTV from {path}...")
        
        response = dispatcharr.client.get(path)
        
        # If public URL failed with 403/401, try internal hostname if we are in a Docker network
        if response is not None and response.status_code in (401, 403):
            logger.warning(f"[LINEAR_EPG] Public access to {path} returned {response.status_code}. Trying internal hostname...")
            
            # Common Dispatcharr internal hostnames
            # Prioritize the one confirmed to work in this environment
            internal_hosts = ["dispatcharr_tito-fork", "dispatcharr", "dispatcharr-api"]
            internal_port = 9191
            
            for host in internal_hosts:
                try:
                    import socket
                    socket.gethostbyname(host) # Check if host exists
                    
                    internal_url = f"http://{host}:{internal_port}{path}"
                    logger.info(f"[LINEAR_EPG] Attempting internal fetch from {internal_url}...")
                    
                    import httpx
                    from urllib.parse import urlparse
                    
                    # We prioritize the fetch with Host header because many internal proxy/routing
                    # setups (like Traefik/Django ALLOWED_HOSTS) require it to correctly route the request.
                    orig_host = urlparse(dispatcharr.client._base_url).hostname
                    
                    with httpx.Client(timeout=httpx.Timeout(120.0, connect=2.0)) as client:
                        # 1. Try with Host header first (most likely to work in this environment)
                        if orig_host:
                            try:
                                logger.debug(f"[LINEAR_EPG] Trying {host} with Host: {orig_host}")
                                int_resp = client.get(internal_url, headers={"Host": orig_host})
                                if int_resp.status_code == 200 and int_resp.content.startswith(b"<?xml"):
                                    logger.info(f"[LINEAR_EPG] Successfully fetched XMLTV from internal host {host} (with Host header)")
                                    response = int_resp
                                    break
                            except httpx.ConnectTimeout:
                                pass
                        
                        # 2. Try without Host header (fallback)
                        try:
                            logger.debug(f"[LINEAR_EPG] Trying {host} without Host header")
                            int_resp = client.get(internal_url)
                            if int_resp.status_code == 200 and int_resp.content.startswith(b"<?xml"):
                                logger.info(f"[LINEAR_EPG] Successfully fetched XMLTV from internal host {host}")
                                response = int_resp
                                break
                        except httpx.ConnectTimeout:
                            continue
                except Exception:
                    continue

        if response is None or response.status_code != 200:
            status = response.status_code if response else "No response"
            raise Exception(f"Failed to fetch XMLTV: HTTP {status}")
        
        content = response.content
        if content.startswith(b"\x1f\x8b"):
            import gzip
            import io
            with gzip.GzipFile(fileobj=io.BytesIO(content)) as f:
                content = f.read()

        # Parse XML
        root = ET.fromstring(content)
        
        # Build mapping from XML channel ID to our tvg_ids
        xml_id_to_tvg_id: Dict[str, str] = {}
        found_xml_channels = root.findall("channel")
        logger.info(f"[LINEAR_EPG] Found {len(found_xml_channels)} channels in XML")
        
        for chan in found_xml_channels:
            xml_id = chan.get("id")
            if not xml_id: continue
            
            resolved_tvg_id = None
            # 1. Try provided ID mapping (internal IDs or channel numbers)
            if xml_id in xml_id_to_tvg_map:
                resolved_tvg_id = xml_id_to_tvg_map[xml_id]
            # 2. Try direct tvg_id match
            elif xml_id in tvg_id_map:
                resolved_tvg_id = xml_id
            # 3. Try display name fallback
            else:
                for dn in chan.findall("display-name"):
                    name = dn.text
                    if name in tvg_id_map:
                        resolved_tvg_id = name
                        break
            
            if resolved_tvg_id:
                # Apply discovery_filter if provided
                if discovery_filter and resolved_tvg_id not in discovery_filter:
                    continue
                xml_id_to_tvg_id[xml_id] = resolved_tvg_id
        
        logger.info(f"[LINEAR_EPG] Mapped {len(xml_id_to_tvg_id)} XML channels to tvg_ids")

        # Clear old cache
        conn.execute("DELETE FROM linear_epg_cache")

        count = 0
        now = datetime.now(timezone.utc)
        import json

        found_xml_progs = root.findall("programme")
        logger.info(f"[LINEAR_EPG] Found {len(found_xml_progs)} programmes in XML")

        # Prioritize programmes with detailed titles (e.g. "Team A vs Team B")
        # to ensure we capture real games even if generic entries exist.
        def prog_priority(p):
            t = p.findtext("title") or ""
            score = len(t)
            if any(x in t.lower() for x in [" vs ", " - ", " @ ", " v "]):
                score += 1000
            return score

        sorted_progs = sorted(found_xml_progs, key=prog_priority, reverse=True)

        # To handle multiple sources for the same tvg_id, we'll keep track 
        # of counts per tvg_id per day.
        tvg_id_day_counts = {}

        for prog in sorted_progs:
            xml_ch_id = prog.get("channel")
            tvg_id = xml_id_to_tvg_id.get(xml_ch_id)
            if not tvg_id:
                continue
            
            # Extract details
            title_elem = prog.find("title")
            title = title_elem.text if title_elem is not None else "Unknown"
            
            subtitle_elem = prog.find("sub-title")
            subtitle = subtitle_elem.text if subtitle_elem is not None else None
            
            start_str = prog.get("start")
            stop_str = prog.get("stop")
            
            if not start_str or not stop_str:
                continue

            try:
                start_time = self._parse_xmltv_datetime(start_str)
                stop_time = self._parse_xmltv_datetime(stop_str)
                
                if stop_time < now:
                    continue

                # Rate limiting: Max 100 programmes per tvg_id per day
                day_key = f"{tvg_id}:{start_time.date()}"
                tvg_id_day_counts[day_key] = tvg_id_day_counts.get(day_key, 0) + 1
                if tvg_id_day_counts[day_key] > 100:
                    continue

                channel_ids = tvg_id_map[tvg_id]

                conn.execute(
                    """
                    INSERT INTO linear_epg_cache 
                    (tvg_id, title, subtitle, start_time, end_time, channel_ids_json)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (tvg_id, title, subtitle, start_time.isoformat(), stop_time.isoformat(), json.dumps(channel_ids))
                )
                count += 1
            except Exception as e:
                logger.debug(f"Failed to parse time for {title}: {e}")

        # 2. Add dummy entries for channels that were mapped but have no programmes
        # This ensures they remain visible in the Discovery Channels list in UI
        all_mapped_tvg_ids = set(xml_id_to_tvg_id.values())
        cached_tvg_ids = {row[0] for row in conn.execute("SELECT DISTINCT tvg_id FROM linear_epg_cache").fetchall()}
        
        missing_tvg_ids = all_mapped_tvg_ids - cached_tvg_ids
        for tid in missing_tvg_ids:
            # Add one empty entry far in future so it doesn't match anything but persists the ID
            conn.execute(
                """INSERT INTO linear_epg_cache 
                   (tvg_id, title, start_time, end_time, channel_ids_json)
                   VALUES (?, ?, ?, ?, ?)""",
                (tid, None, "2099-01-01T00:00:00", "2099-01-01T01:00:00", json.dumps(tvg_id_map.get(tid, [])))
            )

        conn.commit()
        logger.info(f"[LINEAR_EPG] Cached {count} programmes for {len(tvg_id_map)} linear channels")

    def get_active_schedules(self, target_date: datetime) -> List[sqlite3.Row]:
        """Get all cached schedules for a specific date range."""
        with self._get_connection() as conn:
            # Look for everything starting today
            date_str = target_date.strftime("%Y-%m-%d")
            return conn.execute(
                """
                SELECT * FROM linear_epg_cache 
                WHERE date(start_time) = ?
                """,
                (date_str,)
            ).fetchall()

    def discover_linear_events(self, target_date: datetime, events: List[any], leagues: List[str] = None) -> List[Dict]:
        """
        Match cached linear schedules and channel names against a list of official events.
        
        Returns a list of 'virtual streams' that can be injected into the matcher.
        """
        from teamarr.utilities.fuzzy_match import FuzzyMatcher
        from teamarr.dispatcharr import get_dispatcharr_connection
        import json
        
        matcher = FuzzyMatcher()
        virtual_streams = []

        # Filter events by leagues if provided
        filtered_events = events
        if leagues:
            filtered_events = [e for e in events if e.league in leagues]
        
        if not filtered_events:
            return []

        # Fetch channel data from Dispatcharr
        dispatcharr = get_dispatcharr_connection(self.db_factory)
        channel_to_streams: Dict[int, List[int]] = {}
        all_channels_obj = []
        if dispatcharr:
            all_channels_obj = dispatcharr.channels.get_channels()
            for ch in all_channels_obj:
                channel_to_streams[ch.id] = list(ch.streams) if ch.streams else []

        # 1. Discovery via Programme Schedules
        schedules = self.get_active_schedules(target_date)
        if schedules:
            for sched in schedules:
                # Parse the start time from the DB row (stored as ISO string)
                try:
                    sched_start = datetime.fromisoformat(sched["start_time"])
                    # Ensure it is offset-aware (default to UTC if missing)
                    if sched_start.tzinfo is None:
                        from datetime import timezone
                        sched_start = sched_start.replace(tzinfo=timezone.utc)
                except (ValueError, TypeError):
                    continue

                # Match against subtitle first then title
                match_string = sched["subtitle"] if sched["subtitle"] else sched["title"]
                if not match_string: continue

                match_string = self._apply_team_aliases(match_string)
                
                best_match = None
                best_score = 0
                
                for event in filtered_events:
                    # Time-based pre-filter: programme must start within 2 hours of event
                    # This prevents matching a 9 AM 'Preview' to an 8 PM 'Live' game.
                    # We use absolute difference to handle slight guide offsets in both directions.
                    time_diff = abs((sched_start - event.start_time).total_seconds())
                    if time_diff > (2 * 3600): # 2 hours
                        continue

                    result = matcher.match_event_name(match_string, event.name, threshold=75)
                    if result.matched and result.score > best_score:
                        best_match = event
                        best_score = result.score
                
                if best_match:
                    channel_ids = json.loads(sched["channel_ids_json"]) if sched["channel_ids_json"] else []
                    stream_ids = []
                    for cid in channel_ids:
                        stream_ids.extend(channel_to_streams.get(cid, []))
                    stream_ids = list(set(stream_ids))

                    if stream_ids:
                        virtual_streams.append({
                            "id": stream_ids[0],
                            "name": f"{sched['tvg_id']} | {match_string}",
                            "url": f"http://dispatcharr/stream/{stream_ids[0]}",
                            "tvg_id": sched["tvg_id"],
                            "is_linear": True,
                            "matched_event": best_match,
                            "stream_ids": stream_ids,
                        })
                        logger.debug(f"[LINEAR_EPG] Discovered event '{best_match.name}' on {sched['tvg_id']} (via EPG)")

        # 2. Discovery via Channel Display Names (find temporary match channels)
        logger.info(f"[LINEAR_EPG] Scanning {len(all_channels_obj)} channel names for matches...")
        
        # Ensure target_date is aware for comparison
        from datetime import timezone
        aware_target = target_date
        if aware_target.tzinfo is None:
            aware_target = aware_target.replace(tzinfo=timezone.utc)

        for ch in all_channels_obj:
            # Look for match patterns in channel name
            has_match_pattern = any(x in ch.name.lower() for x in [" vs ", " - ", " @ ", " v "])
            if not has_match_pattern:
                continue

            match_string = self._apply_team_aliases(ch.name)
            
            best_match = None
            best_score = 0
            
            for event in filtered_events:
                # Only match if event is actually today
                if aware_target.date() != event.start_time.date():
                    continue
                
                # For temporary channels, we can't be as strict since they often stay
                # up for hours, but a 4-hour window is safe to avoid cross-day matches.
                time_diff = abs((aware_target - event.start_time).total_seconds())
                if time_diff > (4 * 3600): # 4 hours
                    continue
                    
                result = matcher.match_event_name(match_string, event.name, threshold=80)
                if result.matched and result.score > best_score:
                    best_match = event
                    best_score = result.score
            
            if best_match:
                stream_ids = list(ch.streams) if ch.streams else []
                if stream_ids:
                    # Avoid duplication if already matched via EPG
                    if any(v["matched_event"].id == best_match.id for v in virtual_streams):
                        continue

                    virtual_streams.append({
                        "id": stream_ids[0],
                        "name": f"DISPATCH | {ch.name}",
                        "url": f"http://dispatcharr/stream/{stream_ids[0]}",
                        "tvg_id": ch.tvg_id or "dispatcharr.event",
                        "is_linear": True,
                        "matched_event": best_match,
                        "stream_ids": stream_ids,
                    })
                    logger.info(f"[LINEAR_EPG] Discovered event '{best_match.name}' via channel name: '{ch.name}'")

        return virtual_streams
