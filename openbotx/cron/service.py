from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from openbotx.cron.types import (
    CronJob,
    CronJobState,
    CronPayload,
    CronSchedule,
    CronStore,
)

logger = logging.getLogger(__name__)

TICK_INTERVAL = 5.0


class CronService:
    def __init__(
        self,
        workspace: Path,
        on_job_callback: Callable[[CronJob], Awaitable[None]] | None = None,
    ):
        self._workspace = workspace
        self._store_path = workspace / "cron_jobs.json"
        self._on_job_callback = on_job_callback
        self._store = CronStore()
        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()
        self._load()

    def _load(self) -> None:
        if not self._store_path.exists():
            return
        try:
            data = json.loads(self._store_path.read_text(encoding="utf-8"))
            jobs = []
            for jd in data.get("jobs", []):
                schedule = CronSchedule(
                    kind=jd.get("schedule", {}).get("kind", "every"),
                    at_ms=jd.get("schedule", {}).get("at_ms", 0),
                    every_ms=jd.get("schedule", {}).get("every_ms", 0),
                    expr=jd.get("schedule", {}).get("expr", ""),
                    tz=jd.get("schedule", {}).get("tz"),
                )
                payload = CronPayload(
                    message=jd.get("payload", {}).get("message", ""),
                    deliver=jd.get("payload", {}).get("deliver", True),
                    channel=jd.get("payload", {}).get("channel", ""),
                    to=jd.get("payload", {}).get("to", ""),
                )
                state = CronJobState(
                    next_run_ms=jd.get("state", {}).get("next_run_ms", 0),
                    last_run_ms=jd.get("state", {}).get("last_run_ms", 0),
                    status=jd.get("state", {}).get("status", "pending"),
                    run_count=jd.get("state", {}).get("run_count", 0),
                    errors=jd.get("state", {}).get("errors", 0),
                )
                job = CronJob(
                    id=jd.get("id", ""),
                    name=jd.get("name", ""),
                    schedule=schedule,
                    payload=payload,
                    state=state,
                    delete_after_run=jd.get("delete_after_run", False),
                )
                jobs.append(job)
            self._store.jobs = jobs
        except Exception as e:
            logger.warning("failed to load cron jobs: %s", e)

    def _persist(self) -> None:
        self._store_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "version": self._store.version,
            "jobs": [self._job_to_dict(j) for j in self._store.jobs],
        }
        self._store_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    @staticmethod
    def _job_to_dict(job: CronJob) -> dict[str, Any]:
        return {
            "id": job.id,
            "name": job.name,
            "schedule": {
                "kind": job.schedule.kind,
                "at_ms": job.schedule.at_ms,
                "every_ms": job.schedule.every_ms,
                "expr": job.schedule.expr,
                "tz": job.schedule.tz,
            },
            "payload": {
                "message": job.payload.message,
                "deliver": job.payload.deliver,
                "channel": job.payload.channel,
                "to": job.payload.to,
            },
            "state": {
                "next_run_ms": job.state.next_run_ms,
                "last_run_ms": job.state.last_run_ms,
                "status": job.state.status,
                "run_count": job.state.run_count,
                "errors": job.state.errors,
            },
            "delete_after_run": job.delete_after_run,
        }

    def _compute_next_run_ms(self, schedule: CronSchedule) -> int:
        now_ms = int(time.time() * 1000)

        if schedule.kind == "at":
            return schedule.at_ms

        if schedule.kind == "every":
            return now_ms + schedule.every_ms

        if schedule.kind == "cron":
            try:
                from zoneinfo import ZoneInfo

                from croniter import croniter

                if schedule.tz:
                    tz = ZoneInfo(schedule.tz)
                    now = datetime.now(tz)
                else:
                    now = datetime.now()

                cron = croniter(schedule.expr, now)
                next_dt = cron.get_next(datetime)
                return int(next_dt.timestamp() * 1000)
            except Exception as e:
                logger.warning("failed to compute next cron run: %s", e)
                return now_ms + 60000

        return now_ms + 60000

    def add_job(
        self,
        name: str,
        schedule: CronSchedule,
        message: str,
        deliver: bool = True,
        channel: str = "",
        to: str = "",
        delete_after_run: bool = False,
    ) -> CronJob:
        job = CronJob(
            id=str(uuid.uuid4())[:8],
            name=name,
            schedule=schedule,
            payload=CronPayload(
                message=message,
                deliver=deliver,
                channel=channel,
                to=to,
            ),
            state=CronJobState(
                next_run_ms=self._compute_next_run_ms(schedule),
                status="active",
            ),
            delete_after_run=delete_after_run,
        )
        self._store.jobs.append(job)
        self._persist()
        logger.info("cron job added: %s (id: %s)", name, job.id)
        return job

    def remove_job(self, job_id: str) -> bool:
        before = len(self._store.jobs)
        self._store.jobs = [j for j in self._store.jobs if j.id != job_id]
        if len(self._store.jobs) < before:
            self._persist()
            logger.info("cron job removed: %s", job_id)
            return True
        return False

    def list_jobs(self) -> list[CronJob]:
        return list(self._store.jobs)

    async def run(self) -> None:
        logger.info("cron service started (%d jobs)", len(self._store.jobs))
        while not self._stop_event.is_set():
            try:
                await asyncio.sleep(TICK_INTERVAL)
                await self._tick()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("cron tick error: %s", e, exc_info=True)

    async def _tick(self) -> None:
        now_ms = int(time.time() * 1000)
        to_delete: list[str] = []

        for job in self._store.jobs:
            if job.state.status != "active":
                continue
            if job.state.next_run_ms > now_ms:
                continue

            logger.info("executing cron job: %s (id: %s)", job.name, job.id)

            try:
                if self._on_job_callback:
                    await self._on_job_callback(job)

                job.state.last_run_ms = now_ms
                job.state.run_count += 1

                if job.delete_after_run:
                    to_delete.append(job.id)
                else:
                    job.state.next_run_ms = self._compute_next_run_ms(job.schedule)

            except Exception as e:
                logger.error("cron job %s failed: %s", job.id, e)
                job.state.errors += 1

        for job_id in to_delete:
            self._store.jobs = [j for j in self._store.jobs if j.id != job_id]

        if to_delete or any(
            j.state.last_run_ms == int(time.time() * 1000) for j in self._store.jobs
        ):
            self._persist()

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("cron service stopped")
