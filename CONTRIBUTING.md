# 贡献指南

## 开发环境

- Python 3.13
- Node.js 24
- Docker 24+（含 Compose v2）

```bash
python -m pip install -r requirements.txt -r requirements-panel.txt -r requirements-dev.txt
npm ci --prefix web
```

## 本地验证

提交前至少运行：

```bash
python -m pytest -q --cov=panel --cov=scanner --cov-fail-under=80
npm --prefix web run typecheck
npm --prefix web run test
npm --prefix web run build
```

涉及 compose 的改动还要运行：

```bash
cp compose.example.yaml compose.yaml
docker compose config --quiet
docker compose -f compose.yaml -f compose.control.yaml config --quiet
```

涉及镜像/入口脚本的改动，请本地构建并跑一轮 smoke：

```bash
docker compose -f compose.yaml -f compose.build.yaml up -d --build
docker compose ps
docker compose exec -T scanner /usr/local/bin/doctor.sh
```

## 分支与提交

- 从 `main` 切出功能分支；不要直接向 `main` 提交。
- 一个 PR 只做一件事；安全/基础设施改动与 UI 改动分开。
- 提交信息使用 `<type>: <描述>`，type 取 `feat`/`fix`/`docs`/`refactor`/`perf`/`test`/`build`/`ci`/`chore`。
- 不要提交 `.env`、令牌、`panel-data/`、`web/dist/`、`__pycache__/` 等运行产物。

## 代码约定

- Python：保持现有类型标注与模块边界；新增行为先写失败测试。
- 前端：TypeScript `strict`；组件与 store 沿用现有目录结构。
- Shell：POSIX `sh`，避免 bash 专有语法。
- 配置：应用参数只通过 `scanner/schema.py` 定义，面板与扫描器共用同一份 schema。

## 安全相关改动

涉及认证、会话、Docker API、文件写入、密钥或宿主机挂载的改动，请在 PR 描述中写明：

- 威胁模型与影响面；
- 为什么现有边界不足；
- 回滚方式；
- 已执行的验证命令。
