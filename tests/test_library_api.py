from scanner.ippool import library_errors


def test_library_errors_report_line_numbers():
    errors = library_errors("# ok\n1.2.3.4/24\nnot-an-ip\n")
    assert errors == [(3, "not-an-ip", "无法解析的地址条目")]


def test_library_errors_point_port_entries_to_pinned():
    errors = library_errors("1.1.1.1:8443\n")
    assert errors == [(1, "1.1.1.1:8443", "带端口的条目不参与采样，请放到「固定保留」")]


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


def _pin_stride(settings, stride: int = 256) -> None:
    """固定采样步长，让「参与探测」的断言与 conftest 的首次导入无关。"""
    from panel import db, settings_store

    conn = db.connect(settings.db_path)
    try:
        with conn:
            settings_store.apply_overrides(
                conn,
                settings,
                {"PROBE_HOST": "probe.example.com", "SAMPLE_STRIDE": str(stride)},
                actor="test",
            )
    finally:
        conn.close()


def test_stats_expand_networks_and_commented_entries(client, settings, data_dir):
    """注释掉的网段只有落在有效库里才计入「跳过」。"""
    _pin_stride(settings)
    (data_dir / "ip-library.txt").write_text(
        "# 104.22.0.0/24\n"
        "# 说明：这一行不是地址条目\n"
        "104.16.0.0/24\n"
        "104.16.1.0/24\n",
        encoding="utf-8",
    )
    stats = client.get("/api/library").json()["stats"]
    assert stats["probe"] == 2  # 相邻两个 /24 合并成 512 个地址 -> 2 个采样窗口
    assert stats["total"] == 512
    assert stats["skipped"] == 0  # 注释的 /24 不在有效库范围内，什么都没扣掉


def test_stats_follow_sample_stride(client, settings, data_dir):
    """候选量只由地址库决定：改步长才改数量，也没有额外的总量上限。"""
    (data_dir / "ip-library.txt").write_text("104.16.0.0/22\n", encoding="utf-8")

    _pin_stride(settings, 256)
    assert client.get("/api/library").json()["stats"]["probe"] == 4

    _pin_stride(settings, 512)
    assert client.get("/api/library").json()["stats"]["probe"] == 2


def test_projection_file_never_overrides_database(client, settings, data_dir):
    """数据库是唯一真源：改卷内投影文件不会影响面板读到的内容。"""
    _pin_stride(settings)
    document = client.get("/api/library").json()
    response = client.put(
        "/api/library",
        json={"hash": document["hash"], "content": "104.16.0.0/24\n"},
    )
    assert response.status_code == 200
    assert response.json()["stats"]["probe"] == 1

    (data_dir / "ip-library.txt").write_text(
        "104.16.0.0/24\n104.17.0.0/24\n# 104.18.0.0/24\n", encoding="utf-8"
    )
    stats = client.get("/api/library").json()["stats"]
    assert stats["probe"] == 1
    assert stats["skipped"] == 0


def test_save_projects_file_for_scanner(client, settings, data_dir):
    """扫描器只读文件：保存后卷内投影必须立刻等于数据库内容。"""
    document = client.get("/api/library").json()
    client.put(
        "/api/library",
        json={"hash": document["hash"], "content": "# note\n104.16.0.0/24\n"},
    )
    projected = (data_dir / "ip-library.txt").read_text(encoding="utf-8")
    assert projected == "# note\n104.16.0.0/24\n"


def test_put_creates_backup_and_returns_new_hash(client, data_dir):
    (data_dir / "ip-library.txt").write_text("1.2.3.4/24\n", encoding="utf-8")
    document = client.get("/api/library").json()
    response = client.put(
        "/api/library",
        json={
            "hash": document["hash"],
            "content": "# note\n104.16.0.0/24\n",
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


def test_put_rejects_port_entries_in_sampled_library(client):
    document = client.get("/api/library").json()
    response = client.put(
        "/api/library",
        json={"hash": document["hash"], "content": "1.1.1.1:8443\n"},
    )
    assert response.status_code == 422
    detail = response.json()["details"][0]
    assert detail["field"] == "library"
    assert "固定保留" in detail["message"]


def test_stats_report_total_addresses(client, settings, data_dir):
    """注释掉有效网的子集时，真的把它从总量与采样里扣掉。"""
    _pin_stride(settings)
    (data_dir / "ip-library.txt").write_text(
        "104.16.0.0/13\n# 104.16.0.0/14\n", encoding="utf-8"
    )
    stats = client.get("/api/library").json()["stats"]
    assert stats["total"] == 262144  # /13 去掉 /14，只剩 104.20.0.0/14
    assert stats["probe"] == 1024
    assert stats["skipped"] == 262144


def test_pinned_round_trip_and_projection(client, data_dir):
    document = client.get("/api/library").json()
    response = client.put(
        "/api/library",
        json={
            "hash": document["hash"],
            "content": "104.16.0.0/13\n",
            "pinned": "1.2.3.4:443#手动添加\n1.2.3.5\n",
            "pinned_hash": document["pinned"]["hash"],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["pinned"]["count"] == 2
    assert body["pinned"]["content"].startswith("1.2.3.4:443#手动添加")
    assert (data_dir / "ip-pinned.txt").read_text(encoding="utf-8") == (
        "1.2.3.4:443#手动添加\n1.2.3.5\n"
    )


def test_each_section_saves_independently(client):
    """两块各自保存：只提交固定保留时，地址库内容原样保留。"""
    document = client.get("/api/library").json()
    client.put(
        "/api/library",
        json={"hash": document["hash"], "content": "104.16.0.0/13\n"},
    )
    after = client.get("/api/library").json()

    response = client.put(
        "/api/library",
        json={
            "hash": after["hash"],
            "pinned": "1.2.3.4:443#手动\n",
            "pinned_hash": after["pinned"]["hash"],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["content"] == "104.16.0.0/13\n"
    assert body["pinned"]["count"] == 1


def test_pinned_view_exposes_output_file_name(client, settings):
    document = client.get("/api/config").json()
    response = client.put(
        "/api/config",
        json={"hash": document["hash"], "values": {"PINNED_OUTPUT_NAME": "FIXED"}},
    )
    assert response.status_code == 200
    assert client.get("/api/library").json()["pinned"]["output_name"] == "FIXED"


def test_put_rejects_invalid_pinned_line(client):
    document = client.get("/api/library").json()
    response = client.put(
        "/api/library",
        json={
            "hash": document["hash"],
            "content": "104.16.0.0/13\n",
            "pinned": "not-an-ip\n",
            "pinned_hash": document["pinned"]["hash"],
        },
    )
    assert response.status_code == 422
    detail = response.json()["details"][0]
    assert detail["field"] == "pinned"
    assert detail["line"] == 1


def test_put_rejects_stale_hash_after_valid_content(client, data_dir):
    (data_dir / "ip-library.txt").write_text("1.2.3.4/24\n", encoding="utf-8")
    response = client.put(
        "/api/library", json={"hash": "stale", "content": "104.16.0.0/24\n"}
    )
    assert response.status_code == 409


def test_restore_rejects_traversal(client):
    # 用编码的反斜杠让名字到达处理器（路径分隔符会被客户端先规范化）。
    response = client.post("/api/library/backups/..%5C..%5Csecret.txt/restore")
    assert response.status_code == 400
