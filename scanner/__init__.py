"""scanner —— best-cf-ip-scanner 的功能包。

各模块职责（详见模块 docstring）：
    config    全部可调参数（默认值 + 环境变量覆盖）
    timeutil  北京时间工具 + 按小时轮换的采样种子
    atomicio  原子写文件（CSV / JSON / TXT），无业务知识
    ippool    候选地址库解析 / 连续区间合并 / 地址网格采样 / 端口分配
    probe     TCP 握手测量（初筛）+ 边缘端点校验（终筛）
    locations 边缘机房代码 -> 国家代码 的本地映射读取
    outputs   合格候选 -> 明细表（CSV）+ 订阅列表（TXT）

编排入口见仓库根目录的 best_cf_ip_scanner.py。
"""

from . import atomicio, config, ippool, locations, outputs, probe, timeutil

__all__ = [
    "atomicio",
    "config",
    "ippool",
    "locations",
    "outputs",
    "probe",
    "timeutil",
]
