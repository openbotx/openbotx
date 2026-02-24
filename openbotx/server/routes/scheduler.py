from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter()


class JobCreate(BaseModel):
    name: str
    message: str
    cron_expr: str = ""
    every_seconds: int = 0
    at: str = ""
    timezone: str = ""
    channel: str = ""
    to: str = ""


@router.get("/jobs")
async def list_jobs(request: Request):
    cron_service = request.app.state.cron_service
    jobs = cron_service.list_jobs()
    return [
        {
            "id": j.id,
            "name": j.name,
            "schedule": {
                "kind": j.schedule.kind,
                "expr": j.schedule.expr,
                "every_ms": j.schedule.every_ms,
                "at_ms": j.schedule.at_ms,
                "tz": j.schedule.tz,
            },
            "payload": {
                "message": j.payload.message,
                "channel": j.payload.channel,
                "to": j.payload.to,
            },
            "state": {
                "status": j.state.status,
                "next_run_ms": j.state.next_run_ms,
                "last_run_ms": j.state.last_run_ms,
                "run_count": j.state.run_count,
                "errors": j.state.errors,
            },
        }
        for j in jobs
    ]


@router.post("/jobs")
async def create_job(body: JobCreate, request: Request):
    cron_service = request.app.state.cron_service
    from openbotx.cron.types import CronSchedule

    schedule = CronSchedule()
    if body.cron_expr:
        schedule.kind = "cron"
        schedule.expr = body.cron_expr
    elif body.every_seconds > 0:
        schedule.kind = "every"
        schedule.every_ms = body.every_seconds * 1000
    elif body.at:
        schedule.kind = "at"
        from datetime import datetime

        dt = datetime.fromisoformat(body.at)
        schedule.at_ms = int(dt.timestamp() * 1000)

    if body.timezone:
        schedule.tz = body.timezone

    job = cron_service.add_job(
        name=body.name,
        schedule=schedule,
        message=body.message,
        channel=body.channel,
        to=body.to,
    )
    return {"status": "ok", "id": job.id}


@router.delete("/jobs/{job_id}")
async def delete_job(job_id: str, request: Request):
    cron_service = request.app.state.cron_service
    removed = cron_service.remove_job(job_id)
    if not removed:
        return {"error": "Job not found"}
    return {"status": "deleted"}
