# 运维面板

[← 返回首页](../README.md) · [配置手册](configuration.md)

面板是本项目的**默认、首选运维入口**：一个 compose 堆栈、两个容器（`scanner` +
`panel`）、同一个镜像。CLI、`docker compose run` 与手工编辑 `.env` 保留为备用/应急路径。

```
浏览器 ──▶ panel（FastAPI + Vue SPA）
              │  docker.sock（只操作本项目扫描容器）
              │  ./:/project（原子改写 .env）
              ▼
          scanner（supercronic + 扫描任务，每轮重读 .env）
```

## 1. 首次登录

1. `docker compose up -d` 后访问 `http://<宿主IP>:8080`（端口由 `PANEL_PORT` 决定）。
2. 首次打开进入「首次设置」，设置管理员密码（至少 8 个字符）。
3. 之后用该密码登录；忘记密码时见 §6。

> 面板默认监听 `PANEL_BIND=0.0.0.0`，局域网内可访问。只想本机访问就改成
> `127.0.0.1`（配合反向代理）。

## 2. `.env` 是唯一配置源

- 面板保存与手工编辑**同一个文件**：`./.env`（容器内 `/project/.env`）。
- 读取优先级：**显式环境变量 > `.env` > schema 默认值**；空值视为未设置。
- compose 不再用 `env_file` 注入参数；`docker compose exec scanner env` 不再直接
  显示扫描参数，要看生效值用：
  ```bash
  docker compose exec -T scanner python /usr/local/bin/print-config.py --json
  docker compose exec -T scanner /usr/local/bin/doctor.sh
  ```
- 临时覆盖仍然有效：
  ```bash
  docker compose run --rm -e SAMPLE_STRIDE=512 scan-once
  ```

## 3. 保存事务与核对结果

每次保存都是一次可回滚的事务，界面不会把「已写入」显示成「已生效」：

1. 哈希乐观锁：宿主同时改过 `.env` 时返回 **409**，要求刷新/对比，绝不覆盖。
2. 类型与跨字段校验（`check-config.py` 干跑）失败则 **422**，`.env` 不落盘。
3. 原子写入并保留属主/权限，写前自动备份完整 `.env`（`panel-data/backups/env/`，0600，保留 30 份）。
4. 写入后立即从磁盘回读比对；不一致自动回滚。
5. 在扫描容器内执行 `print-config.py` 核对生效值。
6. `CRON_SCHEDULE` 变更时调用 `apply-config.sh` 热重载；失败自动回滚。

响应中的关键字段：

| 字段 | 含义 |
| --- | --- |
| `written` | 是否落盘 |
| `verification.status` | `verified` / `mismatch` / `unavailable` / `restart_required` |
| `effects.next_round` | 下一轮生效的键 |
| `effects.schedule_reloaded` | 调度是否已热重载 |
| `effects.restart_required` | 需要重启扫描容器的键 |
| `next_run` | 下次执行时间（按生效的 `TZ`） |

状态优先级：`mismatch` > `restart_required` > `unavailable` > `verified`。

## 4. 重启类参数

`TZ`、`RUN_ON_START` 在容器入口阶段读取，保存后必须重启扫描容器。
面板会返回 `restart_required` 并提供一键重启；重启面板自身不影响正在运行的扫描。

部署类参数（镜像、容器名、面板端口、运行身份等）属底层部署配置，面板不展示；
探测路径、User-Agent、地址库文件名、运行身份等内置策略同理；
明细表、固定保留与全量/国家列表文件名在「产物与发布 · 文件名调整」中维护。

## 5. 敏感值

- `GIT_TOKEN` 与带认证信息的代理 URL **只写不读**：接口只返回
  `configured: true/false`，永不返回明文。
- diff、审计、日志、版本历史统一脱敏；URL 中的 `user:pass@` 会被遮挡。
- 完整 `.env` 备份与 `./panel-data` 可能含明文令牌，备份/分享前注意脱敏。

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
| `./panel-data/panel.db` | 用户、配置版本、审计、轮次索引 |
| `./panel-data/secret.key` | 会话签名密钥（首次启动生成，0600） |
| `./panel-data/backups/env/` | `.env` 自动备份（可能含明文令牌） |
| `./panel-data/backups/library/` | IP 库自动备份 |

备份 `./panel-data` 即可恢复面板历史（地址库、机房映射、产物快照都在这份数据库里）；命名卷里的投影文件可以重建。

## 9. 权限与安全边界

- 面板只操作**本项目的扫描容器**：按名称/compose 标签解析，前端不能传容器 ID 或任意路径。
- 可执行脚本是固定白名单（扫描一轮、应用调度、打印/校验配置），不经过 shell。
- 文件访问限制在 `OUTPUT_DIR`、`DATA_DIR`、`panel-data` 与项目 `.env` 内，解析后校验
  `relative_to`，拒绝路径穿越。
- 所有写操作要求 `X-CSRF-Token`；容器启停另需 `X-Confirm: restart|stop|start`。
