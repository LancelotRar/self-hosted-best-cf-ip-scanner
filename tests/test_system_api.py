def test_restart_requires_confirmation_header(client):
    assert client.post("/api/system/restart").status_code == 400
    assert (
        client.post(
            "/api/system/restart", headers={"X-Confirm": "restart"}
        ).status_code
        == 202
    )


def test_confirm_header_must_match_action(client):
    assert client.post("/api/system/stop", headers={"X-Confirm": "restart"}).status_code == 400
    assert client.post("/api/system/stop", headers={"X-Confirm": "stop"}).status_code == 202


def test_system_info_reports_versions(client):
    body = client.get("/api/system/info").json()
    assert body["panel_version"]
    assert body["python"]
    assert body["image"]
    assert body["timezone"] == "Asia/Shanghai"


def test_audit_lists_container_operations(client):
    client.post("/api/system/restart", headers={"X-Confirm": "restart"})
    body = client.get("/api/audit?page=1").json()
    assert body["page_size"] == 50
    assert any(item["action"] == "system.restart" for item in body["items"])
