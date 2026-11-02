# syntax=docker/dockerfile:1

# ---------------------------------------------------------------- 构建阶段 --
# 只负责把 Python 依赖装到 /install，不进入最终镜像（无 pip 缓存、无构建残留）。
FROM python:3.13-alpine3.23 AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build
# 依赖清单用 bind mount 引入（不进镜像层），pip 缓存走 BuildKit cache mount：
# 只改代码时不会重装依赖，重装依赖时也能复用下载缓存。
RUN --mount=type=bind,source=requirements.txt,target=requirements.txt \
    --mount=type=cache,target=/root/.cache/pip \
    pip install --prefix=/install -r requirements.txt


# ---------------------------------------------------------------- 运行阶段 --
FROM python:3.13-alpine3.23 AS runtime

# 调度器版本与各架构二进制校验和（升级时两者同步更新）。默认值由
# compose 的 build.args 传入，也可直接 docker build --build-arg 覆盖。
ARG SUPERCRONIC_VERSION=v0.2.51
ARG TARGETARCH=amd64

# 元数据：发布流水线会用 metadata-action 覆盖，本地构建也带上，便于 docker inspect。
LABEL org.opencontainers.image.title="best-cf-ip-scanner" \
      org.opencontainers.image.description="Cloudflare 优选 IP 扫描器：TCP 握手测量 + 边缘端点校验" \
      org.opencontainers.image.source="https://github.com/LancelotRar/self-hosted-best-cf-ip-scanner" \
      org.opencontainers.image.licenses="MIT"

# git      —— 发布产物到 Git 仓库（HTTPS + 令牌头部注入）
# tzdata   —— cron 调度与产物时间戳所依赖的时区库
# ca-certs —— HTTPS 证书链
# su-exec  —— 极小的 setuid 工具：入口以 root 准备挂载目录后降权到 PUID/PGID
# 包缓存走 BuildKit cache mount，不写进镜像层（因此不需要 --no-cache）。
RUN --mount=type=cache,target=/etc/apk/cache,sharing=locked \
    apk add git tzdata ca-certificates su-exec

# supercronic —— 面向容器的 cron 实现：日志直出、不重叠同作业、可热重载。
# 下载用 python 的 urllib 而不是 busybox wget：后者经 HTTP 代理跟随 302 到
# GitHub 资源域名时可能拿到 502；urllib 直接尊重 HTTPS_PROXY/NO_PROXY，
# 且不额外安装下载工具。校验和写死在下方，升级版本必须同步更新。
RUN python - <<'PY'
import hashlib
import os
import sys
import urllib.request

arch = os.environ.get("TARGETARCH", "amd64")
version = os.environ.get("SUPERCRONIC_VERSION", "")
checksums = {
    "amd64": "cc232108374e8e2b537045f2d5eaa1229f619db314c3ba6a14d38b35dc0aa123",
    "arm64": "4ae22576a78223d8ccdf5f3b3660a5cbb5288416bf0ca96afc4a36d195932b94",
}
if arch not in checksums:
    sys.exit(f"不支持的构建架构: {arch}（仅支持 amd64 / arm64）")

url = f"https://github.com/aptible/supercronic/releases/download/{version}/supercronic-linux-{arch}"
with urllib.request.urlopen(url, timeout=180) as response:
    payload = response.read()

digest = hashlib.sha256(payload).hexdigest()
if digest != checksums[arch]:
    sys.exit(f"supercronic 校验和不匹配: {digest}")

target = "/usr/local/bin/supercronic"
with open(target, "wb") as handle:
    handle.write(payload)
os.chmod(target, 0o755)
print(f"supercronic {version} ({arch}) 安装完成")
PY

# 构建期自检：二进制可执行且能解析 crontab，避免把坏二进制带进运行阶段。
RUN printf '* * * * * true\n' > /tmp/smoke.cron \
 && supercronic -test /tmp/smoke.cron \
 && rm -f /tmp/smoke.cron

# 运行期约定：
# PYTHONUNBUFFERED  日志实时进 docker logs（不要缓冲到容器退出）
# PYTHONDONTWRITEBYTECODE 容器只读根文件系统下不产生 __pycache__
# HOME=/tmp          以非 root 运行时给 git/临时文件一个可写落脚点
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=Asia/Shanghai \
    HOME=/tmp \
    OUTPUT_DIR=/output \
    DATA_DIR=/data \
    SUPERCRONIC_VERSION=${SUPERCRONIC_VERSION}

COPY --from=builder /install /usr/local

WORKDIR /app
COPY --link best_cf_ip_scanner.py ./
COPY --link scanner ./scanner
COPY --link docker/entrypoint.sh docker/scan-and-publish.sh docker/publish.sh docker/doctor.sh /usr/local/bin/
COPY --link docker/startup-report.py /usr/local/bin/startup-report.py
COPY --link docker/check-config.py /usr/local/bin/check-config.py
COPY --link docker/crontab.template /etc/supercronic/crontab.template
# 内置候选地址库与机房映射作为"出厂默认值"：容器首次启动时播种到挂载的 /data，
# 之后用户直接编辑宿主目录即可维护，重建镜像也不会覆盖。
COPY --link data /opt/default-data

RUN chmod +x /usr/local/bin/entrypoint.sh /usr/local/bin/scan-and-publish.sh \
      /usr/local/bin/publish.sh /usr/local/bin/doctor.sh /usr/local/bin/check-config.py \
 && adduser -D -u 1000 -h /home/scanner scanner \
 && mkdir -p /output /cache \
 && chown -R 1000:1000 /output /cache /opt/default-data

# 这里刻意不写 USER：镜像需要以 root 启动，才能把 bind mount 进来的宿主目录
# 对齐到 PUID/PGID 并播种默认数据；入口脚本随后用 su-exec 降权，业务进程全程
# 非 root（docker exec 后执行 `id` 可验证）。若强制 USER 1000，宿主机目录属主
# 不一致时会直接启动失败，正是本项目要避免的首次部署摩擦。
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
