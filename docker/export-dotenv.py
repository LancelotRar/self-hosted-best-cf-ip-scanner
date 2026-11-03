#!/usr/bin/env python3
"""把 `.env` 里的已知键输出成 shell `export` 语句。

用法：
    eval "$(export-dotenv.py)"                  # 导出全部已知键
    eval "$(export-dotenv.py --keys PUID,TZ)"   # 只导出指定键（入口阶段用）

规则：
- 只导出 `scanner/schema.py` 里的已知键，忽略注释与未知键；
- 空值视为未设置，不导出；
- 已经存在的非空环境变量优先，不覆盖（`docker compose run -e` 的临时覆盖语义）；
- `.env` 解析失败时退出 1 并打印原因，调用方应停止本轮而不是带错值继续。
"""

from __future__ import annotations

import argparse
import os
import shlex
import sys
from pathlib import Path


def _app_dir() -> Path:
    """容器内是 /app；测试/本地运行时回退到包含 scanner/ 的仓库根。"""
    for parent in Path(__file__).resolve().parents:
        if (parent / "scanner").is_dir():
            return parent
    return Path("/app")


sys.path.insert(0, str(_app_dir()))

from scanner.dotenv import DotenvError  # noqa: E402
from scanner.runtime_env import load  # noqa: E402
from scanner.schema import KNOWN_KEYS  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="导出 .env 中的已知键")
    parser.add_argument("--keys", default="", help="只导出这些键（逗号分隔）")
    args = parser.parse_args(argv)

    selected = {name for name in args.keys.split(",") if name} or None
    try:
        values = load()
    except DotenvError as exc:
        print(f"[export-dotenv] .env 解析失败：{exc}", file=sys.stderr)
        return 1

    for name, value in values.items():
        if name not in KNOWN_KEYS:
            continue
        if selected is not None and name not in selected:
            continue
        if not value.strip():
            continue
        if os.environ.get(name, "").strip():
            continue
        print(f"export {name}={shlex.quote(value)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
