# 配置手册

[← 返回首页](../README.md) · [部署详解](deployment.md) · [运维面板](panel.md)

本项目把配置分成两层，互不重叠：

| 层 | 内容 | 在哪里改 | 真源 |
| --- | --- | --- | --- |
| **应用参数** | 探测域名、端口、并发、采样、调度、订阅档位、发布、代理 | 运维面板 | 面板数据库 |
| **部署参数** | 运行身份、镜像、容器名、面板端口/监听、构建代理与镜像源 | `compose.yaml` | Docker Compose |

应用参数**不需要、也不应该**手工编辑任何配置文件。面板保存后写入 SQLite，
并自动生成扫描器读取的运行期投影 `/scanner-config/runtime.json`；扫描器每轮
重新读取该投影，不直接访问数据库。项目不提供任何手工配置文件，也没有手工编辑入口。

- 首次启动把 `scanner/schema.py` 的默认值写入数据库；之后数据库是唯一真源。
- 空值 = 未设置 = 使用默认值，不是"关闭"。
- 部署参数（`PUID`、`PGID`、端口、镜像等）直接写在 `compose.yaml`，见 [部署详解](deployment.md)。

日常调参：`http://<宿主IP>:8080` → 「参数」。完整说明见 [运维面板](panel.md)。

---

## 生效方式

| 参数类别 | 保存后如何生效 |
| --- | --- |
| 绝大多数扫描/发布参数 | 下一轮任务自动读取新投影 |
| `CRON_SCHEDULE` | 面板立即调用 `apply-config.sh` 热重载 crontab |
| `TZ`、`RUN_ON_START` | 需要重启扫描容器；面板会提示并提供「保存并重启」 |

面板保存是一次事务：校验 → 写临时投影 → 数据库事务 → 替换投影 → 应用调度。
调度应用失败时会恢复数据库并重新生成投影，界面不会把「已写入」显示成「已生效」。

```bash
# 查看扫描器实际读到的生效值
docker compose exec -T scanner python /usr/local/bin/print-config.py --json

# 完整自检（只读，不写产物）
docker compose exec scanner /usr/local/bin/doctor.sh
```

---

## 应用参数总表

共 47 项，按面板分组列出。面板只展示面向业务的参数；文件名、探测路径、User-Agent、
提交作者、推送重试等底层策略由内置默认值决定，不在界面展示。

### 探测端点

<table align="center">
<thead>
<tr><th align="center">参数</th><th align="center">默认值</th><th align="center">说明</th></tr>
</thead>
<tbody>
<tr><td align="center"><code>PROBE_HOST</code></td><td align="center"><code>cloudflare-ech.com</code></td><td align="center">边缘端点校验域名；建议换成自己托管在 Cloudflare、已开启代理的域名</td></tr>
<tr><td align="center"><code>PROBE_PATH</code></td><td align="center"><code>/cdn-cgi/trace</code></td><td align="center">端点校验路径，由 CF 边缘直接应答，一般不修改（面板隐藏）</td></tr>
<tr><td align="center"><code>PROBE_USER_AGENT</code></td><td align="center">内置浏览器 UA</td><td align="center">端点校验请求的 User-Agent（面板隐藏）</td></tr>
<tr><td align="center"><code>LOCATIONS_FILE</code></td><td align="center"><code>locations.json</code></td><td align="center">机房映射投影文件名（面板隐藏；内容在面板「机房映射」维护）</td></tr>
<tr><td align="center"><code>SKIP_LOCATIONS</code></td><td align="center"><code>false</code></td><td align="center">调试用：跳过机房映射（面板隐藏）</td></tr>
</tbody>
</table>

### 探测参数

