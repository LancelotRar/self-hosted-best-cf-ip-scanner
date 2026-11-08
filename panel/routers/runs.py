"""运行路由：手动触发一轮、历史轮次、实时输出。"""

from __future__ import annotations

import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from .. import runs_store
from ..audit import record as audit_record
from ..deps import controller_of, settings_of
from ..docker_api import ScannerUnavailable
from ..redact import redact_secrets
from ..security import client_ip, require_user, verify_csrf

router = APIRouter(prefix="/api/runs", tags=["runs"])

SCAN_SCRIPT = "/usr/local/bin/scan-and-publish.sh"


def _new_run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return f"{stamp}-{secrets.token_hex(2)}"


@router.get("", dependencies=[Depends(require_user)])
def list_runs(request: Request, limit: int = 50) -> dict[str, object]:
    settings = settings_of(request)
    path = runs_store.runs_path(settings)
    runs_store.sync(request.app.state.conn, path)
    records = runs_store.parse(path)[-max(1, min(limit, 200)):]
    active_ids = {
        run_id
        for run_id, handle in request.app.state.active_runs.items()
        if not getattr(handle, "finished", False)
    }
    decorated = runs_store.with_status(
        records, runs_store.scan_lock_held(settings), active_ids
    )
    return {"runs": list(reversed(decorated))}


def _run_env(settings, run_id: str) -> dict[str, str]:
    """面板触发的一轮只带轮次标识；参数由扫描器读取运行投影。"""
    return {"RUN_ID": run_id, "RUN_TRIGGER": "panel"}


@router.post(
    "", status_code=202, dependencies=[Depends(require_user), Depends(verify_csrf)]
)
def trigger_run(request: Request) -> dict[str, object]:
    settings = settings_of(request)
    if runs_store.scan_lock_held(settings):
        raise HTTPException(
            status_code=409,
            detail={"code": "run_in_progress", "message": "已有一轮扫描在运行，请稍后再试"},
        )
    controller = controller_of(request)
    if controller is None:
        raise HTTPException(
            status_code=503,
            detail={"code": "scanner_unavailable", "message": "扫描容器不可用"},
        )
    run_id = _new_run_id()
    try:
        handle = controller.exec_script(SCAN_SCRIPT, _run_env(settings, run_id))
    except ScannerUnavailable as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "scanner_unavailable", "message": str(exc)},
        ) from exc
    active = request.app.state.active_runs
    active[run_id] = handle
    for stale in list(active)[:-50]:
        active.pop(stale, None)
    audit_record(
        request.app.state.conn,
        "admin",
        "run.trigger",
        run_id,
        "手动触发一轮扫描",
        client_ip(request),
    )
    return {"run_id": run_id, "trigger": "panel"}


@router.get("/{run_id}/stream", dependencies=[Depends(require_user)])
def stream_run(run_id: str, request: Request, tail: int = 200):
    handle = request.app.state.active_runs.get(run_id)
    if handle is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "run_not_found", "message": "没有这个运行，可能已结束"},
        )

    def events():
        try:
            for chunk in handle.stream():
                text = redact_secrets(chunk.decode("utf-8", "replace").rstrip("\n"))
                if text:
                    yield {"event": "log", "data": text}
        except ScannerUnavailable as exc:
            yield {"event": "error", "data": str(exc)}
        yield {"event": "done", "data": str(handle.wait())}

    return EventSourceResponse(events())