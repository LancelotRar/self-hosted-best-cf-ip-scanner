"""Docker Compose `.env` 子集解析。

只实现项目实际需要的语法，遇到不支持或歧义写法立即报错并给出行号——
静默读错配置比启动失败更难排查。

支持：
- 空行、整行注释（`#` 开头）；
- `KEY=VALUE` 与 `KEY: VALUE`；
- 单引号字面量（`'...'`，不做转义）；
- 双引号（`"..."`，支持 `\\n` `\\r` `\\t` `\\\\` `\\"` 转义）；
- 未加引号值的行内注释：` #` 之后丢弃（引号内的 `#` 不是注释）。

拒绝（抛 `DotenvError`）：`${VAR}` 插值、`export` 前缀、未闭合引号、
引号外的多余内容、值内换行或 NUL。
"""

from __future__ import annotations

from pathlib import Path

_BOM = "\ufeff"
_KEY_END = ("=", ":")


class DotenvError(ValueError):
    """`.env` 语法错误；`line_no` 从 1 开始。"""

    def __init__(self, line_no: int, message: str) -> None:
        self.line_no = line_no
        self.message = message
        super().__init__(f"第 {line_no} 行：{message}")


def _reject_interpolation(value: str, line_no: int) -> None:
    if "${" in value:
        raise DotenvError(line_no, "不支持 ${VAR} 插值，请写具体值")


def _parse_double_quoted(rest: str, line_no: int) -> tuple[str, str]:
    """解析 `"..."`，返回 (值, 引号之后的剩余文本)。"""
    out: list[str] = []
    i = 0
    escapes = {"n": "\n", "r": "\r", "t": "\t", "\\": "\\", '"': '"'}
    while i < len(rest):
        char = rest[i]
        if char == "\\":
            i += 1
            if i >= len(rest):
                raise DotenvError(line_no, "未闭合的引号")
            nxt = rest[i]
            out.append(escapes.get(nxt, "\\" + nxt))
            i += 1
            continue
        if char == '"':
            return "".join(out), rest[i + 1 :]
        out.append(char)
        i += 1
    raise DotenvError(line_no, "未闭合的引号")


def _parse_value(rest: str, line_no: int) -> str:
    value_text = rest.lstrip()
    if value_text.startswith("'"):
        end = value_text.find("'", 1)
        if end == -1:
            raise DotenvError(line_no, "未闭合的引号")
        value = value_text[1:end]
        _check_tail(value_text[end + 1 :], line_no)
        return value
    if value_text.startswith('"'):
        value, tail = _parse_double_quoted(value_text[1:], line_no)
        _reject_interpolation(value, line_no)
        _check_tail(tail, line_no)
        return value
    # 未加引号：` #` 之后为行内注释
    comment_at = value_text.find(" #")
    if comment_at != -1:
        value_text = value_text[:comment_at]
    value = value_text.strip()
    _reject_interpolation(value, line_no)
    if "\x00" in value:
        raise DotenvError(line_no, "值不能包含 NUL")
    return value


def _check_tail(tail: str, line_no: int) -> None:
    stripped = tail.strip()
    if stripped and not stripped.startswith("#"):
        raise DotenvError(line_no, "引号之后存在无法解析的内容")


def parse_dotenv(text: str) -> dict[str, str]:
    """解析 `.env` 文本；重复键以后出现的为准。"""
    if text.startswith(_BOM):
        text = text[1:]
    values: dict[str, str] = {}
    for line_no, raw in enumerate(text.split("\n"), start=1):
        line = raw.rstrip("\r")
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("export ") or stripped.startswith("export\t"):
            raise DotenvError(line_no, "不支持 export 前缀，直接写 KEY=VALUE")
        positions = [line.find(ch) for ch in _KEY_END]
        positions = [pos for pos in positions if pos != -1]
        if not positions:
            raise DotenvError(line_no, "缺少 '='，无法识别为 KEY=VALUE")
        sep = min(positions)
        key = line[:sep].strip()
        if not key:
            raise DotenvError(line_no, "缺少键名")
        if any(ch.isspace() for ch in key):
            raise DotenvError(line_no, f"键名非法：{key!r}")
        values[key] = _parse_value(line[sep + 1 :], line_no)
    return values


def load_dotenv(path: str | Path) -> dict[str, str]:
    """读取 `.env` 文件；文件不存在返回空字典。"""
    file_path = Path(path)
    if not file_path.is_file():
        return {}
    return parse_dotenv(file_path.read_text(encoding="utf-8"))


def quote_value(value: str) -> str:
    """把值编码成可被 `parse_dotenv` 原样读回的写法。"""
    if any(ch in value for ch in ("\n", "\r", "\x00")):
        raise ValueError("值不能包含换行或 NUL")
    if value == "":
        return "''"
    needs_quote = (
        any(ch.isspace() for ch in value)
        or "#" in value
        or "'" in value
        or '"' in value
    )
    if not needs_quote:
        return value
    if "'" not in value:
        return f"'{value}'"
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


__all__ = ["DotenvError", "load_dotenv", "parse_dotenv", "quote_value"]
