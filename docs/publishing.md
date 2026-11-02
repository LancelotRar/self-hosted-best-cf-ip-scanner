# 自动发布到 Git 仓库

[← 返回首页](../README.md) · [定时设置](scheduling.md)

默认关闭：产物只写在本机 `./output/`。开启后，每轮扫描结束会把产物同步到指定的 Git
仓库并提交推送。

## 配置

| 变量 | 取值 |
| --- | --- |
| `GIT_PUSH_ENABLED` | `true` |
| `GIT_REPO_URL` | 目标仓库 HTTPS 地址，如 `https://github.com/OWNER/REPO.git` |
| `GIT_TOKEN` | 具备该仓库 `contents:write` 权限的令牌 |
| `GIT_BRANCH` | 目标分支，默认 `main` |
| `GIT_OUTPUT_SUBDIR` | 产物在目标仓库中的目录，默认 `result` |

改完生效：

```bash
docker compose up -d --force-recreate
```

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
- 令牌泄露时直接在仓库侧吊销并覆盖 `.env`，无需改动镜像。

## 仓库侧效果

`./cache/repo` 是目标仓库的浅克隆，只在发布瞬间使用：

```
./cache/repo/
└── result/            # 由 GIT_OUTPUT_SUBDIR 决定
    ├── detail.csv
    ├── GLOBAL20.txt
    └── US50.txt
```

怀疑本地克隆状态异常时，删除后下一轮会重新克隆：

```bash
rm -rf ./cache/repo
```

## 不推送远端时的验证方式

目标仓库也可以填本地路径或 `file://`（此时不需要令牌），便于离线验证发布链路：

```dotenv
GIT_REPO_URL=file:///path/to/your/repo.git
```
