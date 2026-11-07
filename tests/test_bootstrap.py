from pathlib import Path

from panel import bootstrap, db, library_store
from panel.settings import Settings


def _settings(tmp_path: Path) -> Settings:
    """project_dir 与 data_dir 分开：旧版布局正是"宿主项目目录 + 容器内挂载点"。"""
    project = tmp_path / "project"
    project.mkdir()
    data = tmp_path / "data"
    data.mkdir()
    output = tmp_path / "output"
    output.mkdir()
    cache = tmp_path / "cache"
    cache.mkdir()
    panel_data = tmp_path / "panel-data"
    panel_data.mkdir()
    return Settings(
        project_dir=project,
        env_path=project / ".env",
        data_dir=data,
        output_dir=output,
        cache_dir=cache,
        panel_data_dir=panel_data,
        scanner_container="best-cf-ip-scanner",
    )


def test_bootstrap_prefers_legacy_library_over_seeded_default(tmp_path):
    settings = _settings(tmp_path)
    (settings.data_dir / "ip-library.txt").write_text(
        "104.16.0.0/24\n", encoding="utf-8"
    )  # 镜像入口脚本播种的内置默认值
    legacy = settings.project_dir / "data"
    legacy.mkdir()
    (legacy / "ip-library.txt").write_text("104.20.0.0/24\n", encoding="utf-8")

    conn = db.connect(settings.db_path)
    db.migrate(conn)
    bootstrap.migrate(conn, settings)
    library_store.ensure(conn, settings)

    assert library_store.read(conn, library_store.LIBRARY)["content"] == "104.20.0.0/24\n"
    assert (settings.data_dir / "ip-library.txt").read_text(encoding="utf-8") == "104.20.0.0/24\n"


def test_bootstrap_moves_runtime_and_output_into_volumes(tmp_path):
    settings = _settings(tmp_path)
    legacy = settings.project_dir / "data" / "runtime"
    legacy.mkdir(parents=True)
    (legacy / "runs.tsv").write_text(
        "START\tr1\tpanel\t2026-11-03T00:00:00Z\t\t\t\t\n", encoding="utf-8"
    )
    legacy_output = settings.project_dir / "output"
    legacy_output.mkdir()
    (legacy_output / "GLOBAL20.txt").write_text("1.1.1.1:443#SG\n", encoding="utf-8")

    conn = db.connect(settings.db_path)
    db.migrate(conn)
    bootstrap.migrate(conn, settings)

    assert (settings.data_dir / "runtime" / "runs.tsv").is_file()
    assert (settings.output_dir / "GLOBAL20.txt").is_file()


def test_bootstrap_does_not_touch_database_once_it_has_content(tmp_path):
    settings = _settings(tmp_path)
    conn = db.connect(settings.db_path)
    db.migrate(conn)
    library_store.save(conn, library_store.LIBRARY, "104.16.0.0/24\n")

    legacy = settings.project_dir / "data"
    legacy.mkdir()
    (legacy / "ip-library.txt").write_text("104.20.0.0/24\n", encoding="utf-8")

    bootstrap.migrate(conn, settings)
    library_store.ensure(conn, settings)

    assert library_store.read(conn, library_store.LIBRARY)["content"] == "104.16.0.0/24\n"
