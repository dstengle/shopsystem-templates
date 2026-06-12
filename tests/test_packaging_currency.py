"""Packaging-currency guard (lead-slkk).

The launcher installs this package from a git tag and pours
templates/skills/<name>/SKILL.md byte-for-byte into a freshly launched
BC. lead-80t0 authored a health-bearing bc-router SKILL.md (auto-heal +
validate beads health incl. a test `dolt push` + hard-block session start
when unhealthy). That capability is additive delivery — for the launcher
to deliver it, the PUBLISHED package version must advance past the stale
0.2.0 that predates it.

These tests build the package *as it would be delivered* (a source
distribution) and assert, against the BUILT ARTIFACT (not the source
tree), that BOTH:

  (a) the delivered package version is >= 0.3.0, and
  (b) the bc-router SKILL.md carried in that artifact is the
      lead-80t0 health-bearing version (health/dolt vocabulary present).

Building the sdist and reading version + content from inside it is what
makes this a genuine *currency* guard: a stale 0.2.0 pyproject yields a
0.2.0 sdist and fails (a), even though the source tree's SKILL.md content
already satisfies (b). Both must hold on the same delivered artifact.
"""
from __future__ import annotations

import re
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

# Health/dolt vocabulary the lead-80t0 bc-router carries. The poured
# SKILL.md must mention auto-heal, beads health, a test `dolt push`, and a
# hard block of session start when the tracker is unhealthy.
HEALTH_VOCAB = ["health", "dolt"]

MIN_VERSION = (0, 5, 0)

REPO_ROOT = Path(__file__).resolve().parent.parent
BC_ROUTER_REL = "templates/skills/bc-router/SKILL.md"

# Self-contained role templates (lead-0nc8 WS-4 Part2): the delivered
# lead-architect / lead-po / bc-reviewer carry NO dangling spec citation
# (a bare `§` section reference or a `findings-from-prototype` pointer that
# resolves to a file the launched shop never receives).
SELF_CONTAINED_RELS = [
    "templates/lead-architect.md",
    "templates/lead-po.md",
    "templates/bc-reviewer.md",
]
DANGLING_CITE = re.compile(r"§|findings-from-prototype")

# PDR-014 skill (po↔architect decomposition exchange) must ride along in
# the delivered artifact so a tag-install pours it.
PDR014_SKILL_REL = "templates/skills/po-architect-decomposition-exchange/SKILL.md"

# v0.5.0 IS the ops-genericity release: it captures lead-faua 90308d0
# (render_ops_template / _ops_slug slug-parametric compose+shop-shell) and
# lead-w87b 51b57dd (agent-vault-provision + agent-vault-check rendered via
# {{OPS_SLUG}}). The currency guard locks what this release delivers: the
# built artifact's ops/ template set must carry the agent-vault scripts, and
# cli.py must carry the slug-rendering mechanism that makes ops/ generic.
OPS_VAULT_RELS = [
    "templates/ops/agent-vault-provision",
    "templates/ops/agent-vault-check",
]
CLI_REL = "shop_templates/cli.py"
CLI_SLUG_MECHANISM = ["render_ops_template", "_ops_slug", "{{OPS_SLUG}}"]


def _parse_version(raw: str) -> tuple[int, int, int]:
    m = re.match(r"(\d+)\.(\d+)\.(\d+)", raw.strip())
    assert m, f"unparseable version: {raw!r}"
    return tuple(int(g) for g in m.groups())  # type: ignore[return-value]


_BUILD_SDIST_SCRIPT = """
import sys
import setuptools.build_meta as backend
name = backend.build_sdist(sys.argv[1])
print(name)
"""


