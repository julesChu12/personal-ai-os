from typing import Any


def scheduler_status(scheduler: Any) -> dict[str, Any]:
    """Return read-only scheduler state suitable for diagnostics APIs."""
    if scheduler is None:
        return {"running": False, "jobs": []}

    jobs = []
    get_jobs = getattr(scheduler, "get_jobs", None)
    if callable(get_jobs):
        for job in get_jobs():
            next_run_time = getattr(job, "next_run_time", None)
            jobs.append(
                {
                    "id": getattr(job, "id", None),
                    "next_run_time": next_run_time.isoformat() if hasattr(next_run_time, "isoformat") else next_run_time,
                    "trigger": str(getattr(job, "trigger", "")),
                }
            )

    return {
        "running": bool(getattr(scheduler, "running", False)),
        "jobs": jobs,
    }
