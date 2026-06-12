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

MIN_VERSION = (0, 6, 0)

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

# lead-llc1 packaging fix (tmpl-263): _render_lead_env_example reads
# templates/ops/.env.example at bootstrap time, but the leading-dot file is a
# packaging hazard — a `templates/ops/*` glob does NOT match dotfiles, so the
# DELIVERED artifact silently omits it and a fresh `pip install` +
# `shop-templates bootstrap --shop-type lead` crashes with FileNotFoundError.
# This guard asserts against the BUILT ARTIFACT (an editable / PYTHONPATH=src
# run would mask the defect): every ops/ template the bootstrap path reads —
# including the dotfile — must ride along in the package. We pin the full ops/
# set so a future glob change cannot drop a sibling either.
OPS_PACKAGED_RELS = [
    "templates/ops/.env.example",
    "templates/ops/Dockerfile.shopsystem-shell",
    "templates/ops/agent-vault-check",
    "templates/ops/agent-vault-provision",
    "templates/ops/compose.yaml",
    "templates/ops/shop-scenario-completion",
    "templates/ops/shop-shell",
]

# lead-emui hardening: the lead-llc1 fix ships `.env.example` via an EXPLICIT
# per-file package-data entry. That is the correct, deliberate choice (a broad
# `templates/ops/.*` glob could sweep stray dotfiles), but it has a hazard: the
# NEXT ops file added — especially another dotfile — silently drops from the
# built artifact again (the same bug class as tmpl-263) until someone remembers
# to add another explicit entry. The hard-coded OPS_PACKAGED_RELS list above has
# the same staleness: it pins today's known set, not whatever the source tree
# actually carries tomorrow. This generic guard closes that gap by deriving the
# expected set from the SOURCE tree at test time: EVERY file present under
# `src/shop_templates/templates/ops/` must be a member of BOTH the built sdist
# and the built wheel. A future dropped ops file is named automatically,
# regardless of its name, with no test edit required.
OPS_SOURCE_DIR = REPO_ROOT / "src" / "shop_templates" / "templates" / "ops"

# v0.6.0 ships the lead-m56e bc-emit work-done wrapper as a PACKAGE-DELIVERED
# console-script: `[project.scripts]` declares `bc-emit = shop_templates.bc_emit:main`
# and the `shop_templates/bc_emit.py` module rides along in the built artifact.
# This is delivery-currency: the wrapper only reaches launched BCs after the
# published version advances past 0.5.0 and the artifact actually carries both
# the entry-point declaration and the module.
BC_EMIT_SCRIPT_DECL = "bc-emit = \"shop_templates.bc_emit:main\""
BC_EMIT_MODULE_REL = "shop_templates/bc_emit.py"

# v0.6.0 ships the lead-llc1 agent-vault compose render fix: the delivered
# ops/compose.yaml must carry the REAL broker image `infisical/agent-vault:latest`
# and must NOT carry the old `hashicorp` placeholder. The dummyco spike (lead-jdfb)
# re-pours this to stand up the real broker, so the published artifact has to
# reflect it.
COMPOSE_REL = "templates/ops/compose.yaml"
COMPOSE_AGENT_VAULT_IMAGE = "infisical/agent-vault:latest"
COMPOSE_FORBIDDEN_IMAGE = "hashicorp"


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

