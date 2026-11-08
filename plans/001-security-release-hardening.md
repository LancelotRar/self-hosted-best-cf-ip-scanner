# 001 — 安全边界与发布链路加固（Orchestrated Plan）

**状态：** S1–S6 与 Step 1–4、Step 6 已完成；Step 5 本地 + TrueNAS 运行时 smoke 完成，E2E/arm64/Trivy 待 CI
**分支：** `refactor/security-release-hardening`（从 `feat/ops-panel` 切出）
**合并策略：** 不合并、不推送 `main`；CI 改动只存在于本分支
**修订：** 3（按 `plan-orchestrate` 重写计划文件）

---

## 1. 目标与范围

### 目标

在不改扫描器业务逻辑、不改面板视觉结构的前提下，把默认部署从
“面板 root + docker.sock + 0.0.0.0 + 首次 setup 开放”收紧为
“默认安全、容器控制可选”，并修复发布漏发、SQLite 并发、会话失效等 P0/P1 问题。

### 已完成范围（S1–S6）

- compose 默认安全化 + 可选 `compose.control.yaml`
- 面板安全响应头、session epoch、setup token、登录限速有界、审计保留上限
- SQLite `LockedConnection` + lifespan 关闭
- 发布 workflow paths、SBOM/provenance、Dependabot、actions SHA 固定
- README/deployment 修正、SECURITY/CONTRIBUTING/issue 模板
- 后端 197 tests / 覆盖率 82.05%；前端 26 tests + typecheck/build

### 剩余范围（本文件后续步骤）

- 全量验证（Step 5，手动 `/test-coverage` + `/code-review`）
- 文档与发布说明（Step 6，手动 `/update-docs`）

### Out of scope（整体）

- 多主机 / Swarm / Kubernetes 部署
- 重新设计面板视觉与交互
- 自动修复依赖漏洞
- 全量 `ruff format` / mypy 迁移

---

## 2. TDD 执行协议

每个可测试行为按 **Red → Green → Refactor → Verify** 循环：

1. 先写一个失败测试，只描述一个可观察行为；
2. 写最小实现让测试通过；
3. 不改变行为的前提下整理；
4. 跑该步骤的完整验证命令，更新验证矩阵；
5. 不提交、不推送、不合并 `main`。

测试 seam：

| 步骤 | 测试 seam | 测试文件 |
| --- | --- | --- |
| S1 | compose YAML 解析结果 | `tests/test_compose_security.py` |
| S2 | TestClient HTTP 行为 + `LoginLimiter` | `tests/test_auth.py`、`tests/test_health.py` |
| S3 | `panel.db.connect` 并发事务 | `tests/test_db.py` |
| S4 | workflow YAML 解析 | `tests/test_ci_contract.py` |
| 后续 | 对应模块的公开接口 | 新增/扩展测试文件 |

---

## 3. 已完成步骤与证据

| 步骤 | 内容 | 证据 |
| --- | --- | --- |
| S1 | 默认只绑 `127.0.0.1`、无 docker.sock、cap_drop ALL、只读 `/output` `/cache`、资源限制、控制 overlay | `tests/test_compose_security.py` 6 passed |
| S2 | 安全响应头、setup token、session epoch、登出/改密失效、限速上限、审计保留 | `tests/test_auth.py`、`tests/test_health.py`、`tests/test_db.py` |
| S3 | SQLite 写事务串行化、shutdown 关闭 | `test_writes_on_shared_connection_are_serialized` |
| S4 | 发布 paths、SBOM/provenance、覆盖率扩到 scanner、contract/smoke/e2e、actions SHA、Dependabot | `tests/test_ci_contract.py` 8 passed |
| S5 | README/deployment 修正、SECURITY/CONTRIBUTING/issue 模板 | 文档 diff |
| S6 | 全量验证 | 后端 197 passed / 82.05%；前端 26 passed + typecheck + build |

**未执行的验证：** 本机无 Docker CLI/daemon，未实际运行 `docker compose up`、镜像构建、
arm64 构建与运行时 capability 检查；CI 工作流仅做 YAML 契约测试。运行时 smoke 需在
有 Docker 的环境执行。

---

## 4. Plan-Orchestrate 结果（剩余工作）

