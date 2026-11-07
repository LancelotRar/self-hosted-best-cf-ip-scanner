"""升级期一次性迁移：把旧版落在宿主的文件搬进容器卷。

旧版布局把数据与产物直接放在宿主 `./data`、`./output`；改成命名卷后宿主机上
看不到文件，这里负责在**数据库还没有内容时**把旧文件优先搬进卷里，避免被镜像
内置的默认库覆盖。迁移是幂等的：目标已存在就不覆盖，数据库已有内容就完全跳过。
"""

from __future__ import annotations

import shutil
from pathlib import Path

from . import artifacts_store, library_store


def migrate(conn, settings) -> None:
    _migrate_documents(conn, settings)
    _migrate_artifacts(settings)


def _migrate_documents(conn, settings) -> None:
    """IP 库与机房映射：数据库为空时以旧宿主文件为准，覆盖卷内的内置默认值。"""
    legacy_dir = Path(settings.project_dir) / "data"
    if not legacy_dir.is_dir():
        return
    for kind in (library_store.LIBRARY, library_store.LOCATIONS):
        target = library_store.file_path(settings, kind)
        legacy = legacy_dir / target.name
        if not legacy.is_file():
            continue
        if library_store.read(conn, kind) is None:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(legacy, target)
    _migrate_runtime(legacy_dir, Path(settings.data_dir) / "runtime")


def _migrate_runtime(legacy_dir: Path, target_dir: Path) -> None:
    """轮次记录 `runs.tsv` 也在 `./data` 下，随目录一起搬。"""
    legacy = legacy_dir / "runtime"
    if not legacy.is_dir():
        return
    target_dir.mkdir(parents=True, exist_ok=True)
    for path in legacy.iterdir():
        destination = target_dir / path.name
        if path.is_file() and not destination.exists():
            shutil.copy2(path, destination)


def _migrate_artifacts(settings) -> None:
    artifacts_store.migrate_legacy(settings)
