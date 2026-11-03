"""IP 库路由：读取、逐行校验、保存（自动备份）与备份恢复。"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, Request

from scanner.ippool import library_errors, read_library
from scanner.schema import BY_NAME

from ..audit import record as audit_record
from ..config_store import read_env
from ..deps import settings_of
from ..files import atomic_write
from ..security import require_user, verify_csrf

router = APIRouter(prefix="/api/library", tags=["library"])

MAX_BYTES = 2 * 1024 * 1024
BACKUP_KEEP = 30


class LibraryPayload(BaseModel):
    hash: str
    content: str


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _library_path(settings) -> Path:
    document = read_env(settings)
    name = (
        document.values.get("LIBRARY_FILE") or str(BY_NAME["LIBRARY_FILE"].default)
    ).strip()
    if not name or "/" in name or "\\" in name or ".." in name:
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_library_file", "message": "LIBRARY_FILE 非法"},
        )
    return settings.data_dir / name


def _read_text(path: Path) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8-sig", errors="replace")


def _payload(path: Path) -> dict[str, object]:
    text = _read_text(path)
    stat = path.stat() if path.is_file() else None
    stats = {"networks": 0, "fixed": 0, "skipped": 0}
    if stat is not None:
        try:
            networks, fixed, skipped = read_library(path)
            stats = {
                "networks": len(networks),
                "fixed": len(fixed),
                "skipped": skipped,
            }
        except OSError:
            pass
    return {
        "content": text,
        "line_count": len(text.splitlines()),
        "hash": _sha256(text),
        "mtime": (
            datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
            if stat
            else None
        ),
        "read_at": _now_iso(),
        "stats": stats,
    }


def _backups_dir(settings) -> Path:
    return settings.panel_data_dir / "backups" / "library"


def _backup(settings, path: Path, text: str) -> Path | None:
    if not path.is_file():
        return None
    target_dir = _backups_dir(settings)
    target_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    target = target_dir / f"{stamp}.txt"
    atomic_write(target, text)
    for old in sorted(target_dir.glob("*.txt"))[:-BACKUP_KEEP]:
        old.unlink(missing_ok=True)
    return target


@router.get("", dependencies=[Depends(require_user)])
def get_library(request: Request) -> dict[str, object]:
    return _payload(_library_path(settings_of(request)))


@router.put("", dependencies=[Depends(require_user), Depends(verify_csrf)])
def put_library(payload: LibraryPayload, request: Request) -> dict[str, object]:
    settings = settings_of(request)
    path = _library_path(settings)
    if len(payload.content.encode("utf-8")) > MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail={"code": "library_too_large", "message": "地址库不能超过 2MB"},
        )
    errors = library_errors(payload.content)
    if errors:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "library_invalid",
                "message": "地址库存在无法解析的行",
                "details": [
                    {"line": line_no, "raw": raw, "message": "无法解析的地址条目"}
                    for line_no, raw in errors
                ],
            },
        )
    current = _payload(path)
    if payload.hash != current["hash"]:
        raise HTTPException(
            status_code=409,
            detail={"code": "library_conflict", "message": "地址库已被修改，请刷新后重试"},
        )

    _backup(settings, path, current["content"])
    atomic_write(path, payload.content)
    audit_record(
        settings_db_conn(request),
        "admin",
        "library.save",
        str(path),
        f"更新地址库（{len(payload.content.splitlines())} 行）",
        "panel",
    )
    return _payload(path)


def settings_db_conn(request: Request):
    return request.app.state.conn


@router.get("/backups", dependencies=[Depends(require_user)])
def list_backups(request: Request) -> dict[str, object]:
    directory = _backups_dir(settings_of(request))
    entries: list[dict[str, object]] = []
    if directory.is_dir():
        for path in directory.glob("*.txt"):
            if path.is_file():
                stat = path.stat()
                entries.append(
                    {
                        "name": path.name,
                        "size": stat.st_size,
                        "mtime": datetime.fromtimestamp(
                            stat.st_mtime, tz=timezone.utc
                        ).isoformat(),
                    }
                )
    entries.sort(key=lambda item: str(item["mtime"]), reverse=True)
    return {"backups": entries, "read_at": _now_iso()}


@router.post(
    "/backups/{name}/restore",
    dependencies=[Depends(require_user), Depends(verify_csrf)],
)
def restore_backup(name: str, request: Request) -> dict[str, object]:
    settings = settings_of(request)
    if not name or "/" in name or "\\" in name or ".." in name:
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_backup_name", "message": "备份文件名非法"},
        )
    backup_path = _backups_dir(settings) / name
    if not backup_path.is_file():
        raise HTTPException(
            status_code=404,
            detail={"code": "backup_not_found", "message": "备份不存在"},
        )
    content = _read_text(backup_path)
    errors = library_errors(content)
    if errors:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "library_invalid",
                "message": "备份内容存在无法解析的行，未恢复",
                "details": [
                    {"line": line_no, "raw": raw, "message": "无法解析的地址条目"}
                    for line_no, raw in errors
                ],
            },
        )
    path = _library_path(settings)
    current = _payload(path)
    _backup(settings, path, current["content"])
    atomic_write(path, content)
    audit_record(
        settings_db_conn(request),
        "admin",
        "library.restore",
        str(path),
        f"从备份恢复地址库：{name}",
        "panel",
    )
    return _payload(path)
