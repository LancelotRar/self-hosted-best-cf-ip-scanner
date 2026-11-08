def test_path_traversal_is_rejected(client):
    for name in ["../secret.txt", "..%2Fsecret.txt", "/etc/passwd", "sub/../../secret.txt"]:
        assert client.get(f"/api/outputs/{name}").status_code in (400, 404)


def test_preview_txt_and_csv(client, output_dir):
    (output_dir / "GLOBAL20.txt").write_text("# 20 条\n1.2.3.4:443#SG\n", encoding="utf-8")
    body = client.get("/api/outputs/GLOBAL20.txt").json()
    assert body["kind"] == "text" and "1.2.3.4" in body["content"]

    (output_dir / "detail.csv").write_text(
        "IP,端口\n1.2.3.4,443\n", encoding="utf-8"
    )
    csv_body = client.get("/api/outputs/detail.csv").json()
    assert csv_body["kind"] == "csv"
    assert csv_body["headers"][0] == "IP"
    assert csv_body["rows"][0][0] == "1.2.3.4"


def test_list_reports_read_time_and_files(client, output_dir):
    (output_dir / "GLOBAL20.txt").write_text(
        "# 20 条\n1.2.3.4\n5.6.7.8\n", encoding="utf-8"
    )
    body = client.get("/api/outputs").json()
    assert body["read_at"]
    names = [item["name"] for item in body["files"]]
    assert names == ["GLOBAL20.txt"]
    assert body["files"][0]["count"] == 2


def test_database_stores_bounded_preview_not_full_file(client, output_dir, settings):
    (output_dir / "BIG.txt").write_text("1.2.3.4\n" * 20000, encoding="utf-8")
    client.get("/api/outputs")

    from panel import db

    conn = db.connect(settings.db_path)
    try:
        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(artifacts)").fetchall()
        }
        assert "content" not in columns
        row = conn.execute(
            "SELECT preview, preview_truncated, count FROM artifacts WHERE name = 'BIG.txt'"
        ).fetchone()
        assert len(row["preview"]) <= 128 * 1024
        assert row["preview_truncated"] == 1
        assert row["count"] == 20000
    finally:
        conn.close()


def test_download_returns_attachment(client, output_dir):
    (output_dir / "GLOBAL20.txt").write_text("x\n", encoding="utf-8")
    response = client.get("/api/outputs/GLOBAL20.txt?download=true")
    assert response.status_code == 200
    assert "attachment" in response.headers["content-disposition"]


def test_missing_file_is_404(client):
    assert client.get("/api/outputs/nope.txt").status_code == 404
