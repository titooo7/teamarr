# Event Group V1 → V2 Parity Plan

## Overview

This document tracks the feature parity work needed to bring V2's event group functionality to match V1. V2 has a simpler architecture by design, but some V1 features are essential for production use.

## Architecture Principles

All changes must follow these principles:

1. **Layer Separation**: API routes → Services → Database
2. **Single Responsibility**: Each module/function has one clear purpose
3. **Type Safety**: Use dataclasses for internal types, Pydantic for API
4. **No Dead Code**: Remove unused code immediately
5. **Explicit > Implicit**: Prefer configuration over detection

## Current State Analysis

### Database Schema Comparison

| Column | V1 | V2 | Status |
|--------|-----|-----|--------|
| **Identity** |
| `id` | ✓ | ✓ | OK |
| `dispatcharr_group_id` | ✓ (unique M3U group ID) | `m3u_group_id` | **Different naming** |
| `dispatcharr_account_id` | ✓ (M3U account) | - | **Missing** |
| `group_name` | ✓ | `name` | OK (renamed) |
| `account_name` | ✓ (display) | - | **Missing** |
| **League Configuration** |
| `assigned_league` | ✓ (single league) | - | **Replaced by `leagues[]`** |
| `assigned_sport` | ✓ | - | **Missing** |
| `is_multi_sport` | ✓ | - | **Missing** (derive from leagues.length) |
| `enabled_leagues` | ✓ (JSON) | `leagues` (JSON) | OK |
| **Template & Channel** |
| `event_template_id` | ✓ | `template_id` | OK |
| `channel_start` | ✓ | `channel_start_number` | OK |
| `channel_group_id` | ✓ | ✓ | OK |
| `channel_group_name` | ✓ (display) | - | **Missing** |
| `stream_profile_id` | ✓ | ✓ | OK |
| `channel_profile_ids` | ✓ | ✓ | OK |
| `channel_assignment_mode` | ✓ | ✓ | OK |
| **Lifecycle** |
| `create_timing` | ✓ | ✓ | OK |
| `delete_timing` | ✓ | ✓ | OK |
| `duplicate_event_handling` | ✓ | ✓ | OK |
| **Custom Regex** |
| `custom_regex_teams` | ✓ | - | **Missing** |
| `custom_regex_teams_enabled` | ✓ | - | **Missing** |
| `custom_regex_date` | ✓ | - | **Missing** |
| `custom_regex_date_enabled` | ✓ | - | **Missing** |
| `custom_regex_time` | ✓ | - | **Missing** |
| `custom_regex_time_enabled` | ✓ | - | **Missing** |
| `stream_include_regex` | ✓ | - | **Missing** |
| `stream_include_regex_enabled` | ✓ | - | **Missing** |
| `stream_exclude_regex` | ✓ | - | **Missing** |
| `stream_exclude_regex_enabled` | ✓ | - | **Missing** |
| `skip_builtin_filter` | ✓ | - | **Missing** |
| **Multi-Sport** |
| `channel_sort_order` | ✓ (`time`, `sport_time`, `league_time`) | - | **Missing** |
| `overlap_handling` | ✓ (`add_stream`, `add_only`, `create_all`, `skip`) | - | **Missing** |
| **Hierarchy** |
| `parent_group_id` | ✓ | ✓ | OK |
| `sort_order` | ✓ | ✓ | OK |
| **Stats** |
| `last_refresh` | ✓ | - | **Missing** |
| `refresh_interval_minutes` | ✓ | - | **Missing** |
| `total_stream_count` | ✓ | ✓ | OK |
| `stream_count` | ✓ (after filtering) | - | **Missing** |
| `matched_count` | ✓ | - | **Missing** |
| `filtered_no_indicator` | ✓ | - | **Missing** |
| `filtered_include_regex` | ✓ | - | **Missing** |
| `filtered_exclude_regex` | ✓ | - | **Missing** |
| `filtered_outside_lookahead` | ✓ | - | **Missing** |
| `filtered_final` | ✓ | - | **Missing** |
| `filtered_league_not_enabled` | ✓ | - | **Missing** |
| `filtered_unsupported_sport` | ✓ | - | **Missing** |

