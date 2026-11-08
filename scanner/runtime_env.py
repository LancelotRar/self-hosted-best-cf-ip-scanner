"""读取运行配置投影（JSON），并支持导出到进程环境。

投影由面板生成；显式环境变量优先。这里只做「读文件 + 导出」，
不解析业务语义（类型转换在 `scanner/schema.py`）。
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from .schema import KNOWN_KEYS

APP_DIR = Path(__file__).resolve().parent.parent
DEFAULT_PATH = Path("/scanner-config/runtime.json")


class RuntimeConfigError(ValueError):
    """运行配置投影缺失或格式非法。"""


def default_path() -> Path:
    """`RUNTIME_CONFIG_PATH` 指向的投影；未设置时使用容器内固定路径。"""
    configured = os.environ.get("RUNTIME_CONFIG_PATH")
    return Path(configured) if configured else DEFAULT_PATH


def load(path: str | Path | None = None) -> dict[str, str]:
    """读取 JSON 投影；文件不存在返回空字典。"""
    file_path = Path(path) if path is not None else default_path()
    if not file_path.is_file():
        return {}
    try:
        payload = json.loads(file_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RuntimeConfigError(f"无法解析运行配置 {file_path}：{exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeConfigError(f"运行配置必须是对象：{file_path}")
    return {
        str(name): "" if value is None else str(value)
        for name, value in payload.items()
    }


def load_into_environ(path: str | Path | None = None) -> dict[str, str]:
    """把投影中的已知键写入 `os.environ`，不覆盖非空的显式环境变量。

    返回实际导出的键值，便于脚本打印或测试断言。
    """
    exported: dict[str, str] = {}
    for name, value in load(path).items():
        if name not in KNOWN_KEYS or not value.strip():
            continue
        if os.environ.get(name, "").strip():
            continue
        os.environ[name] = value
        exported[name] = value
    return exported


__all__ = [
    "APP_DIR",
    "DEFAULT_PATH",
    "RuntimeConfigError",
    "default_path",
    "load",
    "load_into_environ",
]
