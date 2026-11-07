def test_get_lists_params_with_source_and_hash(client, settings):
    settings.env_path.write_text("SAMPLE_STRIDE=128\n", encoding="utf-8")
    body = client.get("/api/config").json()
    assert body["hash"]
    assert body["mtime"]
    params = {param["name"]: param for param in body["params"]}
    assert params["SAMPLE_STRIDE"]["value"] == 128
    assert params["SAMPLE_STRIDE"]["source"] == "dotenv"
    assert params["TCP_MIN_SUCCESS"]["source"] == "default"
    assert params["IMAGE_TAG"]["read_only"] is True
    assert params["GIT_TOKEN"]["secret"] is True


def test_get_does_not_expose_removed_candidate_cap(client, settings):
    """候选量完全由地址库决定：参数表里不应再有 MAX_CANDIDATES。"""
    settings.env_path.write_text("MAX_CANDIDATES=300\n", encoding="utf-8")
    params = {param["name"]: param for param in client.get("/api/config").json()["params"]}
    assert "MAX_CANDIDATES" not in params


def test_put_requires_csrf(client):
    saved = client.headers.pop("X-CSRF-Token")
    try:
        response = client.put("/api/config", json={"hash": "x", "values": {}})
        assert response.status_code == 403
    finally:
        client.headers["X-CSRF-Token"] = saved


def test_put_stale_hash_returns_409(client):
    response = client.put(
        "/api/config", json={"hash": "stale", "values": {"SAMPLE_STRIDE": "512"}}
    )
    assert response.status_code == 409


def test_put_returns_save_result(client, fake_controller):
    doc = client.get("/api/config").json()
    fake_controller.effective = {}
    response = client.put(
        "/api/config",
        json={"hash": doc["hash"], "values": {"SAMPLE_STRIDE": "512"}},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["written"] is True
    assert body["changed"][0]["name"] == "SAMPLE_STRIDE"
    assert body["changed"][0]["effect"] == "next_round"


def test_config_get_requires_login(anon_client):
    assert anon_client.get("/api/config").status_code == 401


def test_repo_userinfo_is_masked_and_not_stored_in_versions(client, settings):
    settings.env_path.write_text(
        "GIT_REPO_URL=https://bob:s3cr3t@github.com/o/r.git\n", encoding="utf-8"
    )
    document = client.get("/api/config").json()
    params = {param["name"]: param for param in document["params"]}
    assert "s3cr3t" not in str(params["GIT_REPO_URL"]["value"])
    assert "***" in str(params["GIT_REPO_URL"]["value"])

    client.put(
        "/api/config",
        json={"hash": document["hash"], "values": {"SAMPLE_STRIDE": "512"}},
    )
    versions = client.get("/api/config/versions").json()["versions"]
    assert versions
    for version in versions:
        assert "s3cr3t" not in version["diff"]


def test_versions_and_rollback(client, fake_controller):
    doc = client.get("/api/config").json()
    client.put(
        "/api/config", json={"hash": doc["hash"], "values": {"SAMPLE_STRIDE": "512"}}
    )
    versions = client.get("/api/config/versions").json()["versions"]
    assert versions and versions[0]["actor"] == "admin"
    assert "GIT_TOKEN" not in versions[0]["diff"]

    doc = client.get("/api/config").json()
    client.put(
        "/api/config", json={"hash": doc["hash"], "values": {"SAMPLE_STRIDE": "1024"}}
    )
    version_id = client.get("/api/config/versions").json()["versions"][-1]["id"]
    doc = client.get("/api/config").json()
    response = client.post(
        f"/api/config/versions/{version_id}/rollback", json={"hash": doc["hash"]}
    )
    assert response.status_code == 200
    current = client.get("/api/config").json()
    params = {param["name"]: param for param in current["params"]}
    assert params["SAMPLE_STRIDE"]["value"] == 512
