from fastapi import APIRouter, Request

from app.scheduler.status import scheduler_status

router = APIRouter()


@router.get("/scheduler/status")
def status(request: Request):
    """Return read-only APScheduler runtime status."""
    scheduler = getattr(request.app.state, "scheduler", None)
    return scheduler_status(scheduler)
