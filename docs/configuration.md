# 配置手册

[← 返回首页](../README.md) · [部署详解](deployment.md)

本项目的全部可调参数只有**一个入口：`.env`**。

- 文件位置：与 `compose.yaml` 同目录（部署目录下）。
- 来源：由仓库里的 `.env.example` 复制而来（见 [部署详解](deployment.md)）。
- 生效方式：改完执行 `docker compose up -d --force-recreate`，**不需要重建镜像**。
- 留空 = 使用镜像内默认值（`scanner/config.py`），不是"关闭"。

```bash
cd <部署目录>          # 里面有 compose.yaml 与 .env
vi .env               # 唯一的配置文件
grep '^PROBE_HOST=' .env      # 确认必填项已填
docker compose up -d --force-recreate
docker compose logs --tail=20  # 启动摘要会打印"生效配置"
```

---

## 完整配置模板

以下是 `.env` 的完整内容（与仓库根目录的 `.env.example` 一致，含全部注释）。
只想先跑通：**填 `PROBE_HOST` 一项即可**，其余保持原样。

```dotenv
# ============================================================================
# best-cf-ip-scanner 运行参数
#
# 用法：
#   1) 复制为 .env
#   2) 只需填写【必填】项（默认只有 PROBE_HOST 一项）
#   3) docker compose up -d
#
# 分级：
#   【必填】 不填无法运行（启动会明确报错）
#   【建议】 按你的环境决定，通常一次性配好就不再动
#   【可选】 保持默认即可，需要时再调
#
# 约定：
#   - 留空 = 使用镜像内默认值（scanner/config.py），不是"关闭"；
#   - 列表用英文逗号 / 分号分隔，不加引号、不加空格；
#   - 改完执行 docker compose up -d --force-recreate 使新值生效，不必重建镜像；
#   - 启动日志会打印「生效配置」摘要，改完对照一眼即可确认。
# ============================================================================

# ----------------------------------------------------- 调度【建议】 ----
# 标准 cron 表达式（分 时 日 月 周），时区由 TZ 决定。
#   30 */6 * * *   每 6 小时的第 30 分钟（默认）
#   0 */2 * * *    每 2 小时整点
#   0 3 * * *      每天 03:00
CRON_SCHEDULE=30 */6 * * *
# 容器启动后立即执行一轮再进入调度：首次部署能马上看到结果。
# 若担心重启触发扫描，改成 false（严格按 cron 等下一个时点）。
RUN_ON_START=true
# 调度与提交信息使用的时区。产物里的扫描时间固定为北京时间（UTC+8），不受此项影响。
TZ=Asia/Shanghai

# ------------------------------------------------- 运行身份【建议】 ----
# 容器内业务进程的 uid/gid。入口脚本会把 ./data ./output ./cache 的属主自动对齐到
# 这两个值，宿主机不需要手工 chown；产物文件属主也是它们。
# 宿主机当前用户不是 1000 时改成 id -u / id -g，方便直接编辑产物与地址库。
PUID=1000
PGID=1000

# --------------------------------------------- 探测端点【必填】 ----
# 【必填】终筛探测域名：必须是你自己托管在 Cloudflare、且已开启代理（小黄云）的域名。
# 它决定"哪些 IP 算合格的 Cloudflare 边缘"，选错会把不可用地址当成优质节点。
#   ✅  probe.example.com      自己的域名，CF 代理已开启
#   ❌  speed.cloudflare.com   CF 自有域名：EIV 受限子池会被误收录
#   ❌  example.com            未接入 Cloudflare
# 换域名时务必同步把它加进下面的 NO_PROXY / no_proxy。
PROBE_HOST=
# 端点校验路径，由 Cloudflare 边缘直接应答，一般不修改。
PROBE_PATH=/cdn-cgi/trace
# 端点校验使用的 User-Agent（留空 = 镜像内置的浏览器指纹，一般不用改）
PROBE_USER_AGENT=

# --------------------------------------------- 探测参数【可选】 ----
# 候选端口集合，每个候选 IP 随机分配一个端口去探测。
# CF 支持的 HTTPS 端口全集：443,2053,2083,2087,2096,8443
#   只测 443（默认，最通用）      PROBE_PORTS=443
#   测全部 HTTPS 端口             PROBE_PORTS=443,2053,2083,2087,2096,8443
# 不能留空或填 0：启动校验会拒绝（端口分配需要至少一个合法端口）。
PROBE_PORTS=443
# 并发线程数（TCP 握手测量与端点校验共用）。带宽/路由器较弱时降到 50~100。
PROBE_CONCURRENCY=200
# 每个候选的 TCP 握手次数（重复测量可区分"稳定快"与"偶发快"）。
TCP_ATTEMPTS=3
# 合格门槛：至少成功几次握手才进入端点校验，不得超过 TCP_ATTEMPTS。
# 线路抖动大时设 1，要求严格时设 3。
TCP_MIN_SUCCESS=2
# 单次 TCP 握手超时（秒）。家用宽带到境外通常 2~5。
TCP_TIMEOUT=3.0
# 单次端点校验超时（秒）。跨境高延迟链路可调到 8~10。
TRACE_TIMEOUT=5
# 端点校验最大尝试次数（含首次）：1 = 不重试，2 = 重试一次（默认）。
TRACE_ATTEMPTS=2

# ------------------------------------------------- 采样【可选】 ----
# 每 N 个地址抽取 1 个代表 IP。默认 256（一个 /24 的长度）= 每个 /24 抽 1 个。
#   128  更密、更慢（候选量翻倍）
#   512  更稀、更快
SAMPLE_STRIDE=256
# 候选总量上限：0 = 不限（默认，全量约 2~5 分钟）；快速验证环境时设小值，如 200。
MAX_CANDIDATES=0
# 采样基础种子：同一小时内结果可复现，跨小时自动轮换覆盖不同 IP 与端口组合。
SAMPLE_SEED=42

# ------------------------------------------------- 输入【可选】 ----
# 候选地址库文件名（相对 DATA_DIR，即宿主 ./data）。
# 每行支持：CIDR / 单个 IP / IP:端口；行首 # 为注释。
LIBRARY_FILE=ip-library.txt
# 调试用：跳过机房映射（国家/国旗列留空）。正常保持 false。
SKIP_LOCATIONS=false

# ------------------------------------------------- 输出【可选】 ----
# 明细表文件名（不含扩展名）：记录全部合格候选及其测量指标。
DETAIL_CSV_NAME=detail

# 全量列表 -> GLOBAL{N}.txt：对全部合格候选排名（不按国家筛选）。
# 填几个数字就生成几个文件（任意正整数，逗号分隔）。
#   OVERALL_TOPS=20,50,100,200,400   -> GLOBAL20 / GLOBAL50 / GLOBAL100 / GLOBAL200 / GLOBAL400
#   OVERALL_TOPS=100                 -> 只生成 GLOBAL100.txt
#   留空                            -> 不生成全量列表
OVERALL_TOPS=20,50,100,200,400

# 国家列表总开关。false（默认）= 不生成任何国家列表；true = 按下面的数值生成。
COUNTRY_FILTERS=false

# 每个国家一个变量：TOP_<国家代码>=N，N 就是该国列表的条数。
# 仅 COUNTRY_FILTERS=true 时生效；0 或留空 = 该国不生成。
#   TOP_US=100 -> US100.txt；TOP_JP=50 -> JP50.txt
TOP_US=100
TOP_JP=100
TOP_SG=100
TOP_DE=100
TOP_NL=100
TOP_FR=100

# --------------------------------------------- 产物发布【建议】 ----
# 是否把产物提交推送到 Git 仓库。
#   false = 只在本地产出（默认，先验证扫描是否正常）
#   true  = 需要同时填好 GIT_REPO_URL 与 GIT_TOKEN
GIT_PUSH_ENABLED=false
# 目标仓库（HTTPS 地址）。产物以"镜像语义"同步到 GIT_OUTPUT_SUBDIR 目录：
# 该目录下旧的 *.txt / *.csv 会被本轮结果替换。
#   https://github.com/OWNER/REPO.git
GIT_REPO_URL=
GIT_BRANCH=main
# 具备目标仓库 contents:write 权限的访问令牌（使用 HTTP(S) 远端时必填）。
# 只经 http.extraheader 注入，不写入 .git/config，也不会出现在日志里。
GIT_TOKEN=
# 产物在目标仓库中的目录名，默认 result/
GIT_OUTPUT_SUBDIR=result
# 提交作者信息（会出现在目标仓库的提交记录里）
GIT_AUTHOR_NAME=cf-ip-scanner-bot
GIT_AUTHOR_EMAIL=cf-ip-scanner-bot@users.noreply.github.com
# 推送失败重试：总尝试次数与初始退避秒数（每次翻倍，10s / 20s）
GIT_RETRY_MAX=3
GIT_RETRY_BASE_DELAY=10

# --------------------------------------------- 网络代理【建议】 ----
# 本工具同时产生两类流量，方向相反，必须分开处理：
#   出网（git push / 拉镜像 / 下载依赖） —— 大陆通常需要代理
#   探测（TCP 握手 + 端点校验到候选 IP） —— 必须直连，否则测到的是代理出口
# 下面两个代理变量只影响"会读环境代理"的客户端（端点校验由 curl_cffi 发起，
# 会读；TCP 握手用原始 socket，不读）。直连环境留空即可。
#   HTTP_PROXY=http://192.168.1.2:7890
HTTP_PROXY=
HTTPS_PROXY=
# 【关键项】必须把 PROBE_HOST 及其后缀加入豁免清单，让端点校验直连候选 IP。
# 经代理时 CONNECT 以域名为目标，会绕过 curl RESOLVE 的钉 IP，导致所有候选落到
# 代理出口的同一机房（症状：全部候选同一机房代码、延迟挤在窄带），而且表面上
# 仍返回 200 + colo，不报错——所以启动时会校验，未豁免直接拒绝运行。
# 内网/回环一并豁免；大小写两种写法都写上，兼容只认其中一种的工具。
# 把 your-probe-domain.example 换成你的 PROBE_HOST：
NO_PROXY=localhost,127.0.0.1,::1,192.168.0.0/16,172.16.0.0/12,your-probe-domain.example
no_proxy=localhost,127.0.0.1,::1,192.168.0.0/16,172.16.0.0/12,your-probe-domain.example
# 注意：若宿主/网关开了 Clash TUN、OpenWrt 透明代理等全局代理，流量不经过这些
# 变量、NO_PROXY 不生效（连 TCP 握手也会被接管）。此时要在代理软件里给 Cloudflare
# 段设直连规则，或让容器不经过 TUN。用 doctor.sh 对比"默认路径/强制直连"可确认。

# --------------------------------------------- 容器与镜像【可选】 ----
# 容器名（与其他 compose 项目冲突时修改）
CONTAINER_NAME=best-cf-ip-scanner
# 镜像坐标：默认使用官方多架构镜像，无需本地构建。
# 锁定版本可把 IMAGE_TAG 改成 sha-xxxxxxx 或 1.2.3。
IMAGE_NAME=ghcr.io/lancelotrar/best-cf-ip-scanner-docker
IMAGE_TAG=latest
```

