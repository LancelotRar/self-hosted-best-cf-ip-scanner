#!/usr/bin/env python3
"""打印当前生效配置（JSON），供 `docker exec` 与面板核对生效值。

输出结构：
    {"SAMPLE_STRIDE": {"value": 256, "source": "projection"}, ...}

`source` 取值：`env`（显式环境变量）/ `projection`（面板生成的运行配置投影）/
`default`（schema 默认值）。
敏感参数（GIT_TOKEN、代理 URL）只输出 `{"value": null, "configured": bool}`，
永不输出明文——面板与日志都复用同一份输出。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def _app_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "scanner").is_dir():
            return parent
    return Path("/app")


sys.path.insert(0, str(_app_dir()))

from scanner.runtime_env import RuntimeConfigError, load  # noqa: E402
from scanner.schema import PARAMS, ParamSpec, coerce  # noqa: E402


def _resolve(spec: ParamSpec, runtime: dict[str, str]) -> dict[str, object]:
    env_raw = os.environ.get(spec.name)
    runtime_raw = runtime.get(spec.name)
    if env_raw is not None and env_raw.strip():
        source, raw = "env", env_raw
    elif runtime_raw is not None and runtime_raw.strip():
        source, raw = "projection", runtime_raw
    else:
        source, raw = "default", None

    if spec.secret:
        return {"value": None, "source": source, "configured": raw is not None}

    if raw is None:
        return {"value": spec.default, "source": source}
    try:
        return {"value": coerce(spec, raw), "source": source}
    except ValueError:
        raise SystemExit(
            f"[print-config] {spec.name}={raw!r} 非法，无法生成生效配置"
        ) from None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="打印当前生效配置 JSON")
    parser.add_argument("--json", action="store_true", help="兼容参数：始终输出 JSON")
    parser.parse_args(argv)

    try:
        runtime = load()
    except RuntimeConfigError as exc:
        print(f"[print-config] 运行配置解析失败：{exc}", file=sys.stderr)
        return 1

    payload = {spec.name: _resolve(spec, runtime) for spec in PARAMS}
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=list))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
