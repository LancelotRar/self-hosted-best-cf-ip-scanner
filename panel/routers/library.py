"""IP 库路由：数据库真源 + 逐行校验 + 保存（自动备份）+ 版本恢复。

数据库是唯一真源；容器卷里的 `ip-library.txt` 只是写给扫描器的投影，
每次保存后重新生成，不参与读取。
"""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Request

from scanner.ippool import (
    commented_networks,
    count_addresses,
    library_errors,
    merge_to_runs,
    parse_library,
    subtract_runs,
    window_count,
)
from scanner.pinned import parse_pinned, pinned_errors
from scanner.schema import BY_NAME

from .. import library_store
from ..audit import record as audit_record
from ..config_store import read_env
from ..deps import settings_of
from ..security import require_user, verify_csrf

router = APIRouter(prefix="/api/library", tags=["library"])

MAX_BYTES = 2 * 1024 * 1024


class LibraryPayload(BaseModel):
    """两块内容各自独立保存：只提交其中一块时，另一块完全不动。"""

    hash: str
    content: str | None = None
    pinned: str | None = None
    pinned_hash: str | None = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _as_int(raw: object, default: int) -> int:
    """`.env` 里的值可能被手工改坏；解析失败退回 schema 默认值。"""
    try:
        return int(str(raw).strip())
    except (TypeError, ValueError):
        return default


def _sample_stride(settings) -> int:
    """采样步长：与扫描器同源（`.env` > schema 默认）。"""
    document = read_env(settings)
    stride = _as_int(
        document.values.get("SAMPLE_STRIDE"), int(BY_NAME["SAMPLE_STRIDE"].default)
    )
    return max(stride, 1)


def _stats(text: str, stride: int) -> dict[str, int]:
    """统计「参与探测」与「被注释跳过」的 IP 数量。

    - **参与探测**：合并网段后按 `stride` 网格每窗口抽 1 个代表（与
      `scanner.ippool.sample_representatives` 同一规则）。候选量完全由地址库决定，
      没有额外的总量上限；带端口的条目属于「固定保留」，不计入这里。
    - **跳过**：`#` 注释行中仍能解析成地址条目的部分，按网段展开、合并去重后求和；
      纯说明性注释（解析不出条目）不计。
    """
    networks, _skipped = parse_library(text)
    active_runs = merge_to_runs(networks)
    runs = subtract_runs(active_runs, merge_to_runs(commented_networks(text)))
    probe = window_count(runs, stride)
    return {
        "probe": probe,
        # 只统计"真的被扣掉"的地址：注释掉一个与有效库不相交的网段，跳过数是 0
        "skipped": count_addresses(active_runs) - count_addresses(runs),
        "networks": len(networks),
        "total": count_addresses(runs),
    }


def _pinned_output_name(settings) -> str:
    """固定保留产物的文件名（不含扩展名）：`.env` > schema 默认。"""
    raw = (read_env(settings).values.get("PINNED_OUTPUT_NAME") or "").strip()
    return raw or str(BY_NAME["PINNED_OUTPUT_NAME"].default)


def _pinned_view(content: str, row, output_name: str) -> dict[str, object]:
    entries, _skipped = parse_pinned(content)
    return {
        "content": content,
        "hash": row["sha256"] if row else library_store.sha256_text(""),
        "count": len(entries),
        "mtime": row["updated_at"] if row else None,
        "output_name": output_name,
    }


def _document(request: Request) -> dict[str, object]:
    """当前 IP 库的完整视图：采样库 + 固定保留。"""
    settings = settings_of(request)
    conn = request.app.state.conn
    row = library_store.read(conn, library_store.LIBRARY)
    if row is None:
        # 面板可能比扫描器先起来（首次启动时卷里还没有投影文件）。
        library_store.ensure(conn, settings)
        row = library_store.read(conn, library_store.LIBRARY)
    content = row["content"] if row else ""

    pinned_row = library_store.read(conn, library_store.PINNED)
    pinned_content = pinned_row["content"] if pinned_row else ""
    return {
        "content": content,
        "line_count": len(content.splitlines()),
        "hash": row["sha256"] if row else library_store.sha256_text(""),
        "mtime": row["updated_at"] if row else None,
        "read_at": _now_iso(),
        "stats": _stats(content, _sample_stride(settings)),
        "pinned": _pinned_view(pinned_content, pinned_row, _pinned_output_name(settings)),
    }


