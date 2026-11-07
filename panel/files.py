"""文件写入的原子实现。

产物预览已改为读数据库快照（见 `artifacts_store`），这里只剩下：
把数据库里的内容安全地写成扫描器可读的投影文件。
"""

from __future__ import annotations

import os
import stat
import tempfile
from pathlib import Path

MAX_TEXT_BYTES = 1024 * 1024
MAX_CSV_BYTES = 2 * 1024 * 1024


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


__all__ = ["MAX_CSV_BYTES", "MAX_TEXT_BYTES", "atomic_write"]
