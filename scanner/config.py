"""配置中心 —— 全部可调参数的唯一入口。

默认值、分组与类型集中在 `scanner/schema.py`；取值优先级：
**显式环境变量 > 项目根 `.env`（`DOTENV_PATH`）> schema 默认值**。
空串一律视为未设置（便于 `.env` 留空保持默认）。

本模块保持原有常量名与类型不变，供全包引用；不 import 扫描业务模块。

取值约定：
- 空字符串等同于未设置（便于 `.env` 留空保持默认）；
- 布尔只认 true/false/yes/no/on/off/1/0（大小写不敏感）；
- 列表用英文逗号分隔（`PROBE_PORTS=443,2053`）；
- 国家档位用「国家代码:档位,档位」分组，组间用分号（`US:50,100;JP:50`），
  填 none 关闭国家订阅；
- 取值非法时进程立即以退出码 1 终止并在 stderr 说明原因（容器日志可见）。
  刻意不做静默回退：配置写错却照常运行，只会得到一轮看不懂的结果。
"""

import os
import sys
from pathlib import Path
from typing import NoReturn

from . import runtime_env
from .schema import BY_NAME, coerce

# 应用目录（代码根）：scanner/ 的上一级，容器内即 /app
APP_DIR = Path(__file__).resolve().parent.parent

# 导入时读取一次 `.env`；每个扫描轮次都是新进程，因此「每轮重读」自然成立。
_DOTENV: dict[str, str] = runtime_env.load()

# 各类型的期望值描述，用于把类型错误翻译成可操作的提示。
_EXPECT: dict[str, str] = {
    "str": "字符串",
    "path": "路径",
    "cron": "cron 表达式（5 段；6 段第 6 位是年，7 段含秒）",
    "secret": "字符串",
    "int": "整数",
    "float": "数字",
    "bool": "true/false",
    "csv_int": "逗号分隔的整数，例如 20,50",
    "ports": "逗号分隔的端口（1-65535），例如 443,2053",
}


# ------------------------------------------------------------ 取值 --
def _raw(name: str) -> str | None:
    """显式环境变量优先，其次 `.env`；空串返回 None（视为未配置）。"""
    value = os.environ.get(name)
    if value is None:
        value = _DOTENV.get(name)
    if value is None:
        return None
    value = value.strip()
    return value or None


def _fail(name: str, value: str, expect: str) -> NoReturn:
    """非法取值：打印可定位的原因后以退出码 1 终止。"""
    print(f"[错误] 环境变量 {name}={value!r} 非法：期望{expect}", file=sys.stderr)
    raise SystemExit(1)


def _value(name: str) -> object:
    """按 schema 读取并转换单个参数；未配置时返回默认值。"""
    spec = BY_NAME[name]
    raw = _raw(name)
    if raw is None:
        return spec.default
    try:
        return coerce(spec, raw)
    except ValueError:
        _fail(name, raw, _EXPECT[spec.kind])


# -------------------------------------------------------------- 探测目标 --
# 终筛探测端点：把 PROBE_HOST 通过 curl RESOLVE "钉"到候选 IP:端口，请求一次
# PROBE_PATH，从响应体里读 colo（边缘机房代码）。一条请求同时完成三件事：
#   1) 判定该 IP 是否真的落在 Cloudflare 边缘；
#   2) 淘汰 EIV 受限子池（专属/静态/BYOIP 地址）；
#   3) 取得边缘机房代码，用于国家/国旗标注。
#
# PROBE_HOST 必须是**你自己托管在 Cloudflare、且已开启代理（小黄云）的域名**：
#   - 用 CF 自有域名（speed.cloudflare.com 等）时，EIV 受限 IP 同样返回 colo，
#     但它们只在所属账号的 zone 上可用，当代理节点不可用，会被误收录；
#   - 用自己 zone 的域名时，受限子池直接返回 403 / error 1034，天然淘汰。
# 另外该域名需满足：证书覆盖、PROBE_PORTS 中的端口都能服务、PROBE_PATH 由
# CF 边缘直接应答（不依赖源站存活）。
#
# 没有默认值：探测域名决定"什么算合格节点"，必须由使用者按自己的 zone 决定。
PROBE_HOST: str = _value("PROBE_HOST")
PROBE_PATH: str = _value("PROBE_PATH")