<table align="center">
<thead>
<tr><th align="center">参数</th><th align="center">默认值</th><th align="center">说明</th></tr>
</thead>
<tbody>
<tr><td align="center"><code>PROBE_PORTS</code></td><td align="center"><code>443</code></td><td align="center">候选端口集合，每个候选随机分配一个</td></tr>
<tr><td align="center"><code>PROBE_CONCURRENCY</code></td><td align="center"><code>200</code></td><td align="center">并发线程数（TCP 握手与端点校验共用）</td></tr>
<tr><td align="center"><code>TCP_ATTEMPTS</code></td><td align="center"><code>3</code></td><td align="center">每候选 TCP 握手次数</td></tr>
<tr><td align="center"><code>TCP_MIN_SUCCESS</code></td><td align="center"><code>2</code></td><td align="center">握手合格门槛（不得大于 <code>TCP_ATTEMPTS</code>）</td></tr>
<tr><td align="center"><code>TCP_TIMEOUT</code></td><td align="center"><code>3.0</code></td><td align="center">单次握手超时（秒）</td></tr>
<tr><td align="center"><code>TRACE_TIMEOUT</code></td><td align="center"><code>5</code></td><td align="center">单次端点校验超时（秒）</td></tr>
<tr><td align="center"><code>TRACE_ATTEMPTS</code></td><td align="center"><code>2</code></td><td align="center">端点校验最大尝试次数（含首次）</td></tr>
</tbody>
</table>

### 采样

<table align="center">
<thead>
<tr><th align="center">参数</th><th align="center">默认值</th><th align="center">说明</th></tr>
</thead>
<tbody>
<tr><td align="center"><code>SAMPLE_STRIDE</code></td><td align="center"><code>256</code></td><td align="center">每 N 个地址抽 1 个；256 = 每个 /24 一个</td></tr>
<tr><td align="center"><code>SAMPLE_SEED</code></td><td align="center"><code>42</code></td><td align="center">采样基础种子，按北京小时自动轮换</td></tr>
<tr><td align="center"><code>SEED_HOUR_FACTOR</code></td><td align="center"><code>1000000</code></td><td align="center">种子轮换的内部系数（面板隐藏，一般不改）</td></tr>
</tbody>
</table>

### 输入输出

<table align="center">
<thead>
<tr><th align="center">参数</th><th align="center">默认值</th><th align="center">说明</th></tr>
</thead>
<tbody>
<tr><td align="center"><code>LIBRARY_FILE</code></td><td align="center"><code>ip-library.txt</code></td><td align="center">地址库投影文件名（面板隐藏；内容在面板「自定义 IP 库」维护）</td></tr>
<tr><td align="center"><code>PINNED_FILE</code></td><td align="center"><code>ip-pinned.txt</code></td><td align="center">固定保留投影文件名（面板隐藏；内容在面板「固定保留」维护）</td></tr>
</tbody>
</table>

### 文件名调整

<table align="center">
<thead>
<tr><th align="center">参数</th><th align="center">默认值</th><th align="center">说明</th></tr>
</thead>
<tbody>
<tr><td align="center"><code>DETAIL_CSV_NAME</code></td><td align="center"><code>detail</code></td><td align="center">明细表文件名（不含扩展名）</td></tr>
<tr><td align="center"><code>PINNED_OUTPUT_NAME</code></td><td align="center"><code>PINNED</code></td><td align="center">固定保留列表文件名（不含扩展名）；单独成文件</td></tr>
<tr><td align="center"><code>LIST_FILENAMES</code></td><td align="center">空</td><td align="center">列表文件名映射，JSON 对象，键为默认名（如 <code>GLOBAL20</code>）；面板「产物定制」自动维护（面板隐藏）</td></tr>
</tbody>
</table>

### 订阅列表

<table align="center">
<thead>
<tr><th align="center">参数</th><th align="center">默认值</th><th align="center">说明</th></tr>
</thead>
<tbody>
<tr><td align="center"><code>OVERALL_ENABLED</code></td><td align="center"><code>true</code></td><td align="center">全量列表总开关；<code>false</code> 时不生成任何 GLOBAL 列表</td></tr>
<tr><td align="center"><code>OVERALL_TOPS</code></td><td align="center"><code>20,50,100,200,400</code></td><td align="center">全量列表条数（逗号分隔，任意正整数）→ 每项一个 <code>GLOBAL{N}.txt</code></td></tr>
<tr><td align="center"><code>COUNTRY_FILTERS</code></td><td align="center"><code>false</code></td><td align="center">国家列表总开关；<code>true</code> 才按各国数值生成</td></tr>
<tr><td align="center"><code>TOP_US</code> / <code>TOP_JP</code> / <code>TOP_SG</code> / <code>TOP_DE</code> / <code>TOP_NL</code> / <code>TOP_FR</code></td><td align="center"><code>100</code></td><td align="center">各国列表条数 → <code>{国家代码}{N}.txt</code>；仅开关为 <code>true</code> 时生效</td></tr>
</tbody>
</table>