**Plan**: `plans/001-security-release-hardening.md`
**Steps**: 6（Step 1–4 已完成）
**Emitted**: 0 · **Done**: 4 · **Blocked**: 2

### Steps overview

| # | Title | Tags | Command | Status |
| --- | --- | --- | --- | --- |
| 1 | 拆分 scanner/panel 镜像 | refactor | `/orch-refine-code` | done |
| 2 | 前端 lint / 懒加载 / 按需引入 | refactor | `/orch-refine-code` | done |
| 3 | 可选 Docker 控制 sidecar | impl, security | `/orch-add-feature` | done |
| 4 | 依赖与镜像安全扫描 | change | `/orch-change-feature` | done |
| 5 | 全量验证 | test, review | `/test-coverage` | local + TrueNAS smoke done; E2E/arm64/Trivy pending |
| 6 | 文档与发布说明 | docs | `/update-docs` | done（手动） |

---

### Step 1 — 拆分 scanner/panel 镜像

**Intent**: 把单镜像拆成 scanner 与 panel 两个 build target，减少各自攻击面与体积，
保持默认安全配置与现有行为不变。
**Tags**: refactor
**Command rationale**: 行为保持的结构性重构，使用 `/orch-refine-code`；拆分范围与
验收条件写入任务描述。

```bash
/orch-refine-code "[Plan: plans/001-security-release-hardening.md#step-1] 将单镜像拆为 scanner 与 panel 两个 build target：scanner 仅保留 curl_cffi/git/supercronic，panel 仅保留 FastAPI/uvicorn/docker SDK/argon2/cryptography；更新 compose 与 CI 矩阵，保持默认无 socket、端口/挂载/能力限制不变；Acceptance: 两个 target 均可构建并启动；scanner 镜像不含 panel 依赖；panel 镜像不含 git/supercronic；smoke/e2e 通过；Out of scope: UI 视觉调整与多主机部署"
```

**Step 1 完成记录（TDD）：**

- Red：`tests/test_image_split.py` 5 failed（无 scanner/panel target、compose 未分 target、CI 未双构建、`scanner` 包急切导入 probe）。
- Green：
  - `Dockerfile` 拆为 `web` / `python-base` / `scanner-builder` / `panel-builder` / `scanner` / `panel`。
  - `scanner/__init__.py` 改为 `__getattr__` 按需导入；panel 可在 `curl_cffi` 缺失时导入。
  - `compose.example.yaml` panel 镜像改为 `...-panel:latest`；`compose.build.yaml` 增加 `target`。
  - `ci.yml` / `docker.yml` 分别构建并发布 scanner、panel 两个 target。
- Verify：`tests/test_image_split.py` 7 passed；全量 204 passed；覆盖率约 82%；前端 26 tests + typecheck。
- 未验证：本机无 Docker CLI，未实际构建两个镜像与 arm64；需在 CI/有 Docker 环境跑 smoke。

### Step 2 — 前端 lint / 懒加载 / 按需引入

**Intent**: 增加前端静态检查与构建优化，保持现有页面行为与视觉不变。
**Tags**: refactor
**Command rationale**: 行为保持的前端工程化重构；`/orch-refine-code` 负责重构、
测试与审查，验收标准携带在任务描述中。

```bash
/orch-refine-code "[Plan: plans/001-security-release-hardening.md#step-2] 为 web 增加 ESLint 或 Biome，并把路由改为懒加载、Element Plus 改为按需引入；保持现有页面行为与视觉不变；Acceptance: lint 通过；首屏 JS 体积明显下降并拆分 chunk；typecheck/unit/e2e 通过；Out of scope: 重新设计 UI 或改交互"
```

**Step 2 完成记录（TDD）：**

- Red：`web/src/__tests__/router.spec.ts` 失败（页面组件仍是静态对象）。
- Green：
  - 路由页面改为 `() => import(...)`，`router.spec.ts` 断言所有页面组件为函数。
  - `unplugin-vue-components` + `ElementPlusResolver` 按需引入组件与样式；
    `main.ts` 移除全量 `ElementPlus` 与 `element-plus/dist/index.css`。
  - `App.vue` 用 `el-config-provider` 保留中文 locale。
  - 新增 `eslint.config.js` 与 `npm run lint`，CI frontend job 执行 lint。