_BUILD_WHEEL_SCRIPT = """
import sys
import setuptools.build_meta as backend
name = backend.build_wheel(sys.argv[1])
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


@pytest.fixture(scope="module")
def built_wheel(tmp_path_factory) -> Path:
    """Build a wheel from the repo and return its path.

    The wheel is the artifact `pip install` actually unpacks onto a fresh
    machine, so wheel membership is the closest in-process proxy for the
    clean-install bootstrap. Like the sdist fixture, it drives the repo's own
    PEP-517 backend (`setuptools.build_meta`) so the package-data globs are
    resolved exactly as a real publish would resolve them."""
    out = tmp_path_factory.mktemp("wheel")
    result = subprocess.run(
        [sys.executable, "-c", _BUILD_WHEEL_SCRIPT, str(out)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"wheel build failed:\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )
    wheel_name = result.stdout.strip().splitlines()[-1]
    wheel = out / wheel_name
    assert wheel.exists(), f"backend reported {wheel_name!r} but it is missing in {out}"
    return wheel


def _wheel_has_member(wheel: Path, suffix: str) -> bool:
    """True iff the wheel carries a member whose path ends with `suffix`."""
    import zipfile

    with zipfile.ZipFile(wheel) as zf:
        return any(name.endswith(suffix) for name in zf.namelist())


def _sdist_has_member(sdist: Path, suffix: str) -> bool:
    """True iff the sdist carries a member whose path ends with `suffix`."""
    with tarfile.open(sdist, "r:gz") as tf:
        return any(m.name.endswith(suffix) for m in tf.getmembers())


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


def test_delivered_artifact_ships_all_ops_templates_including_dotfile(
    built_sdist, built_wheel
):
    """lead-llc1 packaging fix (tmpl-263): every ops/ template the bootstrap
    path reads must ride along in BOTH the sdist and the wheel — including the
    leading-dot `.env.example`, which `_render_lead_env_example` reads at
    `shop-templates bootstrap --shop-type lead` time.

    This asserts against the BUILT ARTIFACTS, not the source tree, because the
    defect this guards is invisible from an editable / PYTHONPATH=src run: the
    file exists in `src/` either way. The hazard is that a `templates/ops/*`
    package-data glob does NOT match dotfiles, so the published sdist+wheel
    silently omit `.env.example` and a fresh `pip install` + bootstrap crashes
    with FileNotFoundError. We pin the full ops/ set so no glob change can drop
    a sibling either."""
    sdist_missing = [
        rel for rel in OPS_PACKAGED_RELS if not _sdist_has_member(built_sdist, rel)
    ]
    wheel_missing = [
        rel for rel in OPS_PACKAGED_RELS if not _wheel_has_member(built_wheel, rel)
    ]
    assert not sdist_missing and not wheel_missing, (
        f"delivered ops/ template set is incomplete in the BUILT ARTIFACT — a "
        f"fresh pip install + `shop-templates bootstrap --shop-type lead` would "
        f"crash on the missing file(s). sdist missing: {sdist_missing}; wheel "
        f"missing: {wheel_missing}. (A `templates/ops/*` glob does not match "
        f"the leading-dot `.env.example`.)"
    )


def test_every_source_ops_template_is_shipped_in_both_artifacts(
    built_sdist, built_wheel
):
    """lead-emui generic parity guard: EVERY file under the source
    `templates/ops/` directory must ride along in BOTH the built sdist and the
    built wheel.

    Unlike `test_delivered_artifact_ships_all_ops_templates_including_dotfile`
    (which pins a hand-maintained list), this guard derives the expected set
    from the SOURCE TREE at test time, so it future-proofs against the *next*
    dropped ops file regardless of name: add an ops template, and if a stale
    `package-data` config omits it from the artifact, this guard fails and names
    it. That is the same bug class as tmpl-263 — `.env.example` was dropped
    because `templates/ops/*` does not match leading-dot files — caught now
    mechanically rather than per-file. This complements (does not reverse) the
    deliberate explicit-entry choice for `.env.example`; it is strictly
    additive coverage.

    Asserts against the BUILT ARTIFACTS, not the source tree, because the defect
    it guards is invisible from an editable / PYTHONPATH=src run (the file exists
    in `src/` either way)."""
    source_rels = sorted(
        f"templates/ops/{p.name}"
        for p in OPS_SOURCE_DIR.iterdir()
        if p.is_file()
    )
    assert source_rels, (
        f"no ops templates found under {OPS_SOURCE_DIR}; the source tree is "
        f"missing the ops/ template set entirely"
    )
    sdist_missing = [
        rel for rel in source_rels if not _sdist_has_member(built_sdist, rel)
    ]
    wheel_missing = [
        rel for rel in source_rels if not _wheel_has_member(built_wheel, rel)
    ]
    assert not sdist_missing and not wheel_missing, (
        f"source-vs-artifact ops parity broken — files present under "
        f"{OPS_SOURCE_DIR} but MISSING from the delivered artifact (a fresh "
        f"pip install would not pour them). sdist missing: {sdist_missing}; "
        f"wheel missing: {wheel_missing}. Add an explicit "
        f"`[tool.setuptools.package-data]` entry for each named file (a "
        f"`templates/ops/*` glob does not match leading-dot files)."
    )


def test_delivered_artifact_declares_bc_emit_console_script(built_sdist):
    """lead-m56e: v0.6.0 ships the bc-emit work-done wrapper as a
    package-delivered console-script. The delivered artifact's PKG-INFO /
    pyproject-derived metadata must declare the `bc-emit` entry point so a
    clean `pip install ...@v0.6.0` exposes the `bc-emit` command. We read the
    pyproject carried inside the sdist (the [project.scripts] table) as the
    authoritative declaration, since that is exactly what the PEP-517 build
    consumes to register the console-script."""
    pyproject = _sdist_member(built_sdist, "/pyproject.toml", prefer_shallowest=True)
    assert BC_EMIT_SCRIPT_DECL in pyproject, (
        f"delivered pyproject does not declare the bc-emit console-script "
        f"({BC_EMIT_SCRIPT_DECL!r}); a clean tag-install would not expose the "
        f"lead-m56e bc-emit work-done wrapper command"
    )


def test_delivered_artifact_ships_bc_emit_module(built_sdist, built_wheel):
    """lead-m56e: the `shop_templates/bc_emit.py` module backing the bc-emit
    console-script must ride along in BOTH the built sdist and the built wheel,
    or the declared entry point resolves to a missing module on a clean
    install."""
    assert _sdist_has_member(built_sdist, BC_EMIT_MODULE_REL), (
        f"delivered sdist is missing the bc-emit module {BC_EMIT_MODULE_REL!r}; "
        f"the declared console-script would fail to import on a clean install"
    )
    assert _wheel_has_member(built_wheel, BC_EMIT_MODULE_REL), (
        f"delivered wheel is missing the bc-emit module {BC_EMIT_MODULE_REL!r}; "
        f"the declared console-script would fail to import on a clean install"
    )


def test_delivered_compose_renders_real_infisical_agent_vault(built_sdist):
    """lead-llc1: v0.6.0 ships the real agent-vault broker render. The
    delivered ops/compose.yaml must carry `infisical/agent-vault:latest` and
    must NOT carry the old `hashicorp` placeholder image, so the dummyco spike
    (lead-jdfb) re-pours a compose that stands up the real broker rather than a
    placeholder."""
    body = _sdist_member(built_sdist, COMPOSE_REL)
    assert COMPOSE_AGENT_VAULT_IMAGE in body, (
        f"delivered ops/compose.yaml does not render the real broker image "
        f"{COMPOSE_AGENT_VAULT_IMAGE!r}; a tag-install would not pour the "
        f"lead-llc1 agent-vault render"
    )
    assert COMPOSE_FORBIDDEN_IMAGE not in body, (
        f"delivered ops/compose.yaml still carries the forbidden placeholder "
        f"image substring {COMPOSE_FORBIDDEN_IMAGE!r}; the lead-llc1 render fix "
        f"replaced it with {COMPOSE_AGENT_VAULT_IMAGE!r}"
    )