# 机房代码 -> 国家代码 的本地映射文件（位于 DATA_DIR，人工维护，运行时不联网）。
LOCATIONS_FILE: str = _value("LOCATIONS_FILE")
# 跳过机房映射（国家/国旗列留空），仅调试用。
SKIP_LOCATIONS: bool = _value("SKIP_LOCATIONS")

# ---------------------------------------------------------------- 端口组 --
# 候选端口集合：每个候选 IP 从中随机分配一个端口去探测。
# Cloudflare 支持的 HTTPS 端口全集：443, 2053, 2083, 2087, 2096, 8443
# 端口越多候选组合越丰富，单轮耗时也越高。
PROBE_PORTS: tuple[int, ...] = _value("PROBE_PORTS")

# -------------------------------------------------------------- 探测参数 --
# 两阶段筛选：
#   TCP 握手测量（初筛 + 排名基准）
#       对"候选 IP:端口"做 N 次 TCP 握手并计时，统计成功次数、丢包率、
#       最小/平均/最大往返时延。选它作基准，是因为这些 IP 最终当代理节点用，
#       代理客户端展示的"TCP 延迟"就是这个口径；而且它比 TLS+HTTP 廉价，
#       适合做第一道粗筛（HTTPS 必然以 TCP 成功为前提）。
#   端点校验（终筛 / 准入门槛）
#       TCP 握手达标的候选，再请求一次 PROBE_HOST 的 PROBE_PATH：
#       要求 HTTP 200 且响应体含合法 colo。缺这一步则非 CF 地址会混入，
#       且拿不到机房/国家标注。
PROBE_CONCURRENCY: int = _value("PROBE_CONCURRENCY")  # 并发线程数（两阶段共用）
TCP_ATTEMPTS: int = _value("TCP_ATTEMPTS")            # 每个候选的握手次数
TCP_MIN_SUCCESS: int = _value("TCP_MIN_SUCCESS")      # 合格门槛：至少成功几次
TCP_TIMEOUT: float = _value("TCP_TIMEOUT")            # 单次握手超时（秒）
TRACE_TIMEOUT: int = _value("TRACE_TIMEOUT")          # 单次端点校验超时（秒）
TRACE_ATTEMPTS: int = _value("TRACE_ATTEMPTS")        # 端点校验最大尝试次数

# -------------------------------------------------------------- 采样参数 --
# 采样密度：每 SAMPLE_STRIDE 个地址抽取 1 个代表 IP。
# 窗口按**地址网格**对齐（窗口起点是 SAMPLE_STRIDE 的整数倍），与库内条目如何
# 切分/合并无关；取 256（一个 /24 的长度）时，等价于每 /24 抽 1 个。
# 末尾不足一个窗口的区间仍抽 1 个。
SAMPLE_STRIDE: int = _value("SAMPLE_STRIDE")
# 采样种子：实际种子 = SAMPLE_SEED * SEED_HOUR_FACTOR + 当前北京小时(YYYYMMDDHH)。
# 同一小时内多次运行结果可复现；跨小时自动轮换，长期覆盖库内更多 IP 与端口组合。
SAMPLE_SEED: int = _value("SAMPLE_SEED")
SEED_HOUR_FACTOR: int = _value("SEED_HOUR_FACTOR")

# ---------------------------------------------------------------- 输入 --
# 候选地址库文件（相对 DATA_DIR）。每行一个条目，支持三种写法：
#   CIDR       104.16.0.0/24     —— 展开为该网段，参与网格采样
#   单个 IP    104.17.3.3        —— 等价 /32
#   IP:端口   104.18.4.4:8443   —— 原样保留为候选，不参与采样、端口不被替换
# 行首 # 为注释；空行与 cidr/ip 表头行会被跳过。
# 脚本不修改该文件——要排除网段在行首加 # 并写明依据即可（可一行恢复）。
LIBRARY_FILE: str = _value("LIBRARY_FILE")
# 固定保留条目：不参与扫描与机房映射，原样附加到全量列表末尾。
PINNED_FILE: str = _value("PINNED_FILE")
# 数据目录（候选地址库 + 机房映射）。容器内默认 /data，由 compose 挂载宿主目录。
DATA_DIR: str = _raw("DATA_DIR") or str(APP_DIR / "data")