---

## 取值规则

| 规则 | 说明 |
| --- | --- |
| 留空 | 视为未配置，使用镜像内默认值 |
| 布尔 | `true` / `false`（也接受 yes/no/on/off/1/0） |
| 列表 | 英文逗号分隔，不加空格、不加引号，如 `443,2053` |
| 非法值 | 启动即报错退出并在日志写明原因（不静默回退） |

三类"配错会静默出错"的情况由启动校验拦截，进程直接退出：

1. `PROBE_HOST` 未配置；
2. 配了出网代理，但 `NO_PROXY` / `no_proxy` 未豁免 `PROBE_HOST`；
3. 数值型参数越界（如 `TCP_MIN_SUCCESS` 大于 `TCP_ATTEMPTS`、`PROBE_CONCURRENCY` 为 0）。

---

## 留空与特殊值

**通用规则：留空 = 使用镜像内默认值**（下表每项都给出了默认值），不是"关闭"。

少数参数的"空值"或特定值有专门语义，单独列出：

| 参数 | 留空 / 特定值 | 实际行为 |
| --- | --- | --- |
| `PROBE_HOST` | 留空 | **无默认值，启动直接报错退出**（不会进入调度） |
| `OVERALL_TOPS` | 留空 | 不生成全量列表 |
| `OVERALL_TOPS` | `20,50,100` | 每个数字生成一个文件：`GLOBAL20.txt` / `GLOBAL50.txt` / `GLOBAL100.txt` |
| `COUNTRY_FILTERS` | `false`（默认） | **不生成国家列表**，所有 `TOP_<国家>` 数值被忽略 |
| `COUNTRY_FILTERS` | `true` | 按 `TOP_<国家>` 的数值生成国家列表 |
| `TOP_US` / `TOP_JP` / … | `0` 或留空 | 该国不生成（需开关为 `true`） |
| `MAX_CANDIDATES` | `0` | 不限制候选量（全量扫描） |
| `TRACE_ATTEMPTS` | `1` | 不重试；`2` = 重试一次（默认） |
| `TCP_MIN_SUCCESS` | 等于 `TCP_ATTEMPTS` | 要求零丢包才合格 |
| `GIT_PUSH_ENABLED` | 留空 | 默认为 `false`，只在本地产出 |
| `GIT_TOKEN` | 留空 | 只在 HTTP(S) 远端发布时报错；`file://` / 本地路径不需要 |
| `HTTP_PROXY` / `HTTPS_PROXY` | 留空 | 直连；配了其中之一就必须同时豁免 `PROBE_HOST` |
| `PROBE_USER_AGENT` | 留空 | 使用镜像内置的浏览器指纹 |

