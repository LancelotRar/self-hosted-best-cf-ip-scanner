"""IATA colo -> 国家二字码 映射: 本地固定文件读取(文件位于 DATA_DIR,
与段库同目录)。

映射数据为人工维护的固定文件(与段库同待遇): CF 官方 locations 接口
一次抓取后固化入库, 运行时不联网。文件为扁平 JSON({iata: cca2})。
文件缺失/损坏时返回空映射, CSV 的"国家/国旗"列留空(优雅降级);
需要更新时手动重新抓取并覆盖文件。
"""

from __future__ import annotations

import json
from pathlib import Path

# iata -> cca2
LocationMap = dict[str, str]


def load_locations(cache_path: Path) -> LocationMap:
    """Load the fixed iata -> cca2 mapping from the local JSON file.

    Returns {} when the file is missing or corrupt, so country/flag
    columns stay empty. No network fetch — the file is the source of
    truth.
    """
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return {}
        return {
            str(iata): str(cca2)
            for iata, cca2 in payload.items()
            if isinstance(cca2, str)
        }
    except (OSError, ValueError, json.JSONDecodeError):
        return {}
