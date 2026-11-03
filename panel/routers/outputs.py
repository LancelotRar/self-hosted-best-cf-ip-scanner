"""产物路由：列表、预览与下载。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse

from ..deps import settings_of
from ..files import FileAccessError, list_files, preview, resolve_child
from ..security import require_user

router = APIRouter(prefix="/api/outputs", tags=["outputs"])


def _resolve(request: Request, name: str):
    try:
        return resolve_child(settings_of(request).output_dir, name)
    except FileAccessError as exc:
        status = 404 if "不存在" in str(exc) else 400
        raise HTTPException(
            status_code=status, detail={"code": "invalid_filename", "message": str(exc)}
        ) from exc


@router.get("", dependencies=[Depends(require_user)])
def list_outputs(request: Request) -> dict[str, object]:
    return list_files(settings_of(request).output_dir)


@router.get("/{name}", dependencies=[Depends(require_user)])
def inspect_output(name: str, request: Request, download: bool = False):
    path = _resolve(request, name)
    if download:
        return FileResponse(
            path,
            filename=path.name,
            media_type="application/octet-stream",
        )
    return preview(path)
