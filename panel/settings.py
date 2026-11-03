"""面板运行时设置。

所有路径与开关都从环境变量读取，测试用 `Settings.for_tests` 注入临时目录——
业务代码不直接读真实 `/panel-data` 或 `docker.from_env()`。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

_TRUE_VALUES = {"1", "true", "yes", "on"}


def _as_bool(raw: str | None) -> bool:
    return (raw or "").strip().lower() in _TRUE_VALUES


@dataclass(frozen=True)
class Settings:
    """面板运行期路径与开关。"""

    project_dir: Path
    env_path: Path
    data_dir: Path
    output_dir: Path
    cache_dir: Path
    panel_data_dir: Path
    scanner_container: str
    trust_proxy: bool = False
    session_days: int = 7
    port: int = 8080

    @classmethod
    def from_env(cls) -> "Settings":
        """从容器环境读取；所有项都有可本地运行的默认值。"""
        project_dir = Path(os.environ.get("PROJECT_DIR") or ".")
        env_path = Path(os.environ.get("DOTENV_PATH") or project_dir / ".env")
        return cls(
            project_dir=project_dir,
            env_path=env_path,
            data_dir=Path(os.environ.get("DATA_DIR") or project_dir / "data"),
            output_dir=Path(os.environ.get("OUTPUT_DIR") or project_dir / "output"),
            cache_dir=Path(os.environ.get("CACHE_DIR") or project_dir / "cache"),
            panel_data_dir=Path(
                os.environ.get("PANEL_DATA_DIR") or project_dir / "panel-data"
            ),
            scanner_container=(
                os.environ.get("SCANNER_CONTAINER")
                or os.environ.get("CONTAINER_NAME")
                or "best-cf-ip-scanner"
            ),
            trust_proxy=_as_bool(os.environ.get("PANEL_TRUST_PROXY")),
            session_days=int(os.environ.get("PANEL_SESSION_DAYS") or 7),
            port=int(os.environ.get("PANEL_PORT") or 8080),
        )

    @classmethod
    def for_tests(cls, tmp_path: Path) -> "Settings":
        """测试用设置：所有目录都在 `tmp_path` 下，并预建最小 `.env`。"""
        settings = cls(
            project_dir=tmp_path,
            env_path=tmp_path / ".env",
            data_dir=tmp_path / "data",
            output_dir=tmp_path / "output",
            cache_dir=tmp_path / "cache",
            panel_data_dir=tmp_path / "panel-data",
            scanner_container="best-cf-ip-scanner",
        )
        for directory in (
            settings.data_dir,
            settings.output_dir,
            settings.cache_dir,
            settings.panel_data_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)
        if not settings.env_path.exists():
            settings.env_path.write_text("", encoding="utf-8")
        return settings

    @property
    def backups_dir(self) -> Path:
        return self.panel_data_dir / "backups"

    @property
    def db_path(self) -> Path:
        return self.panel_data_dir / "panel.db"

    @property
    def secret_path(self) -> Path:
        return self.panel_data_dir / "secret.key"
