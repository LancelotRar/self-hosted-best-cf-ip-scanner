"""认证路由：首次设置、登录、登出、改密。"""

from __future__ import annotations

import hmac
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from ..audit import record
from ..security import (
    MIN_PASSWORD_LENGTH,
    Security,
    client_ip,
    hash_password,
    require_user,
    verify_csrf,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


class SetupIn(BaseModel):
    password: str


class LoginIn(BaseModel):
    password: str
    username: str = "admin"


class PasswordIn(BaseModel):
    current_password: str
    new_password: str


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _admin(conn):
    return conn.execute(
        "SELECT id, username, password_hash, session_epoch"
        " FROM users ORDER BY id LIMIT 1"
    ).fetchone()


def _security(request: Request) -> Security:
    return request.app.state.security


def _validate_password(password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(
            status_code=422, detail=f"密码至少 {MIN_PASSWORD_LENGTH} 个字符"
        )


@router.get("/status")
def status(request: Request) -> dict[str, object]:
    conn = request.app.state.conn
    user = _admin(conn)
    authenticated = False
    if user is not None:
        session = _security(request).read_session(
            request.cookies.get("panel_session")
        )
        authenticated = session == (int(user["id"]), int(user["session_epoch"]))
    return {
        "initialized": user is not None,
        "authenticated": authenticated,
        "username": user["username"] if user is not None else None,
        "setup_token_required": bool(request.app.state.settings.setup_token),
    }


@router.post("/setup", status_code=201)
def setup(payload: SetupIn, request: Request, response: Response) -> dict[str, object]:
    conn = request.app.state.conn
    if _admin(conn) is not None:
        raise HTTPException(status_code=409, detail="面板已初始化，请直接登录")
    expected_token = request.app.state.settings.setup_token
    if expected_token:
        provided = request.headers.get("X-Setup-Token", "")
        if not provided or not hmac.compare_digest(provided, expected_token):
            raise HTTPException(status_code=403, detail="setup token 不正确")
    _validate_password(payload.password)
    now = _now()
    with conn:
        cursor = conn.execute(
            "INSERT INTO users (username, password_hash, created_at, updated_at)"
            " VALUES (?, ?, ?, ?)",
            ("admin", hash_password(payload.password), now, now),
        )
    user_id = int(cursor.lastrowid)
    record(conn, "admin", "auth.setup", "users", "首次设置管理员密码", client_ip(request))
    _security(request).set_cookies(response, request, user_id, 0)
    return {"initialized": True, "username": "admin"}


@router.post("/login")
def login(payload: LoginIn, request: Request, response: Response) -> dict[str, object]:
    conn = request.app.state.conn
    security = _security(request)
    ip = client_ip(request)
    # 只按「用户名 + 来源 IP」限速：全局 user_key 会让任意 IP 用 5 次失败
    # 把管理员锁死 60 秒，构成拒绝服务。
    pair_key = f"{payload.username}:{ip}"
    if not security.limiter.allow(pair_key):
        record(
            conn,
            payload.username,
            "auth.login_rate_limited",
            "users",
            "登录尝试过于频繁",
            ip,
        )
        raise HTTPException(status_code=429, detail="登录尝试过于频繁，请稍后再试")

    user = _admin(conn)
    if user is None or user["username"] != payload.username or not verify_password(
        payload.password, user["password_hash"]
    ):
        security.limiter.record_failure(pair_key)
        record(conn, payload.username, "auth.login_failed", "users", "密码错误", ip)
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    security.limiter.reset(pair_key)
    security.set_cookies(
        response, request, int(user["id"]), int(user["session_epoch"])
    )
    record(conn, user["username"], "auth.login", "users", "登录成功", ip)
    return {"authenticated": True, "username": user["username"]}


@router.post("/logout", dependencies=[Depends(verify_csrf)])
def logout(request: Request, response: Response) -> dict[str, object]:
    conn = request.app.state.conn
    session = _security(request).read_session(request.cookies.get("panel_session"))
    if session is not None:
        user_id, epoch = session
        row = conn.execute(
            "SELECT session_epoch FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if row is not None and int(row["session_epoch"]) == epoch:
            with conn:
                conn.execute(
                    "UPDATE users SET session_epoch = session_epoch + 1 WHERE id = ?",
                    (user_id,),
                )
    Security.clear_cookies(response)
    record(
        conn,
        "admin",
        "auth.logout",
        "users",
        "登出",
        client_ip(request),
    )
    return {"authenticated": False}


@router.post("/password", dependencies=[Depends(require_user), Depends(verify_csrf)])
def change_password(
    payload: PasswordIn, request: Request, response: Response
) -> dict[str, object]:
    conn = request.app.state.conn
    user = _admin(conn)
    if user is None:
        raise HTTPException(status_code=401, detail="未登录")
    if not verify_password(payload.current_password, user["password_hash"]):
        record(
            conn, user["username"], "auth.password_failed", "users", "当前密码错误",
            client_ip(request),
        )
        raise HTTPException(status_code=403, detail="当前密码错误")
    _validate_password(payload.new_password)
    next_epoch = int(user["session_epoch"]) + 1
    with conn:
        conn.execute(
            "UPDATE users SET password_hash = ?, session_epoch = ?, updated_at = ?"
            " WHERE id = ?",
            (hash_password(payload.new_password), next_epoch, _now(), user["id"]),
        )
    # 当前会话换发新 epoch，其他旧会话立即失效。
    _security(request).set_cookies(
        response, request, int(user["id"]), next_epoch
    )
    record(
        conn, user["username"], "auth.password", "users", "修改密码", client_ip(request)
    )
    return {"updated": True}


__all__ = ["router"]
