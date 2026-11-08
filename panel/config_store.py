"""配置事务：校验、落库、生成运行投影、调度应用、生效核对与版本回滚。

数据库是唯一真源，`/scanner-config/runtime.json` 只是派生投影。保存不是"写库就
完事"：投影要在同一事务提交后替换，调度失败要回滚数据库，`written` 与
`verification.status` 也仍是两个概念——保存成功不代表扫描器已经读到新值。
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone

from zoneinfo import ZoneInfo

from scanner.schema import BY_NAME, PARAMS, coerce, format_value

from . import settings_store
from .audit import record as audit_record
from .cron import CronInvalid, validate as validate_cron
from .docker_api import ScannerUnavailable
from .redact import redact_secrets
from .settings import Settings
from .settings_store import ConfigDocument

# 面板不展示、也不允许在面板修改的底层参数：由内置策略或部署配置决定。
# 用户只需要面向业务的概念（域名、端口、采样、发布），不需要看到文件名与运行身份。
PANEL_HIDDEN = frozenset(
    {
        "PROBE_PATH",
        "PROBE_USER_AGENT",
        "LOCATIONS_FILE",
        "SKIP_LOCATIONS",
        "LIBRARY_FILE",
        "PINNED_FILE",
        "GIT_AUTHOR_NAME",
        "GIT_AUTHOR_EMAIL",
        "GIT_RETRY_MAX",
        "GIT_RETRY_BASE_DELAY",
        "no_proxy",
        "LIST_FILENAMES",
        "PUSH_LISTS",
    }
)
CHECK_CONFIG_SCRIPT = "/usr/local/bin/check-config.py"
PRINT_CONFIG_SCRIPT = "/usr/local/bin/print-config.py"
APPLY_CONFIG_SCRIPT = "/usr/local/bin/apply-config.sh"


class ConfigError(Exception):
    """配置事务失败的基类。"""


class ConfigConflict(ConfigError):
    """配置已被其他请求修改（修订哈希不匹配）。"""


class ConfigInvalid(ConfigError):
    """候选配置非法；`errors` 是字段级错误列表。"""

    def __init__(self, errors: Sequence[Mapping[str, object]]) -> None:
        self.errors = [dict(error) for error in errors]
        super().__init__("配置校验失败")


class ConfigApplyFailed(ConfigError):
    """调度应用失败（已回滚）。"""


class ConfigWriteUnverified(ConfigError):
    """数据库已保存，但运行投影未能生成。"""


@dataclass
class SaveResult:
    document: ConfigDocument
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


def read_config(conn, settings: Settings) -> ConfigDocument:
    """读取当前生效配置（数据库覆盖 + schema 默认）。"""
    return settings_store.document(conn, settings)


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


def _semantic_errors(values: Mapping[str, str]) -> list[dict[str, object]]:
    """跨字段与调度/时区类校验：必须在落库前拦截。"""
    errors = _cross_field_errors(values)

    expression = (values.get("CRON_SCHEDULE") or "").strip()
    if expression:
        try:
            validate_cron(expression)
        except CronInvalid as exc:
            errors.append({"name": "CRON_SCHEDULE", "message": str(exc)})

    timezone_name = (values.get("TZ") or "").strip()
    if timezone_name:
        try:
            ZoneInfo(timezone_name)
        except Exception:  # noqa: BLE001 - 任何时区库问题都算非法
            errors.append({"name": "TZ", "message": f"未知时区：{timezone_name}"})

    raw_names = (values.get("LIST_FILENAMES") or "").strip()
    if raw_names:
        try:
            mapping = json.loads(raw_names)
        except ValueError:
            mapping = None
            errors.append(
                {"name": "LIST_FILENAMES", "message": "列表文件名映射不是合法 JSON"}
            )
        if mapping is not None:
            if not isinstance(mapping, dict) or any(
                not isinstance(key, str) or not isinstance(value, str)
                for key, value in mapping.items()
            ):
                errors.append(
                    {
                        "name": "LIST_FILENAMES",
                        "message": "列表文件名映射必须是字符串到字符串的对象",
                    }
                )
            else:
                for value in mapping.values():
                    stem = value[:-4] if value.lower().endswith(".txt") else value
                    if (
                        not stem.strip()
                        or any(char in stem for char in ("/", "\\", "\x00"))
                        or ".." in stem
                    ):
                        errors.append(
                            {
                                "name": "LIST_FILENAMES",
                                "message": f"列表文件名非法：{value!r}",
                            }
                        )
                        break
    raw_push = (values.get("PUSH_LISTS") or "").strip()
    if raw_push:
        try:
            selected = json.loads(raw_push)
        except ValueError:
            selected = None
            errors.append(
                {"name": "PUSH_LISTS", "message": "推送列表不是合法 JSON"}
            )
        if selected is not None and (
            not isinstance(selected, list)
            or any(not isinstance(item, str) for item in selected)
        ):
            errors.append(
                {
                    "name": "PUSH_LISTS",
                    "message": "推送列表必须是字符串数组",
                }
            )
    return errors


def validate_candidate(
    values: Mapping[str, str], env: Mapping[str, str] | None = None
) -> None:
    """候选配置干跑：跨字段/调度/时区校验 + （容器内）`check-config.py`。

    失败抛 `ValueError`，参数为字段级错误列表。
    """
    errors = _semantic_errors(values)
    if errors:
        raise ValueError(errors)

    script = os.environ.get("CHECK_CONFIG_SCRIPT", CHECK_CONFIG_SCRIPT)
    if not os.path.isfile(script):
        return  # 本地/单元测试环境只做 schema 级校验

    with tempfile.TemporaryDirectory() as temporary:
        candidate_path = os.path.join(temporary, "runtime.json")
        with open(candidate_path, "w", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {
                        name: format_value(BY_NAME[name], coerce(BY_NAME[name], value))
                        for name, value in values.items()
                        if name in BY_NAME
                    },
                    ensure_ascii=False,
                )
            )
        # 干跑必须看到候选里的代理/探测变量，否则代理未豁免这类错误会被漏掉；
        # 显式非空环境变量仍然优先（与运行期一致）。
        explicit = {key: value for key, value in os.environ.items() if value.strip()}
        candidate_env = {
            name: str(value) for name, value in values.items() if name in BY_NAME
        }
        process = subprocess.run(
            [sys.executable, script],
            capture_output=True,
            text=True,
            timeout=60,
            env={
                **candidate_env,
                **explicit,
                "RUNTIME_CONFIG_PATH": candidate_path,
            },
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
    """类型校验 + 归一化（返回可直接落库/投影的字符串值）。"""
    errors: list[dict[str, object]] = []
    clean: dict[str, str] = {}
    for name, raw in updates.items():
        spec = BY_NAME.get(name)
        if spec is None:
            errors.append({"name": name, "message": "未知参数"})
            continue
        if spec.read_only:
            errors.append(
                {"name": name, "message": "该参数为只读，无法在面板中修改"}
            )
            continue
        if raw is None:
            continue  # 敏感字段缺省 = 不修改
        text = str(raw)
        if any(char in text for char in ("\n", "\r", "\x00")) or "${" in text:
            errors.append(
                {"name": name, "message": "值不能包含换行、NUL 或 ${} 插值"}
            )
            continue
        try:
            value = coerce(spec, text)
        except ValueError as exc:
            errors.append({"name": name, "message": str(exc) or "取值非法"})
            continue
        clean[name] = format_value(spec, value)
    if errors:
        raise ConfigInvalid(errors)
    # 大小写两份豁免清单对用户只暴露一份，保存时自动同步，兼容只认小写的工具。
    if "NO_PROXY" in clean and "no_proxy" not in clean:
        clean["no_proxy"] = clean["NO_PROXY"]
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
            warnings.append(f"探测域名已变更：已自动放行 {host}")
    return warnings


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
    conn,
    settings: Settings,
    controller,
    names: Sequence[str] | None = None,
) -> dict[str, object]:
    """在扫描容器内读取生效值，与数据库当前值逐项比对。"""
    checked_at = _now_iso()
    if controller is None:
        return {"status": "unavailable", "checked_at": checked_at, "details": []}
    try:
        effective = _print_config(controller)
    except ScannerUnavailable:
        return {"status": "unavailable", "checked_at": checked_at, "details": []}

    document = read_config(conn, settings)
    if names is None:
        names = [
            spec.name
            for spec in PARAMS
            if not spec.secret
            and not spec.read_only
            and not spec.restart
            and spec.consumer in {"scanner", "shell", "publish", "proxy"}
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


def _has_userinfo(text: str) -> bool:
    return bool(re.search(r"[a-zA-Z][a-zA-Z0-9+.\-]*://[^/@\s]+@", text))


def _stored_values(values: Mapping[str, str]) -> dict[str, str]:
    """版本历史里只存可安全回放的值：去掉敏感、只读与非法项。"""
    stored: dict[str, str] = {}
    for name, value in values.items():
        spec = BY_NAME.get(name)
        if spec is None or spec.secret or spec.read_only:
            continue
        try:
            canonical = format_value(spec, coerce(spec, value))
        except ValueError:
            continue  # 只读/发布键的历史脏值不应阻断本次保存
        if _has_userinfo(canonical):
            continue  # 带凭据的 URL 不能进版本历史
        stored[name] = canonical
    return stored


def _effect(spec) -> str:
    if spec.restart:
        return "restart_required"
    if spec.name == "CRON_SCHEDULE":
        return "schedule_reload"
    return "next_round"


def _next_run(document: ConfigDocument) -> str | None:
    expression = document.values.get("CRON_SCHEDULE") or str(
        BY_NAME["CRON_SCHEDULE"].default
    )
    timezone_name = document.values.get("TZ") or str(BY_NAME["TZ"].default)
    try:
        from . import cron
    except ImportError:
        return None  # cron 模块在后续任务落地
    try:
        runs = cron.next_runs(expression, timezone_name, count=1)
    except Exception:  # noqa: BLE001 - 非法 cron 由校验阶段拦截
        return None
    return runs[0].isoformat() if runs else None


# ---------------------------------------------------------------- 保存 --
def _no_op(document: ConfigDocument, warnings: list[str]) -> SaveResult:
    return SaveResult(
        document=document,
        written=False,
        changed=[],
        effects={"next_round": [], "schedule_reloaded": False, "restart_required": []},
        verification={"status": "verified", "checked_at": _now_iso(), "details": []},
        next_run=_next_run(document),
        warnings=warnings,
    )


def save(
    conn,
    settings: Settings,
    expected_hash: str,
    updates: Mapping[str, object],
    actor: str,
    controller=None,
) -> SaveResult:
    """保存事务：校验 -> 落库 -> 替换投影 -> 调度 -> 核对 -> 版本与审计。"""
    document = read_config(conn, settings)
    if expected_hash != document.sha256:
        raise ConfigConflict("设置已被修改，请刷新后重试")

    clean = _canonical_updates(updates)
    warnings = _with_proxy_exemption(clean, document.values)

    merged = dict(document.values)
    merged.update(clean)
    try:
        validate_candidate(merged)
    except ValueError as exc:
        errors = exc.args[0] if exc.args else [{"name": None, "message": str(exc)}]
        if not isinstance(errors, list):
            errors = [{"name": None, "message": str(errors)}]
        raise ConfigInvalid(errors) from exc

    changed: list[dict] = []
    for name, new_value in clean.items():
        if name == "no_proxy" and "NO_PROXY" in clean:
            continue  # 小写清单是自动同步的影子项，不重复展示
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
    if not changed:
        return _no_op(document, warnings)

    staged = settings_store.stage_projection(settings, merged)
    try:
        with conn:
            settings_store.apply_overrides(conn, settings, clean, actor=actor)
            written_document = read_config(conn, settings)
            stored = _stored_values(merged)
            diff = redact(
                "\n".join(
                    f"- {BY_NAME[item['name']].label}={item['old']}\n"
                    f"+ {BY_NAME[item['name']].label}={item['new']}"
                    for item in changed
                    if not BY_NAME[item["name"]].secret
                )
            )
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
                "settings",
                diff or "无实际变更",
                "panel",
            )
    except BaseException:
        staged.unlink(missing_ok=True)
        raise

    try:
        settings_store.commit_projection(settings, staged)
    except OSError as exc:
        raise ConfigWriteUnverified(
            f"配置已保存，但运行配置生成失败：{exc}"
        ) from exc

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
            warnings.append("扫描容器暂不可用：已保存，容器恢复后会自动生效")
        else:
            try:
                handle = controller.exec_script(APPLY_CONFIG_SCRIPT, {})
                code = handle.wait()
            except ScannerUnavailable:
                offline = True
                code = 0
                warnings.append("扫描容器暂不可用：已保存，容器恢复后会自动生效")
            if not offline and code != 0:
                settings_store.restore(conn, settings, document, actor=actor)
                settings_store.project(conn, settings)
                raise ConfigApplyFailed("计划任务应用失败，已回滚")
        schedule_reloaded = not offline

    hot_names = [
        item["name"]
        for item in changed
        if item["effect"] == "next_round"
        and BY_NAME[item["name"]].consumer in {"scanner", "shell", "publish", "proxy"}
    ]
    verification = verify_effective(conn, settings, controller, hot_names)
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

    return SaveResult(
        document=read_config(conn, settings),
        written=True,
        changed=changed,
        effects=effects,
        verification=verification,
        next_run=_next_run(read_config(conn, settings)),
        warnings=warnings,
    )


def param_entries(document: ConfigDocument) -> list[dict[str, object]]:
    """GET /api/config 的参数列表（敏感值永不返回）。"""
    entries: list[dict[str, object]] = []
    for spec in PARAMS:
        configured = spec.name in document.configured
        raw = document.values.get(spec.name)
        if spec.secret:
            value: object = None
        else:
            try:
                value = coerce(spec, raw) if raw is not None else spec.default
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
                "value": (
                    redact_secrets(value) if isinstance(value, str) else value
                ),
                "source": "custom" if configured else "default",
                "configured": configured,
                "secret": spec.secret,
                "read_only": spec.read_only,
                "restart": spec.restart,
                "consumer": spec.consumer,
                "effect": _effect(spec),
                "hidden": spec.name in PANEL_HIDDEN,
            }
        )
    return entries


def rollback(
    conn,
    settings: Settings,
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
    updates = {
        name: value
        for name, value in stored.items()
        if name in BY_NAME
        and not BY_NAME[name].read_only
        and not BY_NAME[name].secret
    }
    document = read_config(conn, settings)
    result = save(
        conn,
        settings,
        expected_hash or document.sha256,
        updates,
        actor=actor,
        controller=controller,
    )
    audit_record(
        conn,
        actor,
        "config.rollback",
        "settings",
        f"回滚到配置版本 {version_id}",
        "panel",
    )
    return result


__all__ = [
    "ConfigApplyFailed",
    "ConfigConflict",
    "ConfigDocument",
    "ConfigError",
    "ConfigInvalid",
    "ConfigWriteUnverified",
    "SaveResult",
    "param_entries",
    "read_config",
    "redact",
    "rollback",
    "save",
    "validate_candidate",
    "verify_effective",
]
