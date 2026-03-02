from typing import Any

from openbotx.cron.service import CronService
from openbotx.cron.types import CronSchedule
from openbotx.tools.base import Tool
from openbotx.tools.context import RequestContext


class CronTool(Tool):
    """Schedule reminders and recurring tasks."""

    name = "cron"
    description = "Schedule reminders and recurring tasks. Actions: add, list, remove."
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["add", "list", "remove"],
                "description": "Action to perform",
            },
            "message": {
                "type": "string",
                "description": "Reminder message (for add)",
            },
            "every_seconds": {
                "type": "integer",
                "description": "Interval in seconds (for recurring tasks)",
            },
            "cron_expr": {
                "type": "string",
                "description": "Cron expression like '0 9 * * *'",
            },
            "tz": {
                "type": "string",
                "description": "IANA timezone for cron expressions",
            },
            "at": {
                "type": "string",
                "description": "ISO datetime for one-time execution",
            },
            "job_id": {
                "type": "string",
                "description": "Job ID (for remove)",
            },
        },
        "required": ["action"],
    }

    def __init__(self, cron_service: CronService):
        self._cron = cron_service

    async def execute(
        self,
        action: str,
        message: str = "",
        every_seconds: int | None = None,
        cron_expr: str | None = None,
        tz: str | None = None,
        at: str | None = None,
        job_id: str | None = None,
        **kwargs: Any,
    ) -> str:
        ctx: RequestContext | None = kwargs.get("_context")
        if action == "add":
            return self._add_job(message, every_seconds, cron_expr, tz, at, ctx)
        if action == "list":
            return self._list_jobs()
        if action == "remove":
            return self._remove_job(job_id)
        return f"Unknown action: {action}"

    def _add_job(
        self,
        message: str,
        every_seconds: int | None,
        cron_expr: str | None,
        tz: str | None,
        at: str | None,
        ctx: RequestContext | None,
    ) -> str:
        channel = ctx.channel if ctx else ""
        chat_id = ctx.chat_id if ctx else ""

        if not message:
            return "Error: message is required for add"
        if not channel or not chat_id:
            return "Error: no session context (channel/chat_id)"
        if tz and not cron_expr:
            return "Error: tz can only be used with cron_expr"
        if tz:
            from zoneinfo import ZoneInfo

            try:
                ZoneInfo(tz)
            except (KeyError, Exception):
                return f"Error: unknown timezone '{tz}'"

        delete_after = False
        if every_seconds:
            schedule = CronSchedule(kind="every", every_ms=every_seconds * 1000)
        elif cron_expr:
            schedule = CronSchedule(kind="cron", expr=cron_expr, tz=tz)
        elif at:
            from datetime import datetime

            dt = datetime.fromisoformat(at)
            at_ms = int(dt.timestamp() * 1000)
            schedule = CronSchedule(kind="at", at_ms=at_ms)
            delete_after = True
        else:
            return "Error: either every_seconds, cron_expr, or at is required"

        job = self._cron.add_job(
            name=message[:30],
            schedule=schedule,
            message=message,
            deliver=True,
            channel=channel,
            to=chat_id,
            delete_after_run=delete_after,
        )
        return f"Created job '{job.name}' (id: {job.id})"

    def _list_jobs(self) -> str:
        jobs = self._cron.list_jobs()
        if not jobs:
            return "No scheduled jobs."
        lines = [f"- {j.name} (id: {j.id}, {j.schedule.kind})" for j in jobs]
        return "Scheduled jobs:\n" + "\n".join(lines)

    def _remove_job(self, job_id: str | None) -> str:
        if not job_id:
            return "Error: job_id is required for remove"
        if self._cron.remove_job(job_id):
            return f"Removed job {job_id}"
        return f"Job {job_id} not found"
