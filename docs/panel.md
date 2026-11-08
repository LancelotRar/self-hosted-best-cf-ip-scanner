# 运维面板

[← 返回首页](../README.md) · [配置手册](configuration.md)

面板是本项目的**默认、首选运维入口**：一个 compose 堆栈、两个容器（`scanner` +
`panel`）、两个独立镜像。应用参数只从面板编辑；CLI、`docker compose run` 保留为
备用/应急路径。

```
浏览器 ──▶ panel（FastAPI + Vue SPA）
              │  docker.sock（直接控制扫描容器）
              │  SQLite（应用参数真源）
              │  /scanner-config/runtime.json（运行期投影，只写）
              ▼
          scanner（supercronic + 扫描任务，每轮重读投影）
```

## 1. 首次登录

1. `docker compose up -d` 后访问 `http://<宿主IP>:8080`（端口由部署参数 `PANEL_PORT` 决定）。
2. 首次打开进入「首次设置」，设置管理员密码（至少 8 个字符）。
3. 之后用该密码登录；忘记密码时见 §6。

> 默认 compose 只监听 `127.0.0.1:8080`；需要局域网访问时配合 TLS 反向代理，
> 不要把面板直接暴露到公网。端口属于部署参数。

## 2. 数据库是唯一配置源

- 应用参数存在 `panel-data/panel.db`；首次启动把 schema 默认值写入数据库。
- 面板保存后写入数据库，并重新生成扫描器读取的 `/scanner-config/runtime.json`。
- 扫描器**不读数据库、不读任何手工配置文件**，每轮只读这份投影；投影是派生文件，
  不要手工编辑。
- 显式环境变量（如 `docker compose run -e SAMPLE_STRIDE=512`）仍然优先于投影，便于临时覆盖。
- 查看生效值：
  ```bash
  docker compose exec -T scanner python /usr/local/bin/print-config.py --json
  docker compose exec -T scanner /usr/local/bin/doctor.sh
  ```

## 3. 保存事务与核对结果

每次保存都是一次可回滚的事务，界面不会把「已写入」显示成「已生效」：

1. 哈希乐观锁：页面打开后数据库被别处改过时返回 **409**，要求刷新/对比，绝不覆盖。
2. 类型与跨字段校验（`check-config.py` 干跑）失败则 **422**，数据库与投影都不落盘。
3. 写临时投影文件；在数据库事务中覆盖显式值、递增 revision、写版本记录与审计。
4. 原子替换投影，属主对齐到 `PUID:PGID`。
5. `CRON_SCHEDULE` 变更时调用 `apply-config.sh` 热重载；失败自动恢复数据库并重投影。
6. 在扫描容器内执行 `print-config.py` 核对生效值。

响应中的关键字段：

| 字段 | 含义 |
| --- | --- |
| `written` | 是否已提交数据库并生成投影 |
| `verification.status` | `verified` / `mismatch` / `unavailable` / `restart_required` |
| `effects.next_round` | 下一轮生效的键 |
| `effects.schedule_reloaded` | 调度是否已热重载 |
| `effects.restart_required` | 需要重启扫描容器的键 |
| `next_run` | 下次执行时间（按生效的 `TZ`） |

状态优先级：`mismatch` > `restart_required` > `unavailable` > `verified`。

## 4. 重启类参数

`TZ`、`RUN_ON_START` 在容器入口阶段读取，保存后必须重启扫描容器。
面板会返回 `restart_required` 并提供一键重启；重启面板自身不影响正在运行的扫描。

部署类参数（镜像、容器名、面板端口/监听、运行身份等）属 Docker 部署配置，
面板不展示、也不提供设置；探测路径、User-Agent、地址库文件名等内置策略同理；
明细表、固定保留与全量/国家列表文件名在「产物与发布 · 文件名调整」中维护。

## 5. 敏感值

- `GIT_TOKEN` 与带认证信息的代理 URL **只写不读**：接口只返回
  `configured: true/false`，永不返回明文。
- 敏感值在数据库中加密存放，密钥是 `panel-data/settings.key`（0600），与会话签名
  `secret.key` 分离。
- diff、审计、日志、版本历史统一脱敏；URL 中的 `user:pass@` 会被遮挡。
- `./panel-data` 可能含加密后的令牌与备份，备份/分享前注意保护。

## 6. 忘记密码

只重置密码，配置版本与审计记录都会保留：

```bash
docker compose exec panel python -m panel.cli reset-password
# 或非交互：
docker compose exec panel python -m panel.cli reset-password --password '<新密码>'
```

不要把删除 `panel.db` 当作恢复手段。

## 7. 反向代理与 HTTPS

- v1 只保证**根路径**反代（`https://panel.example.com/` → `panel:8080`），不支持子路径。
- 面板默认不信任 `X-Forwarded-*`；反代后设 `PANEL_TRUST_PROXY=true`，此时：
  - 来源 IP 取 `X-Forwarded-For` 首项（登录限速按「用户名 + IP」）；
  - `X-Forwarded-Proto=https` 时会话 Cookie 加 `Secure`。
- 局域网 HTTP 无内置 TLS；需要 HTTPS 请用你自己的反代。

## 8. 目录与备份

| 路径 | 内容 |
| --- | --- |
| `./panel-data/panel.db` | 应用参数、用户、配置版本、审计、轮次索引、地址库与产物元数据（含最近 30 份地址库历史） |
| `./panel-data/settings.key` | 配置加密密钥（首次启动生成，0600） |
| `./panel-data/secret.key` | 会话签名密钥（首次启动生成，0600） |

备份 `./panel-data` 即可恢复面板历史（应用参数、地址库、机房映射、产物元数据与有界
预览都在这份数据库里）；完整产物文件在 `scan-output` 卷里，命名卷里的投影文件可以重建。

## 9. 权限与安全边界

- 面板只操作**本项目的扫描容器**：按名称/compose 标签解析，前端不能传容器 ID 或任意路径。
- 可执行脚本是固定白名单（扫描一轮、应用调度、打印/校验配置），不经过 shell。
- 文件访问限制在 `OUTPUT_DIR`、`DATA_DIR`、`panel-data` 与配置投影目录内，解析后校验
  `relative_to`，拒绝路径穿越。
- 所有写操作要求 `X-CSRF-Token`；容器启停另需 `X-Confirm: restart|stop|start`。