# ---------------------------------------------------------------- 输出 --
# 产物目录：明细表与订阅列表直接写在这里。
# 容器内部署时由 compose 注入 /output，对应宿主 ./output。
OUTPUT_DIR: str = _raw("OUTPUT_DIR") or str(APP_DIR / "output")
# 明细表文件名（不含扩展名）：记录全部合格候选及其测量指标，供排查与二次筛选。
DETAIL_CSV_NAME: str = _value("DETAIL_CSV_NAME")
# 固定保留文件名（不含扩展名）：单独成文件，不混入 GLOBAL/国家列表。
PINNED_OUTPUT_NAME: str = _value("PINNED_OUTPUT_NAME")
# 明细表列定义（顺序即列序，下游按列名读取，改列名需同步上游写入逻辑）。
# 语义：
#   TCP握手平均延迟 = TCP_ATTEMPTS 次握手中成功样本的平均往返时延（排名依据）
#   TCP握手丢包率   = (TCP_ATTEMPTS - 成功次数) / TCP_ATTEMPTS
#   TRACE首字节延迟 = 通过校验那次请求的首字节时间（TTFB，含 TCP+TLS+边缘处理），
#                     仅用于排查与对照，不参与筛选和排名
#   边缘机房代码    = Cloudflare colo（IATA 三字码），由端点校验响应解析
DETAIL_COLUMNS: list[str] = [
    "IP", "端口",
    "TCP握手平均延迟(ms)", "TCP握手最小延迟(ms)", "TCP握手最大延迟(ms)",
    "TCP握手丢包率", "TCP握手成功次数", "TCP握手总次数",
    "TRACE首字节延迟(ms)",
    "边缘机房代码", "国家代码", "国旗", "扫描时间",
]
# 订阅列表规格：分两组，各自回答「要不要 / 要多少」。
#   全量列表：OVERALL_TOPS 为条数列表，生成 GLOBAL{N}.txt —— 对**全部合格候选**
#             排名，不按国家筛选。默认 20/50/100/200/400；填多少生成多少
#             （任意正整数，逗号分隔），留空 = 不生成。
#   国家列表：COUNTRY_FILTERS 是总开关。false（默认）= 不生成任何国家列表；
#             true 时才按 TOP_<国家代码> 的数值生成 {国家代码}{N}.txt。
OVERALL_TOPS: tuple[int, ...] = _value("OVERALL_TOPS")
COUNTRY_FILTERS: bool = _value("COUNTRY_FILTERS")

# 每个国家一个变量：TOP_<两位国家代码>=N，N 就是该国家列表的条数。
# 仅当 COUNTRY_FILTERS=true 时生效；0 或留空 = 该国不生成。
_COUNTRY_CODES: tuple[str, ...] = ("US", "JP", "SG", "DE", "NL", "FR")
TOP_US: int = _value("TOP_US")
TOP_JP: int = _value("TOP_JP")
TOP_SG: int = _value("TOP_SG")
TOP_DE: int = _value("TOP_DE")
TOP_NL: int = _value("TOP_NL")
TOP_FR: int = _value("TOP_FR")
COUNTRY_TOPS: dict[str, int] = {
    code: _value(f"TOP_{code}") for code in _COUNTRY_CODES
}

# -------------------------------------------------------------- 请求头 --
# 端点校验请求使用的 User-Agent（保持浏览器指纹，与 curl_cffi 配合）。
PROBE_USER_AGENT: str = _value("PROBE_USER_AGENT")
PROBE_HEADERS: dict[str, str] = {"User-Agent": PROBE_USER_AGENT}
