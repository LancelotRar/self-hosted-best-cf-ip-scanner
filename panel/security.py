"""认证基础：Argon2id 密码哈希、签名会话 Cookie、CSRF 与登录限速。

单管理员场景：
- 密码只存 Argon2id 哈希；
- 会话是 itsdangerous 签名 Cookie（不落库，登出即删）；
- 写操作要求 `X-CSRF-Token` 与 `panel_csrf` Cookie 相等；
- 登录失败按「用户名 + 来源 IP」限速，代理后不会因为单一 IP 锁死所有人。
"""

from __future__ import annotations

import hmac
import os
import secrets
import time
from pathlib import Path

import argon2
from argon2 import PasswordHasher
from fastapi import HTTPException, Request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from .settings import Settings

SESSION_COOKIE = "panel_session"
CSRF_COOKIE = "panel_csrf"
CSRF_HEADER = "X-CSRF-Token"
MIN_PASSWORD_LENGTH = 8

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    """Argon2id 哈希。"""
    return _hasher.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    """校验密码；哈希损坏或格式不符一律视为不匹配。"""
    try:
        return _hasher.verify(hashed, password)
    except (argon2.exceptions.Argon2Error, ValueError):
        return False


class LoginLimiter:
    """滑动窗口限速：窗口内失败次数达到上限即拒绝。"""

    def __init__(
        self,
        max_failures: int = 5,
        window_s: float = 60,
        clock=time.monotonic,
        max_keys: int = 10_000,
    ) -> None:
        self.max_failures = max_failures
        self.window_s = window_s
        self.clock = clock
        self.max_keys = max_keys
        self._failures: dict[str, list[float]] = {}

    def _recent(self, key: str) -> list[float]:
        cutoff = self.clock() - self.window_s
        kept = [stamp for stamp in self._failures.get(key, []) if stamp >= cutoff]
        if kept:
            self._failures[key] = kept
        else:
            self._failures.pop(key, None)
        return kept

    def allow(self, key: str) -> bool:
        return len(self._recent(key)) < self.max_failures

    def record_failure(self, key: str) -> None:
        self._recent(key)
        self._failures.setdefault(key, []).append(self.clock())
        # 攻击者可以用大量随机用户名/IP 撑大字典；超过上限时丢弃最旧 key。
        while len(self._failures) > self.max_keys:
            self._failures.pop(next(iter(self._failures)), None)

    def reset(self, key: str) -> None:
        self._failures.pop(key, None)


class Security:
    """绑定一份 `Settings` 的认证上下文（会话密钥在首次启动时生成）。"""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.serializer = URLSafeTimedSerializer(
            self._load_secret(settings.secret_path), salt="panel-session"
        )
        self.limiter = LoginLimiter()

    @staticmethod
    def _load_secret(path: Path) -> str:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_file():
            existing = path.read_text(encoding="utf-8").strip()
            if existing:
                return existing
        secret = secrets.token_hex(32)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(secret, encoding="utf-8")
        try:
            os.chmod(temporary, 0o600)
        except OSError:
            pass  # Windows 上权限位不生效，文件仍在受控目录内
        os.replace(temporary, path)
        return secret

    def create_session(
        self, user_id: int, epoch: int = 0, days: int | None = None
    ) -> str:
        return self.serializer.dumps({"uid": user_id, "epoch": int(epoch)})

    def read_session(
        self, token: str | None, days: int | None = None
    ) -> tuple[int, int] | None:
        """返回 (user_id, session_epoch)；签名无效或缺少 epoch 时视为未登录。"""
        if not token:
            return None
        max_age = (days or self.settings.session_days) * 86400
        try:
            data = self.serializer.loads(token, max_age=max_age)
        except (BadSignature, SignatureExpired):
            return None
        if not isinstance(data, dict):
            return None
        user_id = data.get("uid")
        epoch = data.get("epoch")
        if not isinstance(user_id, int) or not isinstance(epoch, int):
            return None
        return user_id, epoch

    def set_cookies(
        self, response, request: Request, user_id: int, epoch: int = 0
    ) -> str:
        """写入会话与 CSRF Cookie，返回本次 CSRF token。"""
        days = self.settings.session_days
        secure = self.settings.trust_proxy and (
            request.headers.get("x-forwarded-proto", "").lower() == "https"
        )
        response.set_cookie(
            SESSION_COOKIE,
            self.create_session(user_id, epoch, days),
            max_age=days * 86400,
            httponly=True,
            samesite="strict",
            secure=secure,
            path="/",
        )
        csrf = secrets.token_urlsafe(32)
        response.set_cookie(
            CSRF_COOKIE,
            csrf,
            max_age=days * 86400,
            httponly=False,
            samesite="strict",
            secure=secure,
            path="/",
        )
        return csrf

    @staticmethod
    def clear_cookies(response) -> None:
        response.delete_cookie(SESSION_COOKIE, path="/")
        response.delete_cookie(CSRF_COOKIE, path="/")


# ------------------------------------------------------------ 依赖函数 --
def client_ip(request: Request) -> str:
    """来源 IP：仅在信任反代时采信 `X-Forwarded-For` 首项。"""
    settings = request.app.state.settings
    if settings.trust_proxy:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def require_user(request: Request) -> int:
    """已登录用户 id；未登录、会话过期或密码已变更时返回 401。"""
    security: Security = request.app.state.security
    session = security.read_session(request.cookies.get(SESSION_COOKIE))
    if session is None:
        raise HTTPException(status_code=401, detail="未登录")
    user_id, epoch = session
    row = request.app.state.conn.execute(
        "SELECT session_epoch FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    if row is None or int(row["session_epoch"]) != epoch:
        raise HTTPException(status_code=401, detail="未登录")
    return user_id


def verify_csrf(request: Request) -> None:
    """校验 `X-CSRF-Token` 与 Cookie；缺失或不一致返回 403。"""
    header = request.headers.get(CSRF_HEADER, "")
    cookie = request.cookies.get(CSRF_COOKIE, "")
    if not header or not cookie or not hmac.compare_digest(header, cookie):
        raise HTTPException(status_code=403, detail="CSRF 校验失败，请刷新页面")


# ------------------------------------------------- CLI / 非请求上下文使用 --
_default_security: Security | None = None


def configure(settings: Settings) -> Security:
    """绑定进程默认认证上下文（CLI 与测试使用）。"""
    global _default_security
    _default_security = Security(settings)
    return _default_security


def get_security(settings: Settings | None = None) -> Security:
    global _default_security
    if settings is not None:
        return configure(settings)
    if _default_security is None:
        _default_security = Security(Settings.from_env())
    return _default_security


def create_session(user_id: int, epoch: int = 0, days: int | None = None) -> str:
    return get_security().create_session(user_id, epoch, days)


def read_session(token: str) -> tuple[int, int] | None:
    return get_security().read_session(token)


__all__ = [
    "CSRF_COOKIE",
    "CSRF_HEADER",
    "SESSION_COOKIE",
    "LoginLimiter",
    "Security",
    "client_ip",
    "configure",
    "create_session",
    "get_security",
    "hash_password",
    "read_session",
    "require_user",
    "verify_csrf",
    "verify_password",
]
