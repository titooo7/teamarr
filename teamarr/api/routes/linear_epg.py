"""Linear EPG Discovery endpoints."""

import logging
import json
from typing import List, Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from teamarr.database import get_db
from teamarr.services.linear_epg_service import LinearEpgService

logger = logging.getLogger(__name__)
router = APIRouter()

class ProgrammeResponse(BaseModel):
    """Linear EPG programme response."""
    id: int
    tvg_id: str
    title: Optional[str]
    subtitle: Optional[str]
    start_time: str
    end_time: str
    channel_ids: List[int]

@router.get("/programmes", response_model=List[ProgrammeResponse])
def list_programmes(tvg_id: Optional[str] = None):
    """List all cached linear EPG programmes."""
    with get_db() as conn:
        query = "SELECT * FROM linear_epg_cache"
        params = []
        if tvg_id:
            query += " WHERE tvg_id = ?"
            params.append(tvg_id)
        
        query += " ORDER BY start_time ASC LIMIT 500"
        
        rows = conn.execute(query, params).fetchall()
        
        return [
            ProgrammeResponse(
                id=row["id"],
                tvg_id=row["tvg_id"],
                title=row["title"],
                subtitle=row["subtitle"],
                start_time=row["start_time"],
                end_time=row["end_time"],
                channel_ids=json.loads(row["channel_ids_json"]) if row["channel_ids_json"] else []
            ) for row in rows
        ]

@router.post("/refresh")
def trigger_refresh():
    """Manually trigger a refresh of linear EPG schedules from Dispatcharr."""
    service = LinearEpgService()
    try:
        service.refresh_cache()
        return {"success": True, "message": "Linear EPG cache refresh complete"}
    except Exception as e:
        logger.error(f"Failed to refresh linear EPG: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/channels")
def list_linear_channels():
    """List all unique linear channels currently in cache."""
    with get_db() as conn:
        # We need to aggregate channel_ids from all rows for the same tvg_id
        rows = conn.execute(
            "SELECT tvg_id, channel_ids_json FROM linear_epg_cache"
        ).fetchall()
        
        aggregated = {}
        for row in rows:
            tvg_id = row["tvg_id"]
            if not tvg_id: continue
            
            ids = json.loads(row["channel_ids_json"]) if row["channel_ids_json"] else []
            if tvg_id not in aggregated:
                aggregated[tvg_id] = set()
            for cid in ids:
                aggregated[tvg_id].add(cid)
        
        # Convert to list format
        result = [
            {
                "tvg_id": tid,
                "channel_ids": list(cids)
            } for tid, cids in sorted(aggregated.items())
        ]
        
        return result
