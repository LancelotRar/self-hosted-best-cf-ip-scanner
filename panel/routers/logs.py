"""日志路由：本项目的扫描容器实时日志（SSE）与下载。"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sse_starlette.sse import EventSourceResponse

from ..deps import controller_of
from ..docker_api import ScannerUnavailable
from ..redact import redact_secrets
from ..security import require_user

router = APIRouter(prefix="/api/logs", tags=["logs"])

HEARTBEAT_SECONDS = 15


def _logs_or_503(request: Request, tail: int, follow: bool):
    controller = controller_of(request)
    if controller is None:
        raise HTTPException(
            status_code=503,
            detail={"code": "scanner_unavailable", "message": "扫描容器不可用"},
        )
    try:
        return controller.logs(tail=tail, follow=follow)
    except ScannerUnavailable as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": "scanner_unavailable", "message": str(exc)},
        ) from exc


@router.get("/stream", dependencies=[Depends(require_user)])
def stream_logs(request: Request, tail: int = 200):
    chunks = _logs_or_503(request, max(1, min(tail, 5000)), follow=True)

    def events():
        buffer = b""
        for chunk in chunks:
            buffer += chunk
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                yield {
                    "event": "log",
                    "data": redact_secrets(
                        line.rstrip(b"\r").decode("utf-8", "replace")
                    ),
                }
        if buffer:
            yield {
                "event": "log",
                "data": redact_secrets(buffer.decode("utf-8", "replace")),
            }

    # 同步生成器：sse-starlette 会把它放进线程池，避免阻塞 uvicorn 事件循环。
    # ping 每 15 秒发一次注释行，代理断连时前端能感知并重连。
    return EventSourceResponse(events(), ping=HEARTBEAT_SECONDS)


@router.get("/download", dependencies=[Depends(require_user)])
def download_logs(request: Request, tail: int = 5000) -> Response:
    chunks = _logs_or_503(request, max(1, min(tail, 20000)), follow=False)
    body = redact_secrets(b"".join(chunks).decode("utf-8", "replace"))
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Response(
        content=body,
        media_type="text/plain; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="scanner-logs-{stamp}.txt"'
        },
    )
