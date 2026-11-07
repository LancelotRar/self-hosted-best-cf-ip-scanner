# 测试与上线门禁

[← 返回首页](../README.md) · [运维面板](panel.md)

任何失败都不允许用 `--no-verify`、跳过用例或放宽断言绕过；先修根因。

## 1. 分层与运行命令

| 层 | 命令 | 覆盖 |
| --- | --- | --- |
| 单元 | `python -m pytest -q` | `.env` 解析（CRLF/引号/行内注释）、schema 与配置优先级、cron 5/6/7 段（supercronic 语义）、脱敏、轮次解析、路径安全、认证与限速 |
| API 集成 | 同上（`tests/test_*_api.py`） | 认证/CSRF、配置保存事务与核对、409 冲突、回滚、调度、运行/SSE、日志、产物、IP 库、发布、系统 |
| 脚本/配置契约 | `pytest tests/test_scripts.py -q` | `sh -n` 全部脚本、Python 脚本可编译、`.env.example` 可解析、compose 拓扑、无 `shell=True` |
| 前端单元 | `npm --prefix web run test` | auth/config store、`ParamField` 值转换 |
| 前端类型/构建 | `npm --prefix web run typecheck && npm --prefix web run build` | Vue + TS 严格模式与生产构建 |
| 镜像/Compose 冒烟 | CI `smoke` job | 单镜像双容器、scanner healthy、`/healthz`、首次设置页、`.env` 热读取、`run -e` 优先级 |
| E2E | `npm --prefix web run e2e` | 首次设置/登录、保存结果面板、取消/非法值、409 冲突、日志连接状态、空产物、IP 库行错误、发布空态 |
| 人工上线 | 见 §5 | 真实域名、真实发布、Windows Docker Desktop、反代、备份恢复 |

后端覆盖率门禁：

```bash
python -m pytest -q \
  --cov=panel \
  --cov=scanner/dotenv.py \
  --cov=scanner/schema.py \
  --cov=scanner/runtime_env.py \
  --cov-fail-under=80
```

覆盖率只针对面板与配置单源模块；不为数字给扫描核心补无意义测试。

## 2. 可测试性约定

- 外部依赖全部可注入：`Settings`、`ScannerController`、候选配置校验器、时钟。
  业务代码不直接 `docker.from_env()`、不读真实 `/panel-data`。
- 测试只用 `tmp_path` 与 fake 控制器：不访问网络、不写真实 `.env`/`data`/`output`、
  不使用真实令牌或仓库。
- SSE 的 fake 生成器必须有界，测试不能依赖超时结束。

## 3. 本地全量验证

```bash
# 后端
python -m pytest -q --cov=panel --cov=scanner/dotenv.py --cov=scanner/schema.py \
  --cov=scanner/runtime_env.py --cov-fail-under=80

# 契约
sh -n docker/*.sh scripts/*.sh
python -m pytest tests/test_scripts.py -q

# 前端
npm --prefix web run typecheck
npm --prefix web run build
npm --prefix web run test
```

## 4. E2E 环境准备

E2E 需要一套**干净**的真实栈（CI 由 `e2e` job 自动准备）：

```bash
rm -rf panel-data
docker compose down -v            # 数据与产物在命名卷里，清空才算干净栈
cp compose.example.yaml compose.yaml
cp .env.example .env
sed -i 's|^PROBE_HOST=.*|PROBE_HOST=probe.example.com|' .env
sed -i 's|^RUN_ON_START=.*|RUN_ON_START=false|' .env
sed -i 's|^PANEL_PORT=.*|PANEL_PORT=18080|' .env
docker compose up -d --build

npm --prefix web exec playwright install --with-deps chromium
PANEL_URL=http://127.0.0.1:18080 E2E_PASSWORD=e2e-correct-horse npm --prefix web run e2e
```

E2E 不依赖真实扫描成功：只验证运行流、错误与空态提示。仅允许 1 次基础设施重试；
连续失败按缺陷处理。

## 5. CI 门禁（全部通过才允许合并/发布）

| Job | 内容 |
| --- | --- |
| `backend` | `pip check` 无冲突；pytest + 覆盖率 ≥ 80% |
| `frontend` | `npm ci` → `typecheck` → `build` → `test` |
| `contract` | `sh -n docker/*.sh scripts/*.sh`；`docker compose config --quiet` |
| `build` | 单镜像（含前端 Node 构建阶段）构建成功 |
| `smoke` | 启动两个容器；scanner healthy；面板 `/healthz` 200；首次设置页可访问；`.env` 热读取；`run -e` 优先 |
| `e2e` | 干净 `panel-data` 启动真实栈，Playwright 串行执行关键流程 |

## 6. 兼容性矩阵

| 组件 | 版本 |
| --- | --- |
| Python | 3.13 |
| Node | 24 LTS |
| Docker Engine | 24+（含 compose v2） |
| 浏览器（E2E） | Chromium（Playwright 内置）；开发期另用系统 Edge |
| 时区数据 | 容器内 `tzdata`（Alpine 包） |

## 7. 人工上线检查清单

- [ ] 用真实 `PROBE_HOST` 跑完一轮，产物符合预期。
- [ ] 面板改参数 → 核对通过 → 下一轮日志出现新值；手工改 `.env` 同样验证。
- [ ] cron 热重载后按新时间触发（5 段与 7 段含秒各验一次）。
- [ ] 手动执行、日志实时流、产物预览/下载、IP 库保存/恢复。
- [ ] 发布到测试仓库成功；令牌未出现在页面/日志/审计。
- [ ] 面板重启、扫描容器重启、备份恢复。
- [ ] 反向代理（根路径）与 HTTPS 下 Cookie/CSRF 正常。
- [ ] Windows Docker Desktop 与 Linux 各一台验证（原子替换与目录挂载）。
- [ ] 工作区无未预期文件、无敏感信息、镜像 digest 已记录。
