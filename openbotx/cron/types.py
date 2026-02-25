from dataclasses import dataclass, field


@dataclass
class CronSchedule:
    kind: str = "every"  # "at", "every", "cron"
    at_ms: int = 0
    every_ms: int = 0
    expr: str = ""
    tz: str | None = None


@dataclass
class CronPayload:
    message: str = ""
    deliver: bool = True
    channel: str = ""
    to: str = ""


@dataclass
class CronJobState:
    next_run_ms: int = 0
    last_run_ms: int = 0
    status: str = "pending"
    run_count: int = 0
    errors: int = 0


@dataclass
class CronJob:
    id: str = ""
    name: str = ""
    schedule: CronSchedule = field(default_factory=CronSchedule)
    payload: CronPayload = field(default_factory=CronPayload)
    state: CronJobState = field(default_factory=CronJobState)
    delete_after_run: bool = False


@dataclass
class CronStore:
    version: int = 1
    jobs: list[CronJob] = field(default_factory=list)
