def test_get_lists_params_with_source_and_hash(client, settings):
    settings.env_path.write_text("MAX_CANDIDATES=200\n", encoding="utf-8")
    body = client.get("/api/config").json()
    assert body["hash"]
    assert body["mtime"]
    params = {param["name"]: param for param in body["params"]}
    assert params["MAX_CANDIDATES"]["value"] == 200
    assert params["MAX_CANDIDATES"]["source"] == "dotenv"
    assert params["TCP_MIN_SUCCESS"]["source"] == "default"
    assert params["IMAGE_TAG"]["read_only"] is True
    assert params["GIT_TOKEN"]["secret"] is True


def test_put_requires_csrf(client):
    saved = client.headers.pop("X-CSRF-Token")
    try:
        response = client.put("/api/config", json={"hash": "x", "values": {}})
        assert response.status_code == 403
    finally:
        client.headers["X-CSRF-Token"] = saved


def test_put_stale_hash_returns_409(client):
    response = client.put(
        "/api/config", json={"hash": "stale", "values": {"MAX_CANDIDATES": "5"}}
    )
    assert response.status_code == 409


def test_put_returns_save_result(client, fake_controller):
    doc = client.get("/api/config").json()
    fake_controller.effective = {}
    response = client.put(
        "/api/config",
        json={"hash": doc["hash"], "values": {"MAX_CANDIDATES": "5"}},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["written"] is True
    assert body["changed"][0]["name"] == "MAX_CANDIDATES"
    assert body["changed"][0]["effect"] == "next_round"


def test_versions_and_rollback(client, fake_controller):
    doc = client.get("/api/config").json()
    client.put(
        "/api/config", json={"hash": doc["hash"], "values": {"MAX_CANDIDATES": "7"}}
    )
    versions = client.get("/api/config/versions").json()["versions"]
    assert versions and versions[0]["actor"] == "admin"
    assert "GIT_TOKEN" not in versions[0]["diff"]

    doc = client.get("/api/config").json()
    client.put(
        "/api/config", json={"hash": doc["hash"], "values": {"MAX_CANDIDATES": "9"}}
    )
    version_id = client.get("/api/config/versions").json()["versions"][-1]["id"]
    doc = client.get("/api/config").json()
    response = client.post(
        f"/api/config/versions/{version_id}/rollback", json={"hash": doc["hash"]}
    )
    assert response.status_code == 200
    current = client.get("/api/config").json()
    params = {param["name"]: param for param in current["params"]}
    assert params["MAX_CANDIDATES"]["value"] == 7
