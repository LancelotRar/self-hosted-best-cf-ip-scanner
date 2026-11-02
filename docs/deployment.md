# 部署详解

[← 返回首页](../README.md)

本文覆盖：前置条件、获取配置、最少设置、启动与验证、目录与持久化、完整的
`compose.example.yaml` 说明，以及本地构建镜像。

## 前置条件

<table align="center">
<thead>
<tr>
<th align="center">需要</th>
<th align="center">用途</th>
<th align="center">是否必需</th>
</tr>
</thead>
<tbody>
<tr><td align="center">一个自己托管在 Cloudflare、且已开启代理（小黄云）的域名</td><td align="center"><code>PROBE_HOST</code>，边缘端点校验域名</td><td align="center"><strong>必需</strong></td></tr>
<tr><td align="center">Docker 24+（含 compose v2）与可出网的机器</td><td align="center">运行容器</td><td align="center"><strong>必需</strong></td></tr>
<tr><td align="center">一个 Git 仓库 + 具备 <code>contents:write</code> 的访问令牌</td><td align="center">自动发布产物</td><td align="center">可选</td></tr>
</tbody>
</table>

`PROBE_HOST` 不能省：它决定「哪些 IP 算合格的 Cloudflare 边缘」，选型理由见
[README 的工作原理](../README.md#为什么探测域名必须是自己的域名)。

## 1. 获取配置模板

```bash
mkdir best-cf-ip-scanner && cd best-cf-ip-scanner

curl -fsSLO https://raw.githubusercontent.com/LancelotRar/best-cf-ip-scanner-docker/main/compose.example.yaml
curl -fsSLO https://raw.githubusercontent.com/LancelotRar/best-cf-ip-scanner-docker/main/.env.example

cp compose.example.yaml compose.yaml
cp .env.example .env
```

用 `cp` 而不是 `mv`：模板留在原处，后续可与实际文件对比、或按新版本模板升级。

得到两个文件：

<table align="center">
<thead>
<tr>
<th align="center">文件</th>
<th align="center">作用</th>
</tr>
</thead>
<tbody>
<tr><td align="center"><code>compose.yaml</code></td><td align="center">容器编排：镜像、挂载、权限、健康检查</td></tr>
<tr><td align="center"><code>.env</code></td><td align="center">全部可调参数（由 <code>.env.example</code> 复制而来）</td></tr>
</tbody>
</table>

## 2. 配置 `.env`

最少只需一项：

```dotenv
# 必填：你自己的、已开启 Cloudflare 代理的域名
PROBE_HOST=probe.example.com
```

其余参数都有默认值：每 6 小时第 30 分扫描一轮、每个 /24 抽 1 个代表 IP、TCP 握手
3 次中成功 2 次即合格、端口 443、默认生成 `GLOBAL20/50/100/200/400` 五个全量列表；国家列表由 `COUNTRY_FILTERS`
开关控制（默认关闭）；默认不发布，只在本地产出。

- 需要调频率 / 端口 / 并发 / 订阅档位 / 发布：见 [配置手册](configuration.md)
- 机器需要经代理出网：见 [代理与直连](network.md)（注意 `NO_PROXY` 必须豁免
  `PROBE_HOST`，否则启动会被拒绝）

改完执行 `docker compose up -d --force-recreate` 即生效，不需要重建镜像。

## 3. 启动

```bash
docker compose up -d
docker compose logs -f
```

首次启动会做三件事：

- 创建并授权宿主目录 `./data`、`./output`、`./cache`（属主对齐到 `PUID:PGID`）；
- 把镜像内置的候选地址库与机房映射播种到 `./data`（已存在的文件不覆盖）；
- `RUN_ON_START=true` 时先跑一轮，再交给 cron 调度。

## 4. 验证部署

确认三件事：容器已启动、第一轮扫描已完成、产物已生成。

```bash
docker compose ps                 # 状态应为 Up (healthy)
docker compose logs --tail=30     # 应能看到「本轮完成」
ls output                         # 应看到 detail.csv 与 GLOBAL*.txt
```

一轮完整流程的日志形如：

```
best-cf-ip-scanner 生效配置
探测端点        : PROBE_HOST=...  PROBE_PATH=/cdn-cgi/trace
候选地址库：/data/ip-library.txt（4161 个网段 -> 15 个连续地址区间，...）共 4161 个候选 IP
TCP 握手测量：合格 2673，淘汰 1488（每候选 3 次，至少成功 2 次，超时 3.0s，耗时 78.3s）
边缘端点校验：合格 2328，淘汰 345（TCP 握手达标 2673/4161；耗时 35.9s）
本轮完成：5 个订阅列表 + 1 个明细表 -> /output  总耗时 123.2s
```

异常时见 [故障排查](troubleshooting.md)。

## 5. 目录与持久化

部署目录**不是 git 工作副本**：源码在项目仓库里，部署机只保留运行所需内容。

```
<部署目录>/
├── compose.yaml           # 编排文件（由模板复制而来）
├── compose.example.yaml   # 编排模板，用于对比改动 / 按新版模板升级
├── .env                   # 运行参数（只在这里改）
├── .env.example           # 参数模板，同上
├── data/                  # 候选地址库 + 机房映射（持久化，需备份）
├── output/                # 产物（可随时删除，下一轮重建）
└── cache/                 # 发布缓存（可随时删除）
```

升级用 `docker compose pull && docker compose up -d`；**不要**在部署目录 `git pull`。

<table align="center">
<thead>
<tr>
<th align="center">宿主机</th>
<th align="center">容器内</th>
<th align="center">内容</th>
<th align="center">说明</th>
</tr>
</thead>
<tbody>
<tr><td align="center"><code>./data</code></td><td align="center"><code>/data</code></td><td align="center"><code>ip-library.txt</code> + <code>locations.json</code></td><td align="center">首次启动写入内置默认值，之后可直接编辑</td></tr>
<tr><td align="center"><code>./output</code></td><td align="center"><code>/output</code></td><td align="center"><code>detail.csv</code> + 订阅列表</td><td align="center">每轮全量重写（镜像语义）</td></tr>
<tr><td align="center"><code>./cache/repo</code></td><td align="center"><code>/cache/repo</code></td><td align="center">目标仓库浅克隆</td><td align="center">删掉即可让下一轮重新克隆</td></tr>
</tbody>
</table>

三个目录都以 bind mount 挂载，产物与地址库直接在宿主机可见、可编辑。文件属主是
`PUID:PGID`（默认 `1000:1000`）；宿主机用户不是 1000 时，把 `.env` 的
`PUID` / `PGID` 改成 `id -u` / `id -g`。

## 6. compose.example.yaml 默认配置

```yaml
# best-cf-ip-scanner —— 运行配置（官方镜像）
#
#   1) 本文件复制为 compose.yaml；.env.example 复制为 .env
#   2) 在 .env 里填写 PROBE_HOST
#   3) docker compose up -d && docker compose logs -f
#
# 手动执行一轮：docker compose run --rm scan-once
#
# 宿主目录（首次启动自动创建并对齐属主）：
#   ./data    输入：候选地址库 + 机房映射（含内置默认值，可直接编辑）
#   ./output  产物：明细表 detail.csv + 订阅列表 GLOBAL{N}.txt / {国家代码}{N}.txt
#   ./cache   发布缓存：目标仓库的浅克隆（可随时删除）
#
# 本地构建镜像见 compose.build.yaml：
#   docker compose -f compose.yaml -f compose.build.yaml up -d --build
name: best-cf-ip-scanner

# 两个服务（常驻调度 / 一次性执行）共用同一份运行配置，避免参数漂移
x-scanner-common: &scanner-common
  # 官方镜像（多架构 amd64/arm64）。锁定版本可把 IMAGE_TAG 改成 sha-xxxxxxx 或 1.2.3
  image: ${IMAGE_NAME:-ghcr.io/lancelotrar/best-cf-ip-scanner-docker}:${IMAGE_TAG:-latest}
  # 全部运行参数来自 .env（改完 up -d --force-recreate 生效）
  env_file:
    - .env
  # 容器内路径固定；对应宿主目录见下方 volumes
  environment:
    OUTPUT_DIR: /output
    DATA_DIR: /data
    GIT_REPO_DIR: /cache/repo
  # 最小权限：只读根文件系统
  read_only: true
  tmpfs:
    - /tmp:size=64m
  # 入口以 root 只做「挂载目录 chown + 首启播种数据 + su-exec 降权」，
  # 因此只放这几步必需的五个能力；降权后业务进程不带任何 root 能力。
  cap_drop:
    - ALL
  cap_add:
    - CHOWN
    - DAC_OVERRIDE
    - FOWNER
    - SETUID
    - SETGID
  security_opt:
    - no-new-privileges:true
  volumes:
    # IP 库与 IATA 映射：首次启动自动写入内置默认值，之后直接编辑这两个文件维护
    # （改完下一轮扫描生效，无需重建镜像）
    - ./data:/data
    # 产物：明细表 + 订阅列表，直接出现在宿主目录里
    - ./output:/output
    # 发布缓存：目标仓库的浅克隆，删掉即可让下一轮重新克隆
    - ./cache:/cache

services:
  # 常驻服务：容器内按 CRON_SCHEDULE 调度
  scanner:
    <<: *scanner-common
    # 固定容器名：CI 冒烟与文档命令按此名引用；不需要可删掉这行，Compose 会自动命名
    container_name: ${CONTAINER_NAME:-best-cf-ip-scanner}
    # 单机常驻：随宿主机/守护进程重启自动恢复；每轮任务幂等
    restart: unless-stopped
    # 停止时给当前这一轮留出收尾时间（全量约 2 分钟），避免正在推送产物时被 SIGKILL。
    # 想立刻停可以 docker compose stop -t 5。
    stop_grace_period: 150s
    # 调度器是常驻进程；进程在 = 健康。业务失败只体现在日志与退出码里，
    # 不把"上一轮扫描失败"误报成容器故障。
    # start_period 放宽到 5 分钟：RUN_ON_START=true 时容器会先跑完整轮扫描
    # （全量约 2~5 分钟），期间 supercronic 还没接管，过早判死会误导运维。
    healthcheck:
      test: ["CMD", "pidof", "supercronic"]
      interval: 1m
      timeout: 5s
      retries: 3
      start_period: 5m
    # 日志落盘上限：长期运行不让 json-file 无限增长
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"

  # 一次性服务：手动补跑一轮，跑完即退出（用 run --rm 调用，不参与 up）
  #   docker compose run --rm scan-once
  # 与常驻服务共用锁：若定时任务正在跑，本次会提示并跳过，不会并发写产物。
  scan-once:
    <<: *scanner-common
    profiles: ["manual"]
    restart: "no"
    entrypoint: ["/usr/local/bin/scan-and-publish.sh"]
```

## 7. 本地构建镜像（可选）

```bash
docker compose -f compose.yaml -f compose.build.yaml up -d --build
```

构建产物直接打上 `compose.yaml` 里的镜像名，本地优先于拉取；构建期需要代理时把
`HTTP_PROXY` / `HTTPS_PROXY` / `NO_PROXY` 写进 `.env`。
