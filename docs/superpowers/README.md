# 项目专属运维面板 — 设计/计划索引

- 状态：计划记录完成，已归档，待开发（2026-11-03）
- 范围：`self-hosted-best-cf-ip-scanner` 专属运维面板，一个 compose 堆栈、两个容器、单镜像
- 实施方式：尚未开始；启动时按实施计划从 Task 1 执行
- 产品定位：面板优先；CLI / 手工 `.env` 仅作备用与应急

## 文档

| 文档 | 作用 |
| --- | --- |
| [设计文档](specs/2026-11-03-ops-panel-design.md) | 目标、范围、架构、`.env` 单源、保存事务、标签页 UI、测试与上线门禁 |
| [实施计划](plans/2026-11-03-ops-panel.md) | 21 个任务，含接口、测试、验证命令、提交步骤、启动清单 |

## 关键决策

- 一个 compose 项目、一次 `up -d`、两个容器（scanner + panel）、同一个镜像。
- `.env` 是唯一配置源；扫描器每轮读取，面板原子改写；显式环境变量 > `.env` > 默认值。
- 面板保存是事务：校验 → 写入 → 回读 → 核对生效值 → 调度热重载 → 审计；
  `written` 与 `verification.status` 分开显示，禁止“已写入”冒充“已生效”。
- 顶部九个主标签 + 页内子标签；保存/取消/结果面板/真实状态为硬性交互契约。
- 测试门禁：单元、API、脚本契约、前端、镜像/Compose 冒烟、Playwright E2E、人工上线清单；
  后端覆盖率 ≥ 80%，CI 全绿才允许合并/发布。
- 技术栈：FastAPI/uvicorn/docker SDK/Pydantic/SQLite + Vue 3/TS/Vite/Element Plus/
  Pinia/Vue Router；选型原则与替代方案见 Spec §9，运行期依赖精确锁定，升级单独 PR。

## 开发工具（已接入）

- Playwright MCP：系统 Edge，开发期交互验证；CI 用 Playwright Test。
- Figma MCP：远程 OAuth 已登录；仅在 Figma 设计任务时使用。
- Figma skills（选择性）：`figma-design-to-code`（读设计前必须）、`figma-use`（写画布前
  必须）、`figma-create-new-file`、`figma-generate-design`、`figma-generate-library`、
  `figma-code-connect`、`figma-implement-motion`、`figma-generate-diagram` 等。
- 前端设计 skills：`frontend-design-direction`、`design-system`、
  `make-interfaces-feel-better`、`accessibility`、`vue-patterns`、`vite-patterns`、
  `typescript-patterns`、`ui-to-vue`、`browser-qa` 等，按需调用。

## 备份

- `E:\coding\coding\github\backups\self-hosted-best-cf-ip-scanner_pre-panel_2026-11-03_023806.tar.gz`
- 同目录 `.bundle`（完整 git 历史，已 `git bundle verify`）
