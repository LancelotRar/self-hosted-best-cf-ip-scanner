"""探测核心的离线单元测试：不访问网络，只验证判定与重试语义。"""

from __future__ import annotations

from scanner import probe


def test_parse_endpoint_body_accepts_valid_colo_and_loc():
    assert probe.parse_endpoint_body("colo=HKG\nloc=HK\n") == ("HKG", "HK")


def test_parse_endpoint_body_rejects_malformed_values():
    assert probe.parse_endpoint_body("colo=hk\nloc=H\n") == (None, None)
    assert probe.parse_endpoint_body("") == (None, None)


def test_tcp_rtt_once_returns_elapsed_and_swallows_oserror(monkeypatch):
    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(
        probe.socket, "create_connection", lambda *a, **k: FakeConnection()
    )
    assert probe.tcp_rtt_once("192.0.2.1", 443) is not None

    def fail(*a, **k):
        raise OSError("unreachable")

    monkeypatch.setattr(probe.socket, "create_connection", fail)
    assert probe.tcp_rtt_once("192.0.2.1", 443) is None


def test_measure_tcp_counts_success_and_loss(monkeypatch):
    values = iter([1.0, 2.0, None])
    monkeypatch.setattr(probe, "tcp_rtt_once", lambda *a, **k: next(values))
    result = probe.measure_tcp("192.0.2.1", 443, attempts=3, min_success=2)
    assert result.success_count == 2
    assert result.qualified is True
    assert result.loss_rate == 1 / 3
    assert result.avg_ms == 1.5


def test_measure_tcp_all_failed_is_unqualified(monkeypatch):
    monkeypatch.setattr(probe, "tcp_rtt_once", lambda *a, **k: None)
    result = probe.measure_tcp("192.0.2.1", 443, attempts=2, min_success=1)
    assert result.success_count == 0
    assert result.qualified is False
    assert result.error == "tcp_connect_failed"


def test_check_endpoint_returns_colo_on_200(monkeypatch):
    monkeypatch.setattr(
        probe,
        "_request_endpoint",
        lambda *a, **k: (12.5, 200, "colo=HKG\nloc=HK\n"),
    )
    result = probe.check_endpoint("192.0.2.1", 443, attempts=2)
    assert result.error is None
    assert result.colo == "HKG"
    assert result.country == "HK"


def test_check_endpoint_does_not_retry_deterministic_403(monkeypatch):
    calls = {"n": 0}

    def response(*a, **k):
        calls["n"] += 1
        return 10.0, 403, "error 1034"

    monkeypatch.setattr(probe, "_request_endpoint", response)
    result = probe.check_endpoint("192.0.2.1", 443, attempts=3)
    assert calls["n"] == 1
    assert result.error is not None
    assert result.colo is None


def test_check_endpoint_retries_transient_500(monkeypatch):
    responses = iter([(10.0, 500, "oops"), (11.0, 200, "colo=NRT\n")])
    monkeypatch.setattr(probe, "_request_endpoint", lambda *a, **k: next(responses))
    result = probe.check_endpoint("192.0.2.1", 443, attempts=2)
    assert result.error is None
    assert result.colo == "NRT"


def test_combine_results_requires_tcp_and_endpoint_pass():
    tcp_ok = probe.TcpMetrics(
        "192.0.2.1", 443, 3, 3, 0.0, 1.0, 1.0, 1.0, None, True
    )
    tcp_bad = probe.TcpMetrics(
        "192.0.2.2", 443, 3, 0, 1.0, None, None, None, "tcp_connect_failed", False
    )
    endpoint_ok = probe.EndpointResult(1.0, "HKG", "HK", None)
    endpoint_bad = probe.EndpointResult(None, None, None, "no-colo-field(status=403)")

    combined = probe.combine_results(
        [tcp_ok, tcp_bad],
        {("192.0.2.1", 443): endpoint_ok, ("192.0.2.2", 443): endpoint_bad},
    )
    assert combined[0].qualified is True
    assert combined[1].qualified is False
