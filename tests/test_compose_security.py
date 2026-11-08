"""Compose 安全契约：默认栈必须收紧，控制能力必须显式可选。"""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def _compose(name: str = "compose.example.yaml") -> dict:
    return yaml.safe_load((ROOT / name).read_text(encoding="utf-8"))


def test_default_panel_binds_loopback_only():
    panel = _compose()["services"]["panel"]
    assert panel["ports"] == ["127.0.0.1:8080:8080"]


def test_default_panel_does_not_mount_docker_socket():
    panel = _compose()["services"]["panel"]
    assert not any(
        "/var/run/docker.sock" in str(volume) for volume in panel["volumes"]
    )


def test_default_panel_drops_all_capabilities():
    panel = _compose()["services"]["panel"]
    assert panel["cap_drop"] == ["ALL"]
    assert "no-new-privileges:true" in panel["security_opt"]


def test_panel_reads_outputs_and_cache_only():
    panel = _compose()["services"]["panel"]
    volumes = {str(item) for item in panel["volumes"]}
    assert "scan-output:/output:ro" in volumes
    assert "publish-cache:/cache:ro" in volumes


def test_scanner_and_panel_have_resource_limits():
    compose = _compose()
    scanner = compose["services"]["scanner"]
    panel = compose["services"]["panel"]
    assert scanner["ulimits"]["nofile"]["soft"] == 65536
    assert scanner["pids_limit"] == 512
    assert scanner["mem_limit"] == "1g"
    assert panel["pids_limit"] == 256
    assert panel["mem_limit"] == "256m"


def test_control_overlay_uses_sidecar_not_panel_socket():
    overlay = _compose("compose.control.yaml")
    panel = overlay["services"]["panel"]
    sidecar = overlay["services"]["scanner-control"]

    assert not any(
        "/var/run/docker.sock" in str(volume) for volume in panel.get("volumes", [])
    )
    assert any(
        "/var/run/docker.sock" in str(volume) for volume in sidecar["volumes"]
    )
    assert panel["environment"]["SCANNER_CONTROL_URL"] == "http://scanner-control:8090"
