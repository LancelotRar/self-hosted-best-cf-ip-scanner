"""参数读写路由：GET/PUT `/api/config`、核对、版本与回滚。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from .. import config_store, settings_store
from ..deps import controller_of as _controller, settings_of as _settings
from ..security import require_user, verify_csrf

router = APIRouter(prefix="/api", tags=["config"])


class ConfigPayload(BaseModel):
    hash: str
    values: dict[str, object] = {}


class RollbackPayload(BaseModel):
    hash: str | None = None


def _document(request: Request) -> settings_store.ConfigDocument:
    return config_store.read_config(
        request.app.state.conn, _settings(request)
    )


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
    return {
        "hash": document.sha256,
        "revision": document.revision,
        "updated_at": document.updated_at,
        "params": config_store.param_entries(document),
    }


@router.put("/config", dependencies=[Depends(require_user), Depends(verify_csrf)])
def put_config(payload: ConfigPayload, request: Request) -> dict[str, object]:
    try:
        result = config_store.save(
            request.app.state.conn,
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
        request.app.state.conn, _settings(request), _controller(request)
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
            request.app.state.conn,
            _settings(request),
            version_id,
            payload.hash,
            actor="admin",
            controller=_controller(request),
        )
    except config_store.ConfigError as exc:
        _raise_for(exc)
        raise  # pragma: no cover
    return result.to_dict()
