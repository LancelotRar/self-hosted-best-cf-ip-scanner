"""镜像拆分契约：scanner/panel 各自构建，互不携带对方运行期依赖。"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def _yaml(name: str) -> dict:
    return yaml.safe_load((ROOT / name).read_text(encoding="utf-8"))


def test_dockerfile_has_scanner_and_panel_targets():
    text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert re.search(r"^FROM\s+\S+\s+AS\s+scanner\s*$", text, re.M)
    assert re.search(r"^FROM\s+\S+\s+AS\s+panel\s*$", text, re.M)


def test_compose_build_uses_distinct_targets_and_images():
    base = _yaml("compose.example.yaml")
    build = _yaml("compose.build.yaml")
    scanner_image = base["services"]["scanner"]["image"]
    panel_image = base["services"]["panel"]["image"]
    assert scanner_image != panel_image
    assert panel_image.endswith("-panel:latest")
    assert build["services"]["scanner"]["build"]["target"] == "scanner"
    assert build["services"]["panel"]["build"]["target"] == "panel"


def test_publish_workflow_builds_both_targets():
    workflow = _yaml(".github/workflows/docker.yml")
    steps = workflow["jobs"]["publish"]["steps"]
    targets = {
        step.get("with", {}).get("target")
        for step in steps
        if "docker/build-push-action" in step.get("uses", "")
    }
    assert {"scanner", "panel"} <= targets


def test_ci_builds_both_targets():
    workflow = _yaml(".github/workflows/ci.yml")
    steps = workflow["jobs"]["build"]["steps"]
    targets = {
        step.get("with", {}).get("target")
        for step in steps
        if "docker/build-push-action" in step.get("uses", "")
    }
    assert {"scanner", "panel"} <= targets


def test_targets_do_not_cross_copy_runtime_dependencies():
    text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    scanner_match = re.search(r"^FROM \S+ AS scanner\s*$", text, re.M)
    panel_match = re.search(r"^FROM \S+ AS panel\s*$", text, re.M)
    assert scanner_match and panel_match
    scanner_section = text[scanner_match.end() : panel_match.start()]
    panel_section = text[panel_match.end() :]

    assert "COPY --link panel" not in scanner_section
    assert "web/dist" not in scanner_section
    assert "apk add git su-exec" not in panel_section
    assert "supercronic" not in panel_section


def test_scanner_package_does_not_eagerly_import_probe():
    code = "import sys, scanner; print('scanner.probe' in sys.modules)"
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == "False"


def test_panel_modules_import_without_curl_cffi():
    code = (
        "import sys; sys.modules['curl_cffi'] = None; "
        "import panel.app, panel.config_store, scanner.validation, scanner.ippool; "
        "print('ok')"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == "ok"
