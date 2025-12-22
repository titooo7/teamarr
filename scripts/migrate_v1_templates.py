#!/usr/bin/env python3
"""Migrate V1 templates to V2 database.

Converts V1 template format to V2's restructured format:
- V1 uses individual fields for pregame/postgame/idle
- V2 uses JSON objects with fallback and conditional structures

Field Mappings:
  V1                           -> V2
  ---------------------------------------------------------------------------
  pregame_title/subtitle/desc  -> pregame_fallback (JSON object)
  postgame_title/subtitle/desc -> postgame_fallback (JSON object)
  postgame_conditional_enabled -> postgame_conditional.enabled
  postgame_description_final   -> postgame_conditional.description_final
  idle_title/subtitle/desc     -> idle_content (JSON object)
  idle_conditional_enabled     -> idle_conditional.enabled
  idle_offseason_enabled       -> idle_offseason.description_enabled
  description_options          -> conditional_descriptions
  channel_name                 -> event_channel_name
  flags                        -> xmltv_flags
  categories                   -> xmltv_categories

Usage:
    # Make sure V2 database path is correct (default: data/teamarr.db)
    python scripts/migrate_v1_templates.py

    # The script will:
    # 1. Initialize V2 database schema if empty
    # 2. Read templates from V1 database
    # 3. Convert to V2 format
    # 4. Insert into V2 database

    # If V2 already has templates, migration is skipped to prevent duplicates.

Requirements:
    - V1 database at: /mnt/nvme/scratch/teamarr/data/teamarr.db
    - V2 database at: /mnt/nvme/scratch/teamarrv2/data/teamarr.db
    - V2 schema at: /mnt/nvme/scratch/teamarrv2/teamarr/database/schema.sql
"""

import json
import sqlite3
from pathlib import Path

# Paths
V1_DB = Path("/mnt/nvme/scratch/teamarr/data/teamarr.db")
V2_DB = Path("/mnt/nvme/scratch/teamarrv2/data/teamarr.db")
V2_SCHEMA = Path("/mnt/nvme/scratch/teamarrv2/teamarr/database/schema.sql")


def init_v2_db():
    """Initialize V2 database with schema if empty."""
    conn = sqlite3.connect(V2_DB)
    conn.row_factory = sqlite3.Row

    # Check if templates table exists
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='templates'"
    )
    if not cursor.fetchone():
        print("Initializing V2 database schema...")
        schema = V2_SCHEMA.read_text()
        conn.executescript(schema)
        conn.commit()
        print("Schema created.")

    return conn


