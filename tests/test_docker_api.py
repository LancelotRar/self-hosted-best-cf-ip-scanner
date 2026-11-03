import inspect

import pytest

from panel.docker_api import ScannerController, ScannerUnavailable


def test_resolve_uses_label_when_name_missing(fake_client):
    controller = ScannerController(fake_client, "best-cf-ip-scanner")
    container = controller.resolve()
    assert container.name == "best-cf-ip-scanner"


def test_exec_script_passes_run_id_env(fake_client, fake_container):
    handle = ScannerController(fake_client, "scanner").exec_script(
        "/usr/local/bin/scan-and-publish.sh", {"RUN_ID": "r1", "RUN_TRIGGER": "panel"}
    )
    assert handle.run_id == "r1"
    assert fake_container.exec_env["RUN_ID"] == "r1"
    assert list(handle.stream()) == [b"run-output\n"]
    assert handle.wait() == 0


def test_no_arbitrary_container_id_accepted():
    assert "container_id" not in inspect.signature(ScannerController).parameters


def test_status_maps_state_health_and_image(fake_client):
    status = ScannerController(fake_client, "scanner").status()
    assert status["state"] == "running"
    assert status["health"] == "healthy"
    assert status["image"] == "ghcr.io/example/scanner:test"


def test_unknown_script_is_rejected(fake_client):
    controller = ScannerController(fake_client, "scanner")
    with pytest.raises(ValueError):
        controller.exec_script("/bin/sh", {})


def test_missing_container_raises_unavailable(empty_docker_client):
    controller = ScannerController(empty_docker_client, "nope")
    with pytest.raises(ScannerUnavailable):
        controller.resolve()