@pytest.fixture(scope="module")
def built_sdist(tmp_path_factory) -> Path:
    """Build a source distribution from the repo and return its path.

    This is the package *as it would be delivered* — the launcher's
    `pip install git+...@vX.Y.Z` resolves the same PEP-517 build backend
    (`setuptools.build_meta`, per this repo's [build-system]) over the same
    tree. Reading version + content from the sdist (rather than the working
    tree) is what distinguishes a currency guard from a content check.
    """
    out = tmp_path_factory.mktemp("dist")
    result = subprocess.run(
        [sys.executable, "-c", _BUILD_SDIST_SCRIPT, str(out)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"sdist build failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )
    sdist_name = result.stdout.strip().splitlines()[-1]
    sdist = out / sdist_name
    assert sdist.exists(), f"backend reported {sdist_name!r} but it is missing in {out}"
    return sdist


def _sdist_member(sdist: Path, suffix: str, prefer_shallowest: bool = False) -> str:
    """Return the decoded text of the sdist member whose path ends with
    `suffix`. When several match and `prefer_shallowest` is set, pick the
    one with the fewest path components (e.g. the root PKG-INFO over the
    egg-info copy); otherwise the match must be unique."""
    with tarfile.open(sdist, "r:gz") as tf:
        matches = [m for m in tf.getmembers() if m.name.endswith(suffix)]
        assert matches, f"no sdist member ending with {suffix!r}; members: {[m.name for m in tf.getmembers()][:20]}"
        if prefer_shallowest:
            chosen = min(matches, key=lambda m: m.name.count("/"))
        else:
            assert len(matches) == 1, f"ambiguous sdist members for {suffix!r}: {[m.name for m in matches]}"
            chosen = matches[0]
        f = tf.extractfile(chosen)
        assert f is not None
        return f.read().decode()


def test_delivered_package_version_is_at_least_min_version(built_sdist):
    """The published artifact's version must advance past the prior floor so
    the launcher's tag-install (no --force-reinstall) delivers the
    self-contained templates batch (lead-f3gm / lead-0nc8) and the PDR-014
    skill rather than a stale artifact."""
    # The sdist root carries the canonical PKG-INFO (an egg-info copy also
    # exists under src/; select the top-level one).
    pkg_info = _sdist_member(built_sdist, "/PKG-INFO", prefer_shallowest=True)
    version_line = next(
        l for l in pkg_info.splitlines() if l.startswith("Version:")
    )
    version = _parse_version(version_line.split(":", 1)[1])
    assert version >= MIN_VERSION, (
        f"delivered package version {version} < {MIN_VERSION}; the published "
        f"artifact predates the self-contained-templates batch (lead-f3gm / "
        f"lead-0nc8) and the PDR-014 skill, so a tag-install (no "
        f"--force-reinstall) would pour the stale pre-0.4.0 artifact"
    )


def test_delivered_role_templates_are_self_contained(built_sdist):
    """lead-0nc8 WS-4 Part2: the delivered lead-architect / lead-po /
    bc-reviewer must not carry a dangling spec citation (a bare `§` section
    reference or a `findings-from-prototype` pointer) that resolves to a
    file the launched shop never receives."""
    offenders = {}
    for rel in SELF_CONTAINED_RELS:
        body = _sdist_member(built_sdist, rel)
        hits = sorted(set(DANGLING_CITE.findall(body)))
        if hits:
            offenders[rel] = hits
    assert not offenders, (
        f"delivered role templates carry dangling spec citations "
        f"(§ / findings-from-prototype) that resolve to files the launched "
        f"shop never receives: {offenders}"
    )


def test_delivered_artifact_carries_pdr014_skill(built_sdist):
    """The PDR-014 po↔architect decomposition-exchange skill must ride along
    in the delivered artifact so a tag-install pours it."""
    body = _sdist_member(built_sdist, PDR014_SKILL_REL)
    assert body.strip(), (
        f"delivered PDR-014 skill {PDR014_SKILL_REL} is empty in the built "
        f"artifact; a tag-install would not pour it"
    )


def test_delivered_bc_router_carries_lead_80t0_health_step(built_sdist):
    """The bc-router SKILL.md inside the delivered artifact must be the
    health-bearing version (auto-heal + beads health + test dolt push +
    hard block), not the pre-lead-80t0 111-line/zero-health version."""
    body = _sdist_member(built_sdist, BC_ROUTER_REL)
    lowered = body.lower()
    matches = sum(lowered.count(term) for term in HEALTH_VOCAB)
    assert matches > 0, (
        f"delivered bc-router SKILL.md carries no health/dolt vocabulary "
        f"(matches={matches}); it is the pre-lead-80t0 version"
    )
    # Guard the specific lead-80t0 capability vocabulary, not just the words.
    assert "dolt" in lowered, "delivered bc-router lacks the test `dolt push` health check"
    assert "health" in lowered, "delivered bc-router lacks beads-health validation"


def test_delivered_artifact_carries_agent_vault_ops_scripts(built_sdist):
    """v0.5.0 captures lead-w87b 51b57dd: the agent-vault-provision +
    agent-vault-check ops/ scripts must ride along in the delivered artifact
    so a tag-install pours the {{OPS_SLUG}}-rendered vault provisioning into
    a bootstrapped lead ops/."""
    missing = {}
    for rel in OPS_VAULT_RELS:
        body = _sdist_member(built_sdist, rel)
        if not body.strip():
            missing[rel] = "empty"
    assert not missing, (
        f"delivered ops/ template set is missing the lead-w87b agent-vault "
        f"scripts (a tag-install would not pour them): {missing}"
    )


def test_delivered_cli_carries_slug_ops_mechanism(built_sdist):
    """v0.5.0 captures lead-faua 90308d0: cli.py in the delivered artifact
    must carry the slug-parametric ops/ rendering mechanism
    (render_ops_template / _ops_slug / {{OPS_SLUG}}) — this is the code that
    makes the bootstrapped ops/ generic rather than shopsystem-hardcoded."""
    body = _sdist_member(built_sdist, CLI_REL)
    absent = [tok for tok in CLI_SLUG_MECHANISM if tok not in body]
    assert not absent, (
        f"delivered cli.py lacks the slug-parametric ops/ rendering "
        f"mechanism (lead-faua 90308d0); missing tokens: {absent}"
    )
