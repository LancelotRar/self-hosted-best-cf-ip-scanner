"""敏感值脱敏：diff、审计、日志、配置版本共用。

规则：
- `GIT_TOKEN` 等只写参数：`KEY=值` 整体替换为 `KEY=***`；
- 代理类参数：只遮挡 URL 里的账号密码（`scheme://***@host`），保留主机名便于排障；
- 任意 URL 中的 `://user:pass@` 一律遮挡。

面板永不返回敏感明文，本模块是最后一道兜底：即将落盘/写库/打印的文本都过一遍。
"""

from __future__ import annotations

import re

from scanner.schema import PARAMS

_MASK = "***"

# 代理类参数：值里的凭据要遮，主机与端口保留。
_PROXY_NAMES = frozenset(
    {
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
        "NO_PROXY",
        "no_proxy",
    }
)

# 只写参数：整段值替换掉。
_TOKEN_NAMES = tuple(
    spec.name
    for spec in PARAMS
    if spec.secret and spec.name not in _PROXY_NAMES
)

_URL_USERINFO = re.compile(r"(?P<scheme>[a-zA-Z][a-zA-Z0-9+.\-]*://)[^/@\s]+@")
_TOKEN_ASSIGNMENT = (
    re.compile(
        rf"(?i)\b((?:{'|'.join(map(re.escape, _TOKEN_NAMES))})\s*[=:]\s*)"
        r"(\"[^\"]*\"|'[^']*'|\S+)"
    )
    if _TOKEN_NAMES
    else None
)


def redact_secrets(text: str) -> str:
    """把文本里的凭据替换成 `***`；无凭据时原样返回。"""
    if not text:
        return text
    redacted = _URL_USERINFO.sub(rf"\g<scheme>{_MASK}@", text)
    if _TOKEN_ASSIGNMENT is not None:
        redacted = _TOKEN_ASSIGNMENT.sub(rf"\g<1>{_MASK}", redacted)
    return redacted


__all__ = ["redact_secrets"]
