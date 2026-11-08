"""通过固定操作 sidecar 访问 Docker 的 HTTP 控制器。

面板默认不挂 docker.sock；设置 `SCANNER_CONTROL_URL` 后，所有容器操作都走
sidecar 的固定端点，不把任意 Docker API 暴露给面板。
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterator
from typing import Any

from .docker_api import ScannerUnavailable

SCAN_SCRIPT = "/usr/local/bin/scan-and-publish.sh"
APPLY_SCRIPT = "/usr/local/bin/apply-config.sh"
PRINT_SCRIPT = "/usr/local/bin/print-config.py"

SCRIPT_ACTIONS = {
    SCAN_SCRIPT: "run",
    APPLY_SCRIPT: "apply-config",
    PRINT_SCRIPT: "print-config",
}
ALLOWED_ENV = frozenset({"RUN_ID", "RUN_TRIGGER"})


class HttpExecHandle:
    """sidecar 上一次 exec 的客户端句柄。"""

    def __init__(self, controller: "HttpController", exec_id: str, run_id: str) -> None:
        self._controller = controller
        self.exec_id = exec_id
        self.run_id = run_id
        self._finished = False

    @property
    def finished(self) -> bool:
        if self._finished:
            return True
        try:
            payload = self._controller._json(
                "GET", f"/exec/{self.exec_id}", timeout=1
            )
        except ScannerUnavailable:
            return False
        self._finished = bool(payload.get("finished"))
        return self._finished

    def stream(self) -> Iterator[bytes]:
        yield from self._controller._stream(f"/exec/{self.exec_id}/stream")
        self._finished = True

    def wait(self, timeout_s: float = 3600) -> int:
        payload = self._controller._json(
            "GET",
            f"/exec/{self.exec_id}/wait?timeout_s={int(timeout_s)}",
            timeout=timeout_s + 5,
        )
        self._finished = True
        return int(payload["exit_code"])


class HttpController:
    """实现与 `ScannerController` 相同的面板侧接口。"""

    def __init__(self, base_url: str, token: str | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token or None

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.token:
            headers["X-Control-Token"] = self.token
        return headers

    def _json(
        self,
        method: str,
        path: str,
        body: dict[str, object] | None = None,
        timeout: float = 10,
    ) -> dict[str, Any]:
        data = None
        headers = self._headers()
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            f"{self.base_url}{path}", data=data, headers=headers, method=method
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")
            raise ScannerUnavailable(f"控制 sidecar 返回 {exc.code}: {detail}") from exc
        except (urllib.error.URLError, OSError) as exc:
            raise ScannerUnavailable(f"无法连接控制 sidecar：{exc}") from exc
        if not payload:
            return {}
        try:
            parsed = json.loads(payload)
        except ValueError as exc:
            raise ScannerUnavailable(f"控制 sidecar 返回非 JSON：{exc}") from exc
        return parsed if isinstance(parsed, dict) else {}

    def _stream(self, path: str, timeout: float = 3600) -> Iterator[bytes]:
        request = urllib.request.Request(
            f"{self.base_url}{path}", headers=self._headers(), method="GET"
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                while True:
                    chunk = response.read(8192)
                    if not chunk:
                        return
                    yield chunk
        except (urllib.error.HTTPError, urllib.error.URLError, OSError) as exc:
            raise ScannerUnavailable(f"读取控制 sidecar 失败：{exc}") from exc

    def status(self) -> dict[str, Any]:
        return self._json("GET", "/status")

    def stats(self) -> dict[str, Any]:
        return self._json("GET", "/stats")

    def logs(
        self, tail: int = 200, follow: bool = True, timestamps: bool = True
    ) -> Iterator[bytes]:
        query = urllib.parse.urlencode({"tail": tail, "follow": str(follow).lower()})
        return self._stream(f"/logs?{query}")

    def exec_script(
        self, script: str, env: dict[str, str] | None = None
    ) -> HttpExecHandle:
        action = SCRIPT_ACTIONS.get(script)
        if action is None:
            raise ValueError(f"不允许执行该脚本：{script}")
        clean_env = {
            key: value
            for key, value in (env or {}).items()
            if key in ALLOWED_ENV and isinstance(value, str)
        }
        payload = self._json("POST", f"/exec/{action}", {"env": clean_env})
        return HttpExecHandle(self, str(payload["exec_id"]), str(payload["run_id"]))

    def restart(self, timeout: int = 150) -> None:
        self._json("POST", "/restart")

    def stop(self, timeout: int = 30) -> None:
        self._json("POST", "/stop")

    def start(self) -> None:
        self._json("POST", "/start")


__all__ = ["HttpController", "HttpExecHandle", "SCRIPT_ACTIONS"]
