"""ADR-047 bin/doctor scenario-coherence gate (work_id lead-vzxd.10, tmpl-etd).

The rendered bin/doctor gains a NAMED "scenario coherence" check that runs
`scenarios validate --aggregate <features-dir> --manifest <manifest>
--origin-index <origin-index>` (scenarios v0.3.1) and folds its verdict into
doctor's aggregate diagnosis: the check goes RED (a [FAIL] line that
contributes a non-zero aggregate exit) on ANY corpus violation — E_* per-file
codes, W_BC_UNASSIGNED, W_ORIGIN_UNRESOLVED, or E_STRAY_GHERKIN — and GREEN on
a conformant corpus. This makes doctor's system-consistency gate ENFORCE
ADR-056 (the defined end).

Hermetic: the check's manifest / origin-index / features-dir are
launcher-provisioned, so they resolve through env-overridable DOCTOR_* paths
the tests inject with fixture corpora (conformant vs. non-conformant). The
real `scenarios` CLI runs against those fixtures — no stub — so the assertions
reflect the actual v0.3.1 aggregate verdict. When the corpus is not
provisioned at all (a fresh, unprovisioned shop), the check degrades to a
graceful PASS so doctor's existing aggregate scenarios stay green.
"""
from __future__ import annotations

import os
import stat as _stat
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_ops_generification import _bootstrap  # noqa: E402

from scenarios.outstanding import parse_then_block_only_hash  # noqa: E402


_FAKE_PSQL = """#!/usr/bin/env bash
[ "${DOCTOR_TEST_PG_OK:-0}" = "1" ] && exit 0
exit 2
"""

_FAKE_CURL = """#!/usr/bin/env bash
insecure=0
for a in "$@"; do [ "$a" = "-k" ] && insecure=1; done
if [ "${DOCTOR_TEST_BROKER_UP:-0}" != "1" ]; then exit 7; fi
if [ "$insecure" = "1" ]; then exit 0; fi
[ "${DOCTOR_TEST_CA_TRUSTED:-0}" = "1" ] && exit 0
exit 60
"""

_OAUTH_REFRESHABLE = '{"refresh_token": "rt-abc", "access_token": "at-xyz"}'

# All three pre-existing checks pass; only the scenario-coherence inputs vary.
_ALL_PASS_ENV = {
    "SHOPMSG_DSN": "postgresql://postgres:postgres@localhost:5432/probe",
    "DOCTOR_TEST_PG_OK": "1",
    "DOCTOR_BROKER_URL": "https://localhost:14321/",
    "DOCTOR_TEST_BROKER_UP": "1",
    "DOCTOR_TEST_CA_TRUSTED": "1",
    "CLAUDE_OAUTH": _OAUTH_REFRESHABLE,
}

_COHERENCE_NAME = "scenario coherence"


def _run_doctor(target: Path, env_overrides: dict | None = None) -> subprocess.CompletedProcess:
    stubdir = Path(tempfile.mkdtemp(prefix="doctor_coh_stub_"))
    for name, body in (("psql", _FAKE_PSQL), ("curl", _FAKE_CURL)):
        p = stubdir / name
        p.write_text(body)
        p.chmod(p.stat().st_mode | _stat.S_IXUSR | _stat.S_IXGRP | _stat.S_IXOTH)
    env = dict(os.environ)
    env.pop("SHOPMSG_DSN", None)
    env.pop("CLAUDE_OAUTH", None)
    env["PATH"] = str(stubdir) + os.pathsep + env.get("PATH", "")
    if env_overrides:
        env.update({k: str(v) for k, v in env_overrides.items()})
    return subprocess.run(
        ["bash", str(target / "bin" / "doctor")],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(target),
        timeout=90,
    )


def _check_line(stdout: str, name: str) -> str:
    cands = [
        l
        for l in stdout.splitlines()
        if name in l and (l.lstrip().startswith("[PASS]") or l.lstrip().startswith("[FAIL]"))
    ]
    assert cands, f"no [PASS]/[FAIL] check line named {name!r} in doctor stdout:\n{stdout}"
    assert len(cands) == 1, f"expected exactly one check line named {name!r}; got {cands!r}"
    return cands[0]


def _status(line: str) -> str:
    s = line.lstrip()
    if s.startswith("[PASS]"):
        return "pass"
    if s.startswith("[FAIL]"):
        return "fail"
    raise AssertionError(f"check line carries no explicit [PASS]/[FAIL] status: {line!r}")


def _aggregate_line(stdout: str) -> str:
    cands = [l for l in stdout.splitlines() if "aggregate diagnosis" in l and "overall" in l]
    assert cands, f"no aggregate-diagnosis line in doctor stdout:\n{stdout}"
    return cands[0]


def _write_conformant_corpus(root: Path) -> dict:
    """A schema-conformant fixture corpus: @bc + @origin feature tags, a
    producer-canonical @scenario_hash per scenario, no stray .gherkin, no
    inter-scenario comments (so the v0.3.1 comment-folding defect is avoided)."""
    (root / "features").mkdir(parents=True)
    (root / "bc-manifest.yaml").write_text("bcs:\n  - name: shopsystem-templates\nservices: []\n")
    (root / "origin-index.txt").write_text("adr-056\n")
    s1 = (
        "  Scenario: alpha behavior\n"
        "    Given a thing\n"
        "    When I act\n"
        "    Then it works"
    )
    s2 = (
        "  Scenario: beta behavior\n"
        "    Given another thing\n"
        "    When I go\n"
        "    Then it is done"
    )
    h1 = parse_then_block_only_hash(s1)
    h2 = parse_then_block_only_hash(s2)
    (root / "features" / "clean.feature").write_text(
        "@bc:shopsystem-templates @origin:adr-056\n"
        "Feature: clean sample\n\n"
        f"  @scenario_hash:{h1}\n{s1}\n\n"
        f"  @scenario_hash:{h2}\n{s2}\n"
    )
    return {
        "DOCTOR_FEATURES_DIR": str(root / "features"),
        "DOCTOR_BC_MANIFEST": str(root / "bc-manifest.yaml"),
        "DOCTOR_ORIGIN_INDEX": str(root / "origin-index.txt"),
    }


