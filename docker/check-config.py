#!/usr/bin/env python3
"""启动期配置校验。

有问题时打印原因并以退出码 1 终止 —— 容器因此不会进入调度（docker 会按重启策略
重试，日志里能直接看到原因），而不是等到下一轮定时任务才暴露。
"""

from __future__ import annotations

import sys

sys.path.insert(0, "/app")

from scanner.validation import startup_problems  # noqa: E402


def main() -> int:
    problems = startup_problems()
    if not problems:
        print("[entrypoint] 配置校验通过")
        return 0
    print("[entrypoint] 配置不合法，容器不会进入调度：", file=sys.stderr)
    for index, problem in enumerate(problems, 1):
        print(f"  {index}. {problem}", file=sys.stderr)
    print("  参数说明：docs/configuration.md", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
