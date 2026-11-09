"""系统路由：容器重启/停止/启动、版本信息。

危险操作必须带与服务端动作一致的 `X-Confirm` 头（前端二次确认后发送），
避免误点与 CSRF 组合造成的意外停服。
"""

from __future__ import annotations

import sys
from importlib.metadata import PackageNotFoundError, version

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from scanner.schema import BY_NAME

from .. import __version__ as panel_version
from .. import config_store
from ..audit import record as audit_record
from ..deps import controller_of, settings_of
from ..docker_api import ScannerUnavailable
from ..security import client_ip, require_user, verify_csrf

router = APIRouter(prefix="/api/system", tags=["system"])

ACTIONS = {"restart", "stop", "start"}


@router.post(
    "/{action}", status_code=202, dependencies=[Depends(require_user), Depends(verify_csrf)]
)
def operate(action: str, request: Request, response: Response) -> dict[str, object]:
    if action not in ACTIONS:
        raise HTTPException(
            status_code=404,
            detail={"code": "unknown_action", "message": f"不支持的操作：{action}"},
        )
    confirm = request.headers.get("X-Confirm", "")
    if confirm != action:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "confirm_required",
                "message": f"危险操作需要 X-Confirm: {action} 确认头",
            },
        )
    controller = controller_of(request)
    if controller is None:
        raise HTTPException(
            status_code=503,
            detail={"code": "scanner_unavailable", "message": "扫描容器不可用"},
        )
    try:
        if action == "restart":
            controller.restart()
        elif action == "stop":
            controller.stop()
        else:
            controller.start()
    except ScannerUnavailable as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "scanner_unavailable", "message": str(exc)},
        ) from exc

    audit_record(
        request.app.state.conn,
        "admin",
        f"system.{action}",
        settings_of(request).scanner_container,
        f"扫描容器操作：{action}",
        client_ip(request),
    )
    response.status_code = 202
    return {"status": "accepted", "action": action}


def _docker_version() -> str:
    try:
        return version("docker")
    except PackageNotFoundError:
        return "未知"


@router.get("/info", dependencies=[Depends(require_user)])
def system_info(request: Request) -> dict[str, object]:
    settings = settings_of(request)
    document = config_store.read_config(request.app.state.conn, settings)
    return {
        "panel_version": panel_version,
        "python": sys.version.split()[0],
        "docker": _docker_version(),
        "image": settings.scanner_image,
        "timezone": str(document.values.get("TZ") or BY_NAME["TZ"].default),
    }