注意：`0` 并不是"关闭"的通用写法——只有 `MAX_CANDIDATES` 用 `0` 表示不限，其余数值型
参数取 `0` 会被校验拒绝（例如 `TCP_TIMEOUT=0`、`PROBE_CONCURRENCY=0`）。

## 校验机制

配置错误分三类，处理时机与容器行为不同：

| 类别 | 例子 | 发生时机 | 表现 |
| --- | --- | --- | --- |
| 语法错误 | `PROBE_CONCURRENCY=abc`、`OVERALL_TOPS=abc`、`PROBE_PORTS=abc` | 进程导入配置时 | 打印 `[错误] 环境变量 X=... 非法：期望...`，退出码 1 |
| 语义错误 | 缺 `PROBE_HOST`、`PROBE_HOST` 带协议/端口、`PROBE_PORTS` 为空、条数为负、`TCP_MIN_SUCCESS > TCP_ATTEMPTS`、代理未豁免探测域名 | 容器启动时（`check-config.py`） | 打印编号问题清单，退出码 1，**容器不进入调度** |
| 运行期失败 | 本轮 TCP 握手全灭、端点校验无合格候选、发布失败 | 每轮任务 | 该轮任务失败（日志说明原因），**容器继续运行**，下一轮照常 |

关键区别：

