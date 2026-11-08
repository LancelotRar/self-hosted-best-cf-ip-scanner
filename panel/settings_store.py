"""应用配置的数据库真源与运行期投影。

边界：
- 首次启动把 schema 默认值写入 `settings`；之后数据库是唯一真源。
- 敏感参数落库前用 Fernet 加密，密钥在 `/panel-data/settings.key`，不随数据库导出。
- 扫描器不读数据库：面板把生效值渲染成 `/scanner-config/runtime.json`，
  扫描器每轮读取该投影；投影永远可以从数据库重新生成。

面板是唯一编辑入口，不存在任何手工应用配置文件。
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from scanner.schema import BY_NAME, PARAMS, format_value

from .files import chown
from .settings import Settings


class SettingsKeyError(RuntimeError):
    """配置加密密钥缺失或损坏。"""


@dataclass(frozen=True)
class ConfigDocument:
    """一次读取的生效配置快照。"""

    values: dict[str, str]
    configured: frozenset[str]
    revision: int
    updated_at: str | None
    updated_by: str | None
    sha256: str


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- 密钥 --
def _read_key(path: Path) -> bytes | None:
    try:
        raw = path.read_bytes().strip()
    except FileNotFoundError:
        return None
    except OSError as exc:  # noqa: BLE001 - 密钥读不到就不能安全解密
        raise SettingsKeyError(f"无法读取配置密钥 {path}：{exc}") from exc
    return raw or None


def _key(settings: Settings) -> bytes:
    path = settings.settings_key_path
    raw = _read_key(path)
    if raw is not None:
        return raw
    path.parent.mkdir(parents=True, exist_ok=True)
    key = Fernet.generate_key()
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:  # 另一个进程刚创建：以磁盘上的为准
        existing = _read_key(path)
        if existing is None:
            raise SettingsKeyError(f"配置密钥为空：{path}")
        return existing
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(key)
        handle.flush()
        os.fsync(handle.fileno())
    return key


def _fernet(settings: Settings) -> Fernet:
    try:
        return Fernet(_key(settings))
    except (ValueError, TypeError) as exc:
        raise SettingsKeyError("配置密钥格式不正确，无法解密敏感参数") from exc


def encrypt(settings: Settings, plaintext: str) -> str:
    return _fernet(settings).encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt(settings: Settings, token: str) -> str:
    try:
        return _fernet(settings).decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError, UnicodeError) as exc:
        raise SettingsKeyError("敏感参数解密失败：配置密钥可能已更换") from exc


# ---------------------------------------------------------------- 读取 --
def _meta(conn) -> tuple[int, str | None, str | None]:
    row = conn.execute(
        "SELECT revision, updated_at, updated_by FROM settings_meta WHERE id = 1"
    ).fetchone()
    if row is None:
        return 0, None, None
    return int(row["revision"]), row["updated_at"], row["updated_by"]


def _overrides(conn, settings: Settings) -> dict[str, str]:
    """数据库里的显式值（敏感项已解密）；空字符串视为未设置。"""
    overrides: dict[str, str] = {}
    for row in conn.execute("SELECT name, value, encrypted FROM settings"):
        spec = BY_NAME.get(row["name"])
        if spec is None:
            continue  # 已下线的参数：忽略，不影响启动
        raw = decrypt(settings, row["value"]) if row["encrypted"] else row["value"]
        if spec.kind != "secret":
            raw = raw.strip()
        if not raw:
            continue
        overrides[spec.name] = raw
    return overrides


def resolved(conn, settings: Settings) -> tuple[dict[str, str], frozenset[str]]:
    """全部参数的生效值（数据库 > schema 默认），以配置字符串表示。"""
    overrides = _overrides(conn, settings)
    values: dict[str, str] = {}
    for spec in PARAMS:
        raw = overrides.get(spec.name, "")
        values[spec.name] = raw if raw else format_value(spec, spec.default)
    return values, frozenset(overrides)


def document(conn, settings: Settings) -> ConfigDocument:
    values, configured = resolved(conn, settings)
    revision, updated_at, updated_by = _meta(conn)
    payload = json.dumps(
        {"revision": revision, "values": values},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return ConfigDocument(
        values=values,
        configured=configured,
        revision=revision,
        updated_at=updated_at,
        updated_by=updated_by,
        sha256=_sha256(payload),
    )


def value(conn, settings: Settings, name: str) -> str:
    document_values, _ = resolved(conn, settings)
    return document_values[name]


# ---------------------------------------------------------------- 写入 --
def apply_overrides(
    conn,
    settings: Settings,
    updates: Mapping[str, str],
    actor: str = "admin",
) -> None:
    """在调用方的事务里写入显式值并递增修订号；空值 = 恢复默认。"""
    now = _now_iso()
    for name, raw in updates.items():
        spec = BY_NAME.get(name)
        if spec is None:
            continue
        if not raw:
            conn.execute("DELETE FROM settings WHERE name = ?", (name,))
            continue
        encrypted = bool(spec.secret)
        stored = encrypt(settings, raw) if encrypted else raw
        conn.execute(
            "INSERT INTO settings (name, value, encrypted, updated_at, updated_by)"
            " VALUES (?, ?, ?, ?, ?)"
            " ON CONFLICT(name) DO UPDATE SET"
            " value = excluded.value, encrypted = excluded.encrypted,"
            " updated_at = excluded.updated_at, updated_by = excluded.updated_by",
            (name, stored, 1 if encrypted else 0, now, actor),
        )
    row = conn.execute("SELECT revision FROM settings_meta WHERE id = 1").fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO settings_meta (id, revision, updated_at, updated_by)"
            " VALUES (1, 1, ?, ?)",
            (now, actor),
        )
    else:
        conn.execute(
            "UPDATE settings_meta SET revision = revision + 1,"
            " updated_at = ?, updated_by = ? WHERE id = 1",
            (now, actor),
        )


def restore(conn, settings: Settings, document: ConfigDocument, actor: str) -> None:
    """把配置整体恢复成给定快照（用于计划任务应用失败时回滚）。"""
    with conn:
        conn.execute("DELETE FROM settings")
        apply_overrides(
            conn,
            settings,
            {name: document.values[name] for name in document.configured},
            actor=actor,
        )


def seed_schema_defaults(conn, settings: Settings) -> bool:
    """首次启动把 schema 默认值写入数据库；之后数据库是唯一真源。"""
    if conn.execute("SELECT 1 FROM settings_meta WHERE id = 1").fetchone():
        return False
    now = _now_iso()
    with conn:
        for spec in PARAMS:
            raw = format_value(spec, spec.default)
            if not raw:
                continue
            stored = encrypt(settings, raw) if spec.secret else raw
            conn.execute(
                "INSERT OR IGNORE INTO settings"
                " (name, value, encrypted, updated_at, updated_by)"
                " VALUES (?, ?, ?, ?, 'bootstrap')",
                (spec.name, stored, 1 if spec.secret else 0, now),
            )
        conn.execute(
            "INSERT INTO settings_meta (id, revision, updated_at, updated_by)"
            " VALUES (1, 1, ?, 'bootstrap')",
            (now,),
        )
    return True


# ---------------------------------------------------------------- 投影 --
def projection_json(values: Mapping[str, str]) -> str:
    """把生效值渲染成扫描器读取的 JSON 投影。"""
    payload = {
        spec.name: str(values.get(spec.name, ""))
        for spec in PARAMS
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def stage_projection(settings: Settings, values: Mapping[str, str]) -> Path:
    """把候选配置写到目标目录的临时文件；提交前不替换正式投影。"""
    target = settings.runtime_config_path
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        dir=str(target.parent), prefix=".runtime.", suffix=".tmp"
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            handle.write(projection_json(values))
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        chown(Path(temporary), settings.puid, settings.pgid)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise
    return Path(temporary)


def commit_projection(settings: Settings, staged: Path) -> None:
    os.replace(staged, settings.runtime_config_path)
    chown(settings.runtime_config_path, settings.puid, settings.pgid)


def project(conn, settings: Settings) -> None:
    """按数据库当前值重写运行配置；面板启动与每次保存都会调用。"""
    values, _ = resolved(conn, settings)
    staged = stage_projection(settings, values)
    try:
        commit_projection(settings, staged)
    except BaseException:
        staged.unlink(missing_ok=True)
        raise


__all__ = [
    "ConfigDocument",
    "SettingsKeyError",
    "apply_overrides",
    "commit_projection",
    "decrypt",
    "document",
    "encrypt",
    "project",
    "projection_json",
    "resolved",
    "restore",
    "seed_schema_defaults",
    "stage_projection",
    "value",
]
