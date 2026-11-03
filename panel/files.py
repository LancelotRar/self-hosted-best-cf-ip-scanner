"""产物目录的安全文件访问与预览。

所有名字先过 `resolve_child`：拒绝绝对路径、`..`、路径分隔符、目录与符号链接逃逸，
只允许 `OUTPUT_DIR` 内的普通文件。预览不是"任读任意文件"——路径由服务端白名单决定。
"""

from __future__ import annotations

import csv
import hashlib
import io
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
    stat = path.stat()
    return {
        "name": path.name,
        "size": stat.st_size,
        "mtime": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
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


__all__ = ["FileAccessError", "list_files", "preview", "resolve_child"]
