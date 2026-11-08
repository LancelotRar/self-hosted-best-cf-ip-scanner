import json


def test_get_lists_params_with_source_and_hash(client):
    body = client.get("/api/config").json()
    assert body["hash"]
    assert body["revision"] >= 1
    assert body["updated_at"]
    params = {param["name"]: param for param in body["params"]}
    assert params["SAMPLE_STRIDE"]["value"] == 256
    assert params["SAMPLE_STRIDE"]["source"] == "custom"
    assert params["TCP_MIN_SUCCESS"]["source"] == "custom"
    assert "IMAGE_TAG" not in params
    assert params["GIT_TOKEN"]["secret"] is True
    # 底层参数只保留给后端，不在面板展示与修改
    assert params["PROBE_PATH"]["hidden"] is True
    assert params["SKIP_LOCATIONS"]["hidden"] is True
    assert params["PINNED_FILE"]["hidden"] is True
    assert params["DETAIL_CSV_NAME"]["hidden"] is False
    assert params["PINNED_OUTPUT_NAME"]["hidden"] is False
    assert params["GIT_AUTHOR_NAME"]["hidden"] is True
    assert params["no_proxy"]["hidden"] is True
    assert params["PUSH_LISTS"]["hidden"] is True
    assert params["PROBE_HOST"]["hidden"] is False


def test_get_does_not_expose_removed_candidate_cap(client):
    """候选量完全由地址库决定：参数表里不应再有 MAX_CANDIDATES。"""
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


def test_put_syncs_lowercase_no_proxy(client, fake_controller, settings):
    doc = client.get("/api/config").json()
    response = client.put(
        "/api/config",
        json={"hash": doc["hash"], "values": {"NO_PROXY": "example.com"}},
    )
    assert response.status_code == 200
    data = json.loads(settings.runtime_config_path.read_text(encoding="utf-8"))
    assert data["NO_PROXY"] == "example.com"
    assert data["no_proxy"] == "example.com"


def test_config_get_requires_login(anon_client):
    assert anon_client.get("/api/config").status_code == 401


def test_repo_userinfo_is_masked_and_not_stored_in_versions(client, settings):
    document = client.get("/api/config").json()
    response = client.put(
        "/api/config",
        json={
            "hash": document["hash"],
            "values": {"GIT_REPO_URL": "https://bob:s3cr3t@github.com/o/r.git"},
        },
    )
    assert response.status_code == 200
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
