from dataclasses import replace
from pathlib import Path

from panel import bootstrap
from panel.settings import Settings


def _settings(tmp_path: Path) -> Settings:
    base = Settings.for_tests(tmp_path / "runtime")
    resolved = replace(
        base,
        data_dir=tmp_path / "data",
        output_dir=tmp_path / "output",
        cache_dir=tmp_path / "cache",
        panel_data_dir=tmp_path / "panel-data",
        config_dir=tmp_path / "scanner-config",
        default_data_dir=tmp_path / "default-data",
    )
    for directory in (
        resolved.data_dir,
        resolved.output_dir,
        resolved.cache_dir,
        resolved.panel_data_dir,
        resolved.config_dir,
        resolved.default_data_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)
    return resolved


def test_seed_defaults_copies_factory_data(tmp_path):
    settings = _settings(tmp_path)
    (settings.default_data_dir / "ip-library.txt").write_text(
        "104.16.0.0/24\n", encoding="utf-8"
    )
    (settings.default_data_dir / "locations.json").write_text("{}", encoding="utf-8")

    bootstrap.seed_defaults(settings)

    assert (settings.data_dir / "ip-library.txt").read_text(encoding="utf-8") == "104.16.0.0/24\n"
    assert (settings.data_dir / "locations.json").read_text(encoding="utf-8") == "{}"


def test_seed_defaults_does_not_overwrite_existing_files(tmp_path):
    settings = _settings(tmp_path)
    (settings.default_data_dir / "ip-library.txt").write_text(
        "104.16.0.0/24\n", encoding="utf-8"
    )
    (settings.data_dir / "ip-library.txt").write_text(
        "104.20.0.0/24\n", encoding="utf-8"
    )

    bootstrap.seed_defaults(settings)

    assert (settings.data_dir / "ip-library.txt").read_text(encoding="utf-8") == "104.20.0.0/24\n"
