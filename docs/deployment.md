# 部署详解

[← 返回首页](../README.md) · [配置手册](configuration.md)

本文覆盖：前置条件、获取文件、部署参数、启动与验证、目录与持久化、完整的
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
<tr><td align="center">Docker 24+（含 compose v2）与可出网的机器</td><td align="center">运行容器</td><td align="center"><strong>必需</strong></td></tr>
<tr><td align="center">一个自己托管在 Cloudflare、且已开启代理（小黄云）的域名</td><td align="center">面板里的「探测域名」，边缘端点校验</td><td align="center"><strong>建议</strong></td></tr>
<tr><td align="center">一个 Git 仓库 + 具备 <code>contents:write</code> 的访问令牌</td><td align="center">自动发布产物</td><td align="center">可选</td></tr>
</tbody>
</table>

探测域名可以在首次启动后于面板里填写；默认 `cloudflare-ech.com` 也能直接跑通。
选型理由见 [README 的工作原理](../README.md#为什么探测域名必须是自己的域名)。

## 1. 获取文件

```bash
mkdir best-cf-ip-scanner && cd best-cf-ip-scanner

curl -fsSLO https://raw.githubusercontent.com/LancelotRar/self-hosted-best-cf-ip-scanner/main/compose.example.yaml
cp compose.example.yaml compose.yaml
```

只需要一个 `compose.yaml`。项目不提供任何应用配置文件，也不需要配置文件入口；
应用参数首次启动时由面板写入数据库，之后只在面板里编辑。

## 2. 部署参数

部署参数（运行身份、镜像、容器名、端口）直接写在 `compose.yaml`，面板不展示、
也不提供设置。默认值如下，按环境修改即可：

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
    environment:
      PUID: "1000"
      PGID: "1000"
```

- 宿主机用户不是 1000 时，把 `PUID` / `PGID` 改成 `id -u` / `id -g`。
- 面板默认只监听本机；远程访问用 `ssh -L 8080:127.0.0.1:8080 <user>@<host>`，
  或放在 TLS 反向代理后并把 `PANEL_TRUST_PROXY` 设为 `true`。
- 本版本起 scanner 与 panel 使用两个镜像；升级时请同步把 `panel.image` 改成
  `ghcr.io/lancelotrar/self-hosted-best-cf-ip-scanner-panel:latest`。
- 应用参数（探测域名、调度、发布等）见 [配置手册](configuration.md)。

## 3. 启动

```bash
docker compose up -d
docker compose logs -f
```

首次启动的顺序是：

1. **panel 先启动**：建库并把 schema 默认值写入数据库、把镜像内置的候选地址库与
   机房映射播种到 `ip-data` 卷、把卷内文件属主对齐到 `PUID:PGID`、生成
   `/scanner-config/runtime.json`；
2. **scanner 等 panel 健康后启动**：读取投影、渲染 crontab，`RUN_ON_START=true`
   时先跑一轮，再交给 cron 调度；
3. 浏览器打开 `http://<宿主IP>:8080`，首次会要求设置管理员密码。

首次启动直接使用数据库默认值，不从任何宿主目录或配置文件导入应用参数。

## 4. 验证部署

确认四件事：容器已启动、第一轮扫描已完成、产物已生成、面板可访问。

```bash
docker compose ps                 # scanner 与 panel 都应为 Up (healthy)
docker compose logs --tail=30     # 应能看到「本轮完成」
curl -fsS http://127.0.0.1:8080/healthz   # {"status":"ok",...}
```

产物在面板「信息总览 · 产物情况」里查看：应列出 `detail.csv` 与 `GLOBAL*.txt`。
宿主目录里不会有这些文件。

一轮完整流程的日志形如：

```
best-cf-ip-scanner 生效配置
探测端点        : PROBE_HOST=...  PROBE_PATH=/cdn-cgi/trace
候选地址库：/data/ip-library.txt（15 个网段 -> 14 个连续地址区间，...）共 5956 个候选 IP
TCP 握手测量：合格 2673，淘汰 1488（每候选 3 次，至少成功 2 次，超时 3.0s，耗时 78.3s）
边缘端点校验：合格 2328，淘汰 345（TCP 握手达标 2673/5956；耗时 35.9s）
本轮完成：5 个订阅列表 + 1 个明细表 -> /output  总耗时 123.2s
```

异常时见 [故障排查](troubleshooting.md)。

## 5. 目录与持久化

部署目录**不是 git 工作副本**：源码在项目仓库里，部署机只保留运行所需内容。

```
<部署目录>/
├── compose.yaml           # 编排文件（部署参数的唯一入口）
├── compose.example.yaml   # 编排模板，用于对比改动 / 按新版模板升级
└── panel-data/            # 面板数据库、密钥（需备份，可能含加密后的令牌）
```

扫描产物在**命名卷**里，宿主目录看不到；候选地址库、机房映射、应用参数与审计在
`panel-data/panel.db`（绑定挂载）。备份时必须同时保留 `panel-data/` 下的
`panel.db`、`settings.key` 与 `secret.key`，否则加密的令牌无法解密。
升级用 `docker compose pull && docker compose up -d`；
**不要**在部署目录 `git pull`。升级到包含会话 epoch 的版本后，旧登录 Cookie 会失效，
需要重新登录一次。

<table align="center">
<thead>
<tr>
<th align="center">卷</th>
<th align="center">容器内</th>
<th align="center">内容</th>
<th align="center">说明</th>
</tr>
</thead>
<tbody>
<tr><td align="center"><code>ip-data</code></td><td align="center"><code>/data</code></td><td align="center"><code>ip-library.txt</code> + <code>locations.json</code> + <code>runtime/runs.tsv</code></td><td align="center">数据库的投影；面板启动与保存时重写</td></tr>
<tr><td align="center"><code>scan-output</code></td><td align="center"><code>/output</code></td><td align="center"><code>detail.csv</code> + 订阅列表</td><td align="center">每轮全量重写，供发布与下载使用；面板同步元数据与有界预览</td></tr>
<tr><td align="center"><code>publish-cache</code></td><td align="center"><code>/cache</code></td><td align="center">目标仓库浅克隆</td><td align="center">删掉卷即可让下一轮重新克隆</td></tr>
<tr><td align="center"><code>scanner-config</code></td><td align="center"><code>/scanner-config</code></td><td align="center"><code>runtime.json</code></td><td align="center">应用参数投影；面板唯一写入，扫描器只读</td></tr>
</tbody>
</table>

四个位置都是**命名卷**：宿主机目录里看不到任何文件，地址库与产物只在面板里查看和编辑。
需要备份时用 `docker run --rm -v <项目>_ip-data:/src -v $PWD:/dst alpine tar czf /dst/ip-data.tgz -C /src .`。
卷内文件属主是 `PUID:PGID`（默认 `1000:1000`）；宿主机用户不是 1000 时，改
`compose.yaml` 里的 `PUID` / `PGID`。

## 6. compose.example.yaml 默认配置

```yaml
# best-cf-ip-scanner —— 运行配置（官方镜像）
#
#   1) 本文件复制为 compose.yaml
#   2) 需要改运行身份、端口或镜像版本时，直接编辑本文件（部署参数只在这里）
#   3) docker compose up -d && docker compose logs -f
#   4) 浏览器打开面板，在「参数」页填写探测域名等应用参数
#
# 数据卷（命名卷，宿主目录里看不到文件）：
#   ip-data        输入：候选地址库 + 机房映射（面板里编辑，数据库为唯一真源）
#   scan-output    产物：明细表 detail.csv + 订阅列表 GLOBAL{N}.txt / {国家代码}{N}.txt
#   publish-cache  发布缓存：目标仓库的浅克隆（可随时删除）
#   scanner-config 运行配置投影：面板写入，扫描器只读
name: best-cf-ip-scanner

x-scanner-common: &scanner-common
  image: ghcr.io/lancelotrar/self-hosted-best-cf-ip-scanner:latest
  environment:
    RUNTIME_CONFIG_PATH: /scanner-config/runtime.json
    PUID: "1000"
    PGID: "1000"
    OUTPUT_DIR: /output
    DATA_DIR: /data
    GIT_REPO_DIR: /cache/repo
  depends_on:
    panel:
      condition: service_healthy
  read_only: true
  tmpfs:
    - /tmp:size=64m
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
    - ip-data:/data
    - scan-output:/output
    - publish-cache:/cache
    - scanner-config:/scanner-config:ro

services:
  scanner:
    <<: *scanner-common
    container_name: best-cf-ip-scanner
    restart: unless-stopped
    stop_grace_period: 150s
    healthcheck:
      test: ["CMD", "pidof", "supercronic"]
      interval: 1m
      timeout: 5s
      retries: 3
      start_period: 5m
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"

  scan-once:
    <<: *scanner-common
    profiles: ["manual"]
    restart: "no"
    entrypoint: ["/usr/local/bin/scan-and-publish.sh"]

  panel:
    image: ghcr.io/lancelotrar/self-hosted-best-cf-ip-scanner-panel:latest
    container_name: best-cf-ip-scanner-panel
    entrypoint: ["/usr/local/bin/panel-entrypoint.sh"]
    ports:
      - "127.0.0.1:8080:8080"
    environment:
      CONFIG_DIR: /scanner-config
      DEFAULT_DATA_DIR: /opt/default-data
      PANEL_DATA_DIR: /panel-data
      PANEL_PORT: "8080"
      PUID: "1000"
      PGID: "1000"
      SCANNER_CONTAINER: best-cf-ip-scanner
      SCANNER_IMAGE: ghcr.io/lancelotrar/self-hosted-best-cf-ip-scanner:latest
      DATA_DIR: /data
      OUTPUT_DIR: /output
      CACHE_DIR: /cache
      PANEL_TRUST_PROXY: "false"
      PANEL_SESSION_DAYS: "7"
      HOME: /tmp
    volumes:
      - ip-data:/data
      - scan-output:/output:ro
      - publish-cache:/cache:ro
      - ./panel-data:/panel-data
      - scanner-config:/scanner-config
    read_only: true
    tmpfs:
      - /tmp:size=64m
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
    pids_limit: 256
    mem_limit: 256m
    restart: unless-stopped
    healthcheck:
      test:
        - CMD
        - python
        - -c
        - "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=3)"
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 20s
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"

volumes:
  ip-data:
  scan-output:
  publish-cache:
  scanner-config:
```

> [!NOTE]
> 以上是启动所需的关键片段；完整、可复制的版本以仓库根目录的
> [`compose.example.yaml`](../compose.example.yaml) 为准。
> 面板说明见 [运维面板](panel.md)。

### 6.1 容器控制（可选）

默认栈不挂载 `docker.sock`，面板的「立即执行 / 实时日志 / 启停扫描容器」不可用。
需要时启用 control profile，并把面板的控制地址指向 sidecar：

```bash
SCANNER_CONTROL_URL=http://scanner-control:8090 docker compose --profile control up -d
```

control profile 新增 `scanner-control` sidecar：只有它挂载 `docker.sock`，面板通过内部
`control` 网络调用固定端点（状态、日志、执行一轮、应用配置、启停），不再直接
持有 Engine API。可设置 `SCANNER_CONTROL_TOKEN` 让 panel 与 sidecar 共享请求口令。

`docker.sock` 等价于宿主机 root；只在可信网络、已启用 TLS 反向代理的环境中使用。

## 7. 本地构建镜像（可选）

标准 `compose.yaml` 只拉取官方镜像，不包含构建上下文；改过代码或需要离线构建时，
用两个 Dockerfile 分别构建，再启动 compose：

```bash
docker build -f scanner/Dockerfile -t ghcr.io/lancelotrar/self-hosted-best-cf-ip-scanner:latest .
docker build -f panel/Dockerfile -t ghcr.io/lancelotrar/self-hosted-best-cf-ip-scanner-panel:latest .
docker compose up -d
```

需要代理或镜像加速时通过构建参数传入：

```bash
docker build -f scanner/Dockerfile \
  --build-arg HTTP_PROXY=http://<代理>:7890 \
  --build-arg HTTPS_PROXY=http://<代理>:7890 \
  -t ghcr.io/lancelotrar/self-hosted-best-cf-ip-scanner:latest .

docker build -f panel/Dockerfile \
  --build-arg HTTP_PROXY=http://<代理>:7890 \
  --build-arg HTTPS_PROXY=http://<代理>:7890 \
  --build-arg APK_MIRROR=https://mirrors.aliyun.com/alpine \
  --build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
  --build-arg NPM_CONFIG_REGISTRY=https://registry.npmmirror.com \
  -t ghcr.io/lancelotrar/self-hosted-best-cf-ip-scanner-panel:latest .
```
