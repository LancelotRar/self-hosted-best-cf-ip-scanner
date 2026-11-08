"""镜像拆分契约：scanner/panel 各自 Dockerfile，互不携带对方运行期依赖。"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def _yaml(name: str) -> dict:
    return yaml.safe_load((ROOT / name).read_text(encoding="utf-8"))


def test_each_container_has_its_own_dockerfile():
    assert (ROOT / "scanner" / "Dockerfile").is_file()
    assert (ROOT / "panel" / "Dockerfile").is_file()
    assert not (ROOT / "Dockerfile").exists()


def test_standard_compose_is_pull_only():
    base = _yaml("compose.example.yaml")
    services = base["services"]
    scanner_image = services["scanner"]["image"]
    panel_image = services["panel"]["image"]
    assert scanner_image != panel_image
    assert panel_image.endswith("-panel:latest")
    # 标准部署示例只拉取镜像；本地构建由 Dockerfile + docs/deployment.md 承担。
    assert "build" not in services["scanner"]
    assert "build" not in services["panel"]


def test_publish_workflow_builds_both_dockerfiles():
    workflow = _yaml(".github/workflows/docker.yml")
    steps = workflow["jobs"]["publish"]["steps"]
    files = {
        step.get("with", {}).get("file")
        for step in steps
        if "docker/build-push-action" in step.get("uses", "")
    }
    assert {"scanner/Dockerfile", "panel/Dockerfile"} <= files


def test_ci_builds_both_dockerfiles():
    workflow = _yaml(".github/workflows/ci.yml")
    steps = workflow["jobs"]["build"]["steps"]
    files = {
        step.get("with", {}).get("file")
        for step in steps
        if "docker/build-push-action" in step.get("uses", "")
    }
    assert {"scanner/Dockerfile", "panel/Dockerfile"} <= files


def test_images_do_not_cross_copy_runtime_dependencies():
    scanner = (ROOT / "scanner" / "Dockerfile").read_text(encoding="utf-8")
    panel = (ROOT / "panel" / "Dockerfile").read_text(encoding="utf-8")

    assert "COPY --link panel" not in scanner
    assert "web/dist" not in scanner
    assert "supercronic" not in panel
    assert "apk add git su-exec" not in panel


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
