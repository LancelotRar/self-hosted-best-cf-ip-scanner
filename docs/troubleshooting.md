# 故障排查

[← 返回首页](../README.md)

## 先看日志

```bash
docker compose logs -f --tail=200              # 实时
docker compose logs --no-color > scanner.log   # 导出
```

每轮日志包含：启动时的「生效配置」、两阶段合格/淘汰数与失败原因 top-5、每轮耗时、
产物清单、发布结果。

## 一键自检

```bash
docker compose exec scanner /usr/local/bin/doctor.sh
```

只读、不产物，检查以下内容：

| 检查项 | 内容 |
| --- | --- |
| 生效配置 | 版本、探测端点、端口、采样、代理豁免、发布目标、数据文件 |
| DNS | `PROBE_HOST` 解析结果 |
| 端点连通性 | 默认路径与强制直连各请求一次，用于发现代理劫持 |
| 候选 IP 抽样 | 从库内取前几个网段的地址做 TCP 443 握手 |
| IP 库 | 文件路径、行数、可解析网段、非法行、首末条、修改时间 |
| 发布目标 | `git ls-remote` 是否可达（有令牌时带上鉴权） |
| 磁盘与权限 | `/output`、`/cache`、`/data` 可写性与剩余空间 |
| 调度进程 | supercronic 是否在运行、容器时间 |

## 常见问题

| 现象 | 原因与处理 |
| --- | --- |
| `TCP 握手测量 0/N 合格` | 网络不通、端口被墙、`PROBE_PORTS` 选错。先降 `TCP_MIN_SUCCESS=1`、调大 `TCP_TIMEOUT=5`，并用 `doctor.sh` 看候选 IP 抽样握手是否成功 |
| `边缘端点校验后无合格候选` | `PROBE_HOST` 下线 / 关闭代理 / 证书异常；或候选全是 EIV 受限子池。用 `doctor.sh` 的端点连通性确认 |
| 全部候选同一机房、延迟挤在窄带 | 代理劫持：`NO_PROXY` 没豁免 `PROBE_HOST`，或宿主开了 TUN。见[代理与直连](network.md) |
| 容器反复重启，日志提示「配置不合法」 | 启动校验未通过：缺 `PROBE_HOST`、数值越界、或代理未豁免 `PROBE_HOST`；日志会按编号列出全部问题，修完 `docker compose up -d --force-recreate` |
| 启动即退出，日志提示 `[错误] 环境变量 X 非法` | 取值格式错误（不是整数 / 布尔 / 列表），按提示改正 |
| 启动即退出，日志提示 `bad crontab line` | `CRON_SCHEDULE` 不是合法 cron 表达式，见[定时设置](scheduling.md) |
| 日志提示「目录不可写」 | 挂载目录属主异常，按日志给出的 `chown` 命令处理，或检查 `PUID` / `PGID` |
| 发布失败 + 401/403 | `GIT_TOKEN` 无效或缺少目标仓库 `contents:write` |
| 发布失败 + 网络错误 | 代理未生效或 `HTTPS_PROXY` 未配置 |
| 拉取镜像失败 | 网络问题：配置 `HTTP_PROXY` / `HTTPS_PROXY`，或改用 `compose.build.yaml` 本地构建 |
| 某个列表没有更新 | 看当轮日志是否报错；确认对应的 `*_TOP` 不是 `0`（0 = 不生成） |

## 提 issue 请附上

1. 完整日志：`docker compose logs --no-color > scanner.log`（不要只截片段）；
2. `doctor.sh` 输出；
3. 相关配置行（**删除 `GIT_TOKEN` 等敏感信息**）；
4. 宿主机架构与 Docker 版本：

```bash
uname -m && docker version --format '{{.Server.Version}}'
```