### 定时计划

`CRON_SCHEDULE` / `RUN_ON_START` 在面板「参数 → 计划任务」；`TZ` 在「设置 → 常规」。

<table align="center">
<thead>
<tr><th align="center">参数</th><th align="center">默认值</th><th align="center">说明</th></tr>
</thead>
<tbody>
<tr><td align="center"><code>CRON_SCHEDULE</code></td><td align="center"><code>30 */6 * * *</code></td><td align="center">标准 cron（分 时 日 月 周），保存即热重载</td></tr>
<tr><td align="center"><code>RUN_ON_START</code></td><td align="center"><code>true</code></td><td align="center">容器启动后是否立即执行一轮；保存后需重启扫描容器</td></tr>
<tr><td align="center"><code>TZ</code></td><td align="center"><code>Asia/Shanghai</code></td><td align="center">调度与提交信息时区；产物中的扫描时间固定为北京时间；保存后需重启扫描容器</td></tr>
</tbody>
</table>

### 发布

<table align="center">
<thead>
<tr><th align="center">参数</th><th align="center">默认值</th><th align="center">说明</th></tr>
</thead>
<tbody>
<tr><td align="center"><code>GIT_PUSH_ENABLED</code></td><td align="center"><code>false</code></td><td align="center">是否需要把产物推到 Git 仓库</td></tr>
<tr><td align="center"><code>GIT_REPO_URL</code></td><td align="center">空</td><td align="center">目标仓库 HTTPS 地址</td></tr>
<tr><td align="center"><code>GIT_BRANCH</code></td><td align="center"><code>main</code></td><td align="center">目标分支</td></tr>
<tr><td align="center"><code>GIT_TOKEN</code></td><td align="center">空</td><td align="center"><code>contents:write</code> 权限令牌（HTTP(S) 远端必填，只写不读）</td></tr>
<tr><td align="center"><code>GIT_OUTPUT_SUBDIR</code></td><td align="center">空</td><td align="center">产物子目录；留空推送仓库根目录</td></tr>
<tr><td align="center"><code>PUSH_LISTS</code></td><td align="center">空</td><td align="center">只推送选中的全量/国家列表，JSON 数组；留空推送全部；面板「仓库设置 · 推送列表」维护（面板隐藏）</td></tr>
<tr><td align="center"><code>GIT_AUTHOR_NAME</code> / <code>GIT_AUTHOR_EMAIL</code></td><td align="center"><code>cf-ip-scanner-bot</code> / <code>…@users.noreply.github.com</code></td><td align="center">提交作者（面板隐藏）</td></tr>
<tr><td align="center"><code>GIT_RETRY_MAX</code> / <code>GIT_RETRY_BASE_DELAY</code></td><td align="center"><code>3</code> / <code>10</code></td><td align="center">推送失败重试次数与初始退避秒数（面板隐藏）</td></tr>
</tbody>
</table>

### 网络代理

<table align="center">
<thead>
<tr><th align="center">参数</th><th align="center">默认值</th><th align="center">说明</th></tr>
</thead>
<tbody>
<tr><td align="center"><code>HTTP_PROXY</code> / <code>HTTPS_PROXY</code></td><td align="center">空</td><td align="center">容器出网代理（应用参数；镜像构建代理见部署详解）</td></tr>
<tr><td align="center"><code>ALL_PROXY</code></td><td align="center">空</td><td align="center">通用代理；仅在需要时填写</td></tr>
<tr><td align="center"><code>NO_PROXY</code></td><td align="center">空</td><td align="center"><strong>必须豁免 <code>PROBE_HOST</code></strong>，否则启动被拒绝；保存时自动同步小写 <code>no_proxy</code></td></tr>
<tr><td align="center"><code>no_proxy</code></td><td align="center">空</td><td align="center">与 <code>NO_PROXY</code> 内容一致（面板隐藏，自动同步）</td></tr>
</tbody>
</table>

---

## 取值规则

