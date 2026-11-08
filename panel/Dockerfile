# syntax=docker/dockerfile:1

# ---------------------------------------------------------------- 前端构建 --
FROM node:24-alpine AS web

# 镜像加速（可选）：中国网络下 npm 很慢时可指向 npmmirror。
ARG NPM_CONFIG_REGISTRY=https://registry.npmjs.org
ENV NPM_CONFIG_REGISTRY=${NPM_CONFIG_REGISTRY}

WORKDIR /web
COPY --link panel/web/package.json panel/web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY --link panel/web/ ./
RUN npm run build


# ------------------------------------------------------------- Python 公共层 --
FROM python:3.13-alpine3.23 AS python-base

ARG APK_MIRROR=
ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY

LABEL org.opencontainers.image.title="best-cf-ip-scanner-panel" \
      org.opencontainers.image.description="Cloudflare 优选 IP 扫描器运维面板" \
      org.opencontainers.image.source="https://github.com/LancelotRar/self-hosted-best-cf-ip-scanner" \
      org.opencontainers.image.licenses="MIT"

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


# ----------------------------------------------------------- panel 依赖层 --
FROM python-base AS panel-builder

ARG PIP_INDEX_URL=https://pypi.org/simple
ENV PIP_INDEX_URL=${PIP_INDEX_URL}

RUN --mount=type=bind,source=panel/requirements.txt,target=requirements-panel.txt \
    --mount=type=cache,target=/root/.cache/pip \
    pip install --prefix=/install-panel -r requirements-panel.txt


# --------------------------------------------------------------- panel 运行 --
FROM python-base AS panel

COPY --from=panel-builder /install-panel /usr/local

# 面板需要 scanner 包里的 schema/validation/ippool/pinned；包 __init__ 已改为
# 按需导入，因此不会把 probe/curl_cffi 带进 panel 镜像。
COPY --link scanner/*.py ./scanner/
COPY --link panel/*.py ./panel/
COPY --link panel/routers ./panel/routers
COPY --from=web /web/dist ./panel/static
COPY --link panel/docker/panel-entrypoint.sh /usr/local/bin/
COPY --link docker/check-config.py docker/print-config.py /usr/local/bin/
# 内置候选地址库与机房映射作为"出厂默认值"：面板首次启动时播种到 /data。
COPY --link panel/data /opt/default-data

RUN chmod +x /usr/local/bin/panel-entrypoint.sh \
      /usr/local/bin/check-config.py /usr/local/bin/print-config.py \
  && mkdir -p /data /output /cache /scanner-config /panel-data \
  && chown -R 1000:1000 /opt/default-data /data /output /cache /scanner-config /panel-data

EXPOSE 8080

ENTRYPOINT ["/usr/local/bin/panel-entrypoint.sh"]
