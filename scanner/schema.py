"""参数元数据 —— 全部可调参数的唯一来源。

每个参数在这里声明一次：名称、分组、类型、默认值、中文标签与说明、由谁消费
（scanner / shell / publish / proxy / panel）、是否敏感、是否只读、是否需重启。
`scanner/config.py` 用本文件取值，面板用它生成表单——两处不会各写一份默认值。

`kind` 决定取值与展示方式：
    str / path / cron   原样字符串
    int / float         数值
    bool                true/false/yes/no/on/off/1/0
    csv_int             逗号分隔的整数元组
    ports               逗号分隔的端口元组（1-65535）
    secret              只写不读的字符串（令牌、带认证信息的代理 URL）
"""

from __future__ import annotations

from dataclasses import dataclass

_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}

_USER_AGENT_DEFAULT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0"
)

_COUNTRY_CODES: tuple[str, ...] = ("US", "JP", "SG", "DE", "NL", "FR")


@dataclass(frozen=True)
class ParamSpec:
    """单个可调参数的元数据。"""

    name: str
    group: str
    kind: str
    default: object
    label: str
    help: str
    consumer: str = "scanner"
    restart: bool = False
    secret: bool = False
    read_only: bool = False


PARAMS: tuple[ParamSpec, ...] = (
    # ---------------------------------------------------------- 探测端点 --
    ParamSpec(
        "PROBE_HOST",
        "探测端点",
        "str",
        "",
        "探测域名",
        "你自己托管在 Cloudflare、已开启代理的域名；决定哪些 IP 算合格边缘节点。",
    ),
    ParamSpec(
        "PROBE_PATH",
        "探测端点",
        "str",
        "/cdn-cgi/trace",
        "探测路径",
        "端点校验路径，由 Cloudflare 边缘直接应答，一般不用改。",
    ),
    ParamSpec(
        "PROBE_USER_AGENT",
        "探测端点",
        "str",
        _USER_AGENT_DEFAULT,
        "探测 User-Agent",
        "端点校验使用的浏览器指纹，留空使用默认值。",
    ),
    ParamSpec(
        "LOCATIONS_FILE",
        "探测端点",
        "str",
        "locations.json",
        "机房映射文件",
        "机房代码到国家代码的映射文件名（相对 DATA_DIR），运行时不联网。",
    ),
    ParamSpec(
        "SKIP_LOCATIONS",
        "探测端点",
        "bool",
        False,
        "跳过机房映射",
        "调试用：跳过映射，国家/国旗列留空。",
    ),
    # ---------------------------------------------------------- 探测参数 --
    ParamSpec(
        "PROBE_PORTS",
        "探测参数",
        "ports",
        (443,),
        "候选端口集",
        "每个候选 IP 随机分配一个端口去探测；CF 支持 443,2053,2083,2087,2096,8443。",
    ),
    ParamSpec(
        "PROBE_CONCURRENCY",
        "探测参数",
        "int",
        200,
        "并发线程数",
        "TCP 握手与端点校验共用；带宽或路由器较弱时降到 50~100。",
    ),
    ParamSpec(
        "TCP_ATTEMPTS",
        "探测参数",
        "int",
        3,
        "TCP 握手次数",
        "每个候选重复测量次数，用于区分稳定快与偶发快。",
    ),
    ParamSpec(
        "TCP_MIN_SUCCESS",
        "探测参数",
        "int",
        2,
        "握手成功门槛",
        "至少成功几次才进入端点校验，不得超过 TCP_ATTEMPTS。",
    ),
    ParamSpec(
        "TCP_TIMEOUT",
        "探测参数",
        "float",
        3.0,
        "握手超时（秒）",
        "单次 TCP 握手超时；家用宽带到境外通常 2~5。",
    ),
    ParamSpec(
        "TRACE_TIMEOUT",
        "探测参数",
        "int",
        5,
        "端点校验超时（秒）",
        "单次端点校验超时；跨境高延迟链路可调到 8~10。",
    ),
    ParamSpec(
        "TRACE_ATTEMPTS",
        "探测参数",
        "int",
        2,
        "端点校验尝试次数",
        "含首次；1 = 不重试，2 = 重试一次。",
    ),
    # -------------------------------------------------------------- 采样 --
    ParamSpec(
        "SAMPLE_STRIDE",
        "采样",
        "int",
        256,
        "采样步长",
        "每 N 个地址抽 1 个代表 IP；256 = 每个 /24 抽 1 个。",
    ),
    ParamSpec(
        "SAMPLE_SEED",
        "采样",
        "int",
        42,
        "采样基础种子",
        "同一小时内结果可复现，跨小时自动轮换覆盖更多地址与端口。",
    ),
    ParamSpec(
        "SEED_HOUR_FACTOR",
        "采样",
        "int",
        1_000_000,
        "种子轮换因子",
        "实际种子 = 基础种子 × 本因子 + 当前北京小时，一般不用改。",
    ),
    # ---------------------------------------------------------- 输入输出 --
    ParamSpec(
        "LIBRARY_FILE",
        "输入输出",
        "str",
        "ip-library.txt",
        "地址库文件名",
        "候选地址库文件名（相对 DATA_DIR）；行首 # 为注释。",
    ),
    ParamSpec(
        "PINNED_FILE",
        "输入输出",
        "str",
        "ip-pinned.txt",
        "固定保留文件名",
        "不参与扫描、直接附加到全量列表的条目文件（相对 DATA_DIR）。",
    ),
    ParamSpec(
        "DETAIL_CSV_NAME",
        "输入输出",
        "str",
        "detail",
        "明细表文件名",
        "不含扩展名；记录全部合格候选及测量指标。",
    ),
    ParamSpec(
        "PINNED_OUTPUT_NAME",
        "输入输出",
        "str",
        "PINNED",
        "固定保留文件名",
        "不含扩展名；固定保留条目单独生成该文件，不写入 GLOBAL/国家列表。",
    ),
    ParamSpec(
        "OVERALL_TOPS",
        "输入输出",
        "csv_int",
        (20, 50, 100, 200, 400),
        "全量列表档位",
        "逗号分隔的条数，生成 GLOBAL{N}.txt；留空则不生成。",
    ),
    ParamSpec(
        "COUNTRY_FILTERS",
        "输入输出",
        "bool",
        False,
        "生成国家列表",
        "总开关；开启后按 TOP_<国家代码> 生成国家订阅列表。",
    ),
    *(
        ParamSpec(
            f"TOP_{code}",
            "输入输出",
            "int",
            100,
            f"{code} 列表条数",
            f"仅 COUNTRY_FILTERS=true 时生效；0 表示该国不生成。",
        )
        for code in _COUNTRY_CODES
    ),
    # -------------------------------------------------------------- 调度 --
    ParamSpec(
        "CRON_SCHEDULE",
        "定时计划",
        "cron",
        "30 */6 * * *",
        "调度表达式",
        "5 段（分 时 日 月 周）、6 段（+年）、7 段（秒+5 段+年）；不支持 @daily 宏。",
        consumer="shell",
    ),
    ParamSpec(
        "RUN_ON_START",
        "定时计划",
        "bool",
        True,
        "启动即跑一轮",
        "容器启动后立即执行一轮；重启容器后生效。",
        consumer="shell",
        restart=True,
    ),
    # ---------------------------------------------------------- 运行身份 --
    ParamSpec(
        "PUID",
        "运行身份",
        "int",
        1000,
        "容器内 UID",
        "业务进程与产物文件的属主；重启容器后生效。",
        consumer="shell",
        restart=True,
    ),
    ParamSpec(
        "PGID",
        "运行身份",
        "int",
        1000,
        "容器内 GID",
        "业务进程与产物文件的属组；重启容器后生效。",
        consumer="shell",
        restart=True,
    ),
    ParamSpec(
        "TZ",
        "运行身份",
        "str",
        "Asia/Shanghai",
        "时区",
        "调度与提交信息使用的时区；重启容器后生效。",
        consumer="shell",
        restart=True,
    ),
    # -------------------------------------------------------------- 发布 --
    ParamSpec(
        "GIT_PUSH_ENABLED",
        "发布",
        "bool",
        False,
        "启用 Git 推送",
        "关闭时只在本地产出；开启需同时填好仓库地址与令牌。",
        consumer="publish",
    ),
    ParamSpec(
        "GIT_REPO_URL",
        "发布",
        "str",
        "",
        "目标仓库",
        "HTTPS 地址，例如 https://github.com/OWNER/REPO.git。",
        consumer="publish",
    ),
    ParamSpec(
        "GIT_BRANCH",
        "发布",
        "str",
        "main",
        "目标分支",
        "产物推送到该分支。",
        consumer="publish",
    ),
    ParamSpec(
        "GIT_TOKEN",
        "发布",
        "secret",
        "",
        "访问令牌",
        "具备 contents:write 权限；只写不读，日志与审计脱敏。",
        consumer="publish",
        secret=True,
    ),
    ParamSpec(
        "GIT_OUTPUT_SUBDIR",
        "发布",
        "str",
        "result",
        "产物子目录",
        "产物在目标仓库中的目录名，该目录下旧文件会被本轮结果替换。",
        consumer="publish",
    ),
    ParamSpec(
        "GIT_AUTHOR_NAME",
        "发布",
        "str",
        "cf-ip-scanner-bot",
        "提交作者",
        "出现在目标仓库提交记录里的作者名。",
        consumer="publish",
    ),
    ParamSpec(
        "GIT_AUTHOR_EMAIL",
        "发布",
        "str",
        "cf-ip-scanner-bot@users.noreply.github.com",
        "提交邮箱",
        "出现在目标仓库提交记录里的作者邮箱。",
        consumer="publish",
    ),
    ParamSpec(
        "GIT_RETRY_MAX",
        "发布",
        "int",
        3,
        "推送重试次数",
        "总尝试次数，失败按基础退避时间翻倍。",
        consumer="publish",
    ),
    ParamSpec(
        "GIT_RETRY_BASE_DELAY",
        "发布",
        "int",
        10,
        "重试初始退避（秒）",
        "每次失败后翻倍等待。",
        consumer="publish",
    ),
    # ---------------------------------------------------------- 网络代理 --
    ParamSpec(
        "HTTP_PROXY",
        "网络代理",
        "secret",
        "",
        "HTTP 代理",
        "只影响会读环境代理的客户端；探测流量必须直连。",
        consumer="proxy",
        secret=True,
    ),
    ParamSpec(
        "HTTPS_PROXY",
        "网络代理",
        "secret",
        "",
        "HTTPS 代理",
        "同上，供 git / 拉取依赖等出网流量使用。",
        consumer="proxy",
        secret=True,
    ),
    ParamSpec(
        "ALL_PROXY",
        "网络代理",
        "secret",
        "",
        "通用代理",
        "部分工具读取的兜底代理变量。",
        consumer="proxy",
        secret=True,
    ),
    ParamSpec(
        "NO_PROXY",
        "网络代理",
        "str",
        "",
        "代理豁免清单",
        "必须包含 PROBE_HOST 及其后缀，否则端点校验会走代理出口。",
        consumer="proxy",
    ),
    ParamSpec(
        "no_proxy",
        "网络代理",
        "str",
        "",
        "代理豁免清单（小写）",
        "与 NO_PROXY 内容一致，兼容只认小写的工具。",
        consumer="proxy",
    ),
    # ---------------------------------------------------------- 只读设置 --
    ParamSpec(
        "IMAGE_NAME",
        "只读设置",
        "str",
        "ghcr.io/lancelotrar/self-hosted-best-cf-ip-scanner",
        "镜像名",
        "修改需要重新 docker compose up；页面只读。",
        consumer="panel",
        read_only=True,
    ),
    ParamSpec(
        "IMAGE_TAG",
        "只读设置",
        "str",
        "latest",
        "镜像标签",
        "建议锁定具体版本或 digest；页面只读。",
        consumer="panel",
        read_only=True,
    ),
    ParamSpec(
        "CONTAINER_NAME",
        "只读设置",
        "str",
        "best-cf-ip-scanner",
        "扫描容器名",
        "与其他 compose 项目冲突时在 .env 中修改；页面只读。",
        consumer="panel",
        read_only=True,
    ),
    ParamSpec(
        "PANEL_PORT",
        "只读设置",
        "int",
        8080,
        "面板端口",
        "修改需要重建面板容器；页面只读。",
        consumer="panel",
        read_only=True,
    ),
    ParamSpec(
        "PANEL_BIND",
        "只读设置",
        "str",
        "0.0.0.0",
        "面板监听地址",
        "默认监听全部网卡；页面只读。",
        consumer="panel",
        read_only=True,
    ),
    ParamSpec(
        "PANEL_TRUST_PROXY",
        "只读设置",
        "bool",
        False,
        "信任反向代理",
        "仅在根路径反代后设为 true，才采信 X-Forwarded-*。",
        consumer="panel",
        read_only=True,
    ),
    ParamSpec(
        "PANEL_SESSION_DAYS",
        "只读设置",
        "int",
        7,
        "会话有效期（天）",
        "登录 Cookie 的有效期。",
        consumer="panel",
        read_only=True,
    ),
)

