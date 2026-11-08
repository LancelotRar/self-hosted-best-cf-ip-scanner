# 测试与上线门禁

[← 返回首页](../README.md) · [运维面板](panel.md)

任何失败都不允许用 `--no-verify`、跳过用例或放宽断言绕过；先修根因。

## 1. 分层与运行命令

| 层 | 命令 | 覆盖 |
| --- | --- | --- |
| 单元 | `python -m pytest -q` | schema 默认值落库、配置事务与加密落库、JSON 投影解析、cron 5/6/7 段（supercronic 语义）、脱敏、轮次解析、路径安全、认证与限速 |
| API 集成 | 同上（`tests/test_*_api.py`） | 认证/CSRF、配置保存事务与核对、409 冲突、回滚、调度、运行/SSE、日志、产物、IP 库、发布、系统 |
| 脚本/配置契约 | `pytest tests/test_scripts.py -q` | `sh -n` 全部脚本、Python 脚本可编译、仓库无配置文件模板、compose 拓扑、无 `shell=True` |
| 前端单元 | `npm --prefix panel/web run test` | auth/config store、`ParamField` 值转换 |
| 前端静态检查 | `npm --prefix panel/web run lint` | ESLint + Vue/TS 规则 |
| 前端类型/构建 | `npm --prefix panel/web run typecheck && npm --prefix panel/web run build` | Vue + TS 严格模式与生产构建、路由拆分 |
| 镜像/Compose 冒烟 | CI `smoke` job | scanner/panel 双镜像、scanner healthy、`/healthz`、首次设置页、运行配置投影生成与每轮重读、`run -e` 优先级 |
| 依赖/镜像扫描 | CI `security` + `build` job | pip-audit、npm audit、Trivy HIGH/CRITICAL |
| E2E | `npm --prefix panel/web run e2e` | 首次设置/登录、保存结果面板、取消/非法值、409 冲突、日志连接状态、空产物、IP 库行错误、发布空态 |
| 人工上线 | 见 §5 | 真实域名、真实发布、Windows Docker Desktop、反代、备份恢复 |

后端覆盖率门禁：

```bash
python -m pytest -q \
  --cov=panel \
  --cov=scanner \
  --cov-fail-under=80
```

覆盖率覆盖面板与整个 scanner 包；核心探测逻辑有离线单元测试，不依赖真实网络。

## 2. 可测试性约定

- 外部依赖全部可注入：`Settings`、`ScannerController`、候选配置校验器、时钟。
  业务代码不直接 `docker.from_env()`、不读真实 `/panel-data`。
- 测试只用 `tmp_path` 与 fake 控制器：不访问网络、不写真实 `panel-data`/`data`/`output`、
  不使用真实令牌或仓库。
- SSE 的 fake 生成器必须有界，测试不能依赖超时结束。

## 3. 本地全量验证

```bash
# 后端
python -m pytest -q --cov=panel --cov=scanner --cov-fail-under=80

# 契约
for f in scanner/docker/*.sh panel/docker/*.sh tests/scripts/*.sh; do sh -n "$f"; done
python -m pytest tests/test_scripts.py -q

# 前端
npm --prefix panel/web run lint
npm --prefix panel/web run typecheck
npm --prefix panel/web run build
npm --prefix panel/web run test
```

## 4. E2E 环境准备

E2E 需要一套**干净**的真实栈（CI 由 `e2e` job 自动准备）：

```bash
rm -rf panel-data
docker compose down -v            # 数据与产物在命名卷里，清空才算干净栈
docker build -f scanner/Dockerfile -t ghcr.io/lancelotrar/self-hosted-best-cf-ip-scanner:latest .
docker build -f panel/Dockerfile -t ghcr.io/lancelotrar/self-hosted-best-cf-ip-scanner-panel:latest .
cp compose.example.yaml compose.yaml
docker compose up -d

npm --prefix panel/web exec playwright install --with-deps chromium
PANEL_URL=http://127.0.0.1:8080 E2E_PASSWORD=e2e-correct-horse npm --prefix panel/web run e2e
```

E2E 不依赖真实扫描成功：只验证运行流、错误与空态提示。应用参数使用数据库默认值；
需要特定参数时通过面板保存，不存在配置文件入口。仅允许 1 次基础设施重试；
连续失败按缺陷处理。

## 5. CI 门禁（全部通过才允许合并/发布）

| Job | 内容 |
| --- | --- |
| `backend` | `pip check` 无冲突；pytest + 覆盖率 ≥ 80% |
| `frontend` | `npm ci` → `lint` → `typecheck` → `build` → `test` |
| `contract` | `for f in scanner/docker/*.sh panel/docker/*.sh tests/scripts/*.sh; do sh -n "$f"; done`；默认 compose 配置校验 |
| `build` | scanner 与 panel 两个 Dockerfile 构建成功；Trivy 扫描 HIGH/CRITICAL |
| `security` | pip-audit（两个 requirements）+ npm audit（high） |
| `smoke` | 启动默认栈；scanner healthy；面板 `/healthz` 200；默认无 socket/cap_drop/本机端口；运行配置投影生成且每轮重读；`run -e` 优先 |
| `e2e` | 干净 `panel-data` 启动真实栈（面板直连 docker.sock），Playwright 串行执行关键流程 |

### 5.1 安全扫描豁免

- **Python**：在 `ci.yml` 的 `pypa/gh-action-pip-audit` 步骤用 `ignore-vulns` 列出
  GHSA/PYSEC；PR 描述必须写原因、影响面与到期时间。
- **npm**：`npm audit` 不支持按 ID 豁免；只能升级依赖，或在 PR 中临时调整
  `--audit-level` 并说明原因，禁止静默跳过。
- **镜像**：在根目录 `.trivyignore` 每行写一个 CVE/GHSA/AVD，附注释与到期时间。
- 任何豁免都要在 PR 中可见，不允许用 `continue-on-error` 掩盖。

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
- [ ] 面板改参数 → 核对通过 → 下一轮日志出现新值。
- [ ] 面板保存敏感值（令牌）后落库加密，页面/日志/审计不出现明文。
- [ ] 首次启动把 schema 默认值写入数据库，面板与扫描器一致。
- [ ] cron 热重载后按新时间触发（5 段与 7 段含秒各验一次）。
- [ ] 手动执行、日志实时流、产物预览/下载、IP 库保存/恢复。
- [ ] 发布到测试仓库成功；令牌未出现在页面/日志/审计。
- [ ] 面板重启、扫描容器重启、备份恢复。
- [ ] 反向代理（根路径）与 HTTPS 下 Cookie/CSRF 正常。
- [ ] Windows Docker Desktop 与 Linux 各一台验证（原子替换与目录挂载）。
- [ ] 工作区无未预期文件、无敏感信息、镜像 digest 已记录。