### V2 Simplified Approach

V2 intentionally simplifies some V1 patterns:

1. **Leagues Array**: V2 uses a `leagues[]` array instead of `assigned_league` + `is_multi_sport` + `enabled_leagues`. This is cleaner.

2. **No Sport Column**: V2 derives sport from league configuration. Acceptable since leagues→sport mapping is 1:many.

3. **Display Names**: V2 could store these optionally but can also derive from Dispatcharr lookups.

## Implementation Phases

### Phase 1: Critical Missing Features (Essential for Parity)

These are blocking features users need.

#### 1.1 M3U Account Tracking

**Why needed**: Users need to know which M3U provider a group came from.

**Schema changes**:
```sql
ALTER TABLE event_epg_groups ADD COLUMN m3u_account_id INTEGER;
ALTER TABLE event_epg_groups ADD COLUMN m3u_account_name TEXT;  -- For display
```

**Files to modify**:
- `teamarr/database/schema.sql`
- `teamarr/database/groups.py`
- `teamarr/api/routes/groups.py` (add to models)
- `frontend/src/api/types.ts`
- `frontend/src/pages/EventGroupForm.tsx`
- `frontend/src/pages/EventGroupImport.tsx`

#### 1.2 Processing Stats

**Why needed**: Users need to see last refresh time and match success rates.

**Schema changes**:
```sql
ALTER TABLE event_epg_groups ADD COLUMN last_refresh TIMESTAMP;
ALTER TABLE event_epg_groups ADD COLUMN stream_count INTEGER DEFAULT 0;  -- After filtering
ALTER TABLE event_epg_groups ADD COLUMN matched_count INTEGER DEFAULT 0;
ALTER TABLE event_epg_groups ADD COLUMN matched_rate REAL;  -- Computed: matched/stream
```

**Files to modify**:
- `teamarr/database/schema.sql`
- `teamarr/database/groups.py` - add `update_group_stats()`
- `teamarr/consumers/event_epg.py` - update stats after processing
- `teamarr/api/routes/groups.py` - include in response
- `frontend/src/pages/EventGroups.tsx` - show stats

### Phase 2: Stream Filtering (Important for UX)

#### 2.1 Custom Regex Support

**Why needed**: Power users need custom stream name parsing.

**Schema changes**:
```sql
ALTER TABLE event_epg_groups ADD COLUMN custom_regex_teams TEXT;
ALTER TABLE event_epg_groups ADD COLUMN custom_regex_teams_enabled BOOLEAN DEFAULT 0;
ALTER TABLE event_epg_groups ADD COLUMN stream_include_regex TEXT;
ALTER TABLE event_epg_groups ADD COLUMN stream_include_regex_enabled BOOLEAN DEFAULT 0;
ALTER TABLE event_epg_groups ADD COLUMN stream_exclude_regex TEXT;
ALTER TABLE event_epg_groups ADD COLUMN stream_exclude_regex_enabled BOOLEAN DEFAULT 0;
ALTER TABLE event_epg_groups ADD COLUMN skip_builtin_filter BOOLEAN DEFAULT 0;
```

**New service module**: `teamarr/services/stream_filter.py`

```python
@dataclass
class StreamFilterConfig:
    """Configuration for stream filtering."""
    include_regex: str | None
    include_enabled: bool
    exclude_regex: str | None
    exclude_enabled: bool
    custom_teams_regex: str | None
    custom_teams_enabled: bool
    skip_builtin: bool

class StreamFilter:
    """Filters streams based on regex patterns."""

    def __init__(self, config: StreamFilterConfig):
        self.config = config

    def filter(self, streams: list[Stream]) -> FilterResult:
        """Apply filters and return filtered streams with stats."""
        pass

    def extract_teams(self, stream_name: str) -> tuple[str, str] | None:
        """Extract team names using regex or builtin patterns."""
        pass
```

**Files to modify**:
- `teamarr/database/schema.sql`
- `teamarr/database/groups.py`
- `teamarr/api/routes/groups.py`
- `teamarr/consumers/event_epg.py` - use StreamFilter
- `frontend/src/pages/EventGroupForm.tsx` - add Regex tab