<table align="center">
<thead>
<tr>
<th align="center">规则</th>
<th align="center">说明</th>
</tr>
</thead>
<tbody>
<tr><td align="center">留空</td><td align="center">视为未配置，使用 schema 默认值</td></tr>
<tr><td align="center">布尔</td><td align="center"><code>true</code> / <code>false</code>（也接受 yes/no/on/off/1/0）</td></tr>
<tr><td align="center">列表</td><td align="center">英文逗号分隔，不加空格、不加引号，如 <code>443,2053</code></td></tr>
<tr><td align="center">非法值</td><td align="center">面板保存返回 422 并指出字段；扫描器启动时再次校验，失败则不进入调度</td></tr>
</tbody>
</table>

三类"配错会静默出错"的情况由启动校验拦截，进程直接退出：

- `PROBE_HOST` 未配置；
- 配了出网代理，但 `NO_PROXY` / `no_proxy` 未豁免 `PROBE_HOST`；
- 数值型参数越界（如 `TCP_MIN_SUCCESS` 大于 `TCP_ATTEMPTS`、`PROBE_CONCURRENCY` 为 0）。

---

## 留空与特殊值

**通用规则：留空 = 使用默认值**（下表每项都给出了默认值），不是"关闭"。

少数参数的"空值"或特定值有专门语义：

<table align="center">
<thead>
<tr>
<th align="center">参数</th>
<th align="center">留空 / 特定值</th>
<th align="center">实际行为</th>
</tr>
</thead>
<tbody>
<tr><td align="center"><code>PROBE_HOST</code></td><td align="center">留空</td><td align="center">使用默认 <code>cloudflare-ech.com</code></td></tr>
<tr><td align="center"><code>OVERALL_ENABLED</code></td><td align="center"><code>false</code></td><td align="center">不生成任何全量列表，<code>OVERALL_TOPS</code> 被忽略</td></tr>
<tr><td align="center"><code>OVERALL_TOPS</code></td><td align="center">留空</td><td align="center">不生成全量列表</td></tr>
<tr><td align="center"><code>COUNTRY_FILTERS</code></td><td align="center"><code>false</code>（默认）</td><td align="center"><strong>不生成国家列表</strong>，所有 <code>TOP_&lt;国家代码&gt;</code> 数值被忽略</td></tr>
<tr><td align="center"><code>TOP_US</code> / <code>TOP_JP</code> / …</td><td align="center"><code>0</code> 或留空</td><td align="center">该国不生成（需开关为 <code>true</code>）</td></tr>
<tr><td align="center"><code>TRACE_ATTEMPTS</code></td><td align="center"><code>1</code></td><td align="center">不重试；<code>2</code> = 重试一次（默认）</td></tr>
<tr><td align="center"><code>TCP_MIN_SUCCESS</code></td><td align="center">等于 <code>TCP_ATTEMPTS</code></td><td align="center">要求零丢包才合格</td></tr>
<tr><td align="center"><code>GIT_PUSH_ENABLED</code></td><td align="center">留空</td><td align="center">默认为 <code>false</code>，只在本地产出</td></tr>
<tr><td align="center"><code>GIT_TOKEN</code></td><td align="center">留空</td><td align="center">只在 HTTP(S) 远端发布时报错；<code>file://</code> / 本地路径不需要</td></tr>
<tr><td align="center"><code>HTTP_PROXY</code> / <code>HTTPS_PROXY</code></td><td align="center">留空</td><td align="center">直连；配了其中之一就必须同时豁免 <code>PROBE_HOST</code></td></tr>
<tr><td align="center"><code>GIT_OUTPUT_SUBDIR</code></td><td align="center">留空</td><td align="center">推送到目标仓库根目录</td></tr>
<tr><td align="center"><code>PUSH_LISTS</code></td><td align="center">留空</td><td align="center">推送全部全量/国家列表</td></tr>
</tbody>
</table>

注意：数值型参数的 `0` 不是"关闭"的通用写法——`0` 会被校验拒绝（例如
`TCP_TIMEOUT=0`、`PROBE_CONCURRENCY=0`）。想缩小扫描范围，就在地址库里把那几行注释掉。

---

## 校验机制

配置错误分三类，处理时机与容器行为不同：

