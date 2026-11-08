# 代理与直连

[← 返回首页](../README.md) · [配置手册](configuration.md)

> [!IMPORTANT]
> 本工具同时产生两类方向相反的流量，必须分开处理。配置错误时**不会报错**，只会产出
> 一批看似正常但整体无效的结果。

<table align="center">
<thead>
<tr>
<th align="center">流量</th>
<th align="center">典型目标</th>
<th align="center">是否走代理</th>
</tr>
</thead>
<tbody>
<tr><td align="center">出网（工具链）</td><td align="center"><code>git push</code>、拉取镜像、下载依赖</td><td align="center">大陆通常<strong>需要</strong>代理</td></tr>
<tr><td align="center">探测（被测量对象）</td><td align="center">TCP 握手到候选 <code>IP:端口</code>、端点校验到 <code>PROBE_HOST</code></td><td align="center"><strong>必须直连</strong></td></tr>
</tbody>
</table>

测量的是「你这台机器 → 这个 Cloudflare IP」的真实握手时延与落点。探测一旦走了代理，
测到的就是「你 → 代理 → 目标」：典型表现是所有候选集中到同一机房、延迟挤在很窄的区间。

正确组合是 **出网走代理 + 探测走直连**，`NO_PROXY` 就是用来切开这两类流量的开关。

## 机制

- `HTTP_PROXY` / `HTTPS_PROXY` 只影响"自己会读环境代理"的客户端。端点校验由
  curl_cffi（libcurl）发起，会读这两个变量；**TCP 握手用原始 socket，不读代理变量**，
  天然直连。
- `NO_PROXY` 是豁免清单，按域名后缀匹配。把 `PROBE_HOST` 加进去，端点校验才会从本机
  直接连到候选 IP。
- 端点校验靠 curl `RESOLVE` 把 `PROBE_HOST` 钉到候选 `IP:端口`。如果请求进了代理，
  代理只看到域名、用自己解析的地址建立隧道，**钉 IP 被完全绕过**；而 curl 依然收到
  `200 + colo`，表面上完全正常——这是最危险的地方：错了但不报错。
- 因此 `NO_PROXY` 必须覆盖 `PROBE_HOST`（写后缀即可，子域一并命中），大小写两种写法
  都写上，兼容只认其中一种的工具。

## 配置

在面板「参数 → 代理设置」里填写：

```text
# 出网走代理
HTTP_PROXY=http://192.168.1.2:7890
HTTPS_PROXY=http://192.168.1.2:7890

# 探测域名必须豁免（换成你自己的 PROBE_HOST）
NO_PROXY=localhost,127.0.0.1,::1,192.168.0.0/16,172.16.0.0/12,probe.example.com
no_proxy=localhost,127.0.0.1,::1,192.168.0.0/16,172.16.0.0/12,probe.example.com
```

启动校验：只要配了代理而 `NO_PROXY` 没豁免 `PROBE_HOST`，进程直接报错退出，不会静默
跑出一轮废数据。

## 透明代理 / TUN 模式

宿主或网关若开了 Clash TUN、OpenWrt 透明代理、路由器级全局代理，流量不经过环境变量，
`NO_PROXY` 不生效：连 TCP 握手都会被接管，测量彻底变成代理路径。此时需要：

- 在代理软件里给 Cloudflare 段（如 `104.16.0.0/13`、`172.64.0.0/13`）或容器所在网段
  设「直连」规则；或
- 让容器不经过 TUN（独立 bridge，指定直连网关）。

## 如何确认探测没被劫持

`doctor.sh` 会分别用「默认路径」和「强制直连」请求一次端点，两次结果应当一致：

```bash
docker compose exec scanner /usr/local/bin/doctor.sh | sed -n '/网络与连通性/,/IP 库/p'
```

<table align="center">
<thead>
<tr>
<th align="center">现象</th>
<th align="center">结论</th>
</tr>
</thead>
<tbody>
<tr><td align="center">两次 HTTP 状态与返回内容一致</td><td align="center">探测未走代理，正常</td></tr>
<tr><td align="center">强制直连失败、默认路径成功</td><td align="center">出网依赖代理，探测被代理接管</td></tr>
<tr><td align="center">两次客户端 IP 或返回内容不同</td><td align="center">代理在接管探测流量</td></tr>
</tbody>
</table>

运行结果还有另一个指纹：正常一轮通常包含多个机房、延迟有明显跨度；被劫持时集中在
单一机房。

## 变更探测域名时的同步项

需要同时改两处，缺一不可：

- 面板「参数 → 探测端点」的 `PROBE_HOST`；
- 该域名在 Cloudflare 上的代理（小黄云）状态。

改完在面板里保存即可；面板会自动把新域名追加到代理豁免清单（`NO_PROXY` / `no_proxy`）。
不需要手工编辑任何文件。保存后看面板的「核对状态」或执行
`docker compose exec -T scanner /usr/local/bin/startup-report.py`，确认
「代理 → NO_PROXY 豁免探测域名: 是」。
