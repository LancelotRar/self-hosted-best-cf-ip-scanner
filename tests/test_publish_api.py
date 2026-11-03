def test_token_never_returned(client, settings):
    settings.env_path.write_text("GIT_TOKEN=secret\n", encoding="utf-8")
    body = client.get("/api/publish").json()
    token = next(param for param in body["params"] if param["name"] == "GIT_TOKEN")
    assert token["value"] is None and token["configured"] is True


def test_last_result_distinguishes_publish_failure(client, runs_tsv):
    body = client.get("/api/publish").json()
    assert body["last"]["scan_exit"] == 0
    assert body["last"]["publish_exit"] == 1


def test_last_is_null_without_records(client):
    body = client.get("/api/publish").json()
    assert body["last"] is None


def test_put_updates_git_params(client):
    document = client.get("/api/publish").json()
    response = client.put(
        "/api/publish",
        json={"hash": document["hash"], "values": {"GIT_BRANCH": "release"}},
    )
    assert response.status_code == 200
    assert response.json()["changed"][0]["name"] == "GIT_BRANCH"

    params = {
        param["name"]: param for param in client.get("/api/config").json()["params"]
    }
    assert params["GIT_BRANCH"]["value"] == "release"
