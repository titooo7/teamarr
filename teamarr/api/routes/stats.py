"""Stats API endpoints.

Provides centralized access to all processing statistics:
- Current aggregate stats
- Historical run data
- Daily/weekly trends
"""

from fastapi import APIRouter, Query

from teamarr.database import get_db

router = APIRouter()


# =============================================================================
# CURRENT STATS
# =============================================================================


@router.get("")
def get_stats():
    """Get current aggregate stats.

    Returns all stats from a single endpoint:
    - Overall run counts and performance
    - Stream matching stats (matched, unmatched, cached)
    - Channel lifecycle stats (created, deleted, active)
    - Programme stats by type (events, pregame, postgame, idle)
    - Last 24 hour summary
    - Breakdown by run type
    """
    from teamarr.database.stats import get_current_stats

    with get_db() as conn:
        return get_current_stats(conn)


@router.get("/history")
def get_stats_history(
    days: int = Query(7, ge=1, le=90, description="Number of days of history"),
    run_type: str | None = Query(None, description="Filter by run type"),
):
    """Get daily stats history for charting.

    Returns per-day aggregates for the specified time range.
    """
    from teamarr.database.stats import get_stats_history as get_history

    with get_db() as conn:
        return get_history(conn, days=days, run_type=run_type)


# =============================================================================
# PROCESSING RUNS
# =============================================================================


@router.get("/runs")
def get_runs(
    limit: int = Query(50, ge=1, le=500, description="Max runs to return"),
    run_type: str | None = Query(None, description="Filter by run type"),
    group_id: int | None = Query(None, description="Filter by group ID"),
    status: str | None = Query(None, description="Filter by status"),
):
    """Get recent processing runs.

    Returns detailed information about recent processing runs
    with optional filtering.
    """
    from teamarr.database.stats import get_recent_runs

    with get_db() as conn:
        runs = get_recent_runs(
            conn,
            limit=limit,
            run_type=run_type,
            group_id=group_id,
            status=status,
        )
        return {
            "runs": [run.to_dict() for run in runs],
            "count": len(runs),
        }


@router.get("/runs/{run_id}")
def get_run(run_id: int):
    """Get a specific processing run by ID."""
    from fastapi import HTTPException, status

    from teamarr.database.stats import get_run as get_run_by_id

    with get_db() as conn:
        run = get_run_by_id(conn, run_id)
        if not run:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Run {run_id} not found",
            )
        return run.to_dict()


# =============================================================================
# MAINTENANCE
# =============================================================================


@router.delete("/runs/cleanup")
def cleanup_runs(
    days: int = Query(30, ge=1, le=365, description="Delete runs older than N days"),
):
    """Delete old processing runs.

    Cleans up historical run data to manage database size.
    """
    from teamarr.database.stats import cleanup_old_runs

    with get_db() as conn:
        deleted = cleanup_old_runs(conn, days=days)
        return {
            "deleted": deleted,
            "message": f"Deleted {deleted} runs older than {days} days",
        }
