def test_overview_degrades_when_scanner_unavailable(client, fake_controller):
    fake_controller.raise_unavailable = True
    body = client.get("/api/overview").json()
    assert body["scanner"]["state"] == "unavailable"
    assert "reason" in body["scanner"]


def test_overview_includes_last_run_and_next_runs(client, runs_tsv):
    body = client.get("/api/overview").json()
    assert body["scanner"]["state"] == "running"
    assert body["running"] is False
    assert body["last_run"]["run_id"] == "r1"
    assert len(body["next_runs"]) == 5
    assert body["config_summary"]["PROBE_HOST"] == "cloudflare-ech.com"
    assert body["timezone"] == "Asia/Shanghai"
    assert body["schedule"]["cron"] == "30 */6 * * *"
    assert body["schedule"]["next_runs"] == body["next_runs"]
    assert body["publish"]["enabled"] is False
    assert body["artifacts"]["count"] == 0
    assert body["recent_runs"][0]["run_id"] == "r1"


def test_overview_reads_run_metrics_and_csv_qualified_count(
    client, runs_tsv, settings, output_dir
):
    metrics_dir = settings.data_dir / "runtime" / "runs"
    metrics_dir.mkdir(parents=True, exist_ok=True)
    (metrics_dir / "r1.json").write_text(
        '{"schema": 1, "ok": true, "candidates": 10,'
        ' "stages": {"endpoint": {"qualified": 4}}}',
        encoding="utf-8",
    )
    (output_dir / "detail.csv").write_text(
        "IP,端口\n1.2.3.4,443\n5.6.7.8,443\n", encoding="utf-8"
    )
    body = client.get("/api/overview").json()
    assert body["last_run"]["metrics"]["stages"]["endpoint"]["qualified"] == 4
    assert body["artifacts"]["qualified"] == 2
    assert body["recent_runs"][0]["metrics"]["schema"] == 1


def test_overview_reports_running_state(client, monkeypatch):
    monkeypatch.setattr("panel.runs_store.scan_lock_held", lambda _settings: True)
    assert client.get("/api/overview").json()["running"] is True
