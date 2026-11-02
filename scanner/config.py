"""配置中心 —— 全部可调参数的唯一来源。

每个参数都可以用同名环境变量覆盖（容器部署时由 `.env` 注入）；未设置或留空时
使用本文件里的默认值。这样"运维调参只改 `.env`"，不必改代码或重建镜像。

本模块只依赖标准库（os / sys / pathlib），不 import 任何兄弟模块，供全包引用。

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

# 应用目录（代码根）：scanner/ 的上一级，容器内即 /app
APP_DIR = Path(__file__).resolve().parent.parent


# ------------------------------------------------------------ 环境变量解析 --
def _raw(name: str) -> str | None:
    """读取环境变量；未设置或空串返回 None（视为未配置）。"""
    value = os.environ.get(name)
    if value is None:
        return None
    value = value.strip()
    return value or None


def _fail(name: str, value: str, expect: str) -> NoReturn:
    """非法取值：打印可定位的原因后以退出码 1 终止。"""
    print(f"[错误] 环境变量 {name}={value!r} 非法：期望{expect}", file=sys.stderr)
    raise SystemExit(1)


def _env_str(name: str, default: str) -> str:
    return _raw(name) or default


def _env_int(name: str, default: int) -> int:
    raw = _raw(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        _fail(name, raw, "整数")


def _env_float(name: str, default: float) -> float:
    raw = _raw(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        _fail(name, raw, "数字")


def _env_bool(name: str, default: bool) -> bool:
    raw = _raw(name)
    if raw is None:
        return default
    lowered = raw.lower()
    if lowered in {"1", "true", "yes", "on"}:
        return True
    if lowered in {"0", "false", "no", "off"}:
        return False
    _fail(name, raw, "true/false")


def _csv(raw: str) -> tuple[str, ...]:
    """逗号分隔串 -> 去空白、去空项后的元组。"""
    return tuple(part.strip() for part in raw.split(",") if part.strip())


def _env_int_tuple(name: str, default: tuple[int, ...]) -> tuple[int, ...]:
    raw = _raw(name)
    if raw is None:
        return default
    try:
        return tuple(int(part) for part in _csv(raw))
    except ValueError:
        _fail(name, raw, "逗号分隔的整数，例如 443,2053")


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
PROBE_HOST: str = _env_str("PROBE_HOST", "")
PROBE_PATH: str = _env_str("PROBE_PATH", "/cdn-cgi/trace")

# 机房代码 -> 国家代码 的本地映射文件（位于 DATA_DIR，人工维护，运行时不联网）。
LOCATIONS_FILE: str = _env_str("LOCATIONS_FILE", "locations.json")
# 跳过机房映射（国家/国旗列留空），仅调试用。
SKIP_LOCATIONS: bool = _env_bool("SKIP_LOCATIONS", False)

# ---------------------------------------------------------------- 端口组 --
# 候选端口集合：每个候选 IP 从中随机分配一个端口去探测。
# Cloudflare 支持的 HTTPS 端口全集：443, 2053, 2083, 2087, 2096, 8443
# 端口越多候选组合越丰富，单轮耗时也越高。
PROBE_PORTS: tuple[int, ...] = _env_int_tuple("PROBE_PORTS", (443,))

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
PROBE_CONCURRENCY: int = _env_int("PROBE_CONCURRENCY", 200)  # 并发线程数（两阶段共用）
TCP_ATTEMPTS: int = _env_int("TCP_ATTEMPTS", 3)              # 每个候选的握手次数
TCP_MIN_SUCCESS: int = _env_int("TCP_MIN_SUCCESS", 2)        # 合格门槛：至少成功几次
TCP_TIMEOUT: float = _env_float("TCP_TIMEOUT", 3.0)          # 单次握手超时（秒）
TRACE_TIMEOUT: int = _env_int("TRACE_TIMEOUT", 5)            # 单次端点校验超时（秒）
TRACE_ATTEMPTS: int = _env_int("TRACE_ATTEMPTS", 2)          # 端点校验最大尝试次数

# -------------------------------------------------------------- 采样参数 --
# 采样密度：每 SAMPLE_STRIDE 个地址抽取 1 个代表 IP。
# 窗口按**地址网格**对齐（窗口起点是 SAMPLE_STRIDE 的整数倍），与库内条目如何
# 切分/合并无关；取 256（一个 /24 的长度）时，等价于每个 /24 抽 1 个。
# 末尾不足一个窗口的区间仍抽 1 个。
SAMPLE_STRIDE: int = _env_int("SAMPLE_STRIDE", 256)
# 候选总量上限：0 = 不限；>0 时按采样种子洗牌后截断，
# 避免地址序靠前的网段永远被优先选中（快速验证环境时也很有用）。
MAX_CANDIDATES: int = _env_int("MAX_CANDIDATES", 0)
# 采样种子：实际种子 = SAMPLE_SEED * SEED_HOUR_FACTOR + 当前北京小时(YYYYMMDDHH)。
# 同一小时内多次运行结果可复现；跨小时自动轮换，长期覆盖库内更多 IP 与端口组合。
SAMPLE_SEED: int = _env_int("SAMPLE_SEED", 42)
SEED_HOUR_FACTOR: int = _env_int("SEED_HOUR_FACTOR", 1_000_000)

# ---------------------------------------------------------------- 输入 --
# 候选地址库文件（相对 DATA_DIR）。每行一个条目，支持三种写法：
#   CIDR       104.16.0.0/24     —— 展开为该网段，参与网格采样
#   单个 IP    104.17.3.3        —— 等价 /32
#   IP:端口   104.18.4.4:8443   —— 原样保留为候选，不参与采样、端口不被替换
# 行首 # 为注释；空行与 cidr/ip 表头行会被跳过。
# 脚本不修改该文件——要排除网段在行首加 # 并写明依据即可（可一行恢复）。
LIBRARY_FILE: str = _env_str("LIBRARY_FILE", "ip-library.txt")
# 数据目录（候选地址库 + 机房映射）。容器内默认 /data，由 compose 挂载宿主目录。
DATA_DIR: str = _env_str("DATA_DIR", str(APP_DIR / "data"))

# ---------------------------------------------------------------- 输出 --
# 产物目录：明细表与订阅列表直接写在这里。
# 容器内部署时由 compose 注入 /output，对应宿主 ./output。
OUTPUT_DIR: str = _env_str("OUTPUT_DIR", str(APP_DIR / "output"))
# 明细表文件名（不含扩展名）：记录全部合格候选及其测量指标，供排查与二次筛选。
DETAIL_CSV_NAME: str = _env_str("DETAIL_CSV_NAME", "detail")
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
OVERALL_TOPS: tuple[int, ...] = _env_int_tuple(
    "OVERALL_TOPS", (20, 50, 100, 200, 400)
)
COUNTRY_FILTERS: bool = _env_bool("COUNTRY_FILTERS", False)

# 每个国家一个变量：TOP_<两位国家代码>=N，N 就是该国家列表的条数。
# 仅当 COUNTRY_FILTERS=true 时生效；0 或留空 = 该国不生成。
_COUNTRY_CODES: tuple[str, ...] = ("US", "JP", "SG", "DE", "NL", "FR")
COUNTRY_TOPS: dict[str, int] = {
    code: _env_int(f"TOP_{code}", 100) for code in _COUNTRY_CODES
}

# -------------------------------------------------------------- 请求头 --
# 端点校验请求使用的 User-Agent（保持浏览器指纹，与 curl_cffi 配合）。
PROBE_HEADERS: dict[str, str] = {
    "User-Agent": _env_str(
        "PROBE_USER_AGENT",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0",
    ),
}
