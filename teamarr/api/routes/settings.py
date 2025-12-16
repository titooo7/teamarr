"""Settings management endpoints.

Provides REST API for:
- Reading and updating application settings
- Testing Dispatcharr connection
- Scheduler status and control
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from teamarr.database import get_db

router = APIRouter()


# =============================================================================
# PYDANTIC MODELS
# =============================================================================


class DispatcharrSettingsModel(BaseModel):
    """Dispatcharr integration settings."""

    enabled: bool = False
    url: str | None = None
    username: str | None = None
    password: str | None = None
    epg_id: int | None = None


class DispatcharrSettingsUpdate(BaseModel):
    """Update model for Dispatcharr settings (all fields optional)."""

    enabled: bool | None = None
    url: str | None = None
    username: str | None = None
    password: str | None = None
    epg_id: int | None = None


class LifecycleSettingsModel(BaseModel):
    """Channel lifecycle settings."""

    channel_create_timing: str = "same_day"
    channel_delete_timing: str = "day_after"
    channel_range_start: int = 101
    channel_range_end: int | None = None


class ReconciliationSettingsModel(BaseModel):
    """Reconciliation settings."""

    reconcile_on_epg_generation: bool = True
    reconcile_on_startup: bool = True
    auto_fix_orphan_teamarr: bool = True
    auto_fix_orphan_dispatcharr: bool = False
    auto_fix_duplicates: bool = False
    default_duplicate_event_handling: str = "consolidate"
    channel_history_retention_days: int = 90


class SchedulerSettingsModel(BaseModel):
    """Scheduler settings."""

    enabled: bool = True
    interval_minutes: int = 15


class EPGSettingsModel(BaseModel):
    """EPG generation settings."""

    team_schedule_days_ahead: int = 30
    event_match_days_ahead: int = 7
    epg_output_days_ahead: int = 14
    epg_lookback_hours: int = 6
    epg_timezone: str = "America/New_York"
    epg_output_path: str = "./teamarr.xml"
    include_final_events: bool = False
    midnight_crossover_mode: str = "postgame"
    cron_expression: str = "0 * * * *"


class DurationSettingsModel(BaseModel):
    """Game duration settings (in hours)."""

    default: float = 3.0
    basketball: float = 3.0
    football: float = 3.5
    hockey: float = 3.0
    baseball: float = 3.5
    soccer: float = 2.5
    mma: float = 5.0
    rugby: float = 2.5
    boxing: float = 4.0
    tennis: float = 3.0
    golf: float = 6.0
    racing: float = 3.0
    cricket: float = 4.0


class DisplaySettingsModel(BaseModel):
    """Display and formatting settings."""

    time_format: str = "12h"
    show_timezone: bool = True
    channel_id_format: str = "{team_name_pascal}.{league}"
    xmltv_generator_name: str = "Teamarr v2"
    xmltv_generator_url: str = ""


class AllSettingsModel(BaseModel):
    """Complete application settings."""

    dispatcharr: DispatcharrSettingsModel
    lifecycle: LifecycleSettingsModel
    reconciliation: ReconciliationSettingsModel
    scheduler: SchedulerSettingsModel
    epg: EPGSettingsModel
    durations: DurationSettingsModel
    display: DisplaySettingsModel
    epg_generation_counter: int = 0
    schema_version: int = 2


class ConnectionTestRequest(BaseModel):
    """Request to test Dispatcharr connection."""

    url: str | None = Field(None, description="Override URL (uses saved if not provided)")
    username: str | None = Field(None, description="Override username")
    password: str | None = Field(None, description="Override password")


class ConnectionTestResponse(BaseModel):
    """Response from connection test."""

    success: bool
    url: str | None = None
    username: str | None = None
    version: str | None = None
    channel_count: int | None = None
    error: str | None = None


class SchedulerStatusResponse(BaseModel):
    """Scheduler status response."""

    running: bool
    last_run: str | None = None
    interval_minutes: int | None = None


# =============================================================================
# SETTINGS ENDPOINTS
# =============================================================================


@router.get("/settings", response_model=AllSettingsModel)
def get_settings():
    """Get all application settings."""
    from teamarr.database.settings import get_all_settings

    with get_db() as conn:
        settings = get_all_settings(conn)

    return AllSettingsModel(
        dispatcharr=DispatcharrSettingsModel(
            enabled=settings.dispatcharr.enabled,
            url=settings.dispatcharr.url,
            username=settings.dispatcharr.username,
            password="********" if settings.dispatcharr.password else None,
            epg_id=settings.dispatcharr.epg_id,
        ),
        lifecycle=LifecycleSettingsModel(
            channel_create_timing=settings.lifecycle.channel_create_timing,
            channel_delete_timing=settings.lifecycle.channel_delete_timing,
            channel_range_start=settings.lifecycle.channel_range_start,
            channel_range_end=settings.lifecycle.channel_range_end,
        ),
        reconciliation=ReconciliationSettingsModel(
            reconcile_on_epg_generation=settings.reconciliation.reconcile_on_epg_generation,
            reconcile_on_startup=settings.reconciliation.reconcile_on_startup,
            auto_fix_orphan_teamarr=settings.reconciliation.auto_fix_orphan_teamarr,
            auto_fix_orphan_dispatcharr=settings.reconciliation.auto_fix_orphan_dispatcharr,
            auto_fix_duplicates=settings.reconciliation.auto_fix_duplicates,
            default_duplicate_event_handling=settings.reconciliation.default_duplicate_event_handling,
            channel_history_retention_days=settings.reconciliation.channel_history_retention_days,
        ),
        scheduler=SchedulerSettingsModel(
            enabled=settings.scheduler.enabled,
            interval_minutes=settings.scheduler.interval_minutes,
        ),
        epg=EPGSettingsModel(
            team_schedule_days_ahead=settings.epg.team_schedule_days_ahead,
            event_match_days_ahead=settings.epg.event_match_days_ahead,
            epg_output_days_ahead=settings.epg.epg_output_days_ahead,
            epg_lookback_hours=settings.epg.epg_lookback_hours,
            epg_timezone=settings.epg.epg_timezone,
            epg_output_path=settings.epg.epg_output_path,
            include_final_events=settings.epg.include_final_events,
            midnight_crossover_mode=settings.epg.midnight_crossover_mode,
            cron_expression=settings.epg.cron_expression,
        ),
        durations=DurationSettingsModel(
            default=settings.durations.default,
            basketball=settings.durations.basketball,
            football=settings.durations.football,
            hockey=settings.durations.hockey,
            baseball=settings.durations.baseball,
            soccer=settings.durations.soccer,
            mma=settings.durations.mma,
            rugby=settings.durations.rugby,
            boxing=settings.durations.boxing,
            tennis=settings.durations.tennis,
            golf=settings.durations.golf,
            racing=settings.durations.racing,
            cricket=settings.durations.cricket,
        ),
        display=DisplaySettingsModel(
            time_format=settings.display.time_format,
            show_timezone=settings.display.show_timezone,
            channel_id_format=settings.display.channel_id_format,
            xmltv_generator_name=settings.display.xmltv_generator_name,
            xmltv_generator_url=settings.display.xmltv_generator_url,
        ),
        epg_generation_counter=settings.epg_generation_counter,
        schema_version=settings.schema_version,
    )


# =============================================================================
# DISPATCHARR SETTINGS
# =============================================================================


@router.get("/settings/dispatcharr", response_model=DispatcharrSettingsModel)
def get_dispatcharr_settings():
    """Get Dispatcharr integration settings."""
    from teamarr.database.settings import get_dispatcharr_settings

    with get_db() as conn:
        settings = get_dispatcharr_settings(conn)

    return DispatcharrSettingsModel(
        enabled=settings.enabled,
        url=settings.url,
        username=settings.username,
        password="********" if settings.password else None,
        epg_id=settings.epg_id,
    )


@router.put("/settings/dispatcharr", response_model=DispatcharrSettingsModel)
def update_dispatcharr_settings(update: DispatcharrSettingsUpdate):
    """Update Dispatcharr integration settings."""
    from teamarr.database.settings import (
        get_dispatcharr_settings,
        update_dispatcharr_settings,
    )
    from teamarr.dispatcharr import get_factory

    with get_db() as conn:
        update_dispatcharr_settings(
            conn,
            enabled=update.enabled,
            url=update.url,
            username=update.username,
            password=update.password,
            epg_id=update.epg_id,
        )

    # Trigger reconnect on next use
    try:
        factory = get_factory()
        factory.reconnect()
    except Exception:
        pass  # Factory may not be initialized yet

    # Return updated settings
    with get_db() as conn:
        settings = get_dispatcharr_settings(conn)

    return DispatcharrSettingsModel(
        enabled=settings.enabled,
        url=settings.url,
        username=settings.username,
        password="********" if settings.password else None,
        epg_id=settings.epg_id,
    )


@router.post("/dispatcharr/test", response_model=ConnectionTestResponse)
def test_dispatcharr_connection(request: ConnectionTestRequest | None = None):
    """Test connection to Dispatcharr.

    If no parameters provided, tests with saved settings.
    """
    from teamarr.dispatcharr import get_factory

    try:
        factory = get_factory(get_db)
    except RuntimeError:
        # Factory not initialized, create one
        from teamarr.dispatcharr.factory import DispatcharrFactory

        factory = DispatcharrFactory(get_db)

    if request:
        result = factory.test_connection(
            url=request.url,
            username=request.username,
            password=request.password,
        )
    else:
        result = factory.test_connection()

    return ConnectionTestResponse(
        success=result.success,
        url=result.url,
        username=result.username,
        version=result.version,
        channel_count=result.channel_count,
        error=result.error,
    )


@router.get("/dispatcharr/status")
def get_dispatcharr_status() -> dict:
    """Get current Dispatcharr connection status."""
    from teamarr.dispatcharr import get_factory

    try:
        factory = get_factory(get_db)
        return {
            "configured": factory.is_configured,
            "connected": factory.is_connected,
        }
    except RuntimeError:
        return {
            "configured": False,
            "connected": False,
        }


# =============================================================================
# LIFECYCLE SETTINGS
# =============================================================================


@router.get("/settings/lifecycle", response_model=LifecycleSettingsModel)
def get_lifecycle_settings():
    """Get channel lifecycle settings."""
    from teamarr.database.settings import get_lifecycle_settings

    with get_db() as conn:
        settings = get_lifecycle_settings(conn)

    return LifecycleSettingsModel(
        channel_create_timing=settings.channel_create_timing,
        channel_delete_timing=settings.channel_delete_timing,
        channel_range_start=settings.channel_range_start,
        channel_range_end=settings.channel_range_end,
    )


@router.put("/settings/lifecycle", response_model=LifecycleSettingsModel)
def update_lifecycle_settings(update: LifecycleSettingsModel):
    """Update channel lifecycle settings."""
    from teamarr.database.settings import (
        get_lifecycle_settings,
        update_lifecycle_settings,
    )

    # Validate timing values
    valid_create = {
        "stream_available",
        "same_day",
        "day_before",
        "2_days_before",
        "3_days_before",
        "1_week_before",
        "manual",
    }
    valid_delete = {
        "stream_removed",
        "same_day",
        "day_after",
        "2_days_after",
        "3_days_after",
        "1_week_after",
        "manual",
    }

    if update.channel_create_timing not in valid_create:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid channel_create_timing. Valid: {valid_create}",
        )
    if update.channel_delete_timing not in valid_delete:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid channel_delete_timing. Valid: {valid_delete}",
        )

    with get_db() as conn:
        update_lifecycle_settings(
            conn,
            channel_create_timing=update.channel_create_timing,
            channel_delete_timing=update.channel_delete_timing,
            channel_range_start=update.channel_range_start,
            channel_range_end=update.channel_range_end,
        )

    with get_db() as conn:
        settings = get_lifecycle_settings(conn)

    return LifecycleSettingsModel(
        channel_create_timing=settings.channel_create_timing,
        channel_delete_timing=settings.channel_delete_timing,
        channel_range_start=settings.channel_range_start,
        channel_range_end=settings.channel_range_end,
    )


# =============================================================================
# SCHEDULER SETTINGS & CONTROL
# =============================================================================


@router.get("/settings/scheduler", response_model=SchedulerSettingsModel)
def get_scheduler_settings():
    """Get scheduler settings."""
    from teamarr.database.settings import get_scheduler_settings

    with get_db() as conn:
        settings = get_scheduler_settings(conn)

    return SchedulerSettingsModel(
        enabled=settings.enabled,
        interval_minutes=settings.interval_minutes,
    )


@router.put("/settings/scheduler", response_model=SchedulerSettingsModel)
def update_scheduler_settings(update: SchedulerSettingsModel):
    """Update scheduler settings."""
    from teamarr.database.settings import (
        get_scheduler_settings,
        update_scheduler_settings,
    )

    if update.interval_minutes < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="interval_minutes must be at least 1",
        )

    with get_db() as conn:
        update_scheduler_settings(
            conn,
            enabled=update.enabled,
            interval_minutes=update.interval_minutes,
        )

    with get_db() as conn:
        settings = get_scheduler_settings(conn)

    return SchedulerSettingsModel(
        enabled=settings.enabled,
        interval_minutes=settings.interval_minutes,
    )


@router.get("/scheduler/status", response_model=SchedulerStatusResponse)
def get_scheduler_status():
    """Get current scheduler status."""
    from teamarr.consumers import get_scheduler_status

    status = get_scheduler_status()

    return SchedulerStatusResponse(
        running=status.get("running", False),
        last_run=status.get("last_run"),
        interval_minutes=status.get("interval_minutes"),
    )


@router.post("/scheduler/run")
def trigger_scheduler_run() -> dict:
    """Manually trigger a scheduler run."""
    from teamarr.consumers import LifecycleScheduler
    from teamarr.dispatcharr import get_dispatcharr_client

    try:
        client = get_dispatcharr_client(get_db)
    except Exception:
        client = None

    scheduler = LifecycleScheduler(
        db_factory=get_db,
        dispatcharr_client=client,
    )

    results = scheduler.run_once()

    return {
        "success": True,
        "results": results,
    }


# =============================================================================
# EPG SETTINGS
# =============================================================================


@router.get("/settings/epg", response_model=EPGSettingsModel)
def get_epg_settings():
    """Get EPG generation settings."""
    from teamarr.database.settings import get_epg_settings

    with get_db() as conn:
        settings = get_epg_settings(conn)

    return EPGSettingsModel(
        team_schedule_days_ahead=settings.team_schedule_days_ahead,
        event_match_days_ahead=settings.event_match_days_ahead,
        epg_output_days_ahead=settings.epg_output_days_ahead,
        epg_lookback_hours=settings.epg_lookback_hours,
        epg_timezone=settings.epg_timezone,
        epg_output_path=settings.epg_output_path,
        include_final_events=settings.include_final_events,
        midnight_crossover_mode=settings.midnight_crossover_mode,
        cron_expression=settings.cron_expression,
    )


@router.put("/settings/epg", response_model=EPGSettingsModel)
def update_epg_settings(update: EPGSettingsModel):
    """Update EPG generation settings."""
    from teamarr.database.settings import get_epg_settings, update_epg_settings

    with get_db() as conn:
        update_epg_settings(
            conn,
            team_schedule_days_ahead=update.team_schedule_days_ahead,
            event_match_days_ahead=update.event_match_days_ahead,
            epg_output_days_ahead=update.epg_output_days_ahead,
            epg_lookback_hours=update.epg_lookback_hours,
            epg_timezone=update.epg_timezone,
            epg_output_path=update.epg_output_path,
            include_final_events=update.include_final_events,
            midnight_crossover_mode=update.midnight_crossover_mode,
            cron_expression=update.cron_expression,
        )

    with get_db() as conn:
        settings = get_epg_settings(conn)

    return EPGSettingsModel(
        team_schedule_days_ahead=settings.team_schedule_days_ahead,
        event_match_days_ahead=settings.event_match_days_ahead,
        epg_output_days_ahead=settings.epg_output_days_ahead,
        epg_lookback_hours=settings.epg_lookback_hours,
        epg_timezone=settings.epg_timezone,
        epg_output_path=settings.epg_output_path,
        include_final_events=settings.include_final_events,
        midnight_crossover_mode=settings.midnight_crossover_mode,
        cron_expression=settings.cron_expression,
    )


# =============================================================================
# DURATION SETTINGS
# =============================================================================


@router.get("/settings/durations", response_model=DurationSettingsModel)
def get_duration_settings():
    """Get game duration settings."""
    from teamarr.database.settings import get_all_settings

    with get_db() as conn:
        settings = get_all_settings(conn)

    return DurationSettingsModel(
        default=settings.durations.default,
        basketball=settings.durations.basketball,
        football=settings.durations.football,
        hockey=settings.durations.hockey,
        baseball=settings.durations.baseball,
        soccer=settings.durations.soccer,
        mma=settings.durations.mma,
        rugby=settings.durations.rugby,
        boxing=settings.durations.boxing,
        tennis=settings.durations.tennis,
        golf=settings.durations.golf,
        racing=settings.durations.racing,
        cricket=settings.durations.cricket,
    )


@router.put("/settings/durations", response_model=DurationSettingsModel)
def update_duration_settings(update: DurationSettingsModel):
    """Update game duration settings."""
    from teamarr.database.settings import get_all_settings, update_duration_settings

    with get_db() as conn:
        update_duration_settings(
            conn,
            default=update.default,
            basketball=update.basketball,
            football=update.football,
            hockey=update.hockey,
            baseball=update.baseball,
            soccer=update.soccer,
            mma=update.mma,
            rugby=update.rugby,
            boxing=update.boxing,
            tennis=update.tennis,
            golf=update.golf,
            racing=update.racing,
            cricket=update.cricket,
        )

    with get_db() as conn:
        settings = get_all_settings(conn)

    return DurationSettingsModel(
        default=settings.durations.default,
        basketball=settings.durations.basketball,
        football=settings.durations.football,
        hockey=settings.durations.hockey,
        baseball=settings.durations.baseball,
        soccer=settings.durations.soccer,
        mma=settings.durations.mma,
        rugby=settings.durations.rugby,
        boxing=settings.durations.boxing,
        tennis=settings.durations.tennis,
        golf=settings.durations.golf,
        racing=settings.durations.racing,
        cricket=settings.durations.cricket,
    )


# =============================================================================
# RECONCILIATION SETTINGS
# =============================================================================


@router.get("/settings/reconciliation", response_model=ReconciliationSettingsModel)
def get_reconciliation_settings():
    """Get reconciliation settings."""
    from teamarr.database.settings import get_all_settings

    with get_db() as conn:
        settings = get_all_settings(conn)

    return ReconciliationSettingsModel(
        reconcile_on_epg_generation=settings.reconciliation.reconcile_on_epg_generation,
        reconcile_on_startup=settings.reconciliation.reconcile_on_startup,
        auto_fix_orphan_teamarr=settings.reconciliation.auto_fix_orphan_teamarr,
        auto_fix_orphan_dispatcharr=settings.reconciliation.auto_fix_orphan_dispatcharr,
        auto_fix_duplicates=settings.reconciliation.auto_fix_duplicates,
        default_duplicate_event_handling=settings.reconciliation.default_duplicate_event_handling,
        channel_history_retention_days=settings.reconciliation.channel_history_retention_days,
    )


@router.put("/settings/reconciliation", response_model=ReconciliationSettingsModel)
def update_reconciliation_settings(update: ReconciliationSettingsModel):
    """Update reconciliation settings."""
    from teamarr.database.settings import (
        get_all_settings,
        update_reconciliation_settings,
    )

    valid_modes = {"consolidate", "separate", "ignore"}
    if update.default_duplicate_event_handling not in valid_modes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid duplicate handling mode. Valid: {valid_modes}",
        )

    with get_db() as conn:
        update_reconciliation_settings(
            conn,
            reconcile_on_epg_generation=update.reconcile_on_epg_generation,
            reconcile_on_startup=update.reconcile_on_startup,
            auto_fix_orphan_teamarr=update.auto_fix_orphan_teamarr,
            auto_fix_orphan_dispatcharr=update.auto_fix_orphan_dispatcharr,
            auto_fix_duplicates=update.auto_fix_duplicates,
            default_duplicate_event_handling=update.default_duplicate_event_handling,
            channel_history_retention_days=update.channel_history_retention_days,
        )

    with get_db() as conn:
        settings = get_all_settings(conn)

    return ReconciliationSettingsModel(
        reconcile_on_epg_generation=settings.reconciliation.reconcile_on_epg_generation,
        reconcile_on_startup=settings.reconciliation.reconcile_on_startup,
        auto_fix_orphan_teamarr=settings.reconciliation.auto_fix_orphan_teamarr,
        auto_fix_orphan_dispatcharr=settings.reconciliation.auto_fix_orphan_dispatcharr,
        auto_fix_duplicates=settings.reconciliation.auto_fix_duplicates,
        default_duplicate_event_handling=settings.reconciliation.default_duplicate_event_handling,
        channel_history_retention_days=settings.reconciliation.channel_history_retention_days,
    )
