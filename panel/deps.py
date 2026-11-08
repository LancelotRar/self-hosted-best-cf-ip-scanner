"""请求上下文里的共享依赖：设置与扫描容器控制器。"""

from __future__ import annotations

from fastapi import Request

from .docker_api import default_controller


def settings_of(request: Request):
    return request.app.state.settings


def _build_controller(settings):
    return default_controller(settings)


def controller_of(request: Request):
    """返回注入的控制器；未注入时按环境创建，socket/控制 sidecar 不可用则返回 None。"""
    controller = request.app.state.controller
    if controller is None:
        try:
            controller = _build_controller(settings_of(request))
        except Exception:  # noqa: BLE001 - 降级为"不可核对"，不影响只读页面
            return None
        request.app.state.controller = controller
    return controller
