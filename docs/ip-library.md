# 候选地址库

[← 返回首页](../README.md) · [配置手册](configuration.md)

扫描的输入完全来自一个文本文件：`./data/ip-library.txt`。它挂在宿主目录上，
**直接编辑即可维护**，改完下一轮扫描自动生效，不需要重启容器或重建镜像。

首次启动时容器会把镜像内置的默认库写入该文件；已有文件不会被覆盖。

## 条目格式

每行一个条目，支持三种写法：

```text
104.16.0.0/24          # 网段：展开后参与地址网格采样
104.17.3.3             # 单个 IP：等价 /32
104.18.4.4:8443        # IP:端口：固定条目，原样探测，不参与采样、端口不被替换
# 172.68.0.0/24         # 行首 # = 注释，不参与扫描
```

<table align="center">
<thead>
<tr>
<th align="center">写法</th>
<th align="center">体积</th>
<th align="center">用途</th>
</tr>
</thead>
<tbody>
<tr><td align="center">网段</td><td align="center">大</td><td align="center">常规维护：逐 <code>/24</code> 列举，便于增删</td></tr>
<tr><td align="center">单个 IP</td><td align="center">小</td><td align="center">精确加入某个地址</td></tr>
<tr><td align="center"><code>IP:端口</code></td><td align="center">小</td><td align="center">精确指定地址与端口，优先级最高</td></tr>
</tbody>
</table>

空行、`#` 开头的行、`cidr` / `ip` 这类表头行会被跳过。无法解析的行不会中断扫描，
只在日志里计数（`跳过 N 行无法解析的条目`）。

## 排除网段

**用注释，不要物理删除。** Cloudflare 的路由与 EIV 归属会变化，注释掉可以一行恢复：

```text
# 172.68.0.0/24   实测 TCP 不可达，2026-10 暂时移出
# 104.22.0.0/24    无合格产出
```

建议同时写明依据与日期，便于回溯。

## 采样关系

- 网段条目会先合并成连续地址区间（重叠、首尾相接的会被合并），再按地址网格每
  `SAMPLE_STRIDE`（默认 256，即一个 `/24`）抽 1 个代表 IP。
- `IP:端口` 条目不进采样队列，原样成为候选。
- 因此库越精简，单轮越快；想覆盖更密就减小 `SAMPLE_STRIDE`，或用
  `MAX_CANDIDATES` 限制单轮候选量。

## 机房映射

`./data/locations.json` 是「边缘机房代码 → 国家代码」的固定映射（如 `HKG` → `HK`），
决定订阅行里的国家与国旗。它是扁平 JSON：

```json
{
  "HKG": "HK",
  "NRT": "JP",
  "SIN": "SG"
}
```

- 缺映射不会报错，订阅行会回退显示机房代码（如 `#HKG`）。
- 可以直接增补；调试时可在 `.env` 里设 `SKIP_LOCATIONS=true` 跳过映射。

## 生效与验证

```bash
docker compose run --rm scan-once          # 立刻跑一轮（每轮都重新读文件）

# 看解析结果：行数 / 可解析网段数 / 非法行 / 首末条 / 修改时间
docker compose exec scanner /usr/local/bin/doctor.sh | sed -n '/===== IP 库/,/===== 磁盘/p'

# 看读取汇总
docker compose logs | grep "候选地址库"
```

## 权限

文件属主是 `PUID:PGID`（默认 `1000:1000`）。宿主机当前用户不是 1000 时，把 `.env`
的 `PUID` / `PGID` 改成 `id -u` / `id -g`，即可直接编辑。

容器启动时会把 `./data` 的属主重新对齐到 `PUID:PGID`，所以不必担心文件被写成 root 所有。

## 内容建议

- 底座：Cloudflare 官方 IPv4 段（<https://www.cloudflare.com/ips-v4>）展开为 `/24`。
- 不要引入 `1.0.0.0/24`、`1.1.1.0/24`：这是 CF DNS 解析器地址，扫描必然失败。
- 不要引入第三方「反代 IP」列表：多为 VPS 反代，ASN 不属于 AS13335，带宽与存活不可控。
- 想换用其它库文件：改 `.env` 的 `LIBRARY_FILE`，指向 `./data` 下的另一个文件名。
