"""产物目录的安全文件访问与预览。

所有名字先过 `resolve_child`：拒绝绝对路径、`..`、路径分隔符、目录与符号链接逃逸，
只允许 `OUTPUT_DIR` 内的普通文件。预览不是"任读任意文件"——路径由服务端白名单决定。
"""

from __future__ import annotations

import csv
import hashlib
import io
import os
import stat
import tempfile
from datetime import datetime, timezone
from pathlib import Path

MAX_TEXT_BYTES = 1024 * 1024
MAX_CSV_BYTES = 2 * 1024 * 1024


class FileAccessError(ValueError):
    """名字非法或目标不是普通文件。"""


def resolve_child(root: Path, name: str) -> Path:
    """把 `name` 解析成 `root` 内的普通文件；越界抛 `FileAccessError`。"""
    if (
        not name
        or name in {".", ".."}
        or "/" in name
        or "\\" in name
        or ".." in name
        or "\x00" in name
    ):
        raise FileAccessError("非法文件名")
    root_resolved = Path(root).resolve()
    candidate = (root_resolved / name).resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError as exc:
        raise FileAccessError("文件不在允许的目录内") from exc
    if candidate.is_symlink() or not candidate.is_file():
        raise FileAccessError("文件不存在")
    return candidate


def _meta(path: Path) -> dict[str, object]:
    stat_result = path.stat()
    return {
        "name": path.name,
        "size": stat_result.st_size,
        "mtime": datetime.fromtimestamp(
            stat_result.st_mtime, tz=timezone.utc
        ).isoformat(),
    }


def list_files(root: Path) -> dict[str, object]:
    """产物列表：只列普通文件，按修改时间倒序。"""
    read_at = datetime.now(timezone.utc).isoformat()
    entries: list[dict[str, object]] = []
    if Path(root).is_dir():
        for path in Path(root).iterdir():
            if path.is_file() and not path.is_symlink():
                entries.append(_meta(path))
    entries.sort(key=lambda item: str(item["mtime"]), reverse=True)
    return {"read_at": read_at, "files": entries}


def preview(path: Path, max_rows: int = 200) -> dict[str, object]:
    """TXT 取前 N 行、CSV 取前 N 行并拆出表头；附 mtime 与 sha256。"""
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    base = {**_meta(path), "sha256": digest}
    suffix = path.suffix.lower()

    if suffix == ".csv":
        text = data[:MAX_CSV_BYTES].decode("utf-8", "replace")
        rows = list(csv.reader(io.StringIO(text)))
        headers = rows[0] if rows else []
        body_rows = rows[1 : max_rows + 1]
        return {
            **base,
            "kind": "csv",
            "headers": headers,
            "rows": body_rows,
            "truncated": len(rows) - 1 > max_rows,
        }

    if suffix in {".txt", ""}:
        text = data[:MAX_TEXT_BYTES].decode("utf-8", "replace")
        lines = text.splitlines()
        return {
            **base,
            "kind": "text",
            "content": "\n".join(lines[:max_rows]),
            "line_count": len(lines),
            "truncated": len(lines) > max_rows or len(data) > MAX_TEXT_BYTES,
        }

    return {**base, "kind": "binary"}


def atomic_write(path: Path, text: str) -> None:
    """同目录临时文件 + fsync + os.replace；尽量保留原文件属主与权限。"""
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    original = file_path.stat() if file_path.exists() else None
    descriptor, temporary = tempfile.mkstemp(
        dir=str(file_path.parent), prefix=f".{file_path.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        if original is not None:
            try:
                os.chmod(temporary, stat.S_IMODE(original.st_mode))
            except OSError:
                pass
            try:
                os.chown(temporary, original.st_uid, original.st_gid)
            except (OSError, AttributeError):
                pass
        else:
            try:
                os.chmod(temporary, 0o600)
            except OSError:
                pass
        os.replace(temporary, file_path)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


__all__ = [
    "FileAccessError",
    "atomic_write",
    "list_files",
    "preview",
    "resolve_child",
]
