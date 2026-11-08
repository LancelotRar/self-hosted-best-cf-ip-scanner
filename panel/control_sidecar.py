"""固定操作的 Docker 控制 sidecar。

面板默认不挂 docker.sock；需要日志/执行/启停时，由本 sidecar 持有 socket，
只暴露固定 action，不接受任意容器、任意命令或任意脚本路径。

运行：
    python -m panel.control_sidecar
环境：
    SCANNER_CONTAINER       目标扫描容器名（默认 best-cf-ip-scanner）
    CONTROL_PORT            监听端口（默认 8090）
    SCANNER_CONTROL_TOKEN   可选共享口令；设置后请求必须带 X-Control-Token
"""

from __future__ import annotations

import hmac
import os
import secrets
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .docker_api import ScannerController, ScannerUnavailable, default_controller
from .settings import Settings

ACTION_SCRIPTS = {
    "run": "/usr/local/bin/scan-and-publish.sh",
    "apply-config": "/usr/local/bin/apply-config.sh",
    "print-config": "/usr/local/bin/print-config.py",
}
ALLOWED_ENV = frozenset({"RUN_ID", "RUN_TRIGGER"})
MAX_EXECS = 50


class ExecRequest(BaseModel):
    env: dict[str, str] = {}


def _controller_or_503(app: FastAPI) -> ScannerController:
    if app.state.controller is None:
        try:
            app.state.controller = default_controller(Settings.from_env())
        except Exception as exc:  # noqa: BLE001 - 统一转成 503
            raise HTTPException(
                status_code=503,
                detail={"code": "scanner_unavailable", "message": str(exc)},
            ) from exc
    return app.state.controller


def _check_token(request: Request) -> None:
    expected = request.app.state.token
    if not expected:
        return
    provided = request.headers.get("X-Control-Token", "")
    if not provided or not hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=403, detail="control token 不正确")


def create_sidecar(controller: Any = None, token: str | None = None) -> FastAPI:
    app = FastAPI(
        title="best-cf-ip-scanner control sidecar",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.controller = controller
    app.state.token = token or None
    app.state.execs: dict[str, Any] = {}

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/status")
    def status(request: Request) -> dict[str, object]:
        _check_token(request)
        try:
            return _controller_or_503(app).status()
        except ScannerUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.get("/stats")
    def stats(request: Request) -> dict[str, object]:
        _check_token(request)
        try:
            return _controller_or_503(app).stats()
        except ScannerUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.get("/logs")
    def logs(
        request: Request, tail: int = 200, follow: bool = True
    ) -> StreamingResponse:
        _check_token(request)
        try:
            chunks = _controller_or_503(app).logs(
                tail=max(1, min(tail, 5000)), follow=follow
            )
        except ScannerUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return StreamingResponse(iter(chunks), media_type="application/octet-stream")

    @app.post("/exec/{action}")
    def exec_action(
        action: str, payload: ExecRequest, request: Request
    ) -> dict[str, str]:
        _check_token(request)
        script = ACTION_SCRIPTS.get(action)
        if script is None:
            raise HTTPException(status_code=404, detail="不支持的操作")
        env = {
            key: value
            for key, value in payload.env.items()
            if key in ALLOWED_ENV and isinstance(value, str)
        }
        try:
            handle = _controller_or_503(app).exec_script(script, env)
        except ScannerUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        exec_id = secrets.token_hex(8)
        app.state.execs[exec_id] = handle
        while len(app.state.execs) > MAX_EXECS:
            app.state.execs.pop(next(iter(app.state.execs)), None)
        return {"exec_id": exec_id, "run_id": str(handle.run_id)}

    def _handle(exec_id: str):
        handle = app.state.execs.get(exec_id)
        if handle is None:
            raise HTTPException(status_code=404, detail="执行不存在")
        return handle

    @app.get("/exec/{exec_id}")
    def exec_state(exec_id: str, request: Request) -> dict[str, object]:
        _check_token(request)
        handle = _handle(exec_id)
        return {"finished": bool(getattr(handle, "finished", False))}

    @app.get("/exec/{exec_id}/stream")
    def exec_stream(exec_id: str, request: Request) -> StreamingResponse:
        _check_token(request)
        handle = _handle(exec_id)
        return StreamingResponse(
            handle.stream(), media_type="application/octet-stream"
        )

    @app.get("/exec/{exec_id}/wait")
    def exec_wait(exec_id: str, request: Request, timeout_s: int = 3600) -> dict[str, int]:
        _check_token(request)
        handle = _handle(exec_id)
        try:
            return {"exit_code": int(handle.wait(timeout_s=timeout_s))}
        except ScannerUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.post("/restart")
    def restart(request: Request) -> dict[str, bool]:
        _check_token(request)
        try:
            _controller_or_503(app).restart()
        except ScannerUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return {"ok": True}

    @app.post("/stop")
    def stop(request: Request) -> dict[str, bool]:
        _check_token(request)
        try:
            _controller_or_503(app).stop()
        except ScannerUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return {"ok": True}

    @app.post("/start")
    def start(request: Request) -> dict[str, bool]:
        _check_token(request)
        try:
            _controller_or_503(app).start()
        except ScannerUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return {"ok": True}

    return app


def main() -> None:
    import uvicorn

    token = os.environ.get("SCANNER_CONTROL_TOKEN") or None
    app = create_sidecar(token=token)
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.environ.get("CONTROL_PORT") or 8090),
        log_level="info",
        server_header=False,
    )


if __name__ == "__main__":
    main()
