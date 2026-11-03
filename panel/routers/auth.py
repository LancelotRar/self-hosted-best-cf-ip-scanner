"""认证路由：首次设置、登录、登出、改密。"""

from __future__ import annotations

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
        "SELECT id, username, password_hash FROM users ORDER BY id LIMIT 1"
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
        authenticated = (
            _security(request).read_session(
                request.cookies.get("panel_session")
            )
            == user["id"]
        )
    return {
        "initialized": user is not None,
        "authenticated": authenticated,
        "username": user["username"] if user is not None else None,
    }


@router.post("/setup", status_code=201)
def setup(payload: SetupIn, request: Request, response: Response) -> dict[str, object]:
    conn = request.app.state.conn
    if _admin(conn) is not None:
        raise HTTPException(status_code=409, detail="面板已初始化，请直接登录")
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
    _security(request).set_cookies(response, request, user_id)
    return {"initialized": True, "username": "admin"}


@router.post("/login")
def login(payload: LoginIn, request: Request, response: Response) -> dict[str, object]:
    conn = request.app.state.conn
    security = _security(request)
    ip = client_ip(request)
    user_key = f"user:{payload.username}"
    pair_key = f"{payload.username}:{ip}"
    if not (security.limiter.allow(pair_key) and security.limiter.allow(user_key)):
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
        security.limiter.record_failure(user_key)
        record(conn, payload.username, "auth.login_failed", "users", "密码错误", ip)
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    security.limiter.reset(pair_key)
    security.limiter.reset(user_key)
    security.set_cookies(response, request, int(user["id"]))
    record(conn, user["username"], "auth.login", "users", "登录成功", ip)
    return {"authenticated": True, "username": user["username"]}


@router.post("/logout", dependencies=[Depends(verify_csrf)])
def logout(request: Request, response: Response) -> dict[str, object]:
    Security.clear_cookies(response)
    record(
        request.app.state.conn,
        "admin",
        "auth.logout",
        "users",
        "登出",
        client_ip(request),
    )
    return {"authenticated": False}


@router.post("/password", dependencies=[Depends(require_user), Depends(verify_csrf)])
def change_password(payload: PasswordIn, request: Request) -> dict[str, object]:
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
    with conn:
        conn.execute(
            "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
            (hash_password(payload.new_password), _now(), user["id"]),
        )
    record(
        conn, user["username"], "auth.password", "users", "修改密码", client_ip(request)
    )
    return {"updated": True}


__all__ = ["router"]