- **配置类错误发生在启动阶段**：容器起不来（`docker compose ps` 会显示
  `Restarting` 或退出码非 0），日志首屏就是原因。修好 `.env` 后
  `docker compose up -d --force-recreate` 即可。
- **运行期失败不杀容器**：调度器保持运行，失败信息在当轮日志里；网络抖动导致的失败
  通常下一轮自动恢复。
- 语义类错误还会在**每轮任务开始时再校验一次**（`run()` 内），避免运行期改动绕过启动检查。

启动期的输出形如：

```
[entrypoint] 配置不合法，容器不会进入调度：
  1. 未配置 PROBE_HOST（探测域名）：见 docs/deployment.md 与 .env.example
  2. 已配置出网代理，但 NO_PROXY 未豁免探测域名 probe.example.com：...
  参数说明：docs/configuration.md
```

---

## 参数总表

### 必填（1 项，不填无法运行）

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `PROBE_HOST` | 无 | 边缘端点校验域名。必须是你自己托管在 Cloudflare、且已开启代理（小黄云）的域名 |

### 调度

| 变量 | 默认值 | 级别 | 说明 |
| --- | --- | --- | --- |
| `CRON_SCHEDULE` | `30 */6 * * *` | 建议 | 标准 cron（分 时 日 月 周），时区由 `TZ` 决定 |
| `RUN_ON_START` | `true` | 可选 | 容器启动后是否立即执行一轮 |
| `TZ` | `Asia/Shanghai` | 可选 | 调度与提交信息时区；产物中的扫描时间固定为北京时间 |

### 运行身份

| 变量 | 默认值 | 级别 | 说明 |
| --- | --- | --- | --- |
| `PUID` | `1000` | 建议 | 业务进程 uid；入口会把 `./data ./output ./cache` 属主对齐到它 |
| `PGID` | `1000` | 建议 | 业务进程 gid；同上 |

### 探测端点