@router.get("", dependencies=[Depends(require_user)])
def get_library(request: Request) -> dict[str, object]:
    return _document(request)


@router.put("", dependencies=[Depends(require_user), Depends(verify_csrf)])
def put_library(payload: LibraryPayload, request: Request) -> dict[str, object]:
    settings = settings_of(request)
    conn = request.app.state.conn

    if payload.content is not None:
        if len(payload.content.encode("utf-8")) > MAX_BYTES:
            raise HTTPException(
                status_code=413,
                detail={"code": "library_too_large", "message": "地址库不能超过 2MB"},
            )
    details = [
        {"field": "library", "line": line_no, "raw": raw, "message": message}
        for line_no, raw, message in (
            library_errors(payload.content) if payload.content is not None else []
        )
    ] + [
        {
            "field": "pinned",
            "line": line_no,
            "raw": raw,
            "message": "固定保留条目格式不正确",
        }
        for line_no, raw in (
            pinned_errors(payload.pinned) if payload.pinned is not None else []
        )
    ]
    if details:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "library_invalid",
                "message": "存在无法解析的行，未保存",
                "details": details,
            },
        )

    current = _document(request)
    if payload.content is not None and payload.hash != current["hash"]:
        raise HTTPException(
            status_code=409,
            detail={"code": "library_conflict", "message": "地址库已被修改，请刷新后重试"},
        )
    pinned_view = current["pinned"]
    assert isinstance(pinned_view, dict)
    if (
        payload.pinned is not None
        and payload.pinned_hash
        and payload.pinned_hash != pinned_view["hash"]
    ):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "library_conflict",
                "message": "固定保留列表已被修改，请刷新后重试",
            },
        )

    if payload.content is not None:
        if library_store.read(conn, library_store.LIBRARY) is not None:
            library_store.backup(conn, str(current["content"]))
        library_store.save(conn, library_store.LIBRARY, payload.content)
        library_store.project(settings, library_store.LIBRARY, payload.content)
    if payload.pinned is not None:
        library_store.save(conn, library_store.PINNED, payload.pinned)
        library_store.project(settings, library_store.PINNED, payload.pinned)

    changes: list[str] = []
    if payload.content is not None:
        changes.append(f"地址库 {len(payload.content.splitlines())} 行")
    if payload.pinned is not None:
        entries, _skipped = parse_pinned(payload.pinned)
        changes.append(f"固定保留 {len(entries)} 条")
    audit_record(
        conn,
        "admin",
        "library.save",
        "library",
        "更新 " + " + ".join(changes) if changes else "无改动",
        "panel",
    )
    return _document(request)


@router.get("/backups", dependencies=[Depends(require_user)])
def list_backups(request: Request) -> dict[str, object]:
    return {
        "backups": library_store.versions(request.app.state.conn),
        "read_at": _now_iso(),
    }


@router.post(
    "/backups/{name}/restore",
    dependencies=[Depends(require_user), Depends(verify_csrf)],
)
def restore_backup(name: str, request: Request) -> dict[str, object]:
    settings = settings_of(request)
    conn = request.app.state.conn
    stem = name[:-4] if name.endswith(".txt") else ""
    if not stem.isdigit():
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_backup_name", "message": "备份文件名非法"},
        )
    content = library_store.version_content(conn, int(stem))
    if content is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "backup_not_found", "message": "备份不存在"},
        )
    errors = library_errors(content)
    if errors:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "library_invalid",
                "message": "备份内容存在无法解析的行，未恢复",
                "details": [
                    {"line": line_no, "raw": raw, "message": message}
                    for line_no, raw, message in errors
                ],
            },
        )

    current = _document(request)
    if library_store.read(conn, library_store.LIBRARY) is not None:
        library_store.backup(conn, str(current["content"]))
    library_store.save(conn, library_store.LIBRARY, content)
    library_store.project(settings, library_store.LIBRARY, content)
    audit_record(
        conn,
        "admin",
        "library.restore",
        "library",
        f"从备份恢复地址库：{name}",
        "panel",
    )
    return _document(request)
