# 定时设置

[← 返回首页](../README.md) · [部署详解](deployment.md)

容器内由 cron 调度器（supercronic）驱动，按 `CRON_SCHEDULE` 周期性执行
「扫描 → 产出 → 发布」。时区由 `TZ` 决定，与宿主机时区无关。

## 变量

<table align="center">
<thead>
<tr>
<th align="center">变量</th>
<th align="center">默认值</th>
<th align="center">说明</th>
</tr>
</thead>
<tbody>
<tr><td align="center"><code>CRON_SCHEDULE</code></td><td align="center"><code>30 */6 * * *</code></td><td align="center">5 段（分 时 日 月 周）、6 段（+年）、7 段（秒+5 段+年）；不支持 <code>@daily</code> 宏</td></tr>
<tr><td align="center"><code>RUN_ON_START</code></td><td align="center"><code>true</code></td><td align="center">容器启动后立即执行一轮，再进入调度</td></tr>
<tr><td align="center"><code>TZ</code></td><td align="center"><code>Asia/Shanghai</code></td><td align="center">调度与提交信息时区；产物中的扫描时间固定为北京时间</td></tr>
</tbody>
</table>

## 常用写法

<table align="center">
<thead>
<tr>
<th align="center">需求</th>
<th align="center">取值</th>
</tr>
</thead>
<tbody>
<tr><td align="center">每 6 小时的第 30 分（默认）</td><td align="center"><code>30 */6 * * *</code></td></tr>
<tr><td align="center">每 2 小时整点</td><td align="center"><code>0 */2 * * *</code></td></tr>
<tr><td align="center">每小时整点</td><td align="center"><code>0 * * * *</code></td></tr>
<tr><td align="center">每天 03:00</td><td align="center"><code>0 3 * * *</code></td></tr>
<tr><td align="center">每天 03:00 与 15:00</td><td align="center"><code>0 3,15 * * *</code></td></tr>
<tr><td align="center">工作日 08:00</td><td align="center"><code>0 8 * * 1-5</code></td></tr>
<tr><td align="center">每 15 分钟</td><td align="center"><code>*/15 * * * *</code></td></tr>
</tbody>
</table>

需要秒级精度时写 7 段（秒 分 时 日 月 周 年），如 `*/30 * * * * * *` 表示每 30 秒。
注意 6 段的第 6 位是**年**（supercronic 语义），`*/30 * * * * *` 是每 30 分钟，不是每 30 秒。

cron 字段含义：

```
┌──────── 分 (0-59)
│ ┌────── 时 (0-23)
│ │ ┌──── 日 (1-31)
│ │ │ ┌── 月 (1-12)
│ │ │ │ ┌ 周 (0-6，0 = 周日)
│ │ │ │ │
* * * * *
```

## 生效与观察

```bash
# 面板「调度」页保存即热重载；手工编辑 .env 由 watcher 在 5 秒内自动重载
docker compose logs -f scanner            # 每轮开始与结束都会打印
docker compose exec -T scanner /usr/local/bin/apply-config.sh   # 手动触发一次重渲染
```

- 支持 5 段、6 段（+年）与 7 段（秒+5 段+年）；不接受 `@daily` 这类宏。
- `apply-config.sh` 失败时保留旧 crontab 并记录错误，调度器不会静默停摆。

## 行为说明

- **不会并发**：上一轮未结束时，下一轮不会叠加。单轮耗时超过间隔时，日志会给出
  `job took too long to run` 警告。
- **手动执行不影响计划**：`docker compose run --rm scan-once` 立即跑一轮，与定时任务
  共用一把锁；定时任务正在运行时本轮跳过，计划保持不变。
- **暂停 / 恢复**：`docker compose stop` 停止（`./data`、`./output` 保留）。停止会等
  当前这一轮收尾（`stop_grace_period` 默认 150s），避免打断正在进行的产物推送；
  想立即中断用 `docker compose stop -t 5`。`docker compose start` 恢复后按
  `RUN_ON_START` 决定是否立刻跑一轮。
- **首轮不阻塞启动**：`RUN_ON_START=true` 时那一轮在后台执行，调度器立即接管，
  因此启动扫描期间停止容器也能秒级退出。
- **单轮耗时参考**：全量约 4161 个候选时约 2 分钟；用 `MAX_CANDIDATES` 限制候选量可
  显著缩短。

## 和产物发布的关系

定时任务每轮结束都会尝试发布（`GIT_PUSH_ENABLED=true` 时）。发布失败不影响下一轮
调度，只会在当轮日志里报错并按 `GIT_RETRY_MAX` 重试。详见 [自动发布](publishing.md)。