BY_NAME: dict[str, ParamSpec] = {spec.name: spec for spec in PARAMS}
KNOWN_KEYS: frozenset[str] = frozenset(BY_NAME)


def coerce(spec: ParamSpec, raw: str) -> object:
    """把字符串转成参数对应的 Python 值；非法时抛 `ValueError`。"""
    value = raw if spec.kind == "secret" else raw.strip()
    kind = spec.kind
    if kind in {"str", "path", "cron", "secret"}:
        return value
    if kind == "int":
        return int(value)
    if kind == "float":
        return float(value)
    if kind == "bool":
        lowered = value.lower()
        if lowered in _TRUE_VALUES:
            return True
        if lowered in _FALSE_VALUES:
            return False
        raise ValueError(f"{spec.name} 只接受 true/false")
    if kind == "csv_int":
        parts = [part.strip() for part in value.split(",") if part.strip()]
        return tuple(int(part) for part in parts)
    if kind == "ports":
        parts = [part.strip() for part in value.split(",") if part.strip()]
        if not parts:
            raise ValueError(f"{spec.name} 至少需要一个端口")
        ports = tuple(int(part) for part in parts)
        if any(port < 1 or port > 65535 for port in ports):
            raise ValueError(f"{spec.name} 端口必须在 1-65535")
        return ports
    raise ValueError(f"未知参数类型：{kind}")


def format_value(spec: ParamSpec, value: object) -> str:
    """把参数值编码回 `.env` 可写的字符串，与 `coerce` 互逆。"""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (tuple, list)):
        return ",".join(str(item) for item in value)
    if isinstance(value, float):
        return repr(value)
    return str(value)


__all__ = [
    "BY_NAME",
    "KNOWN_KEYS",
    "PARAMS",
    "ParamSpec",
    "coerce",
    "format_value",
]
