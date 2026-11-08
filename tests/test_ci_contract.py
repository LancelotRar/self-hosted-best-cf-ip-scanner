"""CI/发布契约：面板改动必须触发镜像发布，供应链元数据必须显式开启。"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SHA_PIN = re.compile(r"@[0-9a-f]{40}$")


def _workflow(name: str) -> dict:
    return yaml.safe_load((ROOT / ".github" / "workflows" / name).read_text("utf-8"))


def _on(workflow: dict) -> dict:
    # PyYAML 按 YAML 1.1 把裸 on 解析成 True
    return workflow.get("on") or workflow.get(True) or {}


def _step(job: dict, name: str) -> dict:
    for step in job["steps"]:
        if step.get("name") == name:
            return step
    raise AssertionError(f"找不到步骤：{name}")


def test_publish_paths_include_panel_and_web():
    paths = _on(_workflow("docker.yml"))["push"]["paths"]
    assert "panel/**" in paths
    assert "scanner/**" in paths
    assert "panel/requirements.txt" in paths


def test_publish_enables_sbom_and_max_provenance():
    job = _workflow("docker.yml")["jobs"]["publish"]
    step = next(
        item
        for item in job["steps"]
        if "docker/build-push-action" in item.get("uses", "")
    )
    assert step["with"]["sbom"] is True
    assert step["with"]["provenance"] == "mode=max"


def test_backend_coverage_includes_scanner():
    job = _workflow("ci.yml")["jobs"]["backend"]
    step = _step(job, "Unit and API tests with coverage")
    assert "--cov=scanner" in step["run"]


def test_security_job_runs_dependency_audits():
    job = _workflow("ci.yml")["jobs"]["security"]
    uses = " ".join(step.get("uses", "") for step in job["steps"])
    runs = "\n".join(step.get("run", "") for step in job["steps"])
    assert "pypa/gh-action-pip-audit" in uses
    assert "npm audit --omit=dev --audit-level=high" in runs


def test_build_job_scans_both_images():
    job = _workflow("ci.yml")["jobs"]["build"]
    uses = " ".join(step.get("uses", "") for step in job["steps"])
    assert uses.count("aquasecurity/trivy-action") == 2
    runs = " ".join(
        str(step.get("with", {}).get("severity", "")) for step in job["steps"]
    )
    assert "HIGH,CRITICAL" in runs


def test_trivyignore_exists():
    assert (ROOT / ".trivyignore").is_file()


def test_frontend_lint_runs_in_ci():
    job = _workflow("ci.yml")["jobs"]["frontend"]
    runs = "\n".join(step.get("run", "") for step in job["steps"])
    assert "npm --prefix panel/web run lint" in runs


def test_smoke_checks_panel_has_docker_socket():
    job = _workflow("ci.yml")["jobs"]["smoke"]
    step = _step(job, "Verify default security posture")
    assert "test -S /var/run/docker.sock" in step["run"]
    assert "CapDrop" in step["run"]


def test_e2e_uses_standard_compose():
    job = _workflow("ci.yml")["jobs"]["e2e"]
    step = _step(job, "Start clean stack")
    assert "docker compose up -d" in step["run"]
    assert "--profile control" not in step["run"]


def test_third_party_actions_are_sha_pinned():
    for name in ("ci.yml", "docker.yml"):
        workflow = _workflow(name)
        for job in workflow["jobs"].values():
            for step in job.get("steps", []):
                uses = step.get("uses", "")
                if uses.startswith(("actions/", "docker/")):
                    assert SHA_PIN.search(uses), f"{name}: 未固定 SHA: {uses}"


def test_dependabot_covers_all_dependency_ecosystems():
    text = (ROOT / ".github" / "dependabot.yml").read_text("utf-8")
    for ecosystem in ("docker", "pip", "npm", "github-actions"):
        assert f"package-ecosystem: {ecosystem}" in text
