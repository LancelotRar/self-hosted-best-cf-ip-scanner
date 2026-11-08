"""启动期准备：把镜像内置的默认数据播种到数据卷。

面板先于扫描器启动，因此 `/data` 的初始化责任在这里：
面板以 root 运行，可以复制镜像内置默认库并把属主对齐到 PUID:PGID。
数据库内容由 `settings_store` / `library_store` 管理；这里只负责首次落盘。
"""

from __future__ import annotations

import shutil
from pathlib import Path

from .files import chown


def _chown_tree(path: Path, uid: int, gid: int) -> None:
    chown(path, uid, gid)
    if not path.is_dir():
        return
    for child in path.rglob("*"):
        chown(child, uid, gid)


def seed_defaults(settings) -> None:
    """首次启动把镜像内置的 IP 库 / 机房映射写进 `/data`。"""
    source = Path(settings.default_data_dir)
    target = Path(settings.data_dir)
    if not source.is_dir():
        return
    target.mkdir(parents=True, exist_ok=True)
    for item in source.iterdir():
        destination = target / item.name
        if destination.exists():
            continue
        if item.is_dir():
            shutil.copytree(item, destination)
        else:
            shutil.copy2(item, destination)
    _chown_tree(target, settings.puid, settings.pgid)


__all__ = ["seed_defaults"]
