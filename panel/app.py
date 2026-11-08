"""FastAPI 应用工厂。

`create_app(settings)` 让测试注入临时目录与假控制器；模块级 `app` 供 uvicorn 使用。
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import db
from . import artifacts_store, bootstrap, library_store, settings_store
from .routers import auth as auth_routes
from .routers import config as config_routes
from .routers import schedule as schedule_routes
from .routers import runs as runs_routes
from .routers import logs as logs_routes
from .routers import outputs as outputs_routes
from .routers import library as library_routes
from .routers import locations as locations_routes
from .routers import publish as publish_routes
from .routers import overview as overview_routes
from .routers import system as system_routes
from .routers import audit as audit_routes
from .security import configure
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


def create_app(settings: Settings | None = None, controller=None) -> FastAPI:
    app = FastAPI(
        title="best-cf-ip-scanner 运维面板",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.settings = settings or Settings.from_env()
    app.state.controller = controller
    app.state.active_runs = {}
    conn = db.connect(app.state.settings.db_path)
    db.migrate(conn)
    app.state.conn = conn
    # 数据库是唯一真源：首次启动写入 schema 默认值，之后只从数据库读参数。
    settings_store.seed_schema_defaults(conn, app.state.settings)
    # 面板先于扫描器启动：由面板播种 /data（镜像内置默认库）。
    bootstrap.seed_defaults(app.state.settings)
    library_store.ensure(conn, app.state.settings)
    artifacts_store.sync(conn, app.state.settings)
    # 生成扫描器读取的运行投影；失败会直接阻止启动，避免带旧配置继续跑。
    settings_store.project(conn, app.state.settings)
    app.state.security = configure(app.state.settings)

    static_dir = Path(__file__).resolve().parent / "static"

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        # SPA 深链接（/config、/runs…）由前端路由处理；API 仍返回 JSON 404。
        if (
            exc.status_code == 404
            and request.method == "GET"
            and not request.url.path.startswith("/api/")
        ):
            index = static_dir / "index.html"
            if index.is_file():
                return FileResponse(index, media_type="text/html")
        detail = exc.detail
        if isinstance(detail, dict):
            body = dict(detail)
            body.setdefault("code", "error")
            body.setdefault("message", str(detail))
        else:
            body = {"code": "error", "message": str(detail)}
        return JSONResponse(status_code=exc.status_code, content=body)

    @app.get("/healthz")
    def healthz() -> dict[str, object]:
        return {"status": "ok", "docker": _docker_available()}

    app.include_router(auth_routes.router)
    app.include_router(config_routes.router)
    app.include_router(schedule_routes.router)
    app.include_router(runs_routes.router)
    app.include_router(logs_routes.router)
    app.include_router(outputs_routes.router)
    app.include_router(library_routes.router)
    app.include_router(locations_routes.router)
    app.include_router(publish_routes.router)
    app.include_router(overview_routes.router)
    app.include_router(system_routes.router)
    app.include_router(audit_routes.router)

    # 前端构建产物由后端托管；Task 16 之后是 Vite 生成的 SPA。
    if static_dir.is_dir():
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

    return app


# uvicorn 用 `--factory panel.app:create_app` 启动：不在导入期创建数据库，
# 测试导入模块时不会产生任何目录或文件。

