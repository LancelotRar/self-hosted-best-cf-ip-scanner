# syntax=docker/dockerfile:1

# ------------------------------------------------------------- Python 公共层 --
# 解释器、时区库与证书；不包含 git/supercronic/业务依赖。
FROM python:3.13-alpine3.23 AS python-base

ARG APK_MIRROR=
ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY

# 元数据：发布流水线会用 metadata-action 覆盖，本地构建也带上，便于 docker inspect。
LABEL org.opencontainers.image.title="best-cf-ip-scanner" \
      org.opencontainers.image.description="Cloudflare 优选 IP 扫描器：TCP 握手测量 + 边缘端点校验" \
      org.opencontainers.image.source="https://github.com/LancelotRar/self-hosted-best-cf-ip-scanner" \
      org.opencontainers.image.licenses="MIT"

# tzdata  —— cron 调度与产物时间戳所依赖的时区库
# ca-certificates —— HTTPS 证书链（扫描器出网 / git）
RUN --mount=type=cache,target=/etc/apk/cache,sharing=locked \
    if [ -n "$APK_MIRROR" ]; then \
      sed -i "s|https://dl-cdn.alpinelinux.org/alpine|$APK_MIRROR|g" /etc/apk/repositories; \
    fi \
 && apk add tzdata ca-certificates

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOME=/tmp \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app


# --------------------------------------------------------- scanner 依赖层 --
FROM python-base AS scanner-builder

ARG PIP_INDEX_URL=https://pypi.org/simple
ENV PIP_INDEX_URL=${PIP_INDEX_URL}

RUN --mount=type=bind,source=scanner/requirements.txt,target=requirements.txt \
    --mount=type=cache,target=/root/.cache/pip \
    pip install --prefix=/install-scanner -r requirements.txt


# ------------------------------------------------------------- scanner 运行 --
FROM python-base AS scanner

# 调度器版本与各架构二进制校验和（升级时两者同步更新）。
ARG SUPERCRONIC_VERSION=v0.2.51
ARG TARGETARCH=amd64
# 构建期代理：apk 与 supercronic 下载都可能需要。
ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY

# git      —— 发布产物到 Git 仓库（HTTPS + 令牌头部注入）
# su-exec  —— 极小的 setuid 工具：入口以 root 准备挂载目录后降权到 PUID/PGID
RUN --mount=type=cache,target=/etc/apk/cache,sharing=locked \
    apk add git su-exec

# supercronic —— 面向容器的 cron 实现：日志直出、不重叠同作业、可热重载。
# 下载用 python 的 urllib 而不是 busybox wget：后者经 HTTP 代理跟随 302 到
# GitHub 资源域名时可能拿到 502；urllib 直接尊重 HTTPS_PROXY/NO_PROXY。
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

ENV OUTPUT_DIR=/output \
    DATA_DIR=/data \
    SUPERCRONIC_VERSION=${SUPERCRONIC_VERSION}

COPY --from=scanner-builder /install-scanner /usr/local

COPY --link scanner/*.py ./scanner/
COPY --link scanner/docker/entrypoint.sh scanner/docker/scan-and-publish.sh scanner/docker/publish.sh scanner/docker/doctor.sh /usr/local/bin/
COPY --link scanner/docker/export-runtime.py docker/print-config.py scanner/docker/startup-report.py \
      docker/check-config.py scanner/docker/apply-config.sh scanner/docker/push-filter.py /usr/local/bin/
COPY --link scanner/docker/crontab.template /etc/supercronic/crontab.template

RUN chmod +x /usr/local/bin/entrypoint.sh /usr/local/bin/scan-and-publish.sh \
      /usr/local/bin/publish.sh /usr/local/bin/doctor.sh /usr/local/bin/check-config.py \
      /usr/local/bin/export-runtime.py /usr/local/bin/print-config.py \
      /usr/local/bin/startup-report.py /usr/local/bin/push-filter.py \
      /usr/local/bin/apply-config.sh \
  && adduser -D -u 1000 -h /home/scanner scanner \
  && mkdir -p /output /cache \
  && chown -R 1000:1000 /output /cache

# 入口以 root 启动，把挂载目录对齐到 PUID/PGID 后立刻 su-exec 降权。
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
