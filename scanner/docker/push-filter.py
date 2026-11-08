#!/usr/bin/env python3
"""按 PUSH_LISTS 筛选本轮要推送到仓库的产物。

用法：push-filter.py <源产物目录> <目标目录>

规则：
- PUSH_LISTS 为空：推送全部 *.txt / *.csv（保持旧行为）；
- PUSH_LISTS 是 JSON 数组（如 ["GLOBAL20", "US100"]）：只推送这些列表，
  键名与 LIST_FILENAMES 一致；用户自定义文件名会自动换算；
- 明细表与固定保留始终推送（如果存在）。
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path


def _stem(name: str) -> str:
    text = Path(str(name).strip()).name
    return text[:-4] if text.lower().endswith(".txt") else text


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("用法：push-filter.py <源目录> <目标目录>", file=sys.stderr)
        return 2
    source = Path(argv[1])
    target = Path(argv[2])
    if not source.is_dir():
        print(f"源目录不存在：{source}", file=sys.stderr)
        return 1
    target.mkdir(parents=True, exist_ok=True)

    raw = (os.environ.get("PUSH_LISTS") or "").strip()
    if raw:
        try:
            selected = json.loads(raw)
        except ValueError:
            print("PUSH_LISTS 不是合法 JSON", file=sys.stderr)
            return 2
        if not isinstance(selected, list) or any(
            not isinstance(item, str) for item in selected
        ):
            print("PUSH_LISTS 必须是字符串数组", file=sys.stderr)
            return 2
        try:
            mapping = json.loads(os.environ.get("LIST_FILENAMES") or "{}")
        except ValueError:
            mapping = {}
        if not isinstance(mapping, dict):
            mapping = {}
        wanted = {
            f"{_stem(mapping.get(key, key))}.txt"
            for key in selected
            if _stem(mapping.get(key, key))
        }
    else:
        wanted = {
            path.name
            for path in source.iterdir()
            if path.is_file() and path.suffix.lower() in {".txt", ".csv"}
        }

    # 明细表与固定保留不属于「推送列表」开关，始终跟随推送。
    detail = f"{_stem(os.environ.get('DETAIL_CSV_NAME') or 'detail')}.csv"
    pinned = f"{_stem(os.environ.get('PINNED_OUTPUT_NAME') or 'PINNED')}.txt"
    wanted.update({detail, pinned})

    copied = 0
    for name in sorted(wanted):
        path = source / name
        if not path.is_file():
            continue
        shutil.copy2(path, target / name)
        copied += 1

    if copied == 0:
        print("没有匹配到可推送的产物", file=sys.stderr)
        return 1
    print(f"推送筛选：{copied} 个文件")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
