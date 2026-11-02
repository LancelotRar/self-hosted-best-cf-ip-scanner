# 日常运维

[← 返回首页](../README.md) · [定时设置](scheduling.md)

## 常用命令

```bash
docker compose up -d                      # 启动
docker compose up -d --force-recreate     # 应用 .env 改动
docker compose run --rm scan-once         # 手动执行一轮（带锁，跑完即退出）
docker compose logs -f --tail=200         # 跟踪日志
docker compose pull && docker compose up -d   # 更新镜像
docker compose restart                    # 重启调度器
docker compose stop                       # 暂停（等当前一轮收尾，最多 150s；数据保留）
docker compose stop -t 5                  # 立即暂停（中断当前一轮，产物保留上一轮）
docker compose down                       # 停止并移除容器（数据保留）
```

## 运行身份

镜像以 root 启动，但入口脚本只做两件事：把 bind mount 的宿主目录对齐到 `PUID:PGID`、
首次播种默认数据；随后用 `su-exec` 降权，**业务进程全程非 root**：

```bash
docker compose exec -T scanner sh -c 'grep ^Uid /proc/1/status'   # Uid: 1000
docker compose exec -T scanner ps                                  # 进程 USER 均为 scanner
```

> [!NOTE]
> `docker compose exec` 默认以镜像的 root 身份进入容器（与业务进程无关）。
> 想用与业务一致的身份操作文件，加 `-u`：
> `docker compose exec -u 1000 scanner sh`

## 手动执行一轮

```bash
docker compose run --rm scan-once
```

- 复用同一份配置（镜像 / 环境变量 / 挂载），以非 root 身份运行，跑完即退出。
- 与定时任务共用一把锁：定时任务正在运行时，本轮会提示「已有一轮扫描在运行」并跳过，
  不会并发写产物。
- 临时改参数而不动 `.env`：

```bash
docker compose run --rm -e MAX_CANDIDATES=200 scan-once
```

## 更新镜像

```bash
docker compose pull && docker compose up -d
```

版本标签在 `.env` 的 `IMAGE_TAG`：`latest` 跟随最新，也可锁定 `sha-xxxxxxx` 或 `1.2.3`。

确认拉到的确实是新版本（镜像内置了源码提交号，便于核对）：

```bash
docker inspect ghcr.io/lancelotrar/best-cf-ip-scanner-docker:latest   --format '{{ index .Config.Labels "org.opencontainers.image.revision" }}'
```

> [!NOTE]
> 新版本发布后立刻 `pull` 可能仍拿到上一个镜像（镜像仓库推送有时间差）。
> 建议等发布流水线跑完再更新；用上面的命令核对 revision 是否为新提交。

## 日志

```bash
docker compose logs -f --tail=200              # 实时
docker compose logs --no-color > scanner.log   # 导出
```

日志包含：启动时的「生效配置」、两阶段合格/淘汰数与失败原因 top-5、每轮耗时、产物清单、
发布结果。容器日志按 10MB × 3 个文件轮转。

## 数据与清理

<table align="center">
<thead>
<tr>
<th align="center">目录</th>
<th align="center">内容</th>
<th align="center">清理方式</th>
</tr>
</thead>
<tbody>
<tr><td align="center"><code>./data</code></td><td align="center">候选地址库、机房映射</td><td align="center"><strong>不要删</strong>，删了会重新播种内置默认值</td></tr>
<tr><td align="center"><code>./output</code></td><td align="center">明细表与订阅列表</td><td align="center">可随时删除，下一轮重新生成</td></tr>
<tr><td align="center"><code>./cache/repo</code></td><td align="center">目标仓库浅克隆</td><td align="center">可删除，下一轮重新克隆</td></tr>
</tbody>
</table>

```bash
rm -rf ./cache/repo        # 发布状态异常时重置
rm -rf ./output            # 清空历史产物
```

## 备份

需要备份的只有 `./data`（地址库与机房映射，属于人工维护内容）和 `.env`（配置）。
产物可由任意一轮扫描重新生成，不必备份。

```bash
tar czf scanner-backup.tar.gz .env data/
```
