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

<table align="center">
<thead>
<tr>
<th align="center">检查项</th>
<th align="center">内容</th>
</tr>
</thead>
<tbody>
<tr><td align="center">生效配置</td><td align="center">版本、探测端点、端口、采样、代理豁免、发布目标、数据文件</td></tr>
<tr><td align="center">DNS</td><td align="center"><code>PROBE_HOST</code> 解析结果</td></tr>
<tr><td align="center">端点连通性</td><td align="center">默认路径与强制直连各请求一次，用于发现代理劫持</td></tr>
<tr><td align="center">候选 IP 抽样</td><td align="center">从库内取前几个网段的地址做 TCP 443 握手</td></tr>
<tr><td align="center">IP 库</td><td align="center">文件路径、行数、可解析网段、非法行、首末条、修改时间</td></tr>
<tr><td align="center">发布目标</td><td align="center"><code>git ls-remote</code> 是否可达（有令牌时带上鉴权）</td></tr>
<tr><td align="center">磁盘与权限</td><td align="center"><code>/output</code>、<code>/cache</code>、<code>/data</code> 可写性与剩余空间</td></tr>
<tr><td align="center">调度进程</td><td align="center">supercronic 是否在运行、容器时间</td></tr>
</tbody>
</table>

## 常见问题

<table align="center">
<thead>
<tr>
<th align="center">现象</th>
<th align="center">原因与处理</th>
</tr>
</thead>
<tbody>
<tr><td align="center"><code>TCP 握手测量 0/N 合格</code></td><td align="center">网络不通、端口被墙、<code>PROBE_PORTS</code> 选错。先降 <code>TCP_MIN_SUCCESS=1</code>、调大 <code>TCP_TIMEOUT=5</code>，并用 <code>doctor.sh</code> 看候选 IP 抽样握手是否成功</td></tr>
<tr><td align="center"><code>边缘端点校验后无合格候选</code></td><td align="center"><code>PROBE_HOST</code> 下线 / 关闭代理 / 证书异常；或候选全是 EIV 受限子池。用 <code>doctor.sh</code> 的端点连通性确认</td></tr>
<tr><td align="center">全部候选同一机房、延迟挤在窄带</td><td align="center">代理劫持：<code>NO_PROXY</code> 没豁免 <code>PROBE_HOST</code>，或宿主开了 TUN。见<a href="network.md">代理与直连</a></td></tr>
<tr><td align="center">容器反复重启，日志提示「配置不合法」</td><td align="center">启动校验未通过：缺 <code>PROBE_HOST</code>、数值越界、或代理未豁免 <code>PROBE_HOST</code>；日志会按编号列出全部问题。先在面板改好参数并保存，再 <code>docker compose up -d</code>（必要时 <code>--force-recreate</code>）</td></tr>
<tr><td align="center">日志提示「读取运行配置失败」或投影缺失</td><td align="center">面板没有成功启动/生成投影。看 <code>docker compose logs panel</code>，确认 <code>panel</code> 为 healthy；面板启动后会重建 <code>/scanner-config/runtime.json</code></td></tr>
<tr><td align="center">面板打不开 / 一直 502</td><td align="center"><code>docker compose ps</code> 看 <code>panel</code> 是否 Up；<code>docker compose logs panel</code> 看启动错误；确认 <code>PANEL_PORT</code> 未被占用、<code>PANEL_BIND</code> 允许你的来源网段</td></tr>
<tr><td align="center">面板提示「扫描容器不可用」</td><td align="center"><code>docker.sock</code> 未挂载或权限不足；面板仍可访问，只读页面与配置编辑可用，容器操作与生效核对会显示不可用</td></tr>
<tr><td align="center">面板显示「核对不一致」（mismatch）</td><td align="center">扫描器读到的值仍与面板保存值不同：确认没有另一处显式环境变量覆盖（compose <code>environment:</code> / <code>run -e</code>），再点「重新核对」；不要把它当「已生效」</td></tr>
<tr><td align="center">面板保存返回 409</td><td align="center">页面打开后数据库已被别处修改（另一个标签页/客户端）。面板不会覆盖任何一方：按提示重新加载，确认差异后再保存</td></tr>
<tr><td align="center">启动即退出，日志提示 <code>[错误] 环境变量 X 非法</code></td><td align="center">取值格式错误（不是整数 / 布尔 / 列表），按提示改正</td></tr>
<tr><td align="center">启动即退出，日志提示 <code>bad crontab line</code></td><td align="center"><code>CRON_SCHEDULE</code> 不是合法 cron 表达式，见<a href="scheduling.md">定时设置</a></td></tr>
<tr><td align="center">日志提示「目录不可写」</td><td align="center">挂载目录属主异常，按日志给出的 <code>chown</code> 命令处理，或检查部署参数 <code>PUID</code> / <code>PGID</code></td></tr>
<tr><td align="center">发布失败 + 401/403</td><td align="center"><code>GIT_TOKEN</code> 无效或缺少目标仓库 <code>contents:write</code></td></tr>
<tr><td align="center">发布失败 + 网络错误</td><td align="center">代理未生效或 <code>HTTPS_PROXY</code> 未配置</td></tr>
<tr><td align="center">拉取镜像失败</td><td align="center">网络问题：配置 <code>HTTP_PROXY</code> / <code>HTTPS_PROXY</code>，或改用 <code>compose.build.yaml</code> 本地构建</td></tr>
<tr><td align="center">某个列表没有更新</td><td align="center">看当轮日志是否报错；确认对应的 <code>*_TOP</code> 不是 <code>0</code>（0 = 不生成）</td></tr>
</tbody>
</table>

## 提 issue 请附上

- 完整日志：`docker compose logs --no-color > scanner.log`（不要只截片段）；
- `doctor.sh` 输出；
- 相关配置（面板「参数」页导出的值，**删除 `GIT_TOKEN` 等敏感信息**）；
- 宿主机架构与 Docker 版本：

```bash
uname -m && docker version --format '{{.Server.Version}}'
```
