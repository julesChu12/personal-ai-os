from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes_scheduler import router
from app.scheduler.status import scheduler_status


def test_scheduler_status_reports_absent_scheduler():
    assert scheduler_status(None) == {"running": False, "jobs": []}


def test_scheduler_status_serializes_jobs():
    next_run_time = datetime(2026, 5, 7, 12, 0, tzinfo=UTC)
    scheduler = SimpleNamespace(
        running=True,
        get_jobs=lambda: [
            SimpleNamespace(id="daily_memory_job", next_run_time=next_run_time, trigger="interval[24:00:00]")
        ],
    )

    result = scheduler_status(scheduler)

    assert result["running"] is True
    assert result["jobs"] == [
        {
            "id": "daily_memory_job",
            "next_run_time": "2026-05-07T12:00:00+00:00",
            "trigger": "interval[24:00:00]",
        }
    ]


def test_scheduler_status_route_reads_app_state():
    scheduler = SimpleNamespace(running=True, get_jobs=lambda: [])
    app = FastAPI()
    app.state.scheduler = scheduler
    app.include_router(router)

    response = TestClient(app).get("/scheduler/status")

    assert response.status_code == 200
    assert response.json() == {"running": True, "jobs": []}
