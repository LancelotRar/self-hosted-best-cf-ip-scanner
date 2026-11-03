from scanner.ippool import library_errors


def test_library_errors_report_line_numbers():
    errors = library_errors("# ok\n1.2.3.4/24\nnot-an-ip\n")
    assert errors == [(3, "not-an-ip")]


def test_put_rejects_invalid_line(client, data_dir):
    response = client.put(
        "/api/library", json={"hash": "...", "content": "not-an-ip\n"}
    )
    assert response.status_code == 422
    assert response.json()["details"][0]["line"] == 1


def test_get_reports_hash_mtime_and_stats(client, data_dir):
    (data_dir / "ip-library.txt").write_text("# note\n1.2.3.4/24\n", encoding="utf-8")
    body = client.get("/api/library").json()
    assert body["hash"]
    assert body["mtime"]
    assert body["stats"]["networks"] == 1


def test_put_creates_backup_and_returns_new_hash(client, data_dir):
    (data_dir / "ip-library.txt").write_text("1.2.3.4/24\n", encoding="utf-8")
    document = client.get("/api/library").json()
    response = client.put(
        "/api/library",
        json={
            "hash": document["hash"],
            "content": "# note\n104.16.0.0/24\n1.1.1.1:8443\n",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["hash"] != document["hash"]
    assert (data_dir / "ip-library.txt").read_text(encoding="utf-8").startswith("# note")

    backups = client.get("/api/library/backups").json()["backups"]
    assert backups
    restored = client.post(f"/api/library/backups/{backups[0]['name']}/restore")
    assert restored.status_code == 200
    assert "1.2.3.4/24" in restored.json()["content"]


def test_put_rejects_stale_hash_after_valid_content(client, data_dir):
    (data_dir / "ip-library.txt").write_text("1.2.3.4/24\n", encoding="utf-8")
    response = client.put(
        "/api/library", json={"hash": "stale", "content": "104.16.0.0/24\n"}
    )
    assert response.status_code == 409


def test_restore_rejects_traversal(client):
    # 用编码的反斜杠让名字到达处理器（路径分隔符会被客户端先规范化）。
    response = client.post("/api/library/backups/..%5C..%5C.env/restore")
    assert response.status_code == 400
