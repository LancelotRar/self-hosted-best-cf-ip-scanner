<div align="center">

# Self-hosted Best CF IP Scanner

*以自建容器方式，从 Cloudflare IPv4 段中定时筛出可用作代理节点的优选 IP*

[![CI](https://github.com/LancelotRar/self-hosted-best-cf-ip-scanner/actions/workflows/ci.yml/badge.svg)](https://github.com/LancelotRar/self-hosted-best-cf-ip-scanner/actions/workflows/ci.yml)
[![Image](https://img.shields.io/badge/image-ghcr.io-2496ed?logo=docker&logoColor=white&style=flat-square)](https://github.com/LancelotRar/self-hosted-best-cf-ip-scanner/pkgs/container/self-hosted-best-cf-ip-scanner)
[![License](https://img.shields.io/badge/license-MIT-blue?style=flat-square)](LICENSE)

[文档导航](#文档导航) • [快速开始](#快速开始) • [工作原理](#工作原理)

</div>

先做 **TCP 握手测量**（初筛 + 排名基准），再做 **边缘端点校验**（终筛：判定是否真
Cloudflare 边缘、淘汰 EIV 受限子池、取回边缘机房代码），定时产出可订阅的优选 IP 列表。

> [!NOTE]
> 测量的是 TCP 握手往返时延与边缘落点，非速度测试。结果反映**部署这台机器的网络视角**
> ——同一份配置换到另一个网络，机房分布与延迟会完全不同，这是预期行为。

## 特性

- **拉取即用**：只需一个 `compose.yaml`，不需要克隆仓库、Python 环境、本地构建或任何配置文件。
- **面板优先**：同一个 compose 堆栈内的运维面板（`http://<宿主IP>:8080`）覆盖参数、调度、运行、日志、产物、IP 库与发布；CLI 只作应急路径。
- **应用参数全在面板**：探测域名、采样、订阅档位、发布与代理都在面板里编辑，首次启动把默认值写入数据库，并自动生成扫描器读取的运行期投影。
- **数据与产物集中在卷与面板数据库**：扫描产物在命名卷；候选地址库、机房映射、配置与审计在 `panel-data/panel.db`（绑定挂载，需要备份）。
- **失败不覆盖**：任一筛选阶段全灭时进程返回非零、不写新产物，目标仓库保留上一轮结果。
- **轻量且权限清晰**：Alpine + Python 3.13 多阶段构建；扫描业务进程非 root、只读根文件系统；面板默认只监听本机，并直接挂载 docker.sock 以提供完整容器控制（等价宿主机 root，仅限可信环境）。
- **日志面向排障**：启动打印生效配置，每轮打印阶段耗时与失败原因 top-5，另有 `doctor.sh` 一键自检。

## 文档导航

<table align="center">
<thead>
<tr>
<th align="center">分类</th>
<th align="center">文档</th>
<th align="center">说明</th>
</tr>
</thead>
<tbody>
<tr><th rowspan="4" align="center">部署与运行</th><td align="center"><a href="docs/deployment.md">部署详解</a></td><td align="center">前置条件、完整 compose 文件、目录与持久化、启动与验证、本地构建</td></tr>
<tr><td align="center"><a href="docs/panel.md">运维面板</a></td><td align="center">首次登录、五个页面、保存事务与核对结果、密码重置、反向代理</td></tr>
<tr><td align="center"><a href="docs/scheduling.md">定时设置</a></td><td align="center">cron 表达式写法、启动即执行、热重载、暂停与恢复</td></tr>
<tr><td align="center"><a href="docs/operations.md">日常运维</a></td><td align="center">面板日常操作、手动执行一轮、更新镜像、日志与清理</td></tr>
<tr><th rowspan="4" align="center">配置与数据</th><td align="center"><a href="docs/configuration.md">配置手册</a></td><td align="center">应用参数总表、默认值与影响、常见组合；部署参数见部署详解</td></tr>
<tr><td align="center"><a href="docs/ip-library.md">候选地址库</a></td><td align="center">条目格式、用注释排除网段、改动如何生效与验证</td></tr>
<tr><td align="center"><a href="docs/network.md">代理与直连</a></td><td align="center">出网代理与探测直连为何必须分开、<code>NO_PROXY</code> 机制、TUN 场景</td></tr>
<tr><td align="center"><a href="docs/publishing.md">自动发布</a></td><td align="center">推送到 Git 仓库：开关、令牌、镜像语义与重试</td></tr>
<tr><th rowspan="2" align="center">排障</th><td align="center"><a href="docs/troubleshooting.md">故障排查</a></td><td align="center">日志位置、<code>doctor.sh</code> 自检项、常见问题对照表</td></tr>
<tr><td align="center"><a href="docs/testing.md">测试与门禁</a></td><td align="center">单元/API/脚本/前端/E2E 分层、CI 门禁、人工上线清单</td></tr>
</tbody>
</table>

## 快速开始

### 1. 获取编排文件

```bash
mkdir best-cf-ip-scanner && cd best-cf-ip-scanner

curl -fsSLO https://raw.githubusercontent.com/LancelotRar/self-hosted-best-cf-ip-scanner/main/compose.example.yaml
cp compose.example.yaml compose.yaml
```

只需要一个 `compose.yaml`。项目不提供任何应用配置文件；部署参数（运行身份、镜像、
容器名、端口）直接写在 `compose.yaml` 里，应用参数首次启动后进面板填写。

### 2. 部署与应用参数

部署参数默认值如下，按环境修改 `compose.yaml` 即可：

```yaml
services:
  scanner:
    image: ghcr.io/lancelotrar/self-hosted-best-cf-ip-scanner:latest
    container_name: best-cf-ip-scanner
    environment:
      PUID: "1000"
      PGID: "1000"

  panel:
    image: ghcr.io/lancelotrar/self-hosted-best-cf-ip-scanner-panel:latest
    container_name: best-cf-ip-scanner-panel
    ports:
      - "127.0.0.1:8080:8080"
```

面板默认只监听本机。远程访问用 SSH 隧道：

```bash
ssh -L 8080:127.0.0.1:8080 <user>@<host>
# 然后在本机打开 http://127.0.0.1:8080
```

或放在 TLS 反向代理后，并把 `PANEL_TRUST_PROXY` 设为 `true`。如果要在首次设置前
开放访问，请同时设置 `PANEL_SETUP_TOKEN`，首次设置页会要求输入同一个值。

scanner 与 panel 使用两个独立镜像，compose 会分别拉取；不要把它们改成同一个镜像名。

探测域名、调度、采样、订阅档位、发布与代理等**应用参数全部在面板里填写**。
首次启动后打开 `http://<宿主IP>:8080`，在「参数」页按需修改并保存。

> 默认 `PROBE_HOST=cloudflare-ech.com` 可直接跑通；想更严格地筛选，建议换成
> 你自己托管在 Cloudflare、且已开启代理的域名。

> [!IMPORTANT]
> 应用参数只存在数据库里，不存在任何配置文件入口。配置有误时扫描器**不会进入调度**，
> 启动阶段就会打印问题清单并退出。详细规则见
> [配置手册的「留空与特殊值 / 校验机制」](docs/configuration.md)。

### 3. 启动并验证

- 单次手动运行

```bash
docker compose run --rm scan-once
```

它复用同一份镜像、配置与挂载，以非 root 身份执行，跑完即退出；如果定时任务正在跑，
本轮会提示「已有一轮扫描在运行」并跳过，不会并发写产物。临时改参数也可以直接透传：

```bash
docker compose run --rm -e SAMPLE_STRIDE=512 scan-once
```

- 长期定时运行

```bash
docker compose up -d
docker compose logs -f
```

```bash
docker compose ps                 # scanner 与 panel 均应为 Up (healthy)
docker compose logs --tail=30     # 应能看到「本轮完成」
curl -fsS http://127.0.0.1:8080/healthz   # 面板健康检查
```

产物在面板「信息总览 · 产物情况」里查看；宿主目录里不会出现这些文件。

一轮完整的日志形如：

```
best-cf-ip-scanner 生效配置
探测端点        : PROBE_HOST=...  PROBE_PATH=/cdn-cgi/trace
候选地址库：/data/ip-library.txt（15 个网段 -> 14 个连续地址区间，...）共 5956 个候选 IP
TCP 握手测量：合格 2673，淘汰 1488（每候选 3 次，至少成功 2 次，超时 3.0s，耗时 78.3s）
边缘端点校验：合格 2328，淘汰 345（TCP 握手达标 2673/5956；耗时 35.9s）
本轮完成：5 个订阅列表 + 1 个明细表 -> /output  总耗时 123.2s
```

### 4. 打开运维面板

浏览器访问 `http://<宿主IP>:8080`，首次打开会要求设置管理员密码（至少 8 位）。
面板是日常运维的主入口，五个页面覆盖全部常规操作：

<table align="center">
<thead>
<tr><th align="center">页面</th><th align="center">能做什么</th></tr>
</thead>
<tbody>
<tr><td align="center">总览</td><td align="center">扫描器状态、上次结果、下次执行时间、生效配置摘要、产物列表、近期扫描</td></tr>
<tr><td align="center">参数</td><td align="center">七个子标签：扫描参数 / 计划任务 / 自定义 IP 库 / 机房映射 / 产物定制 / 仓库设置 / 代理设置；分组表单、保存前校验、差异预览、版本历史与回滚</td></tr>
<tr><td align="center">运行</td><td align="center">立即执行一轮、实时输出、历史轮次与扫描/发布退出码</td></tr>
<tr><td align="center">日志</td><td align="center">实时日志（SSE）、关键字过滤、暂停、下载</td></tr>
<tr><td align="center">设置</td><td align="center">时区、外观、改密码、审计日志、扫描容器启停、版本信息</td></tr>
</tbody>
</table>

> [!NOTE]
> 面板保存写入数据库并重新生成扫描器读取的投影，不需要手工编辑任何配置文件。
> 只有 `TZ` / `RUN_ON_START` 需要重启扫描容器（面板会提示并提供「重启扫描容器」）。
> 详见 [运维面板](docs/panel.md)。

> [!IMPORTANT]
> 面板直接挂载 `docker.sock`，因此「立即执行 / 实时日志 / 启停扫描容器 / 生效核对」
> 默认全部可用。`docker.sock` 等价于宿主机 root 权限，只应在可信网络、已启用 TLS
> 反向代理、已设置强管理员密码的环境中使用。

### 5. 产物

每轮生成下面这些产物，全部在面板「信息总览 · 产物情况」里查看（预览明细表或订阅列表）；
它们同时留在容器卷里，供「发布到 Git 仓库」使用，宿主目录里不会出现这些文件：

> 「固定保留」列表不参与扫描，会**单独生成一个产物文件**（默认 `PINNED.txt`，文件名可在
> 「扫描参数 · 输入输出」里改），不写入 `GLOBAL{N}.txt` 或国家列表。

<table align="center">
<thead>
<tr>
<th align="center">文件</th>
<th align="center">内容</th>
</tr>
</thead>
<tbody>
<tr><td align="center"><code>detail.csv</code></td><td align="center">明细表：全部合格候选及测量指标</td></tr>
<tr><td align="center"><code>GLOBAL{N}.txt</code></td><td align="center">订阅列表：全量相对排名前 N（默认 20 / 50 / 100 / 200 / 400）</td></tr>
<tr><td align="center"><code>{国家代码}{N}.txt</code></td><td align="center">订阅列表：某国家内排名前 N（默认 US / JP / SG / DE / NL / FR）</td></tr>
<tr><td align="center"><code>PINNED.txt</code></td><td align="center">固定保留：不参与扫描、原样带入的条目（文件名由 <code>PINNED_OUTPUT_NAME</code> 决定）</td></tr>
</tbody>
</table>

订阅列表可直接作为订阅链接内容：

```
# 20 条 | 按 TCP 丢包率→平均延迟排序 | 扫描时间 2026-11-01 19:27
172.64.156.4:443#SG 🇸🇬
172.64.158.20:443#SG 🇸🇬
```

> [!TIP]
> 首次部署想快速验证环境是否可用：在面板「参数调整 · 自定义 IP 库」里把不想扫的网段
> 行首加 `#` 注释掉，只留几个 /24，一轮只需几十秒；确认无误后再把注释解开。
> 扫描的 IP 范围完全由这份地址库决定，没有额外的候选量上限。

详细部署说明（前置条件、完整的 compose 模板、目录与持久化、本地构建）见
[部署详解](docs/deployment.md)。

## 工作原理

- **解析地址库**：采样库每行是网段或单个 IP；带端口的条目属于「固定保留」，
  不进采样池，也不参与探测。
- **合并 + 网格采样**：重叠与相邻网段合并为连续区间，注释掉的网段再从区间里扣掉（支持只排除某个大段的子集）；
  然后按地址网格每 `SAMPLE_STRIDE` 个地址抽 1 个代表 IP（取 256 即每个 /24 抽一个）。采样种子按北京小时轮换：
  同一小时可复现，跨小时逐步覆盖不同代表与端口组合。
- **TCP 握手测量（初筛）**：每个候选做 `TCP_ATTEMPTS` 次握手计时，统计成功次数、
  丢包率、最小/平均/最大往返时延；成功次数低于 `TCP_MIN_SUCCESS` 淘汰。选它作基准，
  是因为这些 IP 最终当代理节点用，代理客户端展示的「TCP 延迟」就是该口径。
- **边缘端点校验（终筛）**：达标者经 curl `RESOLVE` 把 `PROBE_HOST` 钉到候选
  `IP:端口`——SNI 与证书校验保持有效，但 TCP/TLS 实际直连候选地址——请求
  `PROBE_PATH`。**通过条件：HTTP 200 且响应体含合法 `colo`**。
- **产出**：生成明细表与订阅列表，按「丢包率 → 平均延迟 → IP 数值」相对排名取前 N，
  不设绝对延迟阈值。
- **发布（可选）**：浅克隆目标仓库 → 覆盖产物目录 → 有变化则提交推送。

### 探测域名的默认值与选择

`PROBE_HOST` 默认 `cloudflare-ech.com`，可直接使用。若需要更严格的 EIV 受限子池淘汰，
建议换成满足以下条件的域名：由 CF 边缘代理且证书覆盖、`PROBE_PATH` 返回有效 `colo`、
`PROBE_PORTS` 中的端口都能服务，**且是你自己托管在 Cloudflare 上的域名**。

- 用 **CF 自有域名**（`speed.cloudflare.com` 等）时，EIV 受限子池（专属/静态/BYOIP
  地址）同样返回 `colo`，被误判为合格；但它们只在所属账号的 zone 上可用，当代理节点
  不可用。这类 IP 往往物理最近，「按延迟排名」会优先选中它们。
- 用 **自己 zone 的域名**时，受限子池直接返回 `403 / error 1034`，天然淘汰，返回的
  `colo` 就是代理实际落地的机房。

`PROBE_PATH` 由 CF 边缘直接应答、不经过源站，所以该域名只需保持代理（小黄云）开启，
不要求源站存活。