| 变量 | 默认值 | 级别 | 说明 |
| --- | --- | --- | --- |
| `PROBE_HOST` | 无 | **必填** | 见上表 |
| `PROBE_PATH` | `/cdn-cgi/trace` | 可选 | 端点校验路径，由 CF 边缘直接应答，一般不改 |
| `PROBE_USER_AGENT` | 内置浏览器 UA | 可选 | 端点校验请求的 User-Agent |

### 探测参数

| 变量 | 默认值 | 级别 | 说明 |
| --- | --- | --- | --- |
| `PROBE_PORTS` | `443` | 建议 | 候选端口集合，每个候选随机分配一个 |
| `PROBE_CONCURRENCY` | `200` | 建议 | 并发线程数（两阶段共用） |
| `TCP_ATTEMPTS` | `3` | 可选 | 每候选 TCP 握手次数 |
| `TCP_MIN_SUCCESS` | `2` | 可选 | 握手合格门槛（不得大于 `TCP_ATTEMPTS`） |
| `TCP_TIMEOUT` | `3.0` | 可选 | 单次握手超时（秒） |
| `TRACE_TIMEOUT` | `5` | 可选 | 单次端点校验超时（秒） |
| `TRACE_ATTEMPTS` | `2` | 可选 | 端点校验最大尝试次数（含首次） |

### 采样

| 变量 | 默认值 | 级别 | 说明 |
| --- | --- | --- | --- |
| `SAMPLE_STRIDE` | `256` | 可选 | 每 N 个地址抽 1 个；256 = 每个 /24 一个 |
| `MAX_CANDIDATES` | `0` | 建议 | 候选总量上限，0 = 不限 |
| `SAMPLE_SEED` | `42` | 可选 | 采样基础种子，按北京小时自动轮换 |

### 输入

| 变量 | 默认值 | 级别 | 说明 |
| --- | --- | --- | --- |
| `LIBRARY_FILE` | `ip-library.txt` | 可选 | 候选地址库文件名（相对 `./data`） |
| `SKIP_LOCATIONS` | `false` | 可选 | 调试用：跳过机房映射 |

### 输出

| 变量 | 默认值 | 级别 | 说明 |
| --- | --- | --- | --- |
| `DETAIL_CSV_NAME` | `detail` | 可选 | 明细表文件名（不含扩展名） |
| `OVERALL_TOPS` | `20,50,100,200,400` | 建议 | 全量列表条数（逗号分隔，任意正整数）→ 每项一个 `GLOBAL{N}.txt` |
| `COUNTRY_FILTERS` | `false` | 建议 | 国家列表总开关；`true` 才按各国数值生成 |
| `TOP_US` / `TOP_JP` / `TOP_SG` / `TOP_DE` / `TOP_NL` / `TOP_FR` | `100` | 可选 | 各国列表条数 → `{国家代码}{N}.txt`；仅开关为 `true` 时生效 |

### 产物发布（可选）

| 变量 | 默认值 | 级别 | 说明 |
| --- | --- | --- | --- |
| `GIT_PUSH_ENABLED` | `false` | 建议 | 是否需要把产物推到 Git 仓库 |
| `GIT_REPO_URL` | 空 | 建议 | 目标仓库 HTTPS 地址 |
| `GIT_BRANCH` | `main` | 可选 | 目标分支 |
| `GIT_TOKEN` | 空 | 建议 | `contents:write` 权限令牌（HTTP(S) 远端必填） |
| `GIT_OUTPUT_SUBDIR` | `result` | 可选 | 产物在目标仓库中的目录 |
| `GIT_AUTHOR_NAME` / `GIT_AUTHOR_EMAIL` | `cf-ip-scanner-bot` / `…@users.noreply.github.com` | 可选 | 提交作者 |
| `GIT_RETRY_MAX` / `GIT_RETRY_BASE_DELAY` | `3` / `10` | 可选 | 推送失败重试次数与初始退避秒数 |

### 网络代理

| 变量 | 默认值 | 级别 | 说明 |
| --- | --- | --- | --- |
| `HTTP_PROXY` / `HTTPS_PROXY` | 空 | 建议 | 容器出网代理（也用于镜像构建） |
| `NO_PROXY` / `no_proxy` | 见模板 | 建议 | **必须豁免 `PROBE_HOST`**，否则启动被拒绝 |

### 容器与镜像

