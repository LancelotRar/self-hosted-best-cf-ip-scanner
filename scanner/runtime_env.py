"""读取项目根 `.env`，并支持导出到进程环境。

`.env` 是唯一配置源；显式环境变量优先。这里只做「读文件 + 导出」，
不解析业务语义（类型转换在 `scanner/schema.py`）。
"""

from __future__ import annotations

import os
from pathlib import Path

from .dotenv import load_dotenv
from .schema import KNOWN_KEYS

APP_DIR = Path(__file__).resolve().parent.parent


def default_path() -> Path:
    """`DOTENV_PATH` 指向的 `.env`；未设置时退回代码根目录的 `.env`。"""
    configured = os.environ.get("DOTENV_PATH")
    return Path(configured) if configured else APP_DIR / ".env"


def load(path: str | Path | None = None) -> dict[str, str]:
    """读取 `.env`；文件不存在返回空字典。"""
    return load_dotenv(path if path is not None else default_path())


def load_into_environ(path: str | Path | None = None) -> dict[str, str]:
    """把 `.env` 中的已知键写入 `os.environ`，不覆盖非空的显式环境变量。

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


__all__ = ["APP_DIR", "default_path", "load", "load_into_environ"]