#### 2.2 Filtering Stats

**Why needed**: Users need to understand why streams aren't matching.

**Schema changes**:
```sql
ALTER TABLE event_epg_groups ADD COLUMN filtered_no_indicator INTEGER DEFAULT 0;
ALTER TABLE event_epg_groups ADD COLUMN filtered_include_regex INTEGER DEFAULT 0;
ALTER TABLE event_epg_groups ADD COLUMN filtered_exclude_regex INTEGER DEFAULT 0;
ALTER TABLE event_epg_groups ADD COLUMN filtered_final INTEGER DEFAULT 0;
```

### Phase 3: Multi-Sport Enhancements (Nice to Have)

#### 3.1 Channel Sort Order

**Why needed**: Multi-sport groups need configurable ordering.

**Schema changes**:
```sql
ALTER TABLE event_epg_groups ADD COLUMN channel_sort_order TEXT DEFAULT 'time'
    CHECK(channel_sort_order IN ('time', 'sport_time', 'league_time'));
```

#### 3.2 Overlap Handling

**Why needed**: Control behavior when events overlap.

**Schema changes**:
```sql
ALTER TABLE event_epg_groups ADD COLUMN overlap_handling TEXT DEFAULT 'add_stream'
    CHECK(overlap_handling IN ('add_stream', 'add_only', 'create_all', 'skip'));
```

## Immediate Bug Fixes

### 1. Blank Screen After Import

**Symptom**: Navigating to `/event-groups/new?m3u_group_id=...` shows blank screen.

**Debug steps**:
1. Check browser console for errors
2. Verify all UI components are properly imported
3. Add error boundary to catch rendering errors

### 2. Stream Preview Reverse Order

**Symptom**: Streams displayed in reverse order in preview modal.

**Potential causes**:
- Dispatcharr API returns in reverse order by default
- Client-side sorting issue

**Fix**: Add explicit sort in API or frontend.

## File Organization

New files to create:

```
teamarr/
├── services/
│   └── stream_filter.py          # Stream filtering service
│
├── consumers/
│   └── stream_parser.py          # Stream name parsing (teams, date, time)
│
frontend/src/
├── pages/
│   └── EventGroupForm/           # Split into sub-components
│       ├── index.tsx             # Main form
│       ├── ModeStep.tsx          # Mode selection
│       ├── LeagueStep.tsx        # League selection
│       ├── SettingsStep.tsx      # Settings form
│       └── RegexStep.tsx         # Regex configuration
```

## Testing Requirements

Each phase must include:

1. **Unit tests** for new services
2. **API tests** for endpoint changes
3. **Manual testing** of UI flows

## Migration Path

For existing V2 users:

1. Schema migrations via `schema.sql` (uses `ADD COLUMN IF NOT EXISTS`)
2. Default values for all new columns
3. No data loss or breaking changes

## Progress Tracking

### Phase 1: Critical
- [ ] 1.1 M3U Account Tracking
  - [ ] Schema migration
  - [ ] Database layer
  - [ ] API layer
  - [ ] Frontend
- [ ] 1.2 Processing Stats
  - [ ] Schema migration
  - [ ] Database layer
  - [ ] Consumer updates
  - [ ] API layer
  - [ ] Frontend

### Phase 2: Stream Filtering
- [ ] 2.1 Custom Regex
  - [ ] Schema migration
  - [ ] StreamFilter service
  - [ ] Consumer integration
  - [ ] API layer
  - [ ] Frontend (Regex tab)
- [ ] 2.2 Filtering Stats
  - [ ] Schema migration
  - [ ] Stats collection
  - [ ] Frontend display

### Phase 3: Multi-Sport
- [ ] 3.1 Channel Sort Order
- [ ] 3.2 Overlap Handling

### Bug Fixes
- [ ] Blank screen after import
- [ ] Stream preview order

## Notes

- V1 reference code: `/srv/dev-disk-by-uuid-c332869f-d034-472c-a641-ccf1f28e52d6/scratch/teamarr/`
- V2 codebase: `/srv/dev-disk-by-uuid-c332869f-d034-472c-a641-ccf1f28e52d6/scratch/teamarrv2/`
- This document should be updated as work progresses
