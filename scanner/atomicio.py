"""原子写文件工具(CSV/JSON/TXT) —— 零业务知识, 只负责"写完整或不写"。

写法: 在目标同目录生成唯一临时文件(tempfile, 跨进程安全) ->
os.replace 原子替换。进程被杀时最多留下 *.tmp 文件(已被 .gitignore
忽略), 不会出现半截文件; 并发进程写同一目标也不会互写同一临时名。
"""

from __future__ import annotations

import csv
import json
import os
import tempfile
from pathlib import Path
from typing import Callable, TextIO


def _atomic_write(path: Path, writer: Callable[[TextIO], None]) -> None:
    """原子写通用骨架: 唯一临时文件 + os.replace。

    writer(handle) 负责实际写入内容(handle 为文本模式已打开的文件)。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=path.parent, prefix=path.name + ".", suffix=".tmp"
    )
    temporary = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            writer(handle)
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def write_csv_atomic(path: Path, header: list[str], rows: list[list[str]]) -> None:
    """原子写入 CSV（UTF-8 BOM, 兼容 Excel）。"""

    def _write(handle: TextIO) -> None:
        handle.write("\ufeff")  # BOM: Excel 打开不乱码
        csv_writer = csv.writer(handle)
        csv_writer.writerow(header)
        csv_writer.writerows(rows)

    _atomic_write(path, _write)


def write_json_atomic(path: Path, data: object) -> None:
    """原子写入 JSON。"""

    def _write(handle: TextIO) -> None:
        json.dump(data, handle, ensure_ascii=False, indent=2)

    _atomic_write(path, _write)


def write_txt_atomic(path: Path, lines: list[str]) -> None:
    """原子写入纯文本订阅文件（UTF-8 无 BOM, 行以 \\n 结尾）。"""

    def _write(handle: TextIO) -> None:
        for line in lines:
            handle.write(line + "\n")

    _atomic_write(path, _write)
