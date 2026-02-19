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
    """Service for monitoring linear channels via external EPG."""

    def __init__(self, db_path: str = "/app/data/teamarr.db"):
        self.db_path = db_path

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

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
        """Perform daily refresh of all monitored linear channels."""
        logger.info("[LINEAR_EPG] Starting daily refresh of linear schedules...")
        
        with self._get_connection() as conn:
            monitors = conn.execute(
                "SELECT * FROM linear_epg_monitors WHERE enabled = 1"
            ).fetchall()
            
            if not monitors:
                logger.info("[LINEAR_EPG] No enabled monitors found. Skipping.")
                return

            # Group monitors by XMLTV URL to avoid downloading same file multiple times
            url_groups: Dict[str, List[sqlite3.Row]] = {}
            for m in monitors:
                url = m["xmltv_url"]
                if url not in url_groups:
                    url_groups[url] = []
                url_groups[url].append(m)

            for url, group_monitors in url_groups.items():
                try:
                    self._process_xmltv_source(conn, url, group_monitors)
                except Exception as e:
                    logger.error(f"[LINEAR_EPG] Failed to process source {url}: {e}")

        logger.info("[LINEAR_EPG] Daily refresh complete.")

    def _process_xmltv_source(self, conn: sqlite3.Connection, url: str, monitors: List[sqlite3.Row]):
        """Download and parse XMLTV for a specific set of monitors."""
        logger.info(f"[LINEAR_EPG] Fetching XMLTV from {url}...")
        
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        
        content = response.content
        # Handle compressed .gz files
        if url.endswith(".gz") or content.startswith(b"\x1f\x8b"):
            import gzip
            import io
            logger.debug("[LINEAR_EPG] Decompressing GZIP content...")
            with gzip.GzipFile(fileobj=io.BytesIO(content)) as f:
                content = f.read()

        # Parse XML
        root = ET.fromstring(content)
        
        # Build two maps for lookup: 
        # 1. ID based (primary)
        # 2. Display Name based (fallback)
        channel_map: Dict[str, sqlite3.Row] = {}
        display_name_map: Dict[str, sqlite3.Row] = {}
        
        for m in monitors:
            if m["xmltv_channel_id"]:
                channel_map[m["xmltv_channel_id"]] = m
            channel_map[m["tvg_id"]] = m
            
            if m["display_name"]:
                display_name_map[m["display_name"].lower()] = m

        # Pre-process XML channels to handle display-name mapping
        xml_id_to_monitor: Dict[str, sqlite3.Row] = {}
        for chan in root.findall("channel"):
            xml_id = chan.get("id")
            if not xml_id: continue
            
            # Direct ID match
            if xml_id in channel_map:
                xml_id_to_monitor[xml_id] = channel_map[xml_id]
                continue
                
            # Match via display-name
            for dn in chan.findall("display-name"):
                name = dn.text.lower() if dn.text else ""
                if name in display_name_map:
                    xml_id_to_monitor[xml_id] = display_name_map[name]
                    break

        # Clear existing cache for these monitors before repopulating
        monitor_ids = [str(m["id"]) for m in monitors]
        conn.execute(
            f"DELETE FROM linear_epg_cache WHERE monitor_id IN ({','.join(monitor_ids)})"
        )

        count = 0
        now = datetime.now(timezone.utc)

        for prog in root.findall("programme"):
            ch_id = prog.get("channel")
            if ch_id not in xml_id_to_monitor:
                continue
            
            monitor = xml_id_to_monitor[ch_id]
            
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
                start_time = parser.parse(start_str)
                stop_time = parser.parse(stop_str)
                
                # Only cache future events or very recent ones
                if stop_time < now:
                    continue

                conn.execute(
                    """
                    INSERT INTO linear_epg_cache 
                    (monitor_id, tvg_id, title, subtitle, start_time, end_time)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (monitor["id"], monitor["tvg_id"], title, subtitle, start_time.isoformat(), stop_time.isoformat())
                )
                count += 1
            except Exception as e:
                logger.debug(f"Failed to parse time for {title}: {e}")

        conn.commit()
        logger.info(f"[LINEAR_EPG] Cached {count} programmes for {len(monitors)} channels from {url}")

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
        Match cached linear schedules against a list of official events.
        
        Returns a list of 'virtual streams' that can be injected into the matcher.
        """
        from teamarr.utilities.fuzzy_match import FuzzyMatcher
        
        schedules = self.get_active_schedules(target_date)
        if not schedules:
            return []

        # Filter events by leagues if provided
        if leagues:
            events = [e for e in events if e.league in leagues]
            if not events:
                return []

        matcher = FuzzyMatcher()
        virtual_streams = []

        for sched in schedules:
            # Match against subtitle first (usually contains teams on linear TV)
            # then fall back to title.
            match_string = sched["subtitle"] if sched["subtitle"] else sched["title"]

            # Apply team aliases to improve fuzzy matching (e.g., "PAOK" → "PAOK Salonika")
            match_string = self._apply_team_aliases(match_string)
            
            best_match = None
            best_score = 0
            
            for event in events:
                result = matcher.match_event_name(match_string, event.name, threshold=75)
                if result.matched and result.score > best_score:
                    best_match = event
                    best_score = result.score
            
            if best_match:
                # Create a 'virtual stream' that looks like a Dispatcharr stream
                # but contains the tvg_id of the linear channel.
                virtual_streams.append({
                    "id": f"linear-{sched['id']}",
                    "name": f"{sched['tvg_id']} | {match_string}",
                    "tvg_id": sched["tvg_id"],
                    "is_linear": True,
                    "matched_event": best_match,
                    "start_time": sched["start_time"],
                })
                logger.debug(f"[LINEAR_EPG] Discovered event '{best_match.name}' on {sched['tvg_id']} (via '{match_string}' score={best_score:.1f})")

        return virtual_streams