<table align="center">
<thead>
<tr>
<th align="center">类别</th>
<th align="center">例子</th>
<th align="center">发生时机</th>
<th align="center">表现</th>
</tr>
</thead>
<tbody>
<tr><td align="center">语法错误</td><td align="center"><code>PROBE_CONCURRENCY=abc</code>、<code>OVERALL_TOPS=abc</code>、<code>PROBE_PORTS=abc</code></td><td align="center">面板保存 / 进程读取配置时</td><td align="center">面板返回 422；扫描器打印 <code>[错误] 环境变量 X=... 非法：期望...</code> 并退出码 1</td></tr>
<tr><td align="center">语义错误</td><td align="center">缺 <code>PROBE_HOST</code>、<code>PROBE_HOST</code> 带协议/端口、<code>PROBE_PORTS</code> 为空、条数为负、<code>TCP_MIN_SUCCESS &gt; TCP_ATTEMPTS</code>、代理未豁免探测域名</td><td align="center">面板保存（干跑校验）/ 容器启动（<code>check-config.py</code>）</td><td align="center">面板拒绝保存；扫描器打印编号问题清单，退出码 1，<strong>容器不进入调度</strong></td></tr>
<tr><td align="center">运行期失败</td><td align="center">本轮 TCP 握手全灭、端点校验无合格候选、发布失败</td><td align="center">每轮任务</td><td align="center">该轮任务失败（日志说明原因），<strong>容器继续运行</strong>，下一轮照常</td></tr>
</tbody>
</table>

关键区别：

- **配置类错误在保存或启动阶段暴露**：面板会直接拒绝；若扫描器启动时发现投影非法，
  容器会反复重启，日志首屏就是原因。改好面板参数后保存即可，无需手工改文件。
- **运行期失败不杀容器**：调度器保持运行，失败信息在当轮日志里；网络抖动导致的失败
  通常下一轮自动恢复。
- 语义类错误还会在**每轮任务开始时再校验一次**（`run()` 内），避免运行期改动绕过启动检查。

启动期的输出形如：

```
[entrypoint] 配置不合法，容器不会进入调度：
  1. PROBE_HOST 只能填域名（不带协议/端口/路径），当前为 'https://example.com'
  2. 已配置出网代理，但 NO_PROXY 未豁免探测域名 probe.example.com：...
  参数说明：docs/configuration.md
```

---

## 关键参数详解

### `PROBE_HOST`（默认 `cloudflare-ech.com`）

边缘端点校验域名。工具会把该域名"钉"到候选 `IP:端口` 上请求一次
`/cdn-cgi/trace`，因此这个域名必须满足：

- 由 Cloudflare 边缘代理（小黄云开启），证书覆盖该域名；
- `PROBE_PATH` 能返回 `colo=`（机场码）字段；
- `PROBE_PORTS` 里启用的端口它都能服务；
- 默认 `cloudflare-ech.com` 已满足前三项；若需要更严格的筛选，建议换成
  **你自己 zone 的域名**。

换域名时务必同步把它加进「代理设置」的豁免清单。

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

### `OVERALL_ENABLED` / `OVERALL_TOPS` / `COUNTRY_FILTERS` / `TOP_US` …

订阅列表分两组，每组只回答两个问题：**要不要**、**要多少**。

**全量列表** —— 先看总开关，再看档位：

- `OVERALL_ENABLED=false` → 一个都不生成，档位被忽略。
- `OVERALL_TOPS=20,50,100,200,400`（默认）→ 生成 `GLOBAL20.txt` … `GLOBAL400.txt` 五个文件。
- `OVERALL_TOPS=100` → 只生成 `GLOBAL100.txt`。
- 数字就是文件里的条数，**填多少生成多少**，不限于示例里的档位。

**国家列表** —— 由总开关 + 各国变量共同决定：

- `COUNTRY_FILTERS=false`（默认）→ 一个都不生成，下面的数值全部忽略。
- `COUNTRY_FILTERS=true` → 按 `TOP_<国家代码>=N` 生成 `{国家代码}{N}.txt`：
  `TOP_US=100` → `US100.txt`，`TOP_JP=50` → `JP50.txt`；`0` 表示该国不生成。