| 变量 | 默认值 | 级别 | 说明 |
| --- | --- | --- | --- |
| `CONTAINER_NAME` | `best-cf-ip-scanner` | 可选 | 容器名 |
| `IMAGE_NAME` / `IMAGE_TAG` | `ghcr.io/lancelotrar/best-cf-ip-scanner-docker` / `latest` | 可选 | 镜像坐标与版本 |

---

## 关键参数详解

### `PROBE_HOST`（必填）

边缘端点校验域名。工具会把该域名"钉"到候选 `IP:端口` 上请求一次
`/cdn-cgi/trace`，因此这个域名必须满足：

1. 由 Cloudflare 边缘代理（小黄云开启），证书覆盖该域名；
2. `PROBE_PATH` 能返回 `colo=`（机场码）字段；
3. `PROBE_PORTS` 里启用的端口它都能服务；
4. **是你自己 zone 的域名**，不能是 `speed.cloudflare.com` 这类 CF 自有域名。

第 4 点决定筛选口径：用 CF 自有域名时，EIV 受限子池（专属/静态/BYOIP 地址）也会返回
`colo` 被误判为合格，但它们实际只在所属账号的 zone 上可用。详见 [为什么探测域名必须是自己的域名](../README.md#为什么探测域名必须是自己的域名)。

> 该域名只需要保持 CF 代理开启，不要求源站存活（trace 由边缘直接应答）。

### `PROBE_PORTS`

每个候选 IP 会从该集合里**随机分到一个端口**去探测。

- 只测 443（默认）：最通用，单轮最快。
- 测全集：`443,2053,2083,2087,2096,8443`。候选量不变，但每个 IP 只测其中一个端口，
  多次运行才会覆盖全部组合。
- 端口被运营商/公司网络屏蔽时，往往表现为"握手 0 合格"，可换端口验证。

### `PROBE_CONCURRENCY`

两阶段共用的线程数。单轮耗时大致与它成反比：

- 家用宽带 / 软路由：`50`~`100` 更稳，避免家用 NAT 会话表打满；
- 服务器 / 千兆宽带：`200`~`400` 更快；
- 出现大量 `tcp_connect_failed` 且与端口无关时，先降并发再判断。

### `TCP_ATTEMPTS` / `TCP_MIN_SUCCESS` / `TCP_TIMEOUT`

TCP 握手测量是初筛，也是排名依据（代理客户端显示的"TCP 延迟"就是这个口径）。

- `TCP_ATTEMPTS=3`：每个候选握手 3 次，用重复测量区分"稳定快"与"偶发快"。
- `TCP_MIN_SUCCESS=2`：3 次里至少成功 2 次才合格；等于 `TCP_ATTEMPTS` 就是"零丢包"，
  设为 1 则放宽。
- `TCP_TIMEOUT=3.0`：单次握手超时。跨境高延迟链路可设 `5`，减少误杀。

### `TRACE_TIMEOUT` / `TRACE_ATTEMPTS`

端点校验（终筛）的超时与重试。

- `TRACE_TIMEOUT=5`：含 TLS 握手与边缘处理，通常 5 秒够用；链路差可设 `8`~`10`。
- `TRACE_ATTEMPTS=2`：传输层失败与 5xx/429 会重试一次；确定性失败（如 403）不重试。

### `SAMPLE_STRIDE`

采样密度。每个地址网格窗口抽 1 个代表 IP：

- `256`（默认）= 每个 `/24` 抽 1 个；
- `128` = 样本翻倍，耗时约翻倍；
- `512` = 样本减半、更快，但覆盖变稀。

### `MAX_CANDIDATES`

候选总量上限。`0` = 全量（默认，约 2~5 分钟）。

- 首次验证环境建议设 `200` 左右，几十秒就能看到结果；
- 想逐小时慢慢覆盖整个库，可以保持 `0` 并靠 `CRON_SCHEDULE` 定时跑。

### `OVERALL_TOPS` / `COUNTRY_FILTERS` / `TOP_US` …

订阅列表分两组，每组只回答两个问题：**要不要**、**要多少**。

**全量列表** —— `OVERALL_TOPS` 是一个条数列表：

- `OVERALL_TOPS=20,50,100,200,400`（默认）→ 生成 `GLOBAL20.txt` … `GLOBAL400.txt` 五个文件。
- `OVERALL_TOPS=100` → 只生成 `GLOBAL100.txt`。
- 数字就是文件里的条数，**填多少生成多少**，不限于示例里的档位。
- 留空 = 不生成全量列表。

**国家列表** —— 由总开关 + 各国变量共同决定：

- `COUNTRY_FILTERS=false`（默认）→ 一个都不生成，下面的数值全部忽略。
- `COUNTRY_FILTERS=true` → 按 `TOP_<国家代码>=N` 生成 `{国家代码}{N}.txt`：
  `TOP_US=100` → `US100.txt`，`TOP_JP=50` → `JP50.txt`；`0` 表示该国不生成。
- 国家代码来自 `data/locations.json` 的机房映射；没有映射的机房不会进国家列表。

### `HTTP_PROXY` / `HTTPS_PROXY` / `NO_PROXY`

大陆机器通常需要代理访问 GitHub 与镜像仓库，但**探测必须直连**。要点：

- `HTTP_PROXY` / `HTTPS_PROXY` 只影响会读环境代理的客户端（端点校验走 curl_cffi 会读；
  TCP 握手用原始 socket，不读）。
- `NO_PROXY` / `no_proxy` 必须包含 `PROBE_HOST`（写后缀即可覆盖子域），否则端点校验会被
  代理接管——而且仍然返回 `200 + colo`，**不报错但结果全错**。启动校验会拦住这种配置。
- 如果宿主/网关开了 Clash TUN 或透明代理，环境变量不起作用，需要在代理软件里给
  Cloudflare 段设直连规则。用 `doctor.sh` 对比"默认路径 / 强制直连"可确认。

### `GIT_*`（产物发布）

默认关闭，只在本地产出。开启需要 `GIT_PUSH_ENABLED=true` + `GIT_REPO_URL` + `GIT_TOKEN`。

- 产物以镜像语义同步到 `GIT_OUTPUT_SUBDIR`（默认 `result/`）：目录内旧的 `*.txt` / `*.csv`
  会被本轮替换，把某个 `*_TOP` 改成 0 后不会留下孤儿文件。
- 令牌只经 `http.extraheader` 注入，不写入 `.git/config`，不出现在日志里。
- 提交信息带 `[skip ci]`，不触发目标仓库 CI。
- 目标仓库也可以是本地路径或 `file://`（此时不需要令牌），便于离线验证。

---

## 常见配置组合

**1. 最小可跑（只改一行）**

```dotenv
PROBE_HOST=probe.example.com
```

**2. 大陆机器 + 代理出网**

```dotenv
PROBE_HOST=probe.example.com
HTTP_PROXY=http://192.168.1.2:7890
HTTPS_PROXY=http://192.168.1.2:7890
NO_PROXY=localhost,127.0.0.1,::1,192.168.0.0/16,172.16.0.0/12,probe.example.com
no_proxy=localhost,127.0.0.1,::1,192.168.0.0/16,172.16.0.0/12,probe.example.com
```

**3. 先小规模验证（几十秒出结果）**

```dotenv
PROBE_HOST=probe.example.com
MAX_CANDIDATES=200
RUN_ON_START=true
```

**4. 测全部 CF HTTPS 端口**

```dotenv
PROBE_HOST=probe.example.com
PROBE_PORTS=443,2053,2083,2087,2096,8443
```

**5. 只订阅日本 / 新加坡（各 50 条），不要全量列表，频率提到每 2 小时**

```dotenv
PROBE_HOST=probe.example.com
OVERALL_TOPS=            # 不要全量列表
COUNTRY_FILTERS=true    # 打开国家列表
TOP_US=0
TOP_DE=0
TOP_NL=0
TOP_FR=0
TOP_JP=50
TOP_SG=50
CRON_SCHEDULE=0 */2 * * *
```

**6. 自动发布到自己的订阅仓库**

```dotenv
PROBE_HOST=probe.example.com
GIT_PUSH_ENABLED=true
GIT_REPO_URL=https://github.com/OWNER/REPO.git
GIT_TOKEN=<contents:write 令牌>
```

---

## 改完怎么确认

```bash
docker compose up -d --force-recreate     # 让新参数生效（不需要重建镜像）
docker compose logs --tail=30             # 看"生效配置"摘要
docker compose exec scanner /usr/local/bin/doctor.sh   # 完整自检
```

启动摘要会逐项回显：探测端点、端口、握手/校验参数、采样、数据文件、输出目录、代理
豁免、发布目标。改错或漏填时，进程会直接退出并在日志里说明原因。
