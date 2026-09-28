from fastapi import APIRouter, Depends
from datetime import datetime, timezone
from pydantic import BaseModel
from sqlalchemy import text
from backend.database import get_db


router = APIRouter(prefix="/api/pipeline", tags=["Pipeline Operations"])


class PipelineStatusResponse(BaseModel):
    last_run_time: str
    lead_count_processed: int
    status: str
    errors_encountered: bool


@router.get("/status", response_model=PipelineStatusResponse)
@router.head("/status")
def get_pipeline_telemetry(db=Depends(get_db)):
    """Returns background execution metrics to frontend status layouts."""
    try:
        row = db.execute(
            text(
                "SELECT last_run_time, (SELECT COUNT(*) FROM lead_snapshots), status, errors_encountered "
                "FROM pipeline_status WHERE id='1'"
            )
        ).fetchone()
        if row:
            return PipelineStatusResponse(
                last_run_time=row[0],
                lead_count_processed=row[1] if row[1] else 0,
                status=row[2] if row[2] else "Unknown",
                errors_encountered=bool(row[3]) if row[3] is not None else False
            )
    except Exception:
        pass

    return PipelineStatusResponse(
        last_run_time="Never",
        lead_count_processed=0,
        status="Idle (No runs)",
        errors_encountered=False
    )


@router.post("/run-test")
async def trigger_ui_pipeline_test():
    """
    Triggered when user clicks 'Run Pipeline Test' on the UI.
    Fetches 5 candidates from Airtable starting at current_offset,
    advances current_offset by 5, and processes batch through 3-stage pipeline.
    """
    from backend.pipeline.streaming_orchestrator import trigger_ui_test_run
    res = await trigger_ui_test_run(limit=5)
    return res

@router.get("/cursor-status")
def get_cursor_status():
    """Returns local offset cursor state from pipeline_state.json."""
    from backend.pipeline.airtable_connector import load_pipeline_state
    state = load_pipeline_state()
    return state

@router.post("/cron/midnight")
async def trigger_cron_endpoint():
    """Manually triggers the 2:00 AM midnight cron pipeline sweep (20 companies quota)."""
    from backend.pipeline.streaming_orchestrator import trigger_midnight_cron_run
    res = await trigger_midnight_cron_run(daily_quota=20)
    return res

@router.post("/track-jobs/run-day1")
async def trigger_track_jobs_day1():
    """Manually trigger the first Track Jobs acquisition run."""
    from backend.pipeline.job_pipeline import fetch_day1_jobs

    jobs = await fetch_day1_jobs()

    return {
        "status": "success",
        "qualified_jobs": len(jobs),
        "message": f"Day 1 Track Jobs run completed. {len(jobs)} qualified jobs found."
    }