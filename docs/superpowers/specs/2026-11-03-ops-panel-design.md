# 项目专属运维面板设计

- 日期：2026-11-03
- 状态：已定稿，待开发（第三版：`.env` 单源 + 标签页 UI + 保存事务 + 测试门禁）
- 范围：`self-hosted-best-cf-ip-scanner` 专属运维面板，不是通用 Docker 管理平台

**变更记录**

| 版本 | 变更 |
| --- | --- |
| v1 | 初始设计：sidecar 面板 + docker.sock + 运行时覆盖层 |
| v2 | 改为 `.env` 单源；扫描器每轮读取；删除覆盖层 |
| v3 | 顶部标签页 UI、保存事务与生效核对、测试与上线门禁、MCP/Figma 工具链 |
| v3 定稿 | 2026-11-03，待开发 |

## 1. 背景与目标

当前所有参数只能通过 `.env` 配置，改完必须 `docker compose up -d --force-recreate`
重建容器；排障依赖 `docker compose logs`；产物和 IP 库需要登录宿主机查看与编辑。

目标：在**同一个 compose 堆栈、一次 `docker compose up -d`** 内运行两个容器
（`scanner` + `panel`），通过局域网 `http://<宿主IP>:8080` 完成本项目的日常运维：

- 调整扫描参数并立即/下一轮生效，不重建容器；
- 面板保存与手工编辑 `.env` **完全同源、效果一致**；
- 管理调度、手动执行、实时查看运行输出；
- 查看实时/历史日志、产物、IP 库；
- 查看发布状态与配置变更历史，可回滚。

成功标准：使用者不需要 SSH 到宿主机、不需要改 compose、不需要重建容器，就能完成
上述操作；面板重启或升级不影响正在运行的扫描，扫描容器重启也不影响面板。

**产品定位：面板是默认、首选的运维入口。** CLI、`docker compose run` 与手工编辑
`.env` 保留为备用/应急路径；README、快速开始、日常运维与排障文档都以面板为主路径。
面板需要覆盖全部扫描行为参数、调度、运行、日志、产物、IP 库与发布，不能出现
“必须先上命令行才能完成”的常规操作。

## 2. 范围

### 2.1 做

1. 总览：扫描容器状态/健康、上次结果、下次执行时间、生效配置摘要、最近轮次。
2. 参数：分组表单，类型化控件，默认值/来源显示，保存前校验，配置版本与回滚。
3. 调度：cron 编辑、未来 5 次执行时间预览、热重载、`RUN_ON_START` 管理。
4. 运行：手动执行一轮、实时输出、锁状态、历史轮次与结果。
5. 日志：本项目扫描容器的实时日志（SSE）、搜索、暂停、下载。
6. 产物：`output/` 列表、TXT/CSV 预览、下载、复制订阅内容。
7. IP 库：在线编辑 `ip-library.txt`，保存前解析校验、自动备份。
8. 发布：Git 推送参数、最近一次推送结果、令牌掩码显示。
9. 系统：管理员密码、配置历史/回滚、扫描容器重启与启停、审计日志、版本信息。

### 2.2 不做

- 通用容器/镜像/网络/卷管理；
- 任意文件浏览、任意命令执行、Web 终端；
- 多主机、多用户/RBAC、Swarm/Kubernetes；
- compose 栈编辑、镜像构建；
- `IMAGE_NAME` / `IMAGE_TAG` / `CONTAINER_NAME` / `PANEL_*` 等需要重新
  `docker compose up` 或会改变面板自身拓扑的项：页面只读展示并给命令指引。
- `PUID` / `PGID` / `TZ` / `RUN_ON_START`：面板可编辑，标注「需重启扫描容器」，
  并提供「保存并重启」；这是为了让面板能覆盖全部扫描行为，命令行只作备用。

### 2.3 反目标

- 因为权限预设而砍掉功能：本项目不追求最小权限，优先功能完整与稳定。
- 让用户部署两次或维护第二套 compose：面板必须是同一堆栈内的服务。
- 把面板做成通用平台：所有接口只围绕本项目的容器、目录与参数。
- 制造第二份配置：不再引入 `runtime.env` 之类的覆盖层。

## 3. 约束

- 单 compose 堆栈、**单镜像**：`scanner` 与 `panel` 使用同一个
  `${IMAGE_NAME}:${IMAGE_TAG}`，panel 通过 `entrypoint` 覆盖启动不同进程。
- 面板是独立容器，通过挂载的 `/var/run/docker.sock` 调用 Engine API；所有 Docker 调用
  在服务端限定到本项目扫描容器，前端不能传容器 ID/文件路径。
- 共享卷：`./data:/data`、`./output:/output`、`./cache:/cache`；新增
  `./panel-data:/panel-data`；新增项目目录挂载：
  - `scanner`: `./:/project:ro`（读取 `.env`）
  - `panel`: `./:/project`（读写 `.env`）
- 兼容 Windows（Docker Desktop）与 Linux：不依赖 compose CLI、不要求宿主/容器路径一致。
- 根文件系统只读，`/tmp` 为 tmpfs；面板所有持久化写入挂载目录。
- 面板容器以 root 运行：需要访问 docker.sock，并把写入 `.env` 的属主对齐到宿主机
  原文件属主。功能与跨平台稳定性优先。
- 局域网 HTTP 访问，无内置 TLS；默认强制登录，首次启动设置管理员密码。

## 4. 方案对比

### 方案 1（选中）：独立 panel 服务 + `.env` 单源 + Docker Socket

- 两个容器同一 compose 项目，面板生命周期独立。
- `.env` 仍是唯一配置源；扫描器每轮重新读取，面板直接原子改写 `.env`，
  手工编辑与面板保存效果一致。
- 通过 Engine API 只操作本项目容器：状态、日志、exec、重启/启停。
- 与 Dockge / Dozzle / Portainer 的成熟形态同构，但接口项目专属。

### 方案 2：面板进程塞进扫描容器

- 少一个容器，但扫描容器重启时面板一起断；要完整控制仍需 socket；不满足稳定性。

### 方案 3：覆盖层（`/data/runtime/scanner.env`）

- 能热生效且实现简单，但产生第二份配置：`.env` 与覆盖层谁生效需要解释，
  改 `.env` 不再等于改面板，长期排障成本高。已弃用。

### 方案 4：Dockge 式 compose 全栈管理

- 直接改 `.env` 并 `docker compose up -d`，最“原生”。
- 需要宿主/容器路径完全一致，Windows + Docker Desktop 下易错；每次保存重建容器，
  打断扫描；实现面大。不采用。

## 5. 架构

```
┌─────────────────────────── compose project: best-cf-ip-scanner ───────────────────────────┐
│                                                                                           │
│  ┌────────────────────┐         docker.sock          ┌────────────────────────────────┐  │
│  │ panel              │ ───────────────────────────▶ │ Docker Engine                  │  │
│  │ FastAPI + Vue SPA  │                              └───────────────┬────────────────┘  │
│  │ SQLite             │                                              │ status/logs/exec  │
│  └───┬────────┬───────┘                                              ▼                   │
│      │        │                                     ┌────────────────────────────────┐  │
│      │        │  /data  /output  /cache             │ scanner                        │  │
│      │        └────────────────────────────────────▶│ supercronic + scan job         │  │
│      │                                              └───────┬────────────────────────┘  │
│      │                                                      │ reads /project/.env       │
│      │              /project/.env ◀─────────────────────────┘  each round               │
│      │                    ▲                                                               │
│      └── /panel-data ─────┘  panel writes .env atomically                                 │
│                                                                                           │
│  LAN :8080 ──▶ panel                                                                      │
└───────────────────────────────────────────────────────────────────────────────────────────┘
```

### 5.1 容器与镜像

- 同一镜像内包含 scanner 与 panel 两套运行所需内容；panel 额外依赖
  FastAPI、uvicorn、docker SDK、静态前端资源。用户只拉取一个镜像。
- `scanner`：入口与调度模型不变；增量修改 `scan-and-publish.sh`、`publish.sh`、
  `entrypoint.sh`，用于读取 `.env`、产出轮次记录与分阶段退出码。
- `panel`：`entrypoint: /usr/local/bin/panel-entrypoint.sh`，启动 uvicorn。
- `panel` 服务增加 `ports: ${PANEL_BIND:-0.0.0.0}:${PANEL_PORT:-8080}:8080`、
  `docker.sock`、共享目录、项目目录与 `panel-data` 挂载、健康检查 `/healthz`、
  `restart: unless-stopped`。
- 面板不参与扫描锁；手动执行通过 `docker exec` 调用现有
  `scan-and-publish.sh`，复用同一把 `flock`，不会与定时任务并发。

### 5.2 配置单源：`.env`

**唯一配置源是项目根目录的 `.env`。** 面板与手工编辑都改同一个文件。

- Compose 不再用 `env_file` 把 `.env` 一次性注入容器；`.env` 仍由 Compose 用于
  `${IMAGE_NAME}` / `${CONTAINER_NAME}` / `${PANEL_PORT}` 等插值。
- 扫描器启动时和每轮任务都重新读取 `/project/.env`（项目目录挂载）。
- 读取优先级：**显式环境变量 > `.env` > schema 默认值**。
  - 显式环境变量包括 compose 的 `environment:` 与
    `docker compose run -e KEY=VAL`，保留现有临时覆盖能力。
  - `.env` 中空值仍按“未设置”处理，回落到默认值，与现有语义一致。
- `entrypoint.sh`、`scan-and-publish.sh`、`doctor.sh` 在运行前用共享导出器把
  `.env` 中的已知键导入环境（已存在的键不覆盖），保证 git/curl 等子进程也能读到。
- 调度热重载：容器内 `config-watcher.sh` 每 5 秒检查 `.env` 内容哈希；变化后重新
  渲染 `/tmp/supercronic.crontab`，`supercronic -test` 通过则 `SIGHUP` PID 1。
  面板保存后还会主动调用 `apply-config.sh` 立即生效；手工编辑由 watcher 兜底。
- 重启类参数：`PUID` / `PGID` / `TZ` / `RUN_ON_START` 修改后需要重启扫描容器
  （面板提供「保存并重启」）。`IMAGE_*` / `CONTAINER_NAME` / `PANEL_*` 只读。
- 架构变更：`RUN_ON_START`、`TZ` 等只在入口阶段读取，watcher 不处理，必须重启。

### 5.3 面板写入 `.env` 的规则

- 只改面板管理的键；保留注释、空行、键顺序和未管理内容。
- 原地更新已有 `KEY=...` 行；缺失的键追加到文件末尾的「面板管理」区块。
- 值按 Compose `.env` 子集编码：普通值不加引号；含 `#` 或首尾空格时用单引号；
  拒绝换行与 NUL。
- 同目录临时文件 + `fsync` + `os.replace` 原子替换；保留原文件的 uid/gid/mode
  （无法保留时至少 0600），避免宿主用户失去编辑权。
- 保存前读取文件哈希做乐观锁；宿主同时修改时返回 409，要求用户刷新/对比。
- 每次保存前把完整 `.env` 备份到 `panel-data/backups/env/`（0600），保留最近 30 份；
  版本历史、diff、审计与日志中的敏感值脱敏，回滚时保留当前令牌。
  备份文件可能含明文令牌，文档与页面明确提示。

### 5.4 保存事务与生效核对

每次保存都是一次可回滚的事务，不允许“提示成功但实际没生效”：

1. **定位**：读取 `.env` 当前哈希；与前端提交的哈希不一致 → 409，提示文件已被修改。
2. **校验**：类型/范围 → 跨字段语义（`check-config.py` 干跑，候选文件写入临时路径）。
3. **写入**：原子替换，保留属主/权限；备份完整文件；记录版本。
4. **回读**：从磁盘重新读取并比对哈希与内容；不一致 → 自动回滚并报错。
5. **核对生效值**：容器在线时，在扫描容器内执行 `print-config.py`，逐项比对本次修改的
   非重启类参数；不一致 → 返回 `verification.status="mismatch"` 并显示差异，
   不允许显示“已生效”。状态优先级：
   `mismatch` > `restart_required` > `unavailable` > `verified`。
6. **调度**：若 `CRON_SCHEDULE` 变化且容器在线，执行 `apply-config.sh`；
   脚本退出非 0 或 `supercronic -test` 失败 → 回滚 `.env` 并报错。
   容器离线时不回滚：标记 `schedule_reloaded=false` + `unavailable`，提示
   “已保存，扫描容器恢复后由 watcher 自动重载”。
7. **重启类参数**：`PUID/PGID/TZ/RUN_ON_START` 写入成功但标记
   `verification.status="restart_required"`，提示“已保存，重启扫描容器后生效”，
   提供一键重启；混合变更时同时列出已核对的热参数与待重启参数。
8. **审计**：记录写入、核对、应用结果与最终状态。

接口返回必须区分：
`written`（是否落盘）、`verification.status`（`verified` / `mismatch` /
`unavailable` / `restart_required`）、`effects.next_round`（下一轮生效的键）、
`effects.schedule_reloaded`、`effects.restart_required`、`next_run`、`warnings`。
前端不得把 `written=true` 直接显示成“已生效”。

### 5.5 运行时目录约定

| 路径 | 写入方 | 用途 |
| --- | --- | --- |
| `/project/.env` | panel / 用户 | **唯一配置源** |
| `/data/runtime/runs.tsv` | scanner | **权威**轮次记录：run_id/触发源/开始/结束/扫描退出码/发布退出码/耗时/摘要 |
| `/data/ip-library.txt` | 用户 / panel | 候选地址库 |
| `/panel-data/panel.db` | panel | 用户、配置版本、审计、轮次索引 |
| `/panel-data/secret.key` | panel | 会话签名密钥（首次启动生成） |
| `/panel-data/backups/` | panel | `.env` 与 IP 库备份，保留最近 30 份 |
| `/panel-data/web/` | 构建产物 | 前端静态文件（镜像内只读） |

`runs.tsv` 放在 `./data` 而不是 `./panel-data`，因为扫描器需要写它；面板只读。

## 6. 参数模型与校验

- 新增 `scanner/schema.py` 作为**唯一参数元数据来源**：名称、分组、类型、默认值、
  标签、说明、是否敏感、是否重启生效、约束。
- `scanner/config.py` 改为从 schema 取默认值，并新增 `.env` 文件读取；
  保持现有常量名与导入方式不变，`best_cf_ip_scanner.py` 与各模块无需改动。
- 新增 `scanner/dotenv.py`：严格实现 Docker Compose `.env` 的可支持子集：
  - 注释、空行、`KEY=VALUE` 与 `KEY: VALUE`；
  - 单引号字面量、双引号转义、行内注释（` #`）；
  - 不支持多行值、`${VAR}` 插值、`export` 前缀；遇到不支持写法给出行号并失败。
  - 以 `.env.example` 作为兼容性测试样本。
- 面板复用同一 schema 生成表单，并复用 `scanner/validation.py` 的语义校验函数。
- 保存前做一次「候选配置」干跑：在 panel 容器内以合并后的环境执行
  `check-config.py`，确保扫描器启动路径不会因新配置失败。
- 敏感字段（`GIT_TOKEN`、带认证信息的代理 URL）只写不读：接口返回
  `configured: true/false`，永不返回明文；日志、diff、审计、备份自动脱敏。
- 调度表达式支持 5 段（分 时 日 月 周）与 6 段（秒 分 时 日 月 周），与
  `docs/scheduling.md` 已发布能力一致；保存前用 `supercronic -test` 校验，
  预览器按可选秒字段计算未来 5 次执行时间（按生效的 `TZ`）。不接受 `@daily`
  这类宏写法，UI 明确提示。
- `PROBE_HOST` 变更时，面板自动把新域名追加到 `NO_PROXY` 与 `no_proxy`
  （保留已有条目，不删除旧域名），并在 diff、审计和 UI 中标注联动修改；
  用户手动改 `NO_PROXY` 时不再二次改写。

## 7. 调度与运行

- `CRON_SCHEDULE` 修改后由 watcher/`apply-config.sh` 自动热重载；
  `RUN_ON_START` 保存时标注「重启容器后生效」并提供「保存并重启」。
- 手动执行：`POST /api/runs` → 检查 `/cache/scan.lock` → `docker exec` 启动
  `scan-and-publish.sh`（设置 `RUN_ID`、`RUN_TRIGGER=panel`）→ 通过 SSE 推送
  stdout/stderr → 结束后写入轮次记录。
- 轮次记录由 `scan-and-publish.sh` 追加到 `runs.tsv`；定时与手动都覆盖。
  - 面板传入的 `RUN_ID` 原样写入；定时任务未传时由脚本生成。
  - 分别记录 `scan_exit` 与 `publish_exit`，区分「扫描失败」与「扫描成功但发布失败」。
  - 每轮开始打印一行生效参数摘要，便于确认 `.env` 已生效。
  - `panel.db.runs` 只是 UI 索引，启动时从 `runs.tsv` 重建；权威来源是 `runs.tsv`。
- 同一时间只允许一轮：复用现有 flock；面板检测到锁被占用时禁用「立即执行」。
- 中止当前轮：v1 不提供，避免误杀进程。

## 8. UI 信息架构

- 布局：顶部品牌栏 + 横向主标签页 + 页内子标签；顶部状态条固定显示
  「扫描器在线/离线、是否有轮次在跑、最后更新时间、账号菜单」。窄屏时主标签横向
  滚动，不折叠成隐藏菜单，保证九个入口始终可达。
- 主标签：`总览`、`参数`、`调度`、`运行`、`日志`、`产物`、`IP 库`、`发布`、`系统`。
- 页内子标签：
  - 参数：`扫描参数`、`发布与代理`、`只读设置`；
  - 运行：`立即运行`、`历史轮次`；
  - 日志：`实时日志`、`下载`；
  - 产物：`全部`、`订阅列表`、`明细表`；
  - IP 库：`编辑`、`备份`；
  - 发布：`参数`、`最近结果`；
  - 系统：`账号`、`审计`、`容器`、`关于`。
- 首版（v1）先保证九个主标签全部可用、保存/取消/结果提示/真实状态齐备；
  骨架屏动效、快捷键、深色主题、图表、复杂筛选等放到后续迭代，不阻塞首版。
- 页面：
  - `/` 总览：状态卡片、上次结果、下次执行、最近轮次表、快捷操作。
  - `/config` 参数：分组折叠面板，字段级校验与来源标签，底部固定「保存」操作栏；
    支持查看 diff、版本历史、回滚。
  - `/schedule` 调度：cron 输入 + 常用模板 + 未来 5 次预览 + 应用状态。
  - `/runs` 运行：立即执行、实时输出终端、历史轮次表。
  - `/logs` 日志：SSE 实时流、关键字过滤、暂停/继续、下载。
  - `/outputs` 产物：文件表格、预览抽屉、下载、复制。
  - `/library` IP 库：等宽编辑器、行号、统计、校验结果、保存/备份。
  - `/publish` 发布：Git 参数、令牌掩码、最近推送结果。
  - `/system` 系统：改密码、审计日志、容器重启/启停、版本信息。
- 前端：Vue 3 + TypeScript + Vite + Element Plus + Pinia + Vue Router；
  SSE 用组合式函数封装，断线自动重连并回填最近日志。
- 中文文案；危险操作二次确认；空状态、加载态、错误态必须明确。

**交互硬性约定：**

- **保存/取消**：参数、调度、IP 库、发布页都固定底部操作栏；无改动时「保存」禁用，
  「取消」恢复到最近一次从服务端加载的内容；有未保存改动时离开页面必须二次确认。
- **保存结果**：成功与失败都必须给出明确结果面板，不能只用一闪而过的 toast。
  成功面板显示：修改了哪些键、每项的生效方式（下一轮 / 已热重载 / 需重启）、
  是否回读核对通过、下次执行时间、可执行的后续动作（立即执行 / 重启容器 / 关闭）。
  失败面板显示：失败阶段（校验/写入/回读/调度应用）、字段级错误、原始错误摘要，
  并保留用户已填写的内容以便修正或重试。
- **状态真实性**：产物、日志、IP 库、轮次、配置一律以服务端本次读取为准，展示
  `读取时间`、`文件 mtime`、`内容哈希` 或 `连接状态`；不得用示例数据、旧缓存或
  推断值填充。服务端不可达/解析失败时显示明确错误与重试，不能显示成“空/成功”。
- **实时流状态**：日志与运行输出必须显示 `连接中 / 实时 / 已暂停 / 已断开`，
  断线时提示“正在重连”，重连后回填最近 tail；不得把断开状态显示成仍在实时。
- **空状态**：没有产物、没有轮次、IP 库为空等必须显示“尚无…”，而不是空白表格或
  假数据；空状态要说明产生条件与下一步操作。

## 9. 技术栈（定稿）

| 层 | 选型 | 说明 |
| --- | --- | --- |
| 后端 | Python 3.13 + FastAPI 0.162 + uvicorn 0.54 | 与扫描器同语言；异步、SSE、OpenAPI |
| 数据校验 | Pydantic 2.14 | 请求/响应模型 |
| Docker | docker SDK 7.2 | 通过挂载 socket 调用 Engine API |
| 实时 | sse-starlette 3.6 | 日志/运行输出 SSE，带心跳与断线处理 |
| 认证 | Argon2id（argon2-cffi 25.1）+ itsdangerous 2.2 | 密码哈希 + 签名 Cookie |
| 存储 | SQLite（标准库，WAL） | 单管理员、配置版本、审计、轮次索引 |
| 前端 | Vue 3.5 + TypeScript 5.9 + Vite 8 + Element Plus 2.14 | 中文后台 UI；Pinia + Vue Router |
| 测试 | pytest 9 + httpx 0.28 + Vitest | API/解析器/关键组件 |
| 构建 | Node 24 多阶段 + Python 3.13 Alpine | 单镜像，前端静态文件由后端托管 |

版本为 2026-11-03 核对到的当前版本；实现时写入 `requirements-panel.txt` 与
`package-lock.json` 锁定。

### 9.1 选型原则

1. **主流**：社区活跃、官方文档完整、中文资料与示例多、遇到问题容易搜到答案。
2. **稳定**：有明确发布节奏，不靠破坏性变更推进；运行期依赖全部精确锁定。
3. **资源丰富**：组件库、模板、测试工具、部署案例充足，不引入小众自研框架。
4. **与项目贴合**：后端沿用 Python；前端选择中文后台生态最成熟的 Vue 组合；
   不为“新”而引入第二套 UI 框架、状态库或 ORM。
5. **可替换边界清晰**：前端与后端通过 REST/SSE 契约解耦；未来换 UI 不触碰扫描核心。

### 9.2 为什么是这套

| 选择 | 备选 | 取舍 |
| --- | --- | --- |
| FastAPI + uvicorn | Flask / Django / Go | FastAPI 异步、Pydantic、OpenAPI、SSE 都成熟，且与扫描器同语言；Flask 做 SSE/校验更手工，Django 偏重，Go 会引入第二语言。FastAPI 是 0.x 版本号，但生态与使用量足够大，靠精确锁版本与测试兜底。 |
| Vue 3 + Element Plus | React + Ant Design | 两者都主流；本项目中文后台、表格/表单/抽屉密集，Element Plus 中文文档与现成后台模板更丰富。若团队明确统一 React，必须在 Task 16 前整体切换，不能两套混用。 |
| Pinia + Vue Router | Vuex / 自研路由 | Vue 3 官方推荐组合，资料最多。 |
| SQLite（WAL） | PostgreSQL / MySQL | 单管理员、低并发、无额外服务；备份就是文件。未来多用户再迁移。 |
| SSE | WebSocket | 日志/运行输出是单向流；SSE 浏览器原生支持、自动重连、实现简单，不需要双向通道。 |
| docker SDK | compose CLI / docker.sock 裸调 | SDK 跨 Windows/Linux 一致，不依赖宿主路径映射；调用范围限定本项目容器。 |
| 单镜像双入口 | 两个镜像 | 用户只 pull/up 一次，版本不会漂移；代价是镜像体积增加，已接受。 |
| Argon2id + 签名 Cookie | OAuth / SSO | 单管理员、局域网、无外部 IdP；不引入额外身份服务。 |

### 9.3 版本策略

- 运行期依赖全部精确锁定（`requirements-panel.txt`、`package-lock.json`），
  不使用 `latest`；`@playwright/mcp@latest` 仅用于开发工具，不进入镜像。
- Python 3.13、Node 24 LTS、TypeScript 5.9（不追 7.x）、Vite 8 稳定线。
- 升级按季度或安全公告进行，单独 PR，跑完整测试与 Compose/E2E 门禁；
  功能开发中途不升大版本。
- 依赖超过 12 个月无维护、归档或出现高危漏洞时，优先替换而不是长期打补丁。
- 兼容性矩阵写入 `docs/testing.md`：Python、Node、Docker Engine、浏览器版本。

### 9.4 资源丰富度

- FastAPI / Pydantic / Vue 3 / Element Plus / Vite / Playwright 均有官方文档、
  大量中文教程与社区问答；Element Plus 的后台模板与组件示例尤其充足。
- 不引入小众 UI 框架、非标准状态库、冷门 ORM；SQLite 与 stdlib 优先。
- 需要设计协同时，Figma MCP + `ui-to-vue` 可直接把设计稿映射到 Vue 3 + Element Plus。

## 10. API 设计（概要）

统一前缀 `/api`，JSON；写操作要求 `X-CSRF-Token`；未登录返回 401。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/auth/setup` | 首次设置管理员密码（仅未初始化时可用） |
| POST | `/api/auth/login` | 登录，返回会话 Cookie |
| POST | `/api/auth/logout` | 登出 |
| GET | `/api/overview` | 状态、上次结果、下次执行、配置摘要 |
| GET | `/api/config` | 参数元数据 + 当前值 + 来源 + 文件哈希 + mtime + 每项生效方式 |
| PUT | `/api/config` | 保存 `.env`，返回写入/核对/生效结果 |
| POST | `/api/config/verify` | 在扫描容器内重新核对当前生效值（手动「重新核对」） |
| GET | `/api/config/versions` | 配置版本列表 |
| POST | `/api/config/versions/{id}/rollback` | 回滚并应用 |
| GET | `/api/schedule/preview?cron=` | 未来 5 次执行时间 |
| POST | `/api/schedule/apply` | 重渲染 crontab 并 SIGHUP |
| POST | `/api/runs` | 触发一轮，返回 run id |
| GET | `/api/runs/{id}/stream` | SSE 实时输出 |
| GET | `/api/runs` | 历史轮次 |
| GET | `/api/logs/stream` | SSE 容器日志 |
| GET | `/api/logs/download` | 下载最近日志 |
| GET | `/api/outputs` | 产物列表 |
| GET | `/api/outputs/{name}` | 预览或下载（服务端白名单） |
| GET/PUT | `/api/library` | 读取/保存 IP 库 |
| GET | `/api/library/backups` | 备份列表与恢复 |
| GET/PUT | `/api/publish` | 发布参数（令牌只写） |
| GET | `/api/audit` | 审计日志 |
| POST | `/api/system/restart` | 重启本项目扫描容器 |
| POST | `/api/system/stop` / `start` | 停止/启动扫描容器 |
| GET | `/healthz` | 面板健康检查（免登录） |

错误统一 `{code, message, details?}`；配置校验失败返回 422 与字段级错误列表；
并发修改返回 409（文件哈希不匹配）；回读不一致返回 500 并自动回滚；调度应用失败
返回 500 并自动回滚。

配置保存响应字段（前端按此渲染，不得自行推断）：

```json
{
  "written": true,
  "hash": "sha256:...",
  "changed": [{"name": "MAX_CANDIDATES", "old": "0", "new": "200", "effect": "next_round"}],
  "effects": {
    "next_round": ["MAX_CANDIDATES"],
    "schedule_reloaded": false,
    "restart_required": []
  },
  "verification": {
    "status": "verified",
    "checked_at": "2026-11-03T10:00:00+08:00",
    "details": []
  },
  "next_run": "2026-11-03T12:30:00+08:00",
  "warnings": []
}
```

`verification.status` 取值：`verified`（扫描器已读到新值）、`mismatch`（读到旧值或
不一致，附差异）、`unavailable`（容器离线，下一轮生效但当前无法核对）、
`restart_required`（写入成功，需重启）。

## 11. 数据与持久化

- SQLite（stdlib `sqlite3`，WAL）：
  - `users`：单管理员，Argon2id 哈希；
  - `config_versions`：每次成功保存的脱敏文本、diff、作者、时间；
  - `runs`：从 `runs.tsv` 重建的 UI 索引；
  - `audit`：登录、配置变更、回滚、手动执行、容器操作；
  - `schema_version`：自动迁移。
- 会话：itsdangerous 签名 Cookie（HttpOnly、SameSite=Strict），密钥存
  `secret.key`；不落库，登出即删 Cookie。
- 备份：`.env` 与 IP 库保存前自动备份；保留 30 份，可手动清理。完整 `.env`
  备份权限 0600、可能含明文令牌；版本历史、diff 与审计脱敏，回滚时从当前文件
  保留令牌。
- 面板数据不放进 `./data`，避免污染用户备份；`./panel-data` 单独挂载。

## 12. 稳定性、安全与可观测

- 启动自检：数据库可写、`secret.key` 可读、`.env` 可读、docker.sock 可达；
  socket 不可用时仍启动并在 UI 显示降级原因（数据库不可写则退出）。
- 所有外部调用设置超时；SSE 每 15 秒心跳，客户端断线重连。
- `.env` 写入原子化；保存前干跑；调度应用失败自动回滚文件并提示。
- 登录失败限速（用户名 + 来源 IP，每分钟 5 次）；Argon2id；接口不返回敏感明文。
- Docker 调用白名单：容器按 `com.docker.compose.service=scanner` + 项目标签解析，
  或使用 `SCANNER_CONTAINER`；前端不能指定任意容器/路径。
- 文件访问限制在 `OUTPUT_DIR`、`DATA_DIR`、`PANEL_DATA_DIR`、项目 `.env` 内，
  解析后校验 `relative_to`，拒绝路径穿越。
- 不使用 `shell=True`；exec 命令与参数固定。
- 审计日志记录操作者、时间、动作、目标、结果摘要（敏感值脱敏）。
- 面板健康检查独立于扫描器；扫描器离线时面板仍可用并显示离线原因。

## 13. 部署、升级与兼容

- `compose.example.yaml` 增加 `panel` 服务，移除 `env_file`，增加项目目录挂载。
- `.env.example` 增加：`PANEL_PORT=8080`、`PANEL_BIND=0.0.0.0`、
  `PANEL_SESSION_DAYS=7`（可选）、`PANEL_TRUST_PROXY=false`。
- 用户操作仍是：复制两个模板 → 填 `PROBE_HOST` → `docker compose up -d`。
- 单镜像由 CI 构建一次，tag 不变；`compose.build.yaml` 本地构建同样得到两个服务。
- 升级：`docker compose pull && docker compose up -d`；面板数据库自动迁移；
  `.env` 与备份保留。
- 兼容性变化：`docker compose exec scanner env` 不再直接显示扫描参数（改为每轮
  读取 `.env`）；提供 `print-config` / `doctor.sh` 查看生效值。文档明确说明。
- 文档：README 增加面板章节；新增 `docs/panel.md`、`docs/testing.md`；更新
  `docs/configuration.md`、`docs/operations.md`、`docs/scheduling.md`、
  `docs/troubleshooting.md`、`.env.example`。
- CI：构建（含前端）→ compose config → 冒烟（两容器启动、面板 `/healthz` 200、
  首次设置页可访问、扫描器 healthy）→ 后端单元测试 → 前端构建/测试。

## 14. 验收标准

1. 一次 `docker compose up -d` 后 `docker compose ps` 显示 `scanner` 与 `panel` 均正常。
2. 浏览器访问 `http://<宿主IP>:8080`，完成首次管理员设置并登录。
3. 面板改 `MAX_CANDIDATES=200` 保存，下一轮或「立即执行」的日志体现新值；
   直接手工把 `.env` 改成 300，下一轮同样生效。
4. 修改 cron，页面显示未来 5 次时间；应用后 supercronic 日志出现重载，无需重启容器；
   手工编辑 `.env` 的 cron 也能在 watcher 周期内重载。
5. 手动执行时实时输出可见；同时定时任务触发时不会并发写产物。
6. 日志页 2 秒内出现新日志；过滤、暂停、下载可用。
7. 产物页可预览 TXT/CSV 并下载；路径穿越请求被拒绝。
8. IP 库非法行保存被拒绝并定位行号；合法保存自动备份。
9. 非法参数（如 `TCP_MIN_SUCCESS > TCP_ATTEMPTS`）在保存时被拒绝，`.env` 不落盘。
10. 配置回滚后下一轮恢复旧值；审计日志有记录；敏感值不出现于 diff、审计与日志，
    完整 `.env` 备份为 0600 且页面有提示。
11. 重启面板容器不影响正在运行的扫描；重启扫描容器后面板显示离线再恢复。
12. `docker compose run --rm -e MAX_CANDIDATES=10 scan-once` 的显式值仍优先于 `.env`。
13. 发布失败与扫描失败在轮次记录中可区分，轮次 id 与面板触发记录一致。
14. 忘记密码时 `panel-reset-password` 可恢复登录，配置版本与审计记录保留。
15. 6 段 cron（含秒）可通过校验并给出未来执行时间预览。
16. 参数页保存后有明确的“修改了哪些键 / 每项生效方式 / 是否核对通过 / 下次执行
    时间”结果面板；失败时保留已填内容并显示失败阶段与字段错误。
17. 保存后从磁盘回读并核对；模拟扫描器读到旧值时界面显示“核对不一致”，不得显示
    “已生效”；容器离线时显示“已保存，下一轮生效，当前无法核对”。
18. 参数、调度、IP 库、发布页均有保存/取消、未保存离开确认；保存成功后以服务端
    回读内容更新页面，不使用本地乐观内容冒充已保存。
19. 日志页显示连接状态与最后接收时间；断线显示“正在重连”，不得把断开显示为实时。
20. 产物/IP 库/轮次页显示读取时间、文件 mtime 或哈希；无数据时显示“尚无…”及原因，
    接口失败时显示错误与重试，不显示假数据。
21. 后端单元测试与前端构建在 CI 通过。

## 15. 测试与上线门禁

### 15.1 分层测试

| 层 | 工具 | 覆盖 | 运行时机 |
| --- | --- | --- | --- |
| 单元 | pytest 9 | dotenv/CRLF/引号、schema/config 优先级、cron 5/6 段、校验、脱敏、runs 解析、路径安全、认证/限速 | 每次提交 |
| API 集成 | pytest + TestClient + fake controller | 认证/CSRF、配置保存事务与核对、409 冲突、回滚、调度、运行/SSE、日志、产物、IP 库、发布、系统 | 每次提交 |
| 脚本/配置契约 | `sh -n`、subprocess、`supercronic -test`、`docker compose config` | 导出器引用、apply 失败保留旧 crontab、`.env.example` 可解析、compose 变量 | 每次提交 |
| 前端 | Vitest + Vue Test Utils | 保存/取消/dirty、字段类型、错误映射、SSE 重连 | 每次提交 |
| 镜像/Compose 冒烟 | Docker + compose | 单镜像双容器、health、首启页、scanner healthy、`.env` 热读取、`run -e` 优先级 | 每次 PR / 发布前 |
| E2E | Playwright | 首次设置/登录、保存/取消/结果面板、核对不一致提示、日志连接状态、产物空态/预览、IP 库行错误、回滚、需重启提示 | 每次 PR / 发布前 |
| 人工上线清单 | 真实环境 | 真实域名扫描、真实发布、Windows Docker Desktop、根路径反代、密码找回、备份恢复 | 发布前 |

### 15.2 可测试性要求

- 所有外部依赖可注入：`Settings`、`ScannerController`、配置校验器、时钟（限速/时间预览）、
  Docker 客户端；禁止在业务代码里直接 `docker.from_env()` 或读真实 `/panel-data`。
- 测试使用 `tmp_path` 与 fake controller；不访问网络、不写真实 `.env`/`data`/`output`、
  不使用真实令牌或仓库。
- SSE 的 fake 生成器必须有界，测试不能依赖超时结束。
- `.env` 解析器、cron 解析器、配置保存/回滚、认证与路径安全必须有独立单元测试，
  不能只靠 E2E 覆盖。
- 测试数据放 `tests/fixtures/`；`.env` 样本不得包含真实密钥。

### 15.3 CI 门禁（全部通过才允许合并/发布）

1. **backend**：`pip check` 无依赖冲突；`pytest -q --cov=panel --cov=scanner/dotenv.py --cov=scanner/schema.py --cov=scanner/runtime_env.py --cov-fail-under=80`。
2. **frontend**：`npm ci && npm run typecheck && npm run build && npm run test`。
3. **contract**：`sh -n docker/*.sh`、`docker compose config --quiet`、`.env.example` 解析测试。
4. **image-smoke**：构建单镜像 → `up -d` → scanner healthy、panel `/healthz` 200、
   首次设置页可访问；修改 `.env` 后 `print-config.py` 能读到新值；
   `docker compose run --rm -e MAX_CANDIDATES=10 scan-once` 的 `print-config` 显示 10。
5. **e2e**：干净 `panel-data` 启动 stack，Playwright 串行执行关键 UI 流程。
6. **安全检查**：`GET /api/config` 不含敏感明文；diff/审计/日志脱敏；路径穿越用例全绿。
7. **发布前**：镜像 digest 记录、数据库迁移从空库与上一版各验证一次、备份恢复演练。

覆盖率阈值针对面板与配置单源模块；不为了数字给扫描核心补无意义测试。
任何任务失败不允许用 `--no-verify`、跳过用例或放宽断言绕过。

### 15.4 必须存在的回归用例

1. 面板保存后扫描器读到新值；手工改 `.env` 同样生效。
2. `docker compose run -e` 的显式值优先于 `.env`。
3. `PUID/PGID/TZ/RUN_ON_START` 返回 `restart_required`，不冒充已生效。
4. cron 5 段/6 段可预览；非法 cron 与 `apply-config.sh` 失败保留旧 crontab。
5. 保存后核对到旧值 → `verification.status="mismatch"` 并列出差异。
6. 保存与宿主同时修改 → 409，不覆盖。
7. 产物/备份文件名路径穿越被拒绝。
8. `GIT_TOKEN`/代理凭据不出现在 GET、diff、审计、日志、版本历史。
9. 扫描容器离线时面板可用，操作返回 `unavailable`，SSE 显示断开/重连。
10. 首次设置、登录、改密、忘记密码 CLI 恢复。
11. 面板重启不影响扫描；扫描容器重启后面板恢复在线。
12. Windows Docker Desktop 下 `.env` 原子替换与目录挂载可用。

### 15.5 人工上线检查清单

- [ ] 用真实 `PROBE_HOST` 跑完一轮，产物符合预期。
- [ ] 面板改参数 → 核对通过 → 第二轮日志出现新值；手工改 `.env` 同样验证。
- [ ] cron 热重载后按新时间触发。
- [ ] 手动执行、日志实时流、产物预览/下载、IP 库保存/恢复。
- [ ] 发布到测试仓库成功；令牌未出现在页面/日志。
- [ ] 面板重启、扫描容器重启、备份恢复。
- [ ] 反向代理（根路径）与 HTTPS 下 Cookie/CSRF 正常。
- [ ] Windows Docker Desktop 与 Linux 各一台验证。
- [ ] 工作区无未预期文件、无敏感信息、镜像 digest 已记录。

### 15.6 缺陷与不稳定测试

- 失败测试不得删除、跳过或弱化断言；先修根因。
- E2E 仅允许 1 次基础设施重试；连续失败按缺陷处理，不做静默重试。
- 每个线上缺陷补一条回归测试，优先落在单元/API 层，E2E 只保留用户路径。

## 16. 实施阶段（高层，详细计划另出）

- 阶段 0：完整备份（已完成）。
- 阶段 1：配置单源——`scanner/schema.py`、`scanner/dotenv.py`、`config.py`
  读取 `.env`、导出器、entrypoint/scan/doctor 接入、`config-watcher.sh`、
  `apply-config.sh`、compose 去掉 `env_file` 并加项目目录挂载。
- 阶段 2：基础镜像与后端——单镜像双入口、认证、配置读写、Docker 适配器、
  运行/日志 SSE、产物、IP 库、发布、系统接口、SQLite 迁移。
- 阶段 3：前端——应用骨架、登录/首次设置、总览、参数、调度、运行、日志、
  产物、IP 库、发布、系统页面。
- 阶段 4：硬化——校验/回滚/审计、单元测试、CI、文档、升级路径与发布。

## 17. 风险与待验证项

- Docker Compose `.env` 子集与自定义解析器可能存在语义差异：以
  `.env.example` + 单元测试锁定；不支持的写法明确报错而不是静默。
- Windows Docker Desktop 下项目目录挂载、原子替换、属性保留需实测；
  失败时降级为原地写入并提示。