- 国家代码来自机房映射（面板「机房映射」，投影为 `/data/locations.json`）；
  没有映射的机房不会进国家列表。

### `HTTP_PROXY` / `HTTPS_PROXY` / `NO_PROXY`

大陆机器通常需要代理访问 GitHub 与镜像仓库，但**探测必须直连**。要点：

- `HTTP_PROXY` / `HTTPS_PROXY` 只影响会读环境代理的客户端（端点校验走 curl_cffi 会读；
  TCP 握手用原始 socket，不读）。
- `NO_PROXY` / `no_proxy` 必须包含 `PROBE_HOST`（写后缀即可覆盖子域），否则端点校验会被
  代理接管——而且仍然返回 `200 + colo`，**不报错但结果全错**。面板保存时会自动同步小写。
- 如果宿主/网关开了 Clash TUN 或透明代理，环境变量不起作用，需要在代理软件里给
  Cloudflare 段设直连规则。用 `doctor.sh` 对比"默认路径 / 强制直连"可确认。

### `GIT_*`（产物发布）

默认关闭，只在本地产出。开启需要 `GIT_PUSH_ENABLED=true` + `GIT_REPO_URL` + `GIT_TOKEN`。

- 产物以镜像语义同步到 `GIT_OUTPUT_SUBDIR`（留空 = 仓库根目录）：目录内旧的 `*.txt` / `*.csv`
  会被本轮替换，把某个档位改成 0 后不会留下孤儿文件。
- 「推送列表」可只推送部分全量/国家列表；明细表与固定保留始终跟随推送。
- 令牌只经 `http.extraheader` 注入，不写入 `.git/config`，不出现在日志里。
- 提交信息带 `[skip ci]`，不触发目标仓库 CI。
- 目标仓库也可以是本地路径或 `file://`（此时不需要令牌），便于离线验证。

---

## 常见配置组合

以下都在面板「参数」页对应分组里设置，不是配置文件片段。

**1. 最小可跑（只改一项）**

- 探测端点 → 探测域名：`probe.example.com`
- 其余保持默认。

**2. 大陆机器 + 代理出网**

- 代理设置 → HTTP 代理 / HTTPS 代理：`http://192.168.1.2:7890`
- 代理豁免清单：`localhost,127.0.0.1,::1,192.168.0.0/16,172.16.0.0/12,probe.example.com`
- 保存时自动同步小写 `no_proxy`。

**3. 先小规模验证（几十秒出结果）**

扫描范围只由地址库决定：在「自定义 IP 库」里把暂时不想扫的网段行首加 `#` 注释掉，
只留下几行即可（标题右侧能看到参与探测的数量）。调度保持默认即可。

**4. 测全部 CF HTTPS 端口**

- 探测参数 → 候选端口集：`443,2053,2083,2087,2096,8443`

**5. 只订阅日本 / 新加坡（各 50 条），不要全量列表，频率提到每 2 小时**

- 订阅列表 → 生成全量列表：关闭
- 订阅列表 → 生成国家列表：开启；`TOP_JP=50`、`TOP_SG=50`，其余国家填 0
- 参数 → 计划任务 → 调度表达式：`0 */2 * * *`

**6. 自动发布到自己的订阅仓库**

- 仓库设置 → 启用 Git 推送：开启
- 目标仓库：`https://github.com/OWNER/REPO.git`
- 访问令牌：具备 `contents:write` 权限的令牌
- 推送列表：按需勾选，或保持"全部"

---

## 改完怎么确认

```bash
# 面板：参数页保存后，保存结果面板会显示生效方式与核对结果
docker compose exec -T scanner python /usr/local/bin/print-config.py --json  # 查看生效值
docker compose logs --tail=30             # 看"生效配置"摘要
docker compose exec scanner /usr/local/bin/doctor.sh   # 完整自检
```

仅 `TZ` / `RUN_ON_START` 需要重启扫描容器：

```bash
docker compose restart scanner
```

启动摘要会逐项回显：探测端点、端口、握手/校验参数、采样、数据文件、输出目录、代理
豁免、发布目标。改错或漏填时，面板会拒绝保存；扫描器启动时发现投影非法也会直接退出并
在日志里说明原因。
