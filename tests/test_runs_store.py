from panel.runs_store import parse, read_metrics


def test_parse_pairs_start_and_end(tmp_path):
    path = tmp_path / "runs.tsv"
    path.write_text(
        "START\tr1\tpanel\t2026-11-03T00:00:00Z\t\t\t\t\n"
        "END\tr1\tpanel\t2026-11-03T00:02:00Z\t0\t0\t120\t完成\n",
        encoding="utf-8",
    )
    runs = parse(path)
    assert len(runs) == 1
    assert runs[0].scan_exit == 0 and runs[0].publish_exit == 0
    assert runs[0].duration_s == 120.0


def test_start_without_end_is_interrupted(tmp_path):
    path = tmp_path / "runs.tsv"
    path.write_text("START\tr2\tcron\t2026-11-03T00:00:00Z\t\t\t\t\n", encoding="utf-8")
    assert parse(path)[0].interrupted is True


def test_malformed_lines_are_skipped(tmp_path):
    path = tmp_path / "runs.tsv"
    path.write_text(
        "garbage\n"
        "START\tr3\tpanel\t2026-11-03T00:00:00Z\t\t\t\t\n"
        "END\tr3\tpanel\t2026-11-03T00:01:00Z\t1\t\t60\t扫描失败\n",
        encoding="utf-8",
    )
    runs = parse(path)
    assert len(runs) == 1
    assert runs[0].scan_exit == 1
    assert runs[0].publish_exit is None


def test_read_metrics_ignores_missing_and_unsafe_ids(tmp_path):
    from panel.settings import Settings

    settings = Settings.for_tests(tmp_path)
    assert read_metrics(settings, "missing") is None
    assert read_metrics(settings, "../secret") is None
    assert read_metrics(settings, "r1/../../x") is None


def test_read_metrics_parses_valid_file(tmp_path):
    from panel.settings import Settings

    settings = Settings.for_tests(tmp_path)
    directory = settings.data_dir / "runtime" / "runs"
    directory.mkdir(parents=True)
    (directory / "r1.json").write_text('{"ok": true}', encoding="utf-8")
    assert read_metrics(settings, "r1") == {"ok": True}
