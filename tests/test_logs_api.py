def test_log_stream_emits_lines(client, fake_controller):
    fake_controller.log_chunks = [b"line-1\nline-2\n"]
    with client.stream("GET", "/api/logs/stream?tail=10") as response:
        assert response.status_code == 200
        body = b"".join(response.iter_bytes())
    assert b"line-1" in body and b"line-2" in body


def test_download_has_attachment_header(client, fake_controller):
    response = client.get("/api/logs/download?tail=10")
    assert response.status_code == 200
    assert "attachment" in response.headers["content-disposition"]
    assert "line-1" in response.text


def test_logs_are_redacted(client, fake_controller):
    fake_controller.log_chunks = [b"GIT_TOKEN=abc123\nurl https://u:p@host/x\n"]
    body = client.get("/api/logs/download?tail=10").text
    assert "abc123" not in body
    assert "u:p" not in body
    assert "host/x" in body


def test_logs_unavailable_returns_503(client, fake_controller):
    fake_controller.raise_unavailable = True
    assert client.get("/api/logs/download?tail=10").status_code == 503