- Verify：前端 27 tests；lint/typecheck/build 通过；JS 1,121 KB → 583 KB，
  CSS 406 KB → 188 KB，产物拆为 19 个 JS chunk。
- 未验证：Playwright e2e 需要 Docker，本机未运行。

### Step 3 — 可选 Docker 控制 sidecar

**Intent**: 默认不挂载 docker.sock；需要日志/立即执行/启停时，通过固定操作的
sidecar 访问 Docker API，而不是把完整 Engine API 暴露给面板。
**Tags**: impl, security
**Command rationale**: 新增安全能力，`/orch-add-feature` 覆盖实现、测试与审查；
安全边界与“拒绝任意容器/任意命令”的验收条件写入任务描述。

```bash
/orch-add-feature "[Plan: plans/001-security-release-hardening.md#step-3] 实现可选 Docker 控制 sidecar：默认 compose 不挂 docker.sock；sidecar 只暴露状态/日志/执行一轮/启停固定操作，panel 通过私有网络调用；Acceptance: 默认栈无 socket；启用 sidecar 后日志/运行/启停可用；sidecar 拒绝任意容器与任意命令；测试与文档更新；Out of scope: 多主机与 Swarm"
```

**Step 3 完成记录（TDD）：**

- Red：`tests/test_control_sidecar.py`、`tests/test_http_control.py` 导入失败；
  `tests/test_compose_security.py` 仍期望 panel 直接挂 socket。
- Green：
  - 新增 `panel/control_sidecar.py`：固定 action（run/apply-config/print-config/
    restart/stop/start/logs/status/stats），可选 `X-Control-Token`。
  - 新增 `panel/http_control.py`：panel 侧 `HttpController`，映射固定脚本，不传任意命令。
  - `panel/settings.py` 读取 `SCANNER_CONTROL_URL` / `SCANNER_CONTROL_TOKEN`；
    `panel/deps.py` 优先使用 HTTP 控制器。
  - `compose.control.yaml` 改为 `scanner-control` sidecar 持有 socket；panel 通过
    internal `control` 网络调用，不再挂 socket。
  - README/deployment/panel/troubleshooting 同步说明。
- Verify：`tests/test_control_sidecar.py` + `tests/test_http_control.py` + compose 契约
  22 passed；全量 216 passed；覆盖率 80.87%。
- 未验证：真实 Docker socket 下的 sidecar 端到端（本机无 Docker），需在 CI/宿主环境
  用 `compose.control.yaml` 跑日志/执行/启停。

### Step 4 — 依赖与镜像安全扫描

**Intent**: 在 CI 增加依赖与镜像漏洞扫描，保留现有 SBOM/provenance，并定义
HIGH/CRITICAL 的阻断与豁免流程。
**Tags**: change
**Command rationale**: 改变现有 CI 行为而非修构建错误，使用
`/orch-change-feature`；扫描范围、阻断策略与豁免流程写入任务描述。

```bash
/orch-change-feature "[Plan: plans/001-security-release-hardening.md#step-4] 在 CI 增加依赖与镜像安全扫描：pip-audit、npm audit、Trivy 扫描镜像，保留现有 SBOM/provenance；对 HIGH/CRITICAL 设阻断或明确 allowlist；Acceptance: PR 触发扫描；高危失败可复现；文档说明豁免流程；Out of scope: 自动修复依赖"
```

**Step 4 完成记录（TDD）：**

- Red：`tests/test_ci_contract.py` 新增的 security/Trivy/.trivyignore 断言失败。
- Green：
  - `ci.yml` 新增 `security` job：`pypa/gh-action-pip-audit` + `npm audit --audit-level=high`。
  - `build` job 构建后加载 scanner/panel 镜像，并用 Trivy 扫描 HIGH/CRITICAL；
    `ignore-unfixed: true`，`exit-code: 1`，`.trivyignore` 可豁免。
  - 根目录新增 `.trivyignore`，docs/testing.md 增加豁免流程。
  - `pip-audit` 实际发现 `cryptography 48.0.0` 的 7 条已知漏洞；已升级到 `50.0.2`，
    复扫无已知漏洞。`npm audit` 当前 0 vulnerabilities。
