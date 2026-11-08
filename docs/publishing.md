# 自动发布到 Git 仓库

[← 返回首页](../README.md) · [定时设置](scheduling.md)

默认关闭：产物只留在容器卷里、在面板中查看。开启后，每轮扫描结束会把产物同步到指定的 Git
仓库并提交推送。

## 配置

<table align="center">
<thead>
<tr>
<th align="center">变量</th>
<th align="center">取值</th>
</tr>
</thead>
<tbody>
<tr><td align="center"><code>GIT_PUSH_ENABLED</code></td><td align="center"><code>true</code></td></tr>
<tr><td align="center"><code>GIT_REPO_URL</code></td><td align="center">目标仓库 HTTPS 地址，如 <code>https://github.com/OWNER/REPO.git</code></td></tr>
<tr><td align="center"><code>GIT_TOKEN</code></td><td align="center">具备该仓库 <code>contents:write</code> 权限的令牌</td></tr>
<tr><td align="center"><code>GIT_BRANCH</code></td><td align="center">目标分支，默认 <code>main</code></td></tr>
<tr><td align="center"><code>GIT_OUTPUT_SUBDIR</code></td><td align="center">产物子目录；留空推送到仓库根目录</td></tr>
<tr><td align="center"><code>PUSH_LISTS</code></td><td align="center">只推送选中的全量/国家列表（JSON 数组）；留空推送全部</td></tr>
</tbody>
</table>

改完在面板「仓库设置」页保存即可，下一轮生效。
只有 `TZ` / `RUN_ON_START` 需要重启扫描容器。

目标仓库不需要预先存在任何提交：新建的空仓库也能直接发布，首次会创建
`GIT_BRANCH` 分支并提交产物。

## 同步语义

- **镜像语义**：目标目录下旧的 `*.txt` / `*.csv` 先删再拷，因此把某个 `*_TOP` 改成 0
  后不会留下孤儿文件。
- **只提交产物目录**：其它文件（README、脚本等）不受影响。
- **内容无变化不提交**：明细表含扫描时间，正常情况下每轮会产生一次提交。
- **提交信息**：`top cf ips scanned <北京时间> [skip ci]`，不会触发目标仓库的 CI。

## 失败与重试

- 推送失败按 `GIT_RETRY_MAX`（默认 3）次数退避重试，间隔 10s / 20s。
- 每次重试都会重新拉取远端最新提交，再覆盖产物目录后提交，因此并发推送不会冲突。
- 发布失败不影响下一轮定时任务，也不会清空本地产物。
- 失败原因会写在日志里：`[publish] ...` 开头。

## 令牌安全

- 令牌只通过 `http.extraheader` 注入到本次 git 进程，**不写入 `.git/config`**，
  也不出现在 `git remote -v` 或日志中。
- 建议使用细粒度令牌，仅授予目标仓库 `Contents: Read and write`。
- 令牌泄露时直接在仓库侧吊销，然后在面板「仓库设置」里更新访问令牌。

## 仓库侧效果

`publish-cache` 卷里的 `repo/` 是目标仓库的浅克隆，只在发布瞬间使用：

```
<卷 publish-cache>/repo/
└── result/            # 由 GIT_OUTPUT_SUBDIR 决定；留空则为仓库根目录
    ├── detail.csv
    ├── GLOBAL20.txt
    └── US50.txt
```

推送列表（`PUSH_LISTS`）只影响全量/国家列表；`detail.csv` 与固定保留列表始终跟随推送。

怀疑本地克隆状态异常时，清掉这个卷后下一轮会重新克隆：

```bash
docker run --rm -v <compose项目名>_publish-cache:/cache alpine rm -rf /cache/repo
```

## 不推送远端时的验证方式

目标仓库也可以填本地路径或 `file://`（此时不需要令牌），便于离线验证发布链路。
在面板「仓库设置 → 目标仓库」里填：

```text
file:///path/to/your/repo.git
```
