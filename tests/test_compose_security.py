"""Compose 契约：面板直接持有 docker.sock 换取完整控制，其余权限保持收紧。"""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def _compose(name: str = "compose.example.yaml") -> dict:
    return yaml.safe_load((ROOT / name).read_text(encoding="utf-8"))


def test_default_panel_binds_loopback_only():
    panel = _compose()["services"]["panel"]
    assert panel["ports"] == ["127.0.0.1:8080:8080"]


def test_panel_mounts_docker_socket_for_full_control():
    compose = _compose()
    panel = compose["services"]["panel"]
    assert any(
        "/var/run/docker.sock" in str(volume) for volume in panel["volumes"]
    )
    assert "scanner-control" not in compose["services"]


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
