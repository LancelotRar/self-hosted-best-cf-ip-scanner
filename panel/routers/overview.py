"""总览路由：扫描器状态、上次结果、下次执行与生效配置摘要。

容器不可用不返回 500：总览必须能打开，并明确告诉用户"为什么不可用"。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from scanner.schema import BY_NAME

from .. import artifacts_store, config_store, runs_store
from ..cron import CronInvalid, next_runs
from ..deps import controller_of, settings_of
from ..docker_api import ScannerUnavailable
from ..security import require_user

router = APIRouter(prefix="/api/overview", tags=["overview"])

SUMMARY_KEYS = (
    "PROBE_HOST",
    "PROBE_PORTS",
    "PROBE_CONCURRENCY",
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


def _schedule(document) -> dict[str, object]:
    """把计划相关字段收在一处，前端不再为了时间/时区再拉一次配置。"""
    expression = str(
        document.values.get("CRON_SCHEDULE") or BY_NAME["CRON_SCHEDULE"].default
    )
    timezone_name = str(document.values.get("TZ") or BY_NAME["TZ"].default)
    try:
        runs = [run.isoformat() for run in next_runs(expression, timezone_name, count=5)]
    except CronInvalid:
        runs = []
    return {
        "cron": expression,
        "tz": timezone_name,
        "enabled": bool(expression.strip()),
        "next_runs": runs,
    }


def _value(entries: dict[str, dict], name: str) -> object:
    entry = entries.get(name)
    return entry["value"] if entry else None


@router.get("", dependencies=[Depends(require_user)])
def overview(request: Request) -> dict[str, object]:
    settings = settings_of(request)
    document = config_store.read_config(request.app.state.conn, settings)
    entries = {param["name"]: param for param in config_store.param_entries(document)}
    schedule = _schedule(document)
    timezone_name = str(schedule["tz"])

    lock_held = runs_store.scan_lock_held(settings)
    path = runs_store.runs_path(settings)
    runs_store.sync(request.app.state.conn, path)
    active_ids = {
        run_id
        for run_id, handle in request.app.state.active_runs.items()
        if not getattr(handle, "finished", False)
    }
    decorated = runs_store.attach_metrics(
        settings,
        runs_store.with_status(runs_store.parse(path), lock_held, active_ids),
    )
    decorated.sort(key=lambda record: str(record.get("started_at") or ""))
    finished = [record for record in decorated if record.get("finished_at")]
    last_run = finished[-1] if finished else None
    publish_last = next(
        (record for record in reversed(finished) if record.get("publish_exit") is not None),
        None,
    )

    artifacts_store.sync(request.app.state.conn, settings)
    files = artifacts_store.list_rows(request.app.state.conn)
    detail = next((row for row in files if row.get("kind") == "csv"), None)
    updated_at = max((str(row["mtime"]) for row in files), default=None)

    return {
        "scanner": _scanner_status(request),
        "running": lock_held,
        "last_run": last_run,
        "next_runs": schedule["next_runs"],
        "timezone": timezone_name,
        "schedule": schedule,
        "publish": {
            "enabled": _value(entries, "GIT_PUSH_ENABLED") is True,
            "repo_url": _value(entries, "GIT_REPO_URL"),
            "branch": _value(entries, "GIT_BRANCH"),
            "subdir": _value(entries, "GIT_OUTPUT_SUBDIR"),
            "last": publish_last,
        },
        "recent_runs": list(reversed(decorated[-10:])),
        "artifacts": {
            "count": len(files),
            "files": files,
            "detail": detail,
            "qualified": detail["count"] if detail else None,
            "updated_at": updated_at,
        },
        "config_summary": {
            name: _value(entries, name) for name in SUMMARY_KEYS if name in entries
        },
    }
