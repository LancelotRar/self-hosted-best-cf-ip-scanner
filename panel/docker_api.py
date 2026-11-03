"""扫描容器控制器：把 Docker SDK 收窄到本项目扫描容器。

安全边界：
- 容器只按 `SCANNER_CONTAINER` 名称或 compose 标签解析，**不接受请求参数里的容器 ID**；
- 可执行的脚本是固定白名单，不经过 shell；
- 所有 Docker 异常统一转 `ScannerUnavailable`，由路由层决定返回 503 还是降级。

面板只关心这一个容器：状态、日志、执行一轮、重启/启停。
"""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator
from typing import Any

from .settings import Settings

SCANNER_LABEL = "com.docker.compose.service=scanner"

# 只允许执行镜像内这几个入口脚本；不接受任意命令。
ALLOWED_SCRIPTS = frozenset(
    {
        "/usr/local/bin/scan-and-publish.sh",
        "/usr/local/bin/apply-config.sh",
        "/usr/local/bin/print-config.py",
        "/usr/local/bin/check-config.py",
        "/usr/local/bin/startup-report.py",
    }
)


class ScannerUnavailable(RuntimeError):
    """扫描容器不可用（未启动、被删除，或 docker.sock 不可达）。"""


class ExecHandle:
    """一次 `docker exec` 的句柄：创建即开始执行，输出边跑边缓存。

    先启动、后订阅：即使前端没有立刻打开 SSE（或面板重启），指令也已经真的跑起来了。
    输出在工作线程里累积，`stream()` 只读缓存，不阻塞事件循环。
    """

    def __init__(self, api: Any, exec_id: str, run_id: str) -> None:
        self._api = api
        self.exec_id = exec_id
        self.run_id = run_id
        self._chunks: list[bytes] = []
        self._done = threading.Event()
        self._error: str | None = None
        self._thread: threading.Thread | None = None
        self.start()

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._pump, daemon=True)
        self._thread.start()

    def _pump(self) -> None:
        try:
            for chunk in self._api.exec_start(self.exec_id, stream=True, demux=False):
                if chunk:
                    self._chunks.append(chunk)
        except Exception as exc:  # noqa: BLE001 - 统一转成可展示的不可用
            self._error = str(exc)
        finally:
            self._done.set()

    def stream(self) -> Iterator[bytes]:
        index = 0
        while True:
            while index < len(self._chunks):
                yield self._chunks[index]
                index += 1
            if self._done.is_set():
                if self._error:
                    raise ScannerUnavailable(f"读取运行输出失败：{self._error}")
                return
            time.sleep(0.05)

    def wait(self, timeout_s: float = 3600) -> int:
        """等待执行结束并返回退出码；超时视为不可用。"""
        deadline = time.monotonic() + timeout_s
        self._done.wait(max(0.0, min(1.0, timeout_s)))
        try:
            while True:
                info = self._api.exec_inspect(self.exec_id)
                code = info.get("ExitCode")
                if code is not None:
                    return int(code)
                if time.monotonic() > deadline:
                    raise ScannerUnavailable("等待执行结束超时")
                time.sleep(0.2)
        except ScannerUnavailable:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ScannerUnavailable(f"获取运行退出码失败：{exc}") from exc


class ScannerController:
    """本项目扫描容器的唯一操作入口。"""

    def __init__(self, client: Any, container_ref: str) -> None:
        self.client = client
        self.container_ref = container_ref

    def resolve(self):
        """按名称解析，失败再按 compose 标签；都失败则抛 `ScannerUnavailable`。"""
        try:
            return self.client.containers.get(self.container_ref)
        except Exception:  # noqa: BLE001 - 名称不存在或 socket 异常都继续尝试标签
            pass
        try:
            matches = self.client.containers.list(
                all=True, filters={"label": [SCANNER_LABEL]}
            )
        except Exception as exc:  # noqa: BLE001
            raise ScannerUnavailable(f"无法访问 Docker：{exc}") from exc
        if matches:
            return matches[0]
        raise ScannerUnavailable(
            f"找不到扫描容器 {self.container_ref!r}，请确认 compose 已启动"
        )

    def status(self) -> dict[str, Any]:
        try:
            container = self.resolve()
            attrs = getattr(container, "attrs", {}) or {}
            state = attrs.get("State", {}) or {}
            image = (attrs.get("Config") or {}).get("Image")
            return {
                "name": container.name,
                "state": getattr(container, "status", "unknown"),
                "health": (state.get("Health") or {}).get("Status"),
                "started_at": state.get("StartedAt"),
                "image": image,
            }
        except ScannerUnavailable:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ScannerUnavailable(f"读取容器状态失败：{exc}") from exc

    def stats(self) -> dict[str, Any]:
        try:
            raw = self.resolve().stats(stream=False) or {}
        except ScannerUnavailable:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ScannerUnavailable(f"读取容器资源占用失败：{exc}") from exc
        memory = raw.get("memory_stats") or {}
        return {
            "memory_usage": memory.get("usage"),
            "memory_limit": memory.get("limit"),
        }

    def logs(self, tail: int = 200, follow: bool = True) -> Iterator[bytes]:
        try:
            return iter(self.resolve().logs(tail=tail, follow=follow, stream=True))
        except ScannerUnavailable:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ScannerUnavailable(f"读取容器日志失败：{exc}") from exc

    def exec_script(self, script: str, env: dict[str, str] | None = None) -> ExecHandle:
        """执行白名单脚本；Python 脚本用解释器启动。"""
        if script not in ALLOWED_SCRIPTS:
            raise ValueError(f"不允许执行该脚本：{script}")
        command = ["python", script] if script.endswith(".py") else [script]
        try:
            container = self.resolve()
            created = self.client.api.exec_create(
                container.id,
                command,
                environment=dict(env or {}),
                privileged=False,
                tty=False,
            )
            exec_id = created["Id"]
        except ScannerUnavailable:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ScannerUnavailable(f"启动执行失败：{exc}") from exc
        run_id = (env or {}).get("RUN_ID", exec_id)
        return ExecHandle(self.client.api, exec_id, run_id)

    def restart(self, timeout: int = 150) -> None:
        try:
            self.resolve().restart(timeout=timeout)
        except ScannerUnavailable:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ScannerUnavailable(f"重启扫描容器失败：{exc}") from exc

    def stop(self, timeout: int = 30) -> None:
        try:
            self.resolve().stop(timeout=timeout)
        except ScannerUnavailable:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ScannerUnavailable(f"停止扫描容器失败：{exc}") from exc

    def start(self) -> None:
        try:
            self.resolve().start()
        except ScannerUnavailable:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ScannerUnavailable(f"启动扫描容器失败：{exc}") from exc


def default_controller(settings: Settings) -> ScannerController:
    """按容器环境创建真实控制器；docker.sock 不可达时由调用方降级。"""
    import docker

    client = docker.from_env(timeout=10)
    return ScannerController(client, settings.scanner_container)


__all__ = [
    "ALLOWED_SCRIPTS",
    "ExecHandle",
    "SCANNER_LABEL",
    "ScannerController",
    "ScannerUnavailable",
    "default_controller",
]
