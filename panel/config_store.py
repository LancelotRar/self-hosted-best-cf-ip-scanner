"""`.env` 配置事务：读取、渲染、校验、写入、回读、生效核对、备份与回滚。

保存不是"写文件就完事"：任何一步失败都要么不落盘，要么回滚到保存前的完整文件，
并把失败阶段返回给前端。`written` 与 `verification.status` 是两个概念——
写入成功不代表扫描器已经读到新值。
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from scanner.dotenv import DotenvError, parse_dotenv, quote_value
from scanner.schema import BY_NAME, PARAMS, coerce, format_value

from .audit import record as audit_record
from .docker_api import ScannerUnavailable
from .files import atomic_write
from .redact import redact_secrets
from .settings import Settings

MANAGED_BLOCK = "# --- panel managed ---"
BACKUP_KEEP = 30
CHECK_CONFIG_SCRIPT = "/usr/local/bin/check-config.py"
PRINT_CONFIG_SCRIPT = "/usr/local/bin/print-config.py"
APPLY_CONFIG_SCRIPT = "/usr/local/bin/apply-config.sh"

_ENTRY_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*[=:]")


class ConfigError(Exception):
    """配置事务失败的基类。"""


class ConfigConflict(ConfigError):
    """`.env` 已被其他进程修改（哈希不匹配）。"""


class ConfigInvalid(ConfigError):
    """候选配置非法；`errors` 是字段级错误列表。"""

    def __init__(self, errors: Sequence[Mapping[str, object]]) -> None:
        self.errors = [dict(error) for error in errors]
        super().__init__("配置校验失败")


class ConfigApplyFailed(ConfigError):
    """调度应用失败（已回滚）。"""


class ConfigWriteUnverified(ConfigError):
    """写入后回读不一致（已回滚）。"""


@dataclass(frozen=True)
class EnvDocument:
    path: Path
    text: str
    values: dict[str, str]
    sha256: str


@dataclass
class SaveResult:
    document: EnvDocument
    written: bool
    changed: list[dict]
    effects: dict
    verification: dict
    next_run: str | None
    warnings: list[str]

    @property
    def applied(self) -> bool:
        return self.written

    def to_dict(self) -> dict[str, object]:
        return {
            "written": self.written,
            "hash": self.document.sha256,
            "changed": self.changed,
            "effects": self.effects,
            "verification": self.verification,
            "next_run": self.next_run,
            "warnings": self.warnings,
        }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_env(settings: Settings) -> EnvDocument:
    """读取 `.env`；文件不存在视为空文件。语法不支持时抛 `DotenvError`。"""
    path = settings.env_path
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        text = ""
    values = parse_dotenv(text) if text.strip() else {}
    return EnvDocument(path=path, text=text, values=values, sha256=_sha256(text))


def render_env(text: str, updates: Mapping[str, str]) -> str:
    """原地替换已存在的键（保留注释/顺序），缺失键追加到文件末尾管理区块。"""
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines()
    seen: set[str] = set()
    output: list[str] = []
    for line in lines:
        match = _ENTRY_RE.match(line)
        if match and match.group(1) in updates:
            name = match.group(1)
            output.append(f"{name}={quote_value(str(updates[name]))}")
            seen.add(name)
        else:
            output.append(line)

    missing = [name for name in updates if name not in seen]
    if missing:
        if output and output[-1].strip():
            output.append("")
        output.append(MANAGED_BLOCK)
        for name in missing:
            output.append(f"{name}={quote_value(str(updates[name]))}")
    return newline.join(output) + newline


def redact(text: str) -> str:
    """委托统一的脱敏实现。"""
    return redact_secrets(text)


# ---------------------------------------------------------------- 校验 --
def _cross_field_errors(values: Mapping[str, str]) -> list[dict[str, object]]:
    errors: list[dict[str, object]] = []
    try:
        attempts = int(values.get("TCP_ATTEMPTS", BY_NAME["TCP_ATTEMPTS"].default))
        min_success = int(
            values.get("TCP_MIN_SUCCESS", BY_NAME["TCP_MIN_SUCCESS"].default)
        )
    except (TypeError, ValueError):
        return errors
    if min_success > attempts:
        errors.append(
            {"name": "TCP_MIN_SUCCESS", "message": "不得大于 TCP_ATTEMPTS"}
        )
    return errors


def validate_candidate(
    values: Mapping[str, str], env: Mapping[str, str] | None = None
) -> None:
    """候选配置干跑：跨字段校验 + （容器内）`check-config.py`。

    失败抛 `ValueError`，参数为字段级错误列表。
    """
    errors = _cross_field_errors(values)
    if errors:
        raise ValueError(errors)

    script = Path(CHECK_CONFIG_SCRIPT)
    if not script.is_file():
        return  # 本地/单元测试环境只做 schema 级校验

    payload = "".join(
        f"{name}={quote_value(str(value))}\n"
        for name, value in values.items()
        if name in BY_NAME
    )
    with tempfile.TemporaryDirectory() as temporary:
        candidate_path = Path(temporary) / ".env"
        candidate_path.write_text(payload, encoding="utf-8")
        process = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            timeout=60,
            env={**os.environ, "DOTENV_PATH": str(candidate_path)},
            check=False,
        )
    if process.returncode == 0:
        return
    lines = [line.strip() for line in (process.stderr or "").splitlines() if line.strip()]
    details = [
        {"name": None, "message": re.sub(r"^\d+\.\s*", "", line)} for line in lines[:10]
    ] or [{"name": None, "message": "候选配置校验失败"}]
    raise ValueError(details)


def _canonical_updates(updates: Mapping[str, object]) -> dict[str, str]:
    """类型校验 + 归一化（返回可直接写入 `.env` 的字符串值）。"""
    errors: list[dict[str, object]] = []
    clean: dict[str, str] = {}
    for name, raw in updates.items():
        spec = BY_NAME.get(name)
        if spec is None:
            errors.append({"name": name, "message": "未知参数"})
            continue
        if spec.read_only:
            errors.append(
                {"name": name, "message": "该参数只读，请在 .env 手工修改并重建容器"}
            )
            continue
        if raw is None:
            continue  # 敏感字段缺省 = 不修改
        try:
            value = coerce(spec, str(raw))
        except ValueError as exc:
            errors.append({"name": name, "message": str(exc) or "取值非法"})
            continue
        clean[name] = format_value(spec, value)
    if errors:
        raise ConfigInvalid(errors)
    return clean


def _with_proxy_exemption(
    clean: dict[str, str], current: Mapping[str, str]
) -> list[str]:
    """PROBE_HOST 变更时把新域名追加到 NO_PROXY / no_proxy（不删除旧条目）。"""
    host = clean.get("PROBE_HOST", "").strip()
    if not host:
        return []
    warnings: list[str] = []
    for key in ("NO_PROXY", "no_proxy"):
        if key in clean:
            continue  # 用户显式改了豁免清单就尊重
        raw = current.get(key) or str(BY_NAME[key].default)
        entries = [entry.strip() for entry in raw.split(",") if entry.strip()]
        if host not in entries and host.lower() not in {entry.lower() for entry in entries}:
            entries.append(host)
            clean[key] = ",".join(entries)
            warnings.append(f"PROBE_HOST 变更：已把 {host} 追加到 {key}")
    return warnings


# ------------------------------------------------------------ 写入与备份 --
def _backup_env(settings: Settings, document: EnvDocument) -> Path:
    target_dir = settings.panel_data_dir / "backups" / "env"
    target_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    target = target_dir / f"{stamp}.env"
    target.write_bytes(document.text.encode("utf-8"))
    try:
        os.chmod(target, 0o600)
    except OSError:
        pass
    for old in sorted(target_dir.glob("*.env"))[:-BACKUP_KEEP]:
        old.unlink(missing_ok=True)
    return target


def _write_env(settings: Settings, text: str) -> None:
    """原子替换 `.env`（实现见 `panel.files.atomic_write`）。"""
    atomic_write(settings.env_path, text)


def _restore(settings: Settings, backup: Path) -> None:
    _write_env(settings, backup.read_text(encoding="utf-8"))


# ------------------------------------------------------------ 生效核对 --
def _expectation(spec, raw: str | None) -> object:
    if raw is None or not raw.strip():
        return spec.default
    return coerce(spec, raw)


def _normalize(value: object) -> object:
    if isinstance(value, (tuple, list)):
        return list(value)
    return value


def _print_config(controller) -> dict[str, dict[str, object]]:
    handle = controller.exec_script(PRINT_CONFIG_SCRIPT, {})
    payload = b"".join(handle.stream())
    code = handle.wait()
    if code != 0:
        raise ScannerUnavailable(f"print-config.py 退出码 {code}")
    try:
        return json.loads(payload.decode("utf-8", "replace"))
    except (ValueError, AttributeError) as exc:
        raise ScannerUnavailable(f"无法解析生效配置：{exc}") from exc


def verify_effective(
    settings: Settings, controller, names: Sequence[str] | None = None
) -> dict[str, object]:
    """在扫描容器内读取生效值，与 `.env` 当前值逐项比对。"""
    checked_at = _now_iso()
    if controller is None:
        return {"status": "unavailable", "checked_at": checked_at, "details": []}
    try:
        effective = _print_config(controller)
    except ScannerUnavailable:
        return {"status": "unavailable", "checked_at": checked_at, "details": []}

    document = read_env(settings)
    if names is None:
        names = [
            spec.name
            for spec in PARAMS
            if not spec.secret and not spec.read_only and spec.consumer in {"scanner", "shell"}
        ]
    details: list[dict[str, object]] = []
    for name in names:
        spec = BY_NAME.get(name)
        if spec is None or spec.secret or spec.read_only:
            continue
        try:
            expected = _expectation(spec, document.values.get(name))
        except ValueError:
            continue
        actual = (effective.get(name) or {}).get("value")
        if _normalize(actual) != _normalize(expected):
            details.append({"name": name, "expected": expected, "actual": actual})
    return {
        "status": "mismatch" if details else "verified",
        "checked_at": checked_at,
        "details": details,
    }


def _effect(spec) -> str:
    if spec.restart:
        return "restart_required"
    if spec.name == "CRON_SCHEDULE":
        return "schedule_reload"
    return "next_round"


def _next_run(document: EnvDocument) -> str | None:
    try:
        from . import cron
    except ImportError:
        return None  # cron 模块在后续任务落地
    expression = document.values.get("CRON_SCHEDULE") or str(
        BY_NAME["CRON_SCHEDULE"].default
    )
    timezone_name = document.values.get("TZ") or str(BY_NAME["TZ"].default)
    try:
        runs = cron.next_runs(expression, timezone_name, count=1)
    except Exception:  # noqa: BLE001 - 非法 cron 由校验阶段拦截
        return None
    return runs[0].isoformat() if runs else None


# ---------------------------------------------------------------- 保存 --
def save(
    settings: Settings,
    expected_hash: str,
    updates: Mapping[str, object],
    actor: str,
    controller=None,
) -> SaveResult:
    """保存事务：校验 -> 写入 -> 回读 -> 调度 -> 核对 -> 版本与审计。"""
    document = read_env(settings)
    if expected_hash != document.sha256:
        raise ConfigConflict("配置文件已被修改，请刷新后重试")

    clean = _canonical_updates(updates)
    warnings = _with_proxy_exemption(clean, document.values)

    merged = {name: value for name, value in document.values.items() if name in BY_NAME}
    merged.update(clean)
    try:
        validate_candidate(merged)
    except ValueError as exc:
        errors = exc.args[0] if exc.args else [{"name": None, "message": str(exc)}]
        if not isinstance(errors, list):
            errors = [{"name": None, "message": str(errors)}]
        raise ConfigInvalid(errors) from exc

    if not clean:
        return SaveResult(
            document=document,
            written=False,
            changed=[],
            effects={"next_round": [], "schedule_reloaded": False, "restart_required": []},
            verification={"status": "verified", "checked_at": _now_iso(), "details": []},
            next_run=_next_run(document),
            warnings=warnings,
        )

    candidate = render_env(document.text, clean)
    backup = _backup_env(settings, document)
    _write_env(settings, candidate)

    written_document = read_env(settings)
    if written_document.text != candidate or written_document.sha256 != _sha256(candidate):
        _restore(settings, backup)
        raise ConfigWriteUnverified("写入后回读不一致，已回滚到保存前内容")

    changed: list[dict] = []
    for name, new_value in clean.items():
        spec = BY_NAME[name]
        old_raw = document.values.get(name)
        if old_raw == new_value:
            continue
        changed.append(
            {
                "name": name,
                "old": None if spec.secret else old_raw,
                "new": None if spec.secret else new_value,
                "effect": _effect(spec),
            }
        )

    next_round = [item["name"] for item in changed if item["effect"] == "next_round"]
    restart_required = [
        item["name"] for item in changed if item["effect"] == "restart_required"
    ]

    schedule_reloaded = False
    schedule_changed = "CRON_SCHEDULE" in clean
    if schedule_changed:
        offline = False
        if controller is None:
            offline = True
            warnings.append("扫描容器不可用：已保存，容器恢复后由 watcher 自动重载调度")
        else:
            try:
                handle = controller.exec_script(APPLY_CONFIG_SCRIPT, {})
                code = handle.wait()
            except ScannerUnavailable:
                offline = True
                code = 0
                warnings.append("扫描容器不可用：已保存，容器恢复后由 watcher 自动重载调度")
            if not offline and code != 0:
                _restore(settings, backup)
                raise ConfigApplyFailed("调度应用失败，已回滚 .env")
        schedule_reloaded = not offline

    hot_names = [
        item["name"]
        for item in changed
        if item["effect"] == "next_round" and BY_NAME[item["name"]].consumer in {"scanner", "shell"}
    ]
    verification = verify_effective(settings, controller, hot_names)
    status = verification["status"]
    if status != "mismatch" and restart_required:
        status = "restart_required"
    verification = {**verification, "status": status}
    if status == "unavailable":
        warnings.append("已保存，下一轮扫描会读取新值；当前无法核对扫描器生效值")

    effects = {
        "next_round": next_round,
        "schedule_reloaded": schedule_reloaded,
        "restart_required": restart_required,
    }

    stored = {
        name: format_value(BY_NAME[name], coerce(BY_NAME[name], value))
        for name, value in merged.items()
        if not BY_NAME[name].secret
    }
    diff = redact(
        "\n".join(
            f"- {item['name']}={item['old']}\n+ {item['name']}={item['new']}"
            for item in changed
            if not BY_NAME[item["name"]].secret
        )
    )
    with settings_db(settings) as conn:
        with conn:
            conn.execute(
                "INSERT INTO config_versions (created_at, actor, sha256, values_json, diff)"
                " VALUES (?, ?, ?, ?, ?)",
                (
                    _now_iso(),
                    actor,
                    written_document.sha256,
                    json.dumps(stored, ensure_ascii=False),
                    diff,
                ),
            )
        audit_record(
            conn,
            actor,
            "config.save",
            str(settings.env_path),
            diff or "无实际变更",
            "panel",
        )

    return SaveResult(
        document=written_document,
        written=True,
        changed=changed,
        effects=effects,
        verification=verification,
        next_run=_next_run(written_document),
        warnings=warnings,
    )


def settings_db(settings: Settings):
    """打开面板数据库（配置版本与审计写入用）。"""
    from .db import connect, migrate

    conn = connect(settings.db_path)
    migrate(conn)
    return _Closing(conn)


class _Closing:
    def __init__(self, conn) -> None:
        self._conn = conn

    def __enter__(self):
        return self._conn

    def __exit__(self, *exc_info) -> None:
        self._conn.close()


def param_entries(document: EnvDocument) -> list[dict[str, object]]:
    """GET /api/config 的参数列表（敏感值永不返回）。"""
    entries: list[dict[str, object]] = []
    for spec in PARAMS:
        raw = document.values.get(spec.name)
        configured = bool(raw and raw.strip())
        if spec.secret:
            value: object = None
        else:
            try:
                value = coerce(spec, raw) if configured else spec.default
            except ValueError:
                value = raw  # 非法值原样展示，便于用户发现并修正
        entries.append(
            {
                "name": spec.name,
                "group": spec.group,
                "kind": spec.kind,
                "label": spec.label,
                "help": spec.help,
                "default": spec.default,
                "value": value,
                "source": "dotenv" if configured else "default",
                "configured": configured,
                "secret": spec.secret,
                "read_only": spec.read_only,
                "restart": spec.restart,
                "consumer": spec.consumer,
                "effect": _effect(spec),
            }
        )
    return entries


def rollback(
    settings: Settings,
    conn,
    version_id: int,
    expected_hash: str | None,
    actor: str,
    controller=None,
) -> SaveResult:
    """回滚到历史版本：恢复非敏感值，保留当前敏感值。"""
    row = conn.execute(
        "SELECT values_json FROM config_versions WHERE id = ?", (version_id,)
    ).fetchone()
    if row is None:
        raise ConfigInvalid([{"name": None, "message": "配置版本不存在"}])
    stored = json.loads(row["values_json"])
    updates = {name: value for name, value in stored.items() if name in BY_NAME}
    document = read_env(settings)
    return save(
        settings,
        expected_hash or document.sha256,
        updates,
        actor=actor,
        controller=controller,
    )


__all__ = [
    "BACKUP_KEEP",
    "ConfigApplyFailed",
    "ConfigConflict",
    "ConfigError",
    "ConfigInvalid",
    "ConfigWriteUnverified",
    "EnvDocument",
    "SaveResult",
    "param_entries",
    "read_env",
    "redact",
    "render_env",
    "rollback",
    "save",
    "validate_candidate",
    "verify_effective",
]
