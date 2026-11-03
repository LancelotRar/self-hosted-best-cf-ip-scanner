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
    assert body["config_summary"]["PROBE_HOST"] == "probe.example.com"


def test_overview_reports_running_state(client, monkeypatch):
    monkeypatch.setattr("panel.runs_store.scan_lock_held", lambda _settings: True)
    assert client.get("/api/overview").json()["running"] is True
