"""产物路由：列表与预览读数据库元数据/有界快照，下载读文件卷。

扫描器把完整文件写在容器卷里（发布用），面板每次列表时按 (size, mtime) 同步
元数据与有界预览；数据库不保存整文件，下载时再从卷内读取。
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
        content = artifacts_store.download(settings_of(request), row)
        if content is None:
            raise HTTPException(
                status_code=404,
                detail={"code": "file_missing", "message": "产物文件已不在卷内"},
            )
        return Response(
            content=content,
            media_type="application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{row["name"]}"'},
        )
    return artifacts_store.preview(row)
