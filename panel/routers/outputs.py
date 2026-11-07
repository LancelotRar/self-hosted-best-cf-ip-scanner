"""产物路由：列表、预览与下载，全部读数据库快照。

扫描器把文件写在容器卷里（发布用），面板每次列表时按 (size, mtime) 同步入库，
之后一律从库里读——宿主机上看不到任何产物文件。
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from .. import artifacts_store
from ..deps import settings_of
from ..security import require_user

router = APIRouter(prefix="/api/outputs", tags=["outputs"])


def _sync(request: Request) -> None:
    artifacts_store.sync(request.app.state.conn, settings_of(request))


@router.get("", dependencies=[Depends(require_user)])
def list_outputs(request: Request) -> dict[str, object]:
    _sync(request)
    return {
        "read_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "files": artifacts_store.list_rows(request.app.state.conn),
    }


@router.get("/{name}", dependencies=[Depends(require_user)])
def inspect_output(name: str, request: Request, download: bool = False):
    _sync(request)
    row = artifacts_store.get(request.app.state.conn, name)
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "invalid_filename", "message": "文件不存在"},
        )
    if download:
        return Response(
            content=artifacts_store.content_of(row),
            media_type="application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{row["name"]}"'},
        )
    return artifacts_store.preview(row)
