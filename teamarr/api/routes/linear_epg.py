"""Linear EPG Monitor management endpoints."""

import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, status, Query
from pydantic import BaseModel, Field
from teamarr.database import get_db
from teamarr.services.linear_epg_service import LinearEpgService

logger = logging.getLogger(__name__)
router = APIRouter()

class MonitorCreate(BaseModel):
    tvg_id: str = Field(..., description="The tvg_id to monitor")
    display_name: Optional[str] = None
    xmltv_url: str = Field(..., description="The external XMLTV URL")
    xmltv_channel_id: Optional[str] = None
    include_sports: List[str] = []
    enabled: bool = True

class MonitorUpdate(BaseModel):
    display_name: Optional[str] = None
    xmltv_url: Optional[str] = None
    xmltv_channel_id: Optional[str] = None
    include_sports: Optional[List[str]] = None
    enabled: Optional[bool] = None

class MonitorResponse(BaseModel):
    id: int
    tvg_id: str
    display_name: Optional[str]
    xmltv_url: str
    xmltv_channel_id: Optional[str]
    include_sports: List[str]
    enabled: bool

@router.get("/monitors", response_model=List[MonitorResponse])
def list_monitors():
    """List all linear EPG monitors."""
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM linear_epg_monitors").fetchall()
        import json
        return [
            MonitorResponse(
                id=row["id"],
                tvg_id=row["tvg_id"],
                display_name=row["display_name"],
                xmltv_url=row["xmltv_url"],
                xmltv_channel_id=row["xmltv_channel_id"],
                include_sports=json.loads(row["include_sports"]) if row["include_sports"] else [],
                enabled=bool(row["enabled"])
            ) for row in rows
        ]

@router.post("/monitors", response_model=MonitorResponse, status_code=status.HTTP_201_CREATED)
def create_monitor(request: MonitorCreate):
    """Create a new linear EPG monitor."""
    import json
    with get_db() as conn:
        try:
            cursor = conn.execute(
                """INSERT INTO linear_epg_monitors 
                (tvg_id, display_name, xmltv_url, xmltv_channel_id, include_sports, enabled)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (request.tvg_id, request.display_name, request.xmltv_url, 
                 request.xmltv_channel_id, json.dumps(request.include_sports), int(request.enabled))
            )
            conn.commit()
            monitor_id = cursor.lastrowid
            return MonitorResponse(id=monitor_id, **request.model_dump())
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to create monitor: {e}")

@router.post("/refresh")
def trigger_refresh():
    """Manually trigger a refresh of all linear EPG schedules."""
    service = LinearEpgService()
    try:
        service.refresh_cache()
        return {"success": True, "message": "Linear EPG cache refresh started"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/monitors/{monitor_id}", response_model=MonitorResponse)
def update_monitor(monitor_id: int, request: MonitorUpdate):
    """Update an existing linear EPG monitor."""
    import json
    with get_db() as conn:
        # Get current monitor data
        current = conn.execute("SELECT * FROM linear_epg_monitors WHERE id = ?", (monitor_id,)).fetchone()
        if not current:
            raise HTTPException(status_code=404, detail="Monitor not found")

        # Build update query with only provided fields
        updates = []
        params = []
        if request.display_name is not None:
            updates.append("display_name = ?")
            params.append(request.display_name)
        if request.xmltv_url is not None:
            updates.append("xmltv_url = ?")
            params.append(request.xmltv_url)
        if request.xmltv_channel_id is not None:
            updates.append("xmltv_channel_id = ?")
            params.append(request.xmltv_channel_id)
        if request.include_sports is not None:
            updates.append("include_sports = ?")
            params.append(json.dumps(request.include_sports))
        if request.enabled is not None:
            updates.append("enabled = ?")
            params.append(int(request.enabled))

        if not updates:
            # No fields to update, return current
            return MonitorResponse(
                id=current["id"],
                tvg_id=current["tvg_id"],
                display_name=current["display_name"],
                xmltv_url=current["xmltv_url"],
                xmltv_channel_id=current["xmltv_channel_id"],
                include_sports=json.loads(current["include_sports"]) if current["include_sports"] else [],
                enabled=bool(current["enabled"])
            )

        params.append(monitor_id)
        conn.execute(
            f"UPDATE linear_epg_monitors SET {', '.join(updates)} WHERE id = ?",
            params
        )
        conn.commit()

        # Fetch updated monitor
        updated = conn.execute("SELECT * FROM linear_epg_monitors WHERE id = ?", (monitor_id,)).fetchone()
        return MonitorResponse(
            id=updated["id"],
            tvg_id=updated["tvg_id"],
            display_name=updated["display_name"],
            xmltv_url=updated["xmltv_url"],
            xmltv_channel_id=updated["xmltv_channel_id"],
            include_sports=json.loads(updated["include_sports"]) if updated["include_sports"] else [],
            enabled=bool(updated["enabled"])
        )

@router.delete("/monitors/{monitor_id}")
def delete_monitor(monitor_id: int):
    """Delete a linear EPG monitor."""
    with get_db() as conn:
        cursor = conn.execute("DELETE FROM linear_epg_monitors WHERE id = ?", (monitor_id,))
        conn.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Monitor not found")
    return {"success": True}