def test_scenario_coherence_green_on_conformant_corpus(tmp_path):
    """GREEN: a conformant corpus yields a [PASS] scenario-coherence line, an
    overall-pass aggregate, and exit 0."""
    target = _bootstrap(tmp_path, "shopsystem-product")
    coords = _write_conformant_corpus(tmp_path / "conf")
    proc = _run_doctor(target, {**_ALL_PASS_ENV, **coords})
    line = _check_line(proc.stdout, _COHERENCE_NAME)
    assert _status(line) == "pass", f"conformant corpus must PASS coherence: {line!r}\n{proc.stdout}"
    agg = _aggregate_line(proc.stdout)
    assert "[PASS]" in agg and "[FAIL]" not in agg, f"aggregate must be overall PASS: {agg!r}"
    assert proc.returncode == 0, f"conformant run must exit 0; got {proc.returncode}\n{proc.stdout}"


def test_scenario_coherence_red_on_stray_gherkin(tmp_path):
    """RED: a stray legacy .gherkin (E_STRAY_GHERKIN) drives the coherence
    check to [FAIL], the aggregate to overall FAIL naming the check, and a
    non-zero exit."""
    target = _bootstrap(tmp_path, "shopsystem-product")
    coords = _write_conformant_corpus(tmp_path / "nonconf")
    # Introduce a violation: a legacy .gherkin still under the corpus.
    (Path(coords["DOCTOR_FEATURES_DIR"]) / "legacy.gherkin").write_text("Feature: legacy\n")
    proc = _run_doctor(target, {**_ALL_PASS_ENV, **coords})
    line = _check_line(proc.stdout, _COHERENCE_NAME)
    assert _status(line) == "fail", f"stray .gherkin must FAIL coherence: {line!r}\n{proc.stdout}"
    agg = _aggregate_line(proc.stdout)
    assert "[FAIL]" in agg, f"aggregate must be overall FAIL: {agg!r}"
    assert _COHERENCE_NAME in agg, f"aggregate must name the failed coherence check: {agg!r}"
    assert proc.returncode != 0, f"non-conformant run must exit non-zero; got {proc.returncode}"


def test_scenario_coherence_red_on_unassigned_bc(tmp_path):
    """RED: a transitional @bc:unassigned marker (W_BC_UNASSIGNED) also drives
    the coherence check RED and folds into the non-zero aggregate exit."""
    target = _bootstrap(tmp_path, "shopsystem-product")
    coords = _write_conformant_corpus(tmp_path / "unassigned")
    s = (
        "  Scenario: gamma behavior\n"
        "    Given yet another thing\n"
        "    When I proceed\n"
        "    Then it resolves"
    )
    h = parse_then_block_only_hash(s)
    (Path(coords["DOCTOR_FEATURES_DIR"]) / "pending.feature").write_text(
        "@bc:unassigned @origin:adr-056\n"
        "Feature: pending sample\n\n"
        f"  @scenario_hash:{h}\n{s}\n"
    )
    proc = _run_doctor(target, {**_ALL_PASS_ENV, **coords})
    line = _check_line(proc.stdout, _COHERENCE_NAME)
    assert _status(line) == "fail", f"@bc:unassigned must FAIL coherence: {line!r}\n{proc.stdout}"
    assert proc.returncode != 0, f"unassigned run must exit non-zero; got {proc.returncode}"


def test_scenario_coherence_hint_names_remediation(tmp_path):
    """The [FAIL] coherence line carries a remediation hint naming the
    corrective action (run the aggregate validate + resolve the violations),
    consistent with doctor's existing check shape."""
    target = _bootstrap(tmp_path, "shopsystem-product")
    coords = _write_conformant_corpus(tmp_path / "hint")
    (Path(coords["DOCTOR_FEATURES_DIR"]) / "legacy.gherkin").write_text("Feature: legacy\n")
    proc = _run_doctor(target, {**_ALL_PASS_ENV, **coords})
    line = _check_line(proc.stdout, _COHERENCE_NAME).lower()
    assert "hint:" in line, f"fail line must carry a remediation hint: {line!r}"
    assert "validate" in line, f"hint must name the aggregate validate remediation: {line!r}"


def test_scenario_coherence_graceful_when_unprovisioned(tmp_path):
    """A fresh, unprovisioned shop (no corpus / manifest / origin-index at the
    resolved paths) degrades to a graceful PASS — doctor's aggregate stays
    green and exit 0, so the pre-existing doctor scenarios are unaffected."""
    target = _bootstrap(tmp_path, "shopsystem-product")
    # No DOCTOR_FEATURES_DIR / manifest / origin-index provided, and the
    # bootstrapped shop renders none at the default paths.
    proc = _run_doctor(target, _ALL_PASS_ENV)
    line = _check_line(proc.stdout, _COHERENCE_NAME)
    assert _status(line) == "pass", f"unprovisioned corpus must PASS (graceful): {line!r}\n{proc.stdout}"
    assert proc.returncode == 0, f"unprovisioned run must exit 0; got {proc.returncode}\n{proc.stdout}"
