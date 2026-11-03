"""发布路由：Git 参数（令牌只写）与最近一次推送结果。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from scanner.schema import PARAMS

from .. import config_store, runs_store
from ..deps import controller_of, settings_of
from ..security import require_user, verify_csrf
from .config import _raise_for

router = APIRouter(prefix="/api/publish", tags=["publish"])

PUBLISH_KEYS = frozenset(
    spec.name for spec in PARAMS if spec.consumer == "publish"
)


class PublishPayload(BaseModel):
    hash: str
    values: dict[str, object] = {}


@router.get("", dependencies=[Depends(require_user)])
def get_publish(request: Request) -> dict[str, object]:
    settings = settings_of(request)
    document = config_store.read_env(settings)
    params = [
        param
        for param in config_store.param_entries(document)
        if param["consumer"] == "publish"
    ]
    finished = [
        record
        for record in runs_store.parse(runs_store.runs_path(settings))
        if record.finished_at
    ]
    last = None
    if finished:
        record = finished[-1]
        last = {
            "run_id": record.run_id,
            "scan_exit": record.scan_exit,
            "publish_exit": record.publish_exit,
            "finished_at": record.finished_at,
            "summary": record.summary,
        }
    return {"hash": document.sha256, "params": params, "last": last}


@router.put("", dependencies=[Depends(require_user), Depends(verify_csrf)])
def put_publish(payload: PublishPayload, request: Request) -> dict[str, object]:
    rejected = sorted(set(payload.values) - PUBLISH_KEYS)
    if rejected:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "config_invalid",
                "message": "发布页只能修改发布参数",
                "details": [
                    {"name": name, "message": "不属于发布参数"} for name in rejected
                ],
            },
        )
    try:
        result = config_store.save(
            settings_of(request),
            payload.hash,
            payload.values,
            actor="admin",
            controller=controller_of(request),
        )
    except config_store.ConfigError as exc:
        _raise_for(exc)
        raise  # pragma: no cover
    return result.to_dict()
