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

- **拉取即用**：只需 `compose.yaml` 与 `.env` 两个文件，不需要克隆仓库、Python 环境或本地构建。
- **参数全在 `.env`**：调度、探测、采样、订阅规格、发布目标都可调，改完重建容器即生效。
- **数据与产物在宿主目录**：`./data` 里的候选地址库可直接编辑，`./output` 里直接看到产物。
- **失败不覆盖**：任一筛选阶段全灭时进程返回非零、不写新产物，目标仓库保留上一轮结果。
- **轻量且最小权限**：Alpine + Python 3.13 多阶段构建，约 120MB；业务进程非 root、只读根文件系统。
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
<tr><th rowspan="3" align="center">部署与运行</th><td align="center"><a href="docs/deployment.md">部署详解</a></td><td align="center">前置条件、完整 compose 文件、目录与持久化、启动与验证、本地构建</td></tr>
<tr><td align="center"><a href="docs/scheduling.md">定时设置</a></td><td align="center">cron 表达式写法、启动即执行、暂停与恢复</td></tr>
<tr><td align="center"><a href="docs/operations.md">日常运维</a></td><td align="center">手动执行一轮、应用配置、更新镜像、日志与清理</td></tr>
<tr><th rowspan="4" align="center">配置与数据</th><td align="center"><a href="docs/configuration.md">配置手册</a></td><td align="center">完整 <code>.env</code> 模板、每个参数的默认值与影响、常见组合示例</td></tr>
<tr><td align="center"><a href="docs/ip-library.md">候选地址库</a></td><td align="center">条目格式、用注释排除网段、改动如何生效与验证</td></tr>
<tr><td align="center"><a href="docs/network.md">代理与直连</a></td><td align="center">出网代理与探测直连为何必须分开、<code>NO_PROXY</code> 机制、TUN 场景</td></tr>
<tr><td align="center"><a href="docs/publishing.md">自动发布</a></td><td align="center">推送到 Git 仓库：开关、令牌、镜像语义与重试</td></tr>
<tr><th align="center">排障</th><td align="center"><a href="docs/troubleshooting.md">故障排查</a></td><td align="center">日志位置、<code>doctor.sh</code> 自检项、常见问题对照表</td></tr>
</tbody>
</table>

## 快速开始

### 1. 获取配置模板

```bash
mkdir best-cf-ip-scanner && cd best-cf-ip-scanner

curl -fsSLO https://raw.githubusercontent.com/LancelotRar/self-hosted-best-cf-ip-scanner/main/compose.example.yaml
curl -fsSLO https://raw.githubusercontent.com/LancelotRar/self-hosted-best-cf-ip-scanner/main/.env.example

cp compose.example.yaml compose.yaml   # 容器编排
cp .env.example .env                   # 环境变量
```

模板文件保留在原处，便于日后对比改动或按新版本模板升级。

### 2. 最小设置

`.env` 中填写以下一项即可运行：

```dotenv
# 必填：你自己的、已开启 Cloudflare 代理的域名
PROBE_HOST=probe.example.com
```

其余参数保持默认：每 6 小时第 30 分扫描一轮、每个 /24 抽 1 个代表 IP、TCP 握手
3 次中成功 2 次即合格、端口 443、默认生成 `GLOBAL20/50/100/200/400` 五个全量列表，国家列表默认关闭；只在本地产出。

> [!IMPORTANT]
> 配置有误时容器**不会进入调度**：启动阶段就会打印问题清单并退出。详细规则见
> [配置手册的「留空与特殊值 / 校验机制」](docs/configuration.md)。

### 3. 启动并验证

- 单次手动运行

```bash
docker compose run --rm scan-once
```

它复用同一份镜像、配置与挂载，以非 root 身份执行，跑完即退出；如果定时任务正在跑，
本轮会提示「已有一轮扫描在运行」并跳过，不会并发写产物。临时改参数也可以直接透传：

```bash
docker compose run --rm -e MAX_CANDIDATES=200 scan-once
```

- 长期定时运行

```bash
docker compose up -d
docker compose logs -f
```

```bash
docker compose ps                 # 状态应为 Up (healthy)
docker compose logs --tail=30     # 应能看到「本轮完成」
ls output                         # 应看到 detail.csv 与 GLOBAL*.txt
```

一轮完整的日志形如：

```
best-cf-ip-scanner 生效配置
探测端点        : PROBE_HOST=...  PROBE_PATH=/cdn-cgi/trace
候选地址库：/data/ip-library.txt（4161 个网段 -> 15 个连续地址区间，...）共 4161 个候选 IP
TCP 握手测量：合格 2673，淘汰 1488（每候选 3 次，至少成功 2 次，超时 3.0s，耗时 78.3s）
边缘端点校验：合格 2328，淘汰 345（TCP 握手达标 2673/4161；耗时 35.9s）
本轮完成：5 个订阅列表 + 1 个明细表 -> /output  总耗时 123.2s
```

### 4. 产物

每轮在 `./output/` 下生成：

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
</tbody>
</table>

订阅列表可直接作为订阅链接内容：

```
# 20 条 | 按 TCP 丢包率→平均延迟排序 | 扫描时间 2026-11-01 19:27
172.64.156.4:443#SG 🇸🇬
172.64.158.20:443#SG 🇸🇬
```

> [!TIP]
> 首次部署想快速验证环境是否可用，可以在 `.env` 里设 `MAX_CANDIDATES=200`，
> 一轮只需几十秒；确认无误后改回 `0`（不限）即可。

详细部署说明（前置条件、完整的 compose 模板、目录与持久化、本地构建）见
[部署详解](docs/deployment.md)。

## 工作原理

- **解析地址库**：每行支持网段 / 单个 IP / `IP:端口`；带端口的条目原样保留，
  不参与采样、端口不被替换。
- **合并 + 网格采样**：重叠与相邻网段合并为连续区间；按地址网格每 `SAMPLE_STRIDE`
  个地址抽 1 个代表 IP（取 256 即每个 /24 抽一个）。采样种子按北京小时轮换：
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

### 为什么探测域名必须是自己的域名

`PROBE_HOST` 没有默认值，必须提供一个满足以下条件的域名：由 CF 边缘代理且证书覆盖、
`PROBE_PATH` 返回有效 `colo`、`PROBE_PORTS` 中的端口都能服务，**且是你自己托管在
Cloudflare 上的域名**。

- 用 **CF 自有域名**（`speed.cloudflare.com` 等）时，EIV 受限子池（专属/静态/BYOIP
  地址）同样返回 `colo`，被误判为合格；但它们只在所属账号的 zone 上可用，当代理节点
  不可用。这类 IP 往往物理最近，「按延迟排名」会优先选中它们。
- 用 **自己 zone 的域名**时，受限子池直接返回 `403 / error 1034`，天然淘汰，返回的
  `colo` 就是代理实际落地的机房。

`PROBE_PATH` 由 CF 边缘直接应答、不经过源站，所以该域名只需保持代理（小黄云）开启，
不要求源站存活。
