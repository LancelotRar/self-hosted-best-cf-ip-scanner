"""总览路由：扫描器状态、上次结果、下次执行与生效配置摘要。

容器不可用不返回 500：总览必须能打开，并明确告诉用户"为什么不可用"。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from scanner.schema import BY_NAME

from .. import config_store, runs_store
from ..deps import controller_of, settings_of
from ..docker_api import ScannerUnavailable
from ..security import require_user

router = APIRouter(prefix="/api/overview", tags=["overview"])

SUMMARY_KEYS = (
    "PROBE_HOST",
    "PROBE_PORTS",
    "PROBE_CONCURRENCY",
    "MAX_CANDIDATES",
    "CRON_SCHEDULE",
    "GIT_PUSH_ENABLED",
)


def _scanner_status(request: Request) -> dict[str, object]:
    controller = controller_of(request)
    if controller is None:
        return {"state": "unavailable", "reason": "扫描容器不可用（docker.sock 不可达）"}
    try:
        return controller.status()
    except ScannerUnavailable as exc:
        return {"state": "unavailable", "reason": str(exc)}


def _next_runs(document) -> list[str]:
    from ..cron import CronInvalid, next_runs

    expression = document.values.get("CRON_SCHEDULE") or str(
        BY_NAME["CRON_SCHEDULE"].default
    )
    timezone_name = document.values.get("TZ") or str(BY_NAME["TZ"].default)
    try:
        return [run.isoformat() for run in next_runs(expression, timezone_name, count=5)]
    except CronInvalid:
        return []


@router.get("", dependencies=[Depends(require_user)])
def overview(request: Request) -> dict[str, object]:
    settings = settings_of(request)
    document = config_store.read_env(settings)
    entries = {param["name"]: param for param in config_store.param_entries(document)}

    finished = [
        record
        for record in runs_store.parse(runs_store.runs_path(settings))
        if record.finished_at
    ]
    return {
        "scanner": _scanner_status(request),
        "running": runs_store.scan_lock_held(settings),
        "last_run": finished[-1].to_dict() if finished else None,
        "next_runs": _next_runs(document),
        "config_summary": {
            name: entries[name]["value"] for name in SUMMARY_KEYS if name in entries
        },
    }
