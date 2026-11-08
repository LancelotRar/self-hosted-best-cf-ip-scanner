"""参数读写路由：GET/PUT `/api/config`、核对、版本与回滚。"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from .. import config_store
from ..deps import controller_of as _controller, settings_of as _settings
from ..security import require_user, verify_csrf
from scanner.dotenv import DotenvError

router = APIRouter(prefix="/api", tags=["config"])


class ConfigPayload(BaseModel):
    hash: str
    values: dict[str, object] = {}


class RollbackPayload(BaseModel):
    hash: str | None = None


def _document(request: Request) -> config_store.EnvDocument:
    try:
        return config_store.read_env(_settings(request))
    except DotenvError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "config_unparsable", "message": f"配置解析失败：{exc}"},
        ) from exc


def _raise_for(exc: config_store.ConfigError) -> None:
    """把配置事务异常映射成统一错误体。"""
    if isinstance(exc, config_store.ConfigConflict):
        raise HTTPException(
            status_code=409,
            detail={"code": "config_conflict", "message": str(exc)},
        ) from exc
    if isinstance(exc, config_store.ConfigInvalid):
        raise HTTPException(
            status_code=422,
            detail={
                "code": "config_invalid",
                "message": "配置校验失败",
                "details": exc.errors,
            },
        ) from exc
    if isinstance(exc, config_store.ConfigApplyFailed):
        raise HTTPException(
            status_code=500,
            detail={"code": "config_apply_failed", "message": str(exc)},
        ) from exc
    if isinstance(exc, config_store.ConfigWriteUnverified):
        raise HTTPException(
            status_code=500,
            detail={"code": "config_write_unverified", "message": str(exc)},
        ) from exc
    raise HTTPException(
        status_code=500, detail={"code": "config_error", "message": str(exc)}
    )


@router.get("/config", dependencies=[Depends(require_user)])
def get_config(request: Request) -> dict[str, object]:
    document = _document(request)
    stat = document.path.stat() if document.path.exists() else None
    return {
        "hash": document.sha256,
        "mtime": (
            datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
            if stat
            else None
        ),
        "file_size": stat.st_size if stat else 0,
        "params": config_store.param_entries(document),
    }


@router.put("/config", dependencies=[Depends(require_user), Depends(verify_csrf)])
def put_config(payload: ConfigPayload, request: Request) -> dict[str, object]:
    try:
        result = config_store.save(
            _settings(request),
            payload.hash,
            payload.values,
            actor="admin",
            controller=_controller(request),
        )
    except config_store.ConfigError as exc:
        _raise_for(exc)
        raise  # pragma: no cover - _raise_for 总会抛出
    return result.to_dict()


@router.post(
    "/config/verify", dependencies=[Depends(require_user), Depends(verify_csrf)]
)
def verify_config(request: Request) -> dict[str, object]:
    document = _document(request)
    verification = config_store.verify_effective(
        _settings(request), _controller(request)
    )
    return {"hash": document.sha256, "verification": verification}


@router.get("/config/versions", dependencies=[Depends(require_user)])
def list_versions(request: Request) -> dict[str, object]:
    rows = request.app.state.conn.execute(
        "SELECT id, created_at, actor, sha256, diff FROM config_versions"
        " ORDER BY id DESC LIMIT 50"
    ).fetchall()
    return {"versions": [dict(row) for row in rows]}


@router.post(
    "/config/versions/{version_id}/rollback",
    dependencies=[Depends(require_user), Depends(verify_csrf)],
)
def rollback_config(
    version_id: int, payload: RollbackPayload, request: Request
) -> dict[str, object]:
    try:
        result = config_store.rollback(
            _settings(request),
            request.app.state.conn,
            version_id,
            payload.hash,
            actor="admin",
            controller=_controller(request),
        )
    except config_store.ConfigError as exc:
        _raise_for(exc)
        raise  # pragma: no cover
    return result.to_dict()
