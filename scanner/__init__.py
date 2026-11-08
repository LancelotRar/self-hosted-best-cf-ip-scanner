"""scanner —— best-cf-ip-scanner 的功能包。

各模块职责（详见模块 docstring）：
    config    全部可调参数（默认值 + 环境变量覆盖）
    timeutil  北京时间工具 + 按小时轮换的采样种子
    atomicio  原子写文件（CSV / JSON / TXT），无业务知识
    ippool    候选地址库解析 / 连续区间合并 / 地址网格采样 / 端口分配
    probe     TCP 握手测量（初筛）+ 边缘端点校验（终筛）
    locations 边缘机房代码 -> 国家代码 的本地映射读取
    outputs   合格候选 -> 明细表（CSV）+ 订阅列表（TXT）

编排入口见 `scanner/__main__.py`，在容器内以 `python -m scanner` 运行。
"""

import importlib

__all__ = [
    "atomicio",
    "config",
    "ippool",
    "locations",
    "outputs",
    "probe",
    "timeutil",
]


def __getattr__(name: str):
    """按需导入子模块。

    面板镜像只需要 schema/validation/ippool 等轻量模块；如果这里急切导入
    probe，会把 curl_cffi 一并拉进面板镜像。保留 `scanner.probe` 这类属性
    访问的兼容性，但不在包初始化时加载。
    """
    if name in __all__:
        module = importlib.import_module(f".{name}", __name__)
        globals()[name] = module
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
