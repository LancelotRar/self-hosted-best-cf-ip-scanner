import json


def _empty_hash(client) -> str:
    return client.get("/api/locations").json()["hash"]


def test_get_returns_entries_and_count(client):
    body = client.get("/api/locations").json()
    assert body["entries"] == []
    assert body["count"] == 0
    assert body["hash"]


def test_put_normalizes_and_sorts_entries(client):
    response = client.put(
        "/api/locations",
        json={
            "hash": _empty_hash(client),
            "entries": [
                {"code": "nrt", "country": "jp"},
                {"code": "AMS", "country": "NL"},
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["entries"] == [
        {"code": "AMS", "country": "NL"},
        {"code": "NRT", "country": "JP"},
    ]
    assert body["count"] == 2


def test_put_projects_json_projection_for_scanner(client, data_dir):
    client.put(
        "/api/locations",
        json={"hash": _empty_hash(client), "entries": [{"code": "HKG", "country": "HK"}]},
    )
    projected = json.loads((data_dir / "locations.json").read_text(encoding="utf-8"))
    assert projected == {"HKG": "HK"}


def test_put_rejects_bad_codes_with_row_numbers(client):
    response = client.put(
        "/api/locations",
        json={
            "hash": _empty_hash(client),
            "entries": [
                {"code": "HK", "country": "HK"},
                {"code": "HKG", "country": "HKG"},
            ],
        },
    )
    assert response.status_code == 422
    details = response.json()["details"]
    assert [item["line"] for item in details] == [1, 2]
    assert "3 个大写字母" in details[0]["message"]


def test_put_rejects_duplicate_codes(client):
    response = client.put(
        "/api/locations",
        json={
            "hash": _empty_hash(client),
            "entries": [
                {"code": "HKG", "country": "HK"},
                {"code": "HKG", "country": "CN"},
            ],
        },
    )
    assert response.status_code == 422
    assert "重复" in response.json()["details"][0]["message"]


def test_put_rejects_stale_hash(client):
    response = client.put(
        "/api/locations",
        json={"hash": "stale", "entries": [{"code": "HKG", "country": "HK"}]},
    )
    assert response.status_code == 409
