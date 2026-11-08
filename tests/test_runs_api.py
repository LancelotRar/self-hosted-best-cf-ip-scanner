def test_history_lists_parsed_runs(client, runs_tsv):
    body = client.get("/api/runs").json()
    assert body["runs"][0]["run_id"] == "r1"
    assert body["runs"][0]["publish_exit"] == 1


def test_running_round_is_not_reported_as_interrupted(client, settings, monkeypatch):
    path = settings.data_dir / "runtime" / "runs.tsv"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "START\trun-live\tpanel\t2026-11-03T00:00:00Z\t\t\t\t\n", encoding="utf-8"
    )
    monkeypatch.setattr("panel.runs_store.scan_lock_held", lambda _settings: True)
    body = client.get("/api/runs").json()
    assert body["runs"][0]["status"] == "running"
    assert body["runs"][0]["interrupted"] is True  # 底层仍是"未结束"


def test_unfinished_without_lock_is_interrupted(client, settings, monkeypatch):
    path = settings.data_dir / "runtime" / "runs.tsv"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "START\trun-dead\tpanel\t2026-11-03T00:00:00Z\t\t\t\t\n", encoding="utf-8"
    )
    monkeypatch.setattr("panel.runs_store.scan_lock_held", lambda _settings: False)
    assert client.get("/api/runs").json()["runs"][0]["status"] == "interrupted"


def test_completed_round_status_done(client, runs_tsv):
    assert client.get("/api/runs").json()["runs"][0]["status"] == "done"


def test_trigger_returns_run_id(client, fake_controller):
    response = client.post("/api/runs")
    assert response.status_code == 202
    run_id = response.json()["run_id"]
    assert run_id
    script, env = fake_controller.exec_calls[-1]
    assert script.endswith("scan-and-publish.sh")
    assert env["RUN_TRIGGER"] == "panel"


def test_trigger_rejects_when_lock_is_held(client, settings, fake_controller):
    lock_path = settings.cache_dir / "scan.lock"
    lock_path.write_text("", encoding="utf-8")
    from panel import runs_store

    original = runs_store.scan_lock_held
    runs_store.scan_lock_held = lambda _settings: True
    try:
        response = client.post("/api/runs")
    finally:
        runs_store.scan_lock_held = original
    assert response.status_code == 409


def test_trigger_passes_run_marker_and_audits(client, settings, fake_controller):
    run_id = client.post("/api/runs").json()["run_id"]
    assert run_id
    _, env = fake_controller.exec_calls[-1]
    assert env == {"RUN_ID": run_id, "RUN_TRIGGER": "panel"}
    actions = [item["action"] for item in client.get("/api/audit").json()["items"]]
    assert "run.trigger" in actions


def test_trigger_unavailable_returns_503(client, fake_controller):
    fake_controller.raise_unavailable = True
    assert client.post("/api/runs").status_code == 503


def test_stream_unknown_run_is_404(client):
    assert client.get("/api/runs/nope/stream").status_code == 404


def test_stream_emits_log_and_done(client, fake_controller):
    run_id = client.post("/api/runs").json()["run_id"]
    response = client.get(f"/api/runs/{run_id}/stream?tail=10")
    assert response.status_code == 200
    assert "run-output" in response.text
    assert "done" in response.text