- `.env` 是热文件：面板保存与手工编辑并发时用哈希乐观锁，避免互相覆盖。
- `supercronic` v0.2.51 的 `SIGHUP` 热重载行为需用真实容器验证；
  不可用则回退为「重启扫描容器」并明确提示。
- 移除 `env_file` 后，`docker compose exec` 会话不再自带扫描参数；
  需提供 `print-config` 并在文档中说明。
- 单镜像体积增加（前端 + Python 依赖），功能优先于体积。
- 前端构建引入 Node 阶段，CI 时间增加；使用构建缓存。
- 面板数据库升级需要迁移策略，首版从 `schema_version=1` 开始。

## 18. 评审补充决定

1. **扫描器脚本可改**：允许增量修改 `scan-and-publish.sh` / `publish.sh` /
   `entrypoint.sh`。`runs.tsv` 是轮次权威记录，`panel.db` 只做索引；
   记录包含 `run_id`、触发源、开始/结束时间、`scan_exit`、`publish_exit`、
   耗时与摘要；每轮打印生效参数摘要。面板启动时从 `runs.tsv` 对账重建。
2. **调度与扫描参数同源**：都在 `.env`，共用版本历史；回滚时若包含调度字段，
   必须同时重渲染 crontab 并热重载。`RUN_ON_START` 以「重启容器后生效」提示。
3. **可写/只读集合**：可写为扫描参数、`CRON_SCHEDULE`、`RUN_ON_START`、`GIT_*`、
   `HTTP_PROXY` / `HTTPS_PROXY` / `NO_PROXY` / `no_proxy`，以及
   `PUID` / `PGID` / `TZ`（后三者保存后需重启扫描容器，面板提供一键重启）；
   只读为 `IMAGE_*`、`CONTAINER_NAME`、`PANEL_*`、容器内固定路径。
   `PROBE_HOST` 变更自动追加 `NO_PROXY` / `no_proxy` 并显式标注。
4. **cron 段数**：支持 5 段与 6 段，拒绝宏写法；校验以 `supercronic -test` 为准。
5. **管理员找回**：新增 `panel-reset-password` 命令，只重置密码，保留配置版本、
   审计与轮次索引；不把「删除 panel.db」作为恢复手段。
6. **敏感值**：`GIT_TOKEN` 与带认证信息的代理 URL 留在 `.env`（唯一源），
   接口只写不读；版本历史、diff 与审计脱敏；完整 `.env` 备份权限 0600、可能含
   明文令牌；回滚保留当前令牌。README 与备份文档提示 `./data` 与 `./panel-data`
   备份可能含敏感值。
7. **反向代理**：v1 只保证根路径反代，不支持子路径挂载。新增
   `PANEL_TRUST_PROXY=false`；设为 `true` 时才采信 `X-Forwarded-For` 与
   `X-Forwarded-Proto`。登录限速按「用户名 + 来源 IP」，避免代理后单一 IP 锁死。
8. **技术栈**：按 §9 定稿；单镜像双入口；前端构建产物由 FastAPI 托管。
9. **保存事务与交互契约**：按 §5.4 与 §8 执行；`written`、`verification.status`、
   生效方式与下次执行时间必须分别展示；禁止把“已写入”显示为“已生效”，禁止用
   示例数据填充日志/产物/IP 库/轮次。

## 19. 开发工具与设计协作（已接入）

### 19.1 MCP

| MCP | 状态 | 用途 |
| --- | --- | --- |
| Playwright MCP | 已接入并实测 | 开发期交互验证、截图、检查真实页面状态；CI 仍用 Playwright Test，不依赖 MCP |
| Figma MCP | 已接入并完成 OAuth | 读取设计上下文、生成/更新 Figma 设计、Code Connect、设计系统 |

Playwright MCP 使用系统 Edge（`--browser msedge`），快照输出到系统临时目录，不写入仓库。
Figma 使用远程 `https://mcp.figma.com/mcp`，OAuth 凭据由 OpenCode 管理，不写入配置或仓库。

### 19.2 Figma 使用规则（选择性）

只有在存在 Figma 文件/链接/设计任务时才调用 Figma 工具；普通按 Spec 编码不触发。

必须先加载对应 skill，再调用工具：
- `figma-design-to-code` → 之后才能 `get_design_context`（Figma → 代码）。
- `figma-use` → 之后才能 `use_figma`（写入/修改画布）。
- `figma-create-new-file` → 之后才能 `create_new_file`。
- `figma-generate-design` → 代码/页面 push 到 Figma。
- `figma-generate-library` / `figma-code-connect` → 设计系统/组件映射。
- `figma-implement-motion` / `figma-use-motion` → 动效。
- `figma-generate-diagram` → FigJam 架构图。

设计稿是**参考**，不是最终代码：必须适配本项目 Vue 3 + Element Plus、现有 token 与
交互契约；不得因为 Figma 输出而偏离 §8 的标签页结构与 §5.4 的保存事务。

### 19.3 前端设计 skills（按需）

直接适用：`frontend-design-direction`、`design-system`、
`make-interfaces-feel-better`、`accessibility`、`vue-patterns`、`vite-patterns`、
`typescript-patterns`、`ui-to-vue`、`browser-qa`、`dashboard-builder`。
React/Next 专用（只参考原则）：`frontend-patterns`、`frontend-a11y`、`react-*`、
`motion-*`。没有专门的 Element Plus skill；由 `ui-to-vue` 覆盖。

### 19.4 推荐工作流

1. 无设计稿：按 §8 的标签页结构直接实现，使用 `frontend-design-direction` 与
   `design-system` 定 token。
2. 有 Figma 设计：加载 `figma-design-to-code` → `get_design_context` → 用
   `ui-to-vue`/`vue-patterns` 落地 → `make-interfaces-feel-better`/`accessibility`
   打磨 → Playwright MCP 实测 → Playwright Test 固化为回归。
3. 需要把实现回推设计：加载 `figma-generate-design`/`figma-use`；先
   `search_design_system` 复用组件，不凭空生成。
4. 设计系统/组件映射：`figma-generate-library`、`figma-code-connect`。
