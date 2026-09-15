"""Shape of the CI/CD configuration: every action SHA-pinned, the seven CI jobs present,
the release path tag-triggered, dependabot weekly and grouped for all three ecosystems."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"
SHA_PIN = re.compile(r"^[\w.-]+/[\w.-]+(?:/[\w./-]+)?@[0-9a-f]{40}$")


def _load(name: str) -> dict:
    return yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))


def _uses(doc: dict) -> list[str]:
    """Every external `uses:` in a workflow or a composite action. Local `./` refs are ours."""
    out = []
    jobs = doc.get("jobs") or {}
    steps = list(doc.get("runs", {}).get("steps", []))  # composite action
    for job in jobs.values():
        if "uses" in job:
            out.append(job["uses"])
        steps.extend(job.get("steps", []))
    out.extend(step["uses"] for step in steps if "uses" in step)
    return [u for u in out if not u.startswith("./")]


def test_every_action_is_pinned_to_a_commit_sha() -> None:
    files = sorted(WORKFLOWS.glob("*.yml")) + sorted(
        (ROOT / ".github" / "actions").glob("*/action.yml")
    )
    assert len(files) >= 4
    for path in files:
        wf = yaml.safe_load(path.read_text(encoding="utf-8"))
        text = path.read_text(encoding="utf-8")
        for ref in _uses(wf):
            assert SHA_PIN.match(ref), f"{path.name}: {ref} is not pinned to a 40-hex commit SHA"
            line = next(ln for ln in text.splitlines() if ref in ln)
            assert re.search(r"#\s*v?\d", line), f"{path.name}: {ref} has no version comment"


def test_ci_has_the_seven_jobs_in_dependency_order() -> None:
    ci = _load("ci.yml")
    jobs = ci["jobs"]
    for name in ("lint", "test-js", "test-py", "licence", "sbom", "build-sim", "e2e-smoke"):
        assert name in jobs, f"ci.yml lacks job {name}"
    assert "lint" in jobs["test-js"]["needs"]
    assert "lint" in jobs["test-py"]["needs"]
    assert "build-sim" in jobs["e2e-smoke"]["needs"]
    assert jobs["licence"]["uses"] == "./.github/workflows/licence-gate.yml"
    triggers = ci[True] if True in ci else ci["on"]
    assert "push" in triggers and "pull_request" in triggers
    assert "sbom" in jobs and any(
        "upload-artifact" in s.get("uses", "") for s in jobs["sbom"]["steps"]
    )


def test_release_is_tag_triggered_and_needs_no_human() -> None:
    rel = _load("release.yml")
    triggers = rel[True] if True in rel else rel["on"]
    assert triggers["push"]["tags"] == ["v*"]
    assert "workflow_dispatch" not in triggers
    text = (WORKFLOWS / "release.yml").read_text(encoding="utf-8")
    for needle in ("uv build", "docker build", "docker push", "gh release create", "ghcr.io"):
        assert needle in text, f"release.yml lacks {needle}"
    perms = rel.get("permissions") or {}
    assert perms.get("contents") == "write" and perms.get("packages") == "write"


def test_licence_gate_is_callable_from_ci() -> None:
    gate = _load("licence-gate.yml")
    triggers = gate[True] if True in gate else gate["on"]
    assert "workflow_call" in triggers


def test_dependabot_weekly_grouped_three_ecosystems() -> None:
    cfg = yaml.safe_load((ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8"))
    assert cfg["version"] == 2
    ecosystems = {u["package-ecosystem"] for u in cfg["updates"]}
    assert ecosystems == {"npm", "uv", "github-actions"}
    for u in cfg["updates"]:
        assert u["schedule"]["interval"] == "weekly", u
        assert u.get("groups"), f"{u['package-ecosystem']} updates are not grouped"