def get_v1_templates():
    """Read templates from V1 database."""
    conn = sqlite3.connect(V1_DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("SELECT * FROM templates")
    templates = cursor.fetchall()
    conn.close()
    return templates


def parse_json(value, default=None):
    """Parse JSON string, returning default on failure."""
    if value is None:
        return default if default is not None else {}
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return default if default is not None else {}


def convert_v1_to_v2(v1_row):
    """Convert V1 template row to V2 format."""
    # Parse V1 JSON fields
    v1_flags = parse_json(v1_row["flags"], {"new": True, "live": False, "date": False})
    v1_categories = parse_json(v1_row["categories"], ["Sports"])
    v1_description_options = parse_json(v1_row["description_options"], [])

    # Build V2 pregame_fallback from V1 individual fields
    pregame_fallback = {
        "title": v1_row["pregame_title"] or "Pregame Coverage",
        "subtitle": v1_row["pregame_subtitle"],
        "description": v1_row["pregame_description"],
        "art_url": v1_row["pregame_art_url"],
    }

    # Build V2 postgame_fallback from V1 individual fields
    postgame_fallback = {
        "title": v1_row["postgame_title"] or "Postgame Recap",
        "subtitle": v1_row["postgame_subtitle"],
        "description": v1_row["postgame_description"],
        "art_url": v1_row["postgame_art_url"],
    }

    # Build V2 postgame_conditional from V1 fields
    postgame_conditional = {
        "enabled": bool(v1_row["postgame_conditional_enabled"]),
        "description_final": v1_row["postgame_description_final"],
        "description_not_final": v1_row["postgame_description_not_final"],
    }

    # Build V2 idle_content from V1 individual fields
    idle_content = {
        "title": v1_row["idle_title"] or "{team_name} Programming",
        "subtitle": v1_row["idle_subtitle"],
        "description": v1_row["idle_description"],
        "art_url": v1_row["idle_art_url"],
    }

    # Build V2 idle_conditional from V1 fields
    idle_conditional = {
        "enabled": bool(v1_row["idle_conditional_enabled"]),
        "description_final": v1_row["idle_description_final"],
        "description_not_final": v1_row["idle_description_not_final"],
    }

    # Build V2 idle_offseason from V1 fields
    idle_offseason = {
        "title_enabled": bool(v1_row["idle_title_offseason_enabled"]),
        "title": v1_row["idle_title_offseason"],
        "subtitle_enabled": bool(v1_row["idle_subtitle_offseason_enabled"]),
        "subtitle": v1_row["idle_subtitle_offseason"],
        "description_enabled": bool(v1_row["idle_offseason_enabled"]),
        "description": v1_row["idle_description_offseason"],
    }

    # Map V1 to V2 fields
    v2_template = {
        "name": v1_row["name"],
        "template_type": v1_row["template_type"] or "team",
        "sport": v1_row["sport"],
        "league": v1_row["league"],
        "title_format": v1_row["title_format"],
        "subtitle_template": v1_row["subtitle_template"],
        "description_template": None,  # V2 uses conditional_descriptions instead
        "program_art_url": v1_row["program_art_url"],
        "game_duration_mode": v1_row["game_duration_mode"] or "sport",
        "game_duration_override": v1_row["game_duration_override"],
        "xmltv_flags": json.dumps(v1_flags),
        "xmltv_categories": json.dumps(v1_categories),
        "categories_apply_to": v1_row["categories_apply_to"] or "all",
        "pregame_enabled": bool(v1_row["pregame_enabled"]),
        "pregame_periods": json.dumps([]),  # V2 uses periods array, V1 didn't
        "pregame_fallback": json.dumps(pregame_fallback),
        "postgame_enabled": bool(v1_row["postgame_enabled"]),
        "postgame_periods": json.dumps([]),  # V2 uses periods array, V1 didn't
        "postgame_fallback": json.dumps(postgame_fallback),
        "postgame_conditional": json.dumps(postgame_conditional),
        "idle_enabled": bool(v1_row["idle_enabled"]),
        "idle_content": json.dumps(idle_content),
        "idle_conditional": json.dumps(idle_conditional),
        "idle_offseason": json.dumps(idle_offseason),
        "conditional_descriptions": json.dumps(v1_description_options),
        "event_channel_name": v1_row["channel_name"],
        "event_channel_logo_url": v1_row["channel_logo_url"],
    }

    return v2_template


def insert_template(conn, template):
    """Insert template into V2 database."""
    columns = list(template.keys())
    placeholders = ", ".join("?" * len(columns))
    column_str = ", ".join(columns)
    values = [template[col] for col in columns]

    conn.execute(
        f"INSERT INTO templates ({column_str}) VALUES ({placeholders})",
        values,
    )


def main():
    """Migrate V1 templates to V2."""
    print("Migrating V1 templates to V2...")

    # Initialize V2 database
    v2_conn = init_v2_db()

    # Check if templates already exist in V2
    cursor = v2_conn.execute("SELECT COUNT(*) FROM templates")
    count = cursor.fetchone()[0]
    if count > 0:
        print(f"V2 already has {count} templates. Skipping migration.")
        v2_conn.close()
        return

    # Get V1 templates
    v1_templates = get_v1_templates()
    print(f"Found {len(v1_templates)} templates in V1 database")

    # Convert and insert each template
    for v1_row in v1_templates:
        v2_template = convert_v1_to_v2(v1_row)
        print(f"  Migrating: {v2_template['name']} ({v2_template['template_type']})")
        insert_template(v2_conn, v2_template)

    v2_conn.commit()
    v2_conn.close()
    print(f"Successfully migrated {len(v1_templates)} templates to V2!")


if __name__ == "__main__":
    main()