- Verify：CI 契约 12 passed；全量 219 passed；覆盖率 80.87%；前端 lint/typecheck/test 通过。
- 未验证：GitHub Actions 实际运行（需推送分支/手动 dispatch）；Trivy 镜像扫描需 CI 或本地 Docker。

### Step 5 — 全量验证（blocked）

**Intent**: 运行后端覆盖率、前端三连、compose 契约与运行时 smoke，并审查 diff。
**Tags**: test, review
**Command rationale**: `/test-coverage` 与 `/code-review` 不接受计划步骤参数，无法携带
本步骤 scope；按 skill 规则标记为 blocked，需手动执行。

```text
BLOCKED — /test-coverage cannot carry plan scope; run manually if wanted: /test-coverage
BLOCKED — /code-review cannot carry plan scope; run manually if wanted: /code-review
```

**Step 5 完成记录（本地 + TrueNAS）：**

- 后端（TrueNAS `python:3.13-alpine3.23` 容器）：`219 passed`，覆盖率 `80.87%`。
  - 首次在干净 Alpine 环境运行时发现 `requirements-dev.txt` 缺少 `pytest-asyncio`，
    导致 async 用例失败；已补 `pytest-asyncio==1.4.1.post1`，复跑全绿。
- 前端（TrueNAS `node:24-alpine` 容器）：`lint`、`typecheck`、`27 tests`、`build` 全部通过；
  JS 约 583 KB，CSS 约 188 KB，19 个 JS chunk。
- Compose（TrueNAS）：默认 / build / control 三种配置 `config --quiet` 全部通过。
- 运行时 smoke（TrueNAS，独立项目 `cf-ip-hardening-test`，端口 18081）：
  - 默认栈：panel `127.0.0.1:18081`、无 `/var/run/docker.sock`、
    `CapDrop=["ALL"]`、`no-new-privileges:true`、scanner healthy、`/healthz` 200。
  - 控制覆盖层：`scanner-control` healthy；panel 仍无 socket；sidecar 能读取 scanner
    status 与 logs；固定 action 拒绝未知操作（单测覆盖）。
  - 测试栈已 `down -v` 清理；原有 `cf-ip-panel-test` 项目保持运行且 healthy。
- 镜像构建：
  - panel target 在 TrueNAS 构建成功。
  - scanner target 的 supercronic GitHub 下载被网络拒绝（`Connection refused`）；
    用**测试专用** `Dockerfile.test`（从运行中的 scanner 镜像取出 supercronic 后 COPY）
    构建并验证了 scanner 运行阶段；生产 Dockerfile 的下载+校验逻辑未改。
- **未执行**：arm64 构建、Playwright e2e、Trivy 实际镜像扫描（需 CI 或本地 Docker 环境）。

### 5.1 验证环境记录（TrueNAS，2026-11-08）

- 本地测试机为 TrueNAS；**已有一个正在运行的 `best-cf-ip-scanner` 项目**。
- TrueNAS UI 中当前能看到**两个同名 `best-cf-ip-scanner` 目录**；重建前必须先确认
  目标是哪一个目录/Compose 项目，避免误删另一个。
- 需要重建时可以重建，但先备份：
  - `panel-data/`（`panel.db`、`settings.key`、`secret.key`）；
  - 命名卷 `ip-data`、`scan-output`、`publish-cache`、`scanner-config`。
- 不要在未确认数据可丢的情况下执行 `docker compose down -v`；它会删除命名卷。
- 推荐验证顺序：
  1. 在目标目录 `docker compose pull` 后 `up -d`，确认旧数据可读；
  2. 需要本地构建时用 `docker compose -f compose.yaml -f compose.build.yaml up -d --build`；
  3. 控制功能用 `docker compose -f compose.yaml -f compose.build.yaml -f compose.control.yaml up -d`；
  4. 验证默认栈无 socket、panel 只绑本机、控制 sidecar 日志/运行/启停正常。

**2026-11-08 实测：**

- 使用独立目录 `/mnt/d16/all/tmp/cf-ip-hardening-test-20261108` 和独立项目名
  `cf-ip-hardening-test`，端口 `18081`；未改动正在运行的 `cf-ip-panel-test`。
