"""面板运行时设置。

路径与开关只来自部署环境（容器变量 / 测试注入），应用参数一律存数据库。
测试用 `Settings.for_tests` 注入临时目录——业务代码不直接读真实 `/panel-data`。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

_TRUE_VALUES = {"1", "true", "yes", "on"}

_DEFAULT_IMAGE = "ghcr.io/lancelotrar/self-hosted-best-cf-ip-scanner:latest"


def _as_bool(raw: str | None) -> bool:
    return (raw or "").strip().lower() in _TRUE_VALUES


@dataclass(frozen=True)
class Settings:
    """面板运行期路径与开关。"""

    project_dir: Path
    data_dir: Path
    output_dir: Path
    cache_dir: Path
    panel_data_dir: Path
    config_dir: Path
    scanner_container: str
    default_data_dir: Path = Path("/opt/default-data")
    scanner_image: str = _DEFAULT_IMAGE
    puid: int = 1000
    pgid: int = 1000
    trust_proxy: bool = False
    session_days: int = 7
    port: int = 8080
    # 可选：首次设置的一次性口令。为空时保持原有首次设置行为；
    # 面板暴露到非可信网络时应设置，setup 请求必须带 X-Setup-Token。
    setup_token: str | None = None
    # 可选：通过固定操作 sidecar 访问 Docker；为空时使用本地 docker.sock。
    control_url: str | None = None
    control_token: str | None = None

    @classmethod
    def from_env(cls) -> "Settings":
        """从容器环境读取；所有项都有可本地运行的默认值。"""
        project_dir = Path(os.environ.get("PROJECT_DIR") or ".")
        return cls(
            project_dir=project_dir,
            data_dir=Path(os.environ.get("DATA_DIR") or project_dir / "data"),
            output_dir=Path(os.environ.get("OUTPUT_DIR") or project_dir / "output"),
            cache_dir=Path(os.environ.get("CACHE_DIR") or project_dir / "cache"),
            panel_data_dir=Path(
                os.environ.get("PANEL_DATA_DIR") or project_dir / "panel-data"
            ),
            config_dir=Path(
                os.environ.get("CONFIG_DIR") or project_dir / "scanner-config"
            ),
            scanner_container=(
                os.environ.get("SCANNER_CONTAINER")
                or os.environ.get("CONTAINER_NAME")
                or "best-cf-ip-scanner"
            ),
            default_data_dir=Path(
                os.environ.get("DEFAULT_DATA_DIR") or "/opt/default-data"
            ),
            scanner_image=os.environ.get("SCANNER_IMAGE") or _DEFAULT_IMAGE,
            puid=int(os.environ.get("PUID") or 1000),
            pgid=int(os.environ.get("PGID") or 1000),
            trust_proxy=_as_bool(os.environ.get("PANEL_TRUST_PROXY")),
            session_days=int(os.environ.get("PANEL_SESSION_DAYS") or 7),
            port=int(os.environ.get("PANEL_PORT") or 8080),
            setup_token=(os.environ.get("PANEL_SETUP_TOKEN") or "").strip() or None,
            control_url=(os.environ.get("SCANNER_CONTROL_URL") or "").strip() or None,
            control_token=(os.environ.get("SCANNER_CONTROL_TOKEN") or "").strip()
            or None,
        )

    @classmethod
    def for_tests(cls, tmp_path: Path) -> "Settings":
        """测试用设置：所有目录都在 `tmp_path` 下。"""
        settings = cls(
            project_dir=tmp_path,
            data_dir=tmp_path / "data",
            output_dir=tmp_path / "output",
            cache_dir=tmp_path / "cache",
            panel_data_dir=tmp_path / "panel-data",
            config_dir=tmp_path / "scanner-config",
            scanner_container="best-cf-ip-scanner",
            default_data_dir=tmp_path / "default-data",
        )
        for directory in (
            settings.data_dir,
            settings.output_dir,
            settings.cache_dir,
            settings.panel_data_dir,
            settings.config_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)
        return settings

    @property
    def runtime_config_path(self) -> Path:
        """面板生成、扫描器读取的运行配置投影。"""
        return self.config_dir / "runtime.json"

    @property
    def backups_dir(self) -> Path:
        return self.panel_data_dir / "backups"

    @property
    def db_path(self) -> Path:
        return self.panel_data_dir / "panel.db"

    @property
    def secret_path(self) -> Path:
        """会话签名密钥（与配置加密密钥分开）。"""
        return self.panel_data_dir / "secret.key"

    @property
    def settings_key_path(self) -> Path:
        """配置加密密钥；不随数据库一起导出。"""
        return self.panel_data_dir / "settings.key"
