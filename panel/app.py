"""FastAPI 应用工厂。

`create_app(settings)` 让测试注入临时目录与假控制器；模块级 `app` 供 uvicorn 使用。
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .settings import Settings


def _docker_available() -> bool:
    """docker.sock 是否可达；不可达时面板仍启动，只在 UI 显示降级原因。"""
    try:
        import docker

        client = docker.from_env(timeout=2)
        try:
            return bool(client.ping())
        finally:
            client.close()
    except Exception:  # noqa: BLE001 - 健康检查只关心"可用/不可用"
        return False


def create_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(
        title="best-cf-ip-scanner 运维面板",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.settings = settings or Settings.from_env()

    @app.get("/healthz")
    def healthz() -> dict[str, object]:
        return {"status": "ok", "docker": _docker_available()}

    # 前端构建产物由后端托管；Task 16 之后是 Vite 生成的 SPA。
    static_dir = Path(__file__).resolve().parent / "static"
    if static_dir.is_dir():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

    return app


app = create_app()
