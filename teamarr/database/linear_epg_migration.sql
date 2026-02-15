-- Migration: Add Linear EPG Monitoring and Cache
-- Supports discovery of sports events on linear 24/7 channels

-- =============================================================================
-- LINEAR_EPG_MONITORS TABLE
-- Defines which linear channels to monitor for sports events.
-- Mapped to Dispatcharr streams via tvg_id.
-- =============================================================================

CREATE TABLE IF NOT EXISTS linear_epg_monitors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- The tvg_id to monitor (e.g., 'DAZN.1.ES', 'Movistar.LaLiga.es')
    tvg_id TEXT NOT NULL,
    
    -- Display name for logs/UI
    display_name TEXT,

    -- XMLTV source URL (where to fetch the EPG from)
    xmltv_url TEXT NOT NULL,

    -- XMLTV Channel ID (in case it differs from tvg_id)
    xmltv_channel_id TEXT,

    -- Optional filters for this specific channel
    include_sports JSON DEFAULT '[]',   -- ["soccer", "basketball"]
    
    -- Status
    enabled BOOLEAN DEFAULT 1,
    
    UNIQUE(tvg_id, xmltv_url)
);

CREATE INDEX IF NOT EXISTS idx_linear_monitors_enabled ON linear_epg_monitors(enabled);

-- =============================================================================
-- LINEAR_EPG_CACHE TABLE
-- Pre-filtered sports schedule from linear XMLTV sources.
-- Populated once daily to avoid redundant XML processing.
-- =============================================================================

CREATE TABLE IF NOT EXISTS linear_epg_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- Source reference
    monitor_id INTEGER NOT NULL,
    tvg_id TEXT NOT NULL,

    -- Event details from XMLTV
    title TEXT NOT NULL,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP NOT NULL,
    
    -- Matching details (populated during generation/discovery)
    matched_event_id TEXT,    -- Link to official event (ESPN/TSDB)
    matched_league TEXT,
    
    -- Housekeeping
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (monitor_id) REFERENCES linear_epg_monitors(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_linear_cache_time ON linear_epg_cache(start_time);
CREATE INDEX IF NOT EXISTS idx_linear_cache_tvg ON linear_epg_cache(tvg_id);
CREATE INDEX IF NOT EXISTS idx_linear_cache_match ON linear_epg_cache(matched_event_id);
