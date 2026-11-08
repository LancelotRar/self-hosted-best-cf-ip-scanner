"""文件写入的原子实现。

产物预览已改为读数据库快照（见 `artifacts_store`），这里只剩下把数据库里的
内容安全地写成扫描器可读的投影文件（配置与 IP 库）。
"""

from __future__ import annotations

import os
import stat
import tempfile
from pathlib import Path


def _is_root() -> bool:
    getter = getattr(os, "geteuid", None)
    return bool(getter and getter() == 0)


def chown(path: Path, uid: int | None = None, gid: int | None = None) -> None:
    """把路径属主对齐到运行用户；非 root（含 Windows）时静默跳过。"""
    if uid is None and gid is None:
        return
    if not _is_root():
        return
    try:
        os.chown(path, -1 if uid is None else uid, -1 if gid is None else gid)
    except (OSError, AttributeError):
        pass


def atomic_write(
    path: Path,
    text: str,
    *,
    mode: int | None = None,
    uid: int | None = None,
    gid: int | None = None,
) -> None:
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
                os.chmod(temporary, 0o600 if mode is None else mode)
            except OSError:
                pass
        if uid is not None or gid is not None:
            chown(Path(temporary), uid, gid)
        os.replace(temporary, file_path)
        chown(file_path, uid, gid)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


__all__ = ["atomic_write", "chown"]
