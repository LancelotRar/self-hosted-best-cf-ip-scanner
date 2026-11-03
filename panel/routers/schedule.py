"""调度路由：cron 预览与热重载应用。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from ..config_store import APPLY_CONFIG_SCRIPT, read_env
from ..cron import CronInvalid, next_runs, validate
from ..deps import controller_of, settings_of
from ..docker_api import ScannerUnavailable
from ..security import require_user, verify_csrf

router = APIRouter(prefix="/api/schedule", tags=["schedule"])


def _effective_tz(request: Request) -> str:
    from scanner.schema import BY_NAME

    document = read_env(settings_of(request))
    return document.values.get("TZ") or str(BY_NAME["TZ"].default)


@router.get("/preview", dependencies=[Depends(require_user)])
def preview(request: Request, cron: str = "", tz: str | None = None) -> dict[str, object]:
    from scanner.schema import BY_NAME

    expression = cron.strip() or str(BY_NAME["CRON_SCHEDULE"].default)
    timezone_name = tz or _effective_tz(request)
    try:
        validate(expression, timezone_name)
        runs = next_runs(expression, timezone_name, count=5)
    except CronInvalid as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "cron_invalid", "message": str(exc)},
        ) from exc
    return {
        "cron": expression,
        "tz": timezone_name,
        "runs": [run.isoformat() for run in runs],
    }


@router.post("/apply", dependencies=[Depends(require_user), Depends(verify_csrf)])
def apply_schedule(request: Request) -> dict[str, object]:
    controller = controller_of(request)
    if controller is None:
        raise HTTPException(
            status_code=503,
            detail={"code": "scanner_unavailable", "message": "扫描容器不可用"},
        )
    try:
        handle = controller.exec_script(APPLY_CONFIG_SCRIPT, {})
        code = handle.wait()
    except ScannerUnavailable as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "scanner_unavailable", "message": str(exc)},
        ) from exc
    if code != 0:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "schedule_apply_failed",
                "message": "调度应用失败，旧 crontab 保持不变",
            },
        )
    return {"applied": True}
