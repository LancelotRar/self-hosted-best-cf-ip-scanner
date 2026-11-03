from panel.runs_store import parse


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
