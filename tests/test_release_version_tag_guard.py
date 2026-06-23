"""Release-process safeguard guarding against a tag being cut with a
pyproject [project].version that lags the tag — the regression scenario 192
(88a5418db371a12a, lead-g72o) pins against and that the v0.21.0 tag exhibited.

The pinned scenario asserts the invariant over EXISTING tags; this guard is
the forward-looking counterpart wired into the release path so a FUTURE tag
push cannot ship a lagging pyproject. We assert two things:

  1. The version-tag release workflow (.github/workflows/release.yml) carries
     a step that gates the run on the pushed tag's vX.Y.Z matching the
     pyproject [project].version at that commit, failing the run on mismatch.

  2. The guard is realized by a committed, executable check script that
     actually performs the comparison and exits non-zero on a mismatch —
     so the workflow step is not merely a comment but a real gate.

Per ADR-022 the obsolete cross-repo repository_dispatch fan-in (the
"Notify shopsystem-bc-launcher" step + its BC_LAUNCHER_DISPATCH_TOKEN) has
been retired in favor of the centralized bc-launcher poll (lead-czwo). We
therefore also assert the release workflow no longer carries any
repository_dispatch step or BC_LAUNCHER_DISPATCH_TOKEN reference, so the
failing curl step that broke every release cannot regress back in.
"""
from __future__ import annotations

import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

import yaml


def _bc_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _release_workflow_path() -> Path:
    return _bc_root() / ".github" / "workflows" / "release.yml"


def _guard_script_path() -> Path:
    return _bc_root() / "scripts" / "check_tag_matches_pyproject_version.py"


def _iter_steps(parsed: dict):
    jobs = parsed.get("jobs")
    if not isinstance(jobs, dict):
        return
    for job in jobs.values():
        if not isinstance(job, dict):
            continue
        for step in job.get("steps", []) or []:
            if isinstance(step, dict):
                yield step


def _step_text(step: dict) -> str:
    parts = []
    for key in ("uses", "run", "name"):
        val = step.get(key)
        if isinstance(val, str):
            parts.append(val)
    return "\n".join(parts)


def test_release_workflow_gates_tag_against_pyproject_version():
    """The version-tag release workflow must carry a step that runs the
    version-equals-tag guard, so a tag cut with a lagging pyproject fails
    the release run rather than shipping bad dist metadata."""
    wf_path = _release_workflow_path()
    assert wf_path.is_file(), f"missing release workflow at {wf_path}"
    parsed = yaml.safe_load(wf_path.read_text())

    guard_steps = [
        s for s in _iter_steps(parsed)
        if "check_tag_matches_pyproject_version" in _step_text(s)
    ]
    assert guard_steps, (
        "release.yml has no step invoking the version-equals-tag guard "
        "(check_tag_matches_pyproject_version); a future tag could be cut "
        "with a lagging pyproject [project].version and ship bad dist "
        "metadata (the v0.21.0 -> 0.20.0 regression)."
    )

    # The guard must run after checkout so the working tree (pyproject.toml,
    # the guard script) is present. Assert it is a step in the job, ordered
    # after the checkout step.
    for job in parsed["jobs"].values():
        steps = job.get("steps") or []
        idx_guard = next(
            (i for i, s in enumerate(steps)
             if "check_tag_matches_pyproject_version" in _step_text(s)),
            None,
        )
        idx_checkout = next(
            (i for i, s in enumerate(steps)
             if "actions/checkout" in _step_text(s)),
            None,
        )
        if idx_guard is not None and idx_checkout is not None:
            assert idx_checkout < idx_guard, (
                "the version-equals-tag guard step must run AFTER checkout so "
                "the working tree (pyproject.toml + guard script) is present"
            )


def test_release_workflow_has_no_repository_dispatch_fanout():
    """Per ADR-022 the cross-repo repository_dispatch fan-in to
    shopsystem-bc-launcher is retired (superseded by the centralized
    bc-launcher poll, lead-czwo). The failing curl step (exit 22 on an
    empty/unauthorized token, which broke every release) must be gone, and
    neither the repository_dispatch wiring nor its BC_LAUNCHER_DISPATCH_TOKEN
    secret reference may regress back into the release workflow."""
    wf_path = _release_workflow_path()
    text = wf_path.read_text()

    assert "repository_dispatch" not in text, (
        "release.yml still references repository_dispatch; ADR-022 retired "
        "the cross-repo dispatch fan-in to shopsystem-bc-launcher."
    )
    assert "BC_LAUNCHER_DISPATCH_TOKEN" not in text, (
        "release.yml still references BC_LAUNCHER_DISPATCH_TOKEN; ADR-022 "
        "decommissioned the cross-repo dispatch token."
    )
    assert "shopsystem-bc-launcher" not in text, (
        "release.yml still references shopsystem-bc-launcher; the cross-repo "
        "dispatch step was retired by ADR-022."
    )

    # And structurally: no step in the workflow POSTs to a dispatches endpoint.
    parsed = yaml.safe_load(text)
    dispatch_steps = [
        s for s in _iter_steps(parsed)
        if "dispatches" in _step_text(s)
    ]
    assert not dispatch_steps, (
        "release.yml still carries a step targeting a dispatches endpoint; "
        "the repository_dispatch fan-in was retired by ADR-022."
    )


def test_guard_script_exists_and_is_executable():
    path = _guard_script_path()
    assert path.is_file(), (
        f"missing release guard script at {path}: the workflow step must be "
        "backed by a real, committed check, not a comment"
    )
    mode = path.stat().st_mode
    assert mode & stat.S_IXUSR, f"{path} must be executable (chmod +x)"


def _run_guard(tag: str, version: str, tmp_path: Path) -> subprocess.CompletedProcess:
    """Run the guard against a synthetic pyproject carrying `version`,
    passing it `tag` as the pushed tag. Returns the completed process."""
    proj = tmp_path / "pyproject.toml"
    proj.write_text(
        "[project]\n"
        'name = "shop-templates"\n'
        f'version = "{version}"\n'
    )
    return subprocess.run(
        [sys.executable, str(_guard_script_path()), "--tag", tag,
         "--pyproject", str(proj)],
        capture_output=True, text=True,
    )


def test_guard_passes_when_tag_matches_pyproject(tmp_path):
    cp = _run_guard("v0.21.0", "0.21.0", tmp_path)
    assert cp.returncode == 0, (
        f"guard should pass when tag v0.21.0 matches pyproject 0.21.0; "
        f"exited {cp.returncode}\n{cp.stdout}\n{cp.stderr}"
    )


def test_guard_fails_when_pyproject_lags_tag(tmp_path):
    # The exact regression: tag v0.21.0, pyproject 0.20.0.
    cp = _run_guard("v0.21.0", "0.20.0", tmp_path)
    assert cp.returncode != 0, (
        "guard MUST fail (non-zero exit) when the pushed tag v0.21.0 does "
        "not match the pyproject version 0.20.0 — this is the v0.21.0 lag "
        "the guard exists to prevent"
    )
    assert "0.21.0" in (cp.stdout + cp.stderr) and "0.20.0" in (cp.stdout + cp.stderr), (
        "guard failure should name both the tag version and the pyproject "
        "version so the operator can see the mismatch"
    )


def test_guard_fails_when_tag_is_a_later_version_than_pyproject(tmp_path):
    cp = _run_guard("v0.22.0", "0.21.0", tmp_path)
    assert cp.returncode != 0, (
        "guard must fail on any tag-vs-pyproject mismatch, not only lags"
    )
