# 日常运维

[← 返回首页](../README.md) · [定时设置](scheduling.md) · [运维面板](panel.md)

## 面板优先

日常操作都在面板完成：`http://<宿主IP>:8080`

- 改参数 → 「参数」页保存（校验 → 写入 → 回读 → 核对 → 调度热重载 → 审计）；
- 立即跑一轮 → 「运行」页，实时看输出；
- 看日志 → 「日志」页（SSE、过滤、暂停、下载）；
- 看产物 / 编辑 IP 库 / 改发布参数 → 对应标签页；
- 重启或启停扫描容器 → 「系统 → 容器」。

下面的命令是备用/应急路径。

## 常用命令

```bash
docker compose up -d                      # 启动（scanner + panel）
docker compose run --rm scan-once         # 手动执行一轮（带锁，跑完即退出）
docker compose logs -f --tail=200         # 跟踪日志
docker compose pull && docker compose up -d   # 更新镜像
docker compose restart scanner            # 仅重启扫描容器（TZ / RUN_ON_START 等）
docker compose stop                       # 暂停（等当前一轮收尾，最多 150s；数据保留）
docker compose stop -t 5                  # 立即暂停（中断当前一轮，产物保留上一轮）
docker compose down                       # 停止并移除容器（数据保留）
```

## 运行身份

扫描镜像以 root 启动，但入口脚本只做一件事：把三个命名卷对齐到 `PUID:PGID`；
随后用 `su-exec` 降权，**业务进程全程非 root**。首次默认数据由面板播种，扫描器入口
不再复制出厂文件：

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

- 复用同一份镜像、部署参数与挂载，以非 root 身份运行，跑完即退出。
- 与定时任务共用一把锁：定时任务正在运行时，本轮会提示「已有一轮扫描在运行」并跳过，
  不会并发写产物。
- 临时改应用参数而不动面板（显式环境变量优先于投影）：

```bash
docker compose run --rm -e SAMPLE_STRIDE=512 scan-once
```

## 更新镜像

```bash
docker compose pull && docker compose up -d
```

版本标签在 `compose.yaml` 的镜像坐标里：`latest` 跟随最新，也可锁定 `sha-xxxxxxx` 或 `1.2.3`。

确认拉到的确实是新版本（镜像内置了源码提交号，便于核对）：

```bash
docker inspect ghcr.io/lancelotrar/self-hosted-best-cf-ip-scanner:latest   --format '{{ index .Config.Labels "org.opencontainers.image.revision" }}'
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
<tr><td align="center"><code>ip-data</code>（卷）</td><td align="center">地址库、机房映射、轮次记录 <code>runs.tsv</code> 与每轮指标 <code>runs/*.json</code></td><td align="center">地址库/映射由数据库重建；轮次记录与指标可按需清理</td></tr>
<tr><td align="center"><code>scan-output</code>（卷）</td><td align="center">明细表与订阅列表</td><td align="center">可随时删除，下一轮重新生成</td></tr>
<tr><td align="center"><code>publish-cache</code>（卷）</td><td align="center">目标仓库浅克隆</td><td align="center">可删除，下一轮重新克隆</td></tr>
<tr><td align="center"><code>scanner-config</code>（卷）</td><td align="center">应用参数投影 <code>runtime.json</code></td><td align="center">由面板重建；不要手工编辑</td></tr>
</tbody>
</table>

```bash
# 发布状态异常时重置克隆缓存
docker run --rm -v <compose项目名>_publish-cache:/cache alpine rm -rf /cache/repo
```

## 备份

真正需要备份的是 `./panel-data`（面板数据库：应用参数、地址库、机房映射、产物元数据与
有界预览、配置版本、审计与账号）。四个命名卷里的内容都能由数据库重建或由下一轮扫描
重新生成；完整产物文件在 `scan-output` 卷里，按需另行备份。

```bash
tar czf scanner-backup.tar.gz panel-data/
```
