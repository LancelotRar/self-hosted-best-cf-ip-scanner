"""机房映射路由：以结构化条目读写数据库里的「机房代码 → 国家代码」。

前端用表格编辑，所以接口收发的是条目数组而不是原始 JSON；服务端负责规范化
（大写）、逐行校验与去重，再序列化成卷内投影文件给扫描器读。
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from .. import library_store
from ..audit import record as audit_record
from ..deps import settings_of
from ..security import require_user, verify_csrf

router = APIRouter(prefix="/api/locations", tags=["locations"])

CODE_RE = re.compile(r"^[A-Z]{3}$")
COUNTRY_RE = re.compile(r"^[A-Z]{2}$")


class LocationEntry(BaseModel):
    code: str
    country: str


class LocationsPayload(BaseModel):
    hash: str
    entries: list[LocationEntry]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _parse(content: str) -> list[dict[str, str]]:
    """把库里的 JSON 文本还原成条目；内容损坏时返回空表而不是 500。"""
    try:
        payload = json.loads(content)
    except (TypeError, ValueError):
        return []
    if not isinstance(payload, dict):
        return []
    return [
        {"code": str(code), "country": str(country)}
        for code, country in sorted(payload.items())
    ]


def _document(conn, settings) -> dict[str, object]:
    row = library_store.read(conn, library_store.LOCATIONS)
    if row is None:
        library_store.ensure(conn, settings)
        row = library_store.read(conn, library_store.LOCATIONS)
    content = row["content"] if row else ""
    entries = _parse(content)
    return {
        "hash": row["sha256"] if row else library_store.sha256_text(""),
        "mtime": row["updated_at"] if row else None,
        "count": len(entries),
        "entries": entries,
        "read_at": _now_iso(),
    }


def _validate(entries: list[LocationEntry]) -> tuple[list[tuple[str, str]], list[dict]]:
    """规范化并逐行校验；返回 (清理后的条目, 错误列表)。"""
    cleaned: list[tuple[str, str]] = []
    errors: list[dict] = []
    first_seen: dict[str, int] = {}
    for index, entry in enumerate(entries, start=1):
        code = entry.code.strip().upper()
        country = entry.country.strip().upper()
        if not CODE_RE.match(code):
            errors.append(
                {"line": index, "message": "机房代码必须是 3 个大写字母（如 HKG）"}
            )
        if not COUNTRY_RE.match(country):
            errors.append(
                {"line": index, "message": "国家代码必须是 2 个大写字母（如 HK）"}
            )
        if code in first_seen:
            errors.append(
                {
                    "line": index,
                    "message": f"机房代码 {code} 与第 {first_seen[code]} 行重复",
                }
            )
        elif CODE_RE.match(code):
            first_seen[code] = index
        cleaned.append((code, country))
    return cleaned, errors


def _serialize(entries: list[tuple[str, str]]) -> str:
    payload = {code: country for code, country in sorted(entries)}
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


@router.get("", dependencies=[Depends(require_user)])
def get_locations(request: Request) -> dict[str, object]:
    return _document(request.app.state.conn, settings_of(request))


@router.put("", dependencies=[Depends(require_user), Depends(verify_csrf)])
def put_locations(payload: LocationsPayload, request: Request) -> dict[str, object]:
    settings = settings_of(request)
    conn = request.app.state.conn

    cleaned, errors = _validate(payload.entries)
    if errors:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "locations_invalid",
                "message": "机房映射存在不合法的条目",
                "details": errors,
            },
        )

    current = _document(conn, settings)
    if payload.hash != current["hash"]:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "locations_conflict",
                "message": "机房映射已被修改，请刷新后重试",
            },
        )

    content = _serialize(cleaned)
    library_store.save(conn, library_store.LOCATIONS, content)
    library_store.project(settings, library_store.LOCATIONS, content)
    audit_record(
        conn,
        "admin",
        "locations.save",
        "locations",
        f"更新机房映射（{len(cleaned)} 条）",
        "panel",
    )
    return _document(conn, settings)