- 测试完成后已 `down -v` 清理测试栈；原项目仍为 healthy。
- 生产 scanner 镜像的 supercronic 下载受 TrueNAS 到 GitHub 的网络限制；测试时使用
  `Dockerfile.test` 从现有镜像复制 supercronic，仅用于运行阶段验证。

### Step 6 — 文档与发布说明（blocked）

**Intent**: 同步 README、部署文档、安全策略与发布说明。
**Tags**: docs
**Command rationale**: `/update-docs` 不接受计划步骤参数，无法携带本步骤 scope；
按 skill 规则标记为 blocked，需手动执行。

```text
BLOCKED — /update-docs cannot carry plan scope; run manually if wanted: /update-docs
```

**Step 6 完成记录（手动）：**

- README：双镜像、本机端口、控制 sidecar、setup token、数据位置修正。
- deployment：panel 镜像名、双镜像升级说明、控制 sidecar、备份密钥说明。
- panel/troubleshooting/testing：控制 sidecar、双镜像、lint/audit/Trivy 门禁。
- 新增 `SECURITY.md`、`CONTRIBUTING.md`、issue 模板、Dependabot、`.trivyignore`。

---

## 5. Batch execution（仅未完成的 emitted 步骤）

当前没有未完成的 emitted 步骤（Step 1–4 已完成，Step 6 已完成）。
Step 5 的 Docker 运行时/E2E 部分需在有 Docker 的环境手动执行：

```text
/test-coverage
/code-review
```

---

## 6. 验收标准（S1–S6 已完成部分）

| ID | 验收点 | 状态 |
| --- | --- | --- |
| AC-001 | 默认 panel 只绑 `127.0.0.1:8080` | 静态通过 / 运行时待验 |
| AC-002 | 默认不挂载 `docker.sock` | 静态通过 / 运行时待验 |
| AC-003 | panel `cap_drop: ALL` + `no-new-privileges` | 静态通过 / 运行时待验 |
| AC-004 | 追加 `compose.control.yaml` 后才恢复容器控制 | 静态通过 / 运行时待验 |
| AC-005 | panel 对 `/output`、`/cache` 只读 | 静态通过 / 运行时待验 |
| AC-006 | 发布 workflow 覆盖 panel/web/requirements-panel | 通过 |
| AC-007 | SQLite 写事务串行化 | 通过 |
| AC-008 | API 返回 CSP/nosniff/frame/no-store | 通过 |
| AC-009 | 改密/登出后旧 Cookie 立即 401 | 通过 |
| AC-010 | 配置 setup token 时首次设置必须带 token | 通过 |
| AC-011 | 登录限速有界且不全局锁死 | 通过 |
| AC-012 | 后端 ≥80% + 前端三连 | 通过（82.05% / 26 tests） |
| AC-013 | 文档与代码一致 | 通过 |
| AC-014 | 分支隔离，不合并/不推送 main | 通过 |

---

## 7. 验证矩阵

| 验收 | 证据 | 状态 |
| --- | --- | --- |
| AC-001/002/003/004/005 | `tests/test_compose_security.py` 6 passed；运行时 smoke 待 Docker | 静态通过 |
| AC-006 | `tests/test_ci_contract.py` 8 passed | 通过 |
| AC-007 | `test_writes_on_shared_connection_are_serialized` | 通过 |
| AC-008 | `test_security_headers_are_present` | 通过 |
| AC-009 | `test_password_change_invalidates_previous_session` / `test_logout_invalidates_previous_session` | 通过 |
| AC-010 | `test_setup_token_is_required_when_configured` + 前端 setup token 字段 | 通过 |
| AC-011 | `test_login_limiter_has_bounded_memory` / `test_login_lockout_is_scoped_to_source_ip` | 通过 |
| AC-012 | 后端 197 passed / 82.05%；前端 26 tests + typecheck + build | 通过 |
| AC-013 | README/deployment diff | 通过 |
| AC-014 | 当前分支 `refactor/security-release-hardening` | 通过 |

---

## 8. 回滚

- 所有改动仅在分支，不推送/不合并即可回滚到 `feat/ops-panel`。
- 未提交改动可用 `git restore -- <files>` 撤销；已提交改动用 revert。
- DB v6 迁移是加法（新增列），旧代码可继续读取。
- 默认移除 socket 是行为变更；恢复控制能力追加 `compose.control.yaml`，不改代码。
