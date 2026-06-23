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

NOTE (lead-q1wy): the guards in THIS module assert that each
`[project.scripts]` declaration is present and that the backing module rides
in the sdist/wheel — they are import-BLIND (they never check that the
installed console-script actually IMPORTS on a clean install). A
module-top-level import of an undeclared/transitive dep passes both
assertions yet dies at first invocation (the tmpl-20n bug class). That
import-currency check is covered GENERICALLY for every current and future
console-script in `tests/test_console_script_import_currency.py`; extend
THAT guard (it enumerates `[project.scripts]` automatically) rather than
adding another bc-emit-specific importability test.
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

MIN_VERSION = (0, 13, 0)

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
# PDR-020 slice 2: the dedicated shell Dockerfile (templates/ops/
# Dockerfile.shopsystem-shell) is retired — bin/shop-shell launches an
# ephemeral product-neutral bc-base instead — so it is no longer a packaged
# ops template.
OPS_PACKAGED_RELS = [
    "templates/ops/.env.example",
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

# v0.7.0 ships the lead-beym agent-vault-provision rewrite against the REAL
# agent-vault 0.32.0 command surface (owner/vault/credential/service/agent flow
# per ADR-026 D2). The delivered ops/agent-vault-provision must NOT carry the
# fabricated `agent-vault put` verb (0.32.0 has no such subcommand) and MUST use
# the real verbs, so the dummyco spike (lead-jdfb) re-pours a provision script
# that drives the live broker rather than crashing on an unknown subcommand.
PROVISION_REL = "templates/ops/agent-vault-provision"
PROVISION_FORBIDDEN_VERB = "agent-vault put"
PROVISION_REAL_VERBS = ["agent-vault vault credential", "agent-vault agent create"]

# v0.7.0 also locks the lead-beym sh-compatible compose healthcheck: the
# delivered ops/compose.yaml agent-vault healthcheck must use a real sh-callable
# probe (`nc -z`) and must NOT rely on the bash-only `/dev/tcp` pseudo-device,
# which the broker image's `sh` healthcheck shell cannot expand.
COMPOSE_FORBIDDEN_HEALTHCHECK = "/dev/tcp"
COMPOSE_SH_HEALTHCHECK_PROBE = "nc"

# v0.7.0 ships the lead-ld7i fix: bc-emit declares the `scenarios` VCS-pinned
# dependency so the published artifact's lazy import resolves on a clean install.
# The delivered pyproject must declare `scenarios` as a project dependency.
SCENARIOS_DEP_TOKEN = "scenarios"

# v0.8.0 ships the lead-l95x credential-key rename (2936c70): the delivered
# ops/agent-vault-provision must use SCREAMING_SNAKE_CASE credential keys and
# MUST NOT carry kebab-case credential keys. agent-vault rejects kebab
# credential keys, so a tag-install that poured the old casing would crash the
# dummyco spike (lead-jdfb) at `vault credential set`. lead-8jar CORRECTS the
# key NAMES to the live `fleet` vault's authoritative keys (GITHUB_USERNAME /
# GITHUB_TOKEN) — still SCREAMING_SNAKE, no kebab — and the `--username-key
# GITHUB_USERNAME --password-key GITHUB_TOKEN` service-add references ride along.
PROVISION_SCREAMING_SNAKE_KEYS = ["GITHUB_USERNAME", "GITHUB_TOKEN"]
PROVISION_FORBIDDEN_KEBAB_KEYS = ["github-pat-user", "github-pat", "github-username", "github-token"]

# v0.9.0 ships the lead-8jar five-live-fleet-service provision rewrite (4797c35,
# folds lead-eqzi + lead-71tq). The delivered ops/agent-vault-provision must
# register the Claude broker services — in particular `claude-api` against host
# `api.anthropic.com` attaching the `CLAUDE_OAUTH` bearer credential — so a fresh
# dummyco provision (spike iter-7) wires the full broker set and the iter-6
# Claude-401 is fixed. The human-gate prompt must reference the credential by its
# authoritative SCREAMING_SNAKE name `CLAUDE_OAUTH` and MUST NOT carry the old
# kebab `claude-oauth` (agent-vault rejects kebab credential keys). The .env
# writeback must reference both AGENT_VAULT_VAULT and AGENT_VAULT_CA_PEM so the
# provisioned broker address/vault/CA ride into the launched shop's .env.
PROVISION_CLAUDE_SERVICE_TOKENS = ["claude-api", "api.anthropic.com", "CLAUDE_OAUTH"]
PROVISION_FORBIDDEN_KEBAB_OAUTH = "claude-oauth"
PROVISION_ENV_WRITEBACK_KEYS = ["AGENT_VAULT_VAULT", "AGENT_VAULT_CA_PEM"]

# v0.10.0 ships the lead-yrex Claude-OAuth human-gate rewrite (d47c110): the
# delivered ops/agent-vault-provision must drive the CLAUDE_OAUTH credential
# through a PRE-POPULATED OAuth-TYPED credential-slot PROPOSAL — the operator
# only APPROVES it, rather than the script hand-creating the credential with a
# flat `vault credential set CLAUDE_OAUTH=...`. The proposal path preserves the
# refresh machinery (type:oauth + token_url) which a flat static credential set
# would destroy. So the delivered provision must carry the proposal verbs
# (`proposal create` + `proposal approve`) and the OAuth type marker (`type:oauth`
# or `"type": "oauth"`), and MUST NOT carry a flat `credential set CLAUDE_OAUTH`
# fallback. A tag-install that poured a flat-credential-set provision would
# store a non-refreshing CLAUDE_OAUTH and reproduce the broker token-expiry that
# lead-yrex fixed.
PROVISION_PROPOSAL_GATE_TOKENS = ["proposal create", "proposal approve"]
PROVISION_OAUTH_TYPE_FORMS = ['type:oauth', '"type": "oauth"', '"type":"oauth"']
PROVISION_FORBIDDEN_FLAT_OAUTH_SET = "credential set CLAUDE_OAUTH"

# v0.11.0 corrected-behavior (lead-9qdn / WALL-2): proposal create/approve run
# in AGENT mode on agent-vault 0.32.0 and REQUIRE a vault-scoped session — the
# owner session that authorized vault create / credential set / service add is
# insufficient ("Error: Session requires vault scope"). The delivered provision
# must mint a vault-scoped session via `vault token --vault` BEFORE the proposal
# step, and run the proposal subcommands under it with the three env vars
# (AGENT_VAULT_TOKEN=<scoped> / AGENT_VAULT_ADDR=http://localhost:14321 /
# AGENT_VAULT_VAULT). A tag-install that poured the pre-fix owner-session
# proposal step would die on "Session requires vault scope" at provision time.
PROVISION_SCOPED_SESSION_TOKENS = [
    "vault token --vault",
    "-e AGENT_VAULT_TOKEN=",
    "-e AGENT_VAULT_ADDR=http://localhost:14321",
    "-e AGENT_VAULT_VAULT=",
]

# v0.11.0 corrected-behavior (lead-7if5 / af58736): the bootstrap-poured
# top-level .gitignore must ignore `.env` (and `.env.*`) while keeping the
# `.env.example` scaffold tracked via a `!.env.example` negation, closing the
# master-password-commit gap. The CLI pours `templates/gitignore.template`
# verbatim into a launched shop's `.gitignore`, so the DELIVERED template must
# carry the `.env` ignore rule AND the `!.env.example` negation. A tag-install
# that poured the pre-fix template would let an operator's `.env` (holding the
# AGENT_VAULT_MASTER_PASSWORD / broker token) be committed.
GITIGNORE_TEMPLATE_REL = "templates/gitignore.template"
GITIGNORE_ENV_IGNORE_TOKENS = [".env"]
GITIGNORE_ENV_EXAMPLE_NEGATION = "!.env.example"

# v0.12.0 ships the lead-xgs0 authoring-time @scenario_hash move (59d2b93): the
# canonical lead-po template now writes the `@scenario_hash` tag at AUTHORING
# time as an explicit step (the PO owns the hash and computes it with
# `scenarios hash` as part of authoring), and the prohibition that the hash is
# "not yours" / "do NOT add @scenario_hash" is GONE. The `@bc:<name>` tag stays
# dispatch-time (CLI/Architect-added at assignment). This is delivery-currency:
# the reframed lead-po only reaches launched lead shops after the published
# version advances past 0.11.0 and the artifact actually carries the
# authoring-time hash step. We assert against the BUILT ARTIFACT so a
# tag-install that dropped or omitted the reframed template is caught.
LEAD_PO_REL = "templates/lead-po.md"
# The authoring-time hash step must be present: the PO computes
# `@scenario_hash` with `scenarios hash` AS PART OF AUTHORING.
LEAD_PO_AUTHORING_HASH_TOKENS = ["@scenario_hash", "scenarios hash"]
LEAD_PO_AUTHORING_PHRASE = "as part of authoring"
# The removed prohibition: the delivered lead-po must NOT tell the PO to leave
# the hash to someone else (e.g. "do NOT add @scenario_hash" / "hash
# computation is ... not yours" against the scenario_hash tag).
LEAD_PO_FORBIDDEN_PROHIBITIONS = [
    "do not add `@scenario_hash`",
    "do not add @scenario_hash",
    "hash computation is not yours",
    "@scenario_hash` is not yours",
    "@scenario_hash is not yours",
]
# The `@bc` tag must remain dispatch-time (Architect / assignment / CLI-added),
# not authored by the PO.
LEAD_PO_BC_DISPATCH_TOKEN = "@bc"

# v0.13.0 IS the release vehicle for lead-5mr5 (25fa894): lead bootstrap now
# pours the canonical lead skill-group (bring-up-bc + create-bc). This is
# delivery-currency: the skill-group only reaches launched lead shops once the
# published version advances past 0.12.0 AND the built artifact actually carries
# both SKILL.md files. We assert against the BUILT ARTIFACTS (sdist + wheel) so a
# tag-install that dropped them from the `templates/lead_skills/**/*` package-data
# glob is caught. The create-bc body must name the BC-creation mechanism it
# drives: `shop-templates bootstrap --shop-type bc`, `gh repo create`, and the
# bc-container launch flags — otherwise a poured create-bc cannot stand up a BC.
LEAD_SKILLS_RELS = [
    "templates/lead_skills/create-bc/SKILL.md",
    "templates/lead_skills/bring-up-bc/SKILL.md",
]
CREATE_BC_REL = "templates/lead_skills/create-bc/SKILL.md"
CREATE_BC_BODY_TOKENS = [
    "shop-templates bootstrap --shop-type bc",
    "gh repo create",
    "bc-container launch",
    "--repo-url",
]


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


def test_delivered_provision_uses_real_agent_vault_032_verbs(built_sdist):
    """lead-beym: v0.7.0 captures the agent-vault-provision rewrite against the
    REAL agent-vault 0.32.0 command surface. The delivered
    ops/agent-vault-provision must NOT carry the fabricated `agent-vault put`
    verb (0.32.0 has no such subcommand) and MUST use the real verbs
    (`agent-vault vault credential ...`, `agent-vault agent create ...`), so a
    tag-install pours a provision script that drives the live broker rather than
    crashing on an unknown subcommand (the dummyco spike lead-jdfb re-pours
    this to run the real end-to-end credential gate)."""
    body = _sdist_member(built_sdist, PROVISION_REL)
    assert PROVISION_FORBIDDEN_VERB not in body, (
        f"delivered ops/agent-vault-provision still carries the fabricated "
        f"{PROVISION_FORBIDDEN_VERB!r} verb; agent-vault 0.32.0 has no such "
        f"subcommand and the lead-beym rewrite replaced it with the real "
        f"owner/vault/credential/service/agent flow"
    )
    missing = [v for v in PROVISION_REAL_VERBS if v not in body]
    assert not missing, (
        f"delivered ops/agent-vault-provision lacks the real agent-vault 0.32.0 "
        f"verbs {missing}; the lead-beym rewrite drives the "
        f"owner/vault/credential/service/agent flow"
    )


def test_delivered_compose_healthcheck_is_sh_compatible(built_sdist):
    """lead-beym: the delivered ops/compose.yaml agent-vault healthcheck must be
    sh-compatible — it must use a real sh-callable probe (`nc -z`) and must NOT
    rely on the bash-only `/dev/tcp` pseudo-device, which the broker image's
    `sh` healthcheck shell cannot expand (the probe would silently never report
    healthy)."""
    body = _sdist_member(built_sdist, COMPOSE_REL)
    assert COMPOSE_FORBIDDEN_HEALTHCHECK not in body, (
        f"delivered ops/compose.yaml healthcheck still relies on the bash-only "
        f"{COMPOSE_FORBIDDEN_HEALTHCHECK!r} pseudo-device; the broker image's sh "
        f"healthcheck shell cannot expand it (lead-beym made it sh-compatible "
        f"via `nc -z`)"
    )
    assert COMPOSE_SH_HEALTHCHECK_PROBE in body, (
        f"delivered ops/compose.yaml does not carry the sh-compatible "
        f"{COMPOSE_SH_HEALTHCHECK_PROBE!r} healthcheck probe (lead-beym)"
    )


def test_delivered_pyproject_declares_scenarios_dependency(built_sdist):
    """lead-ld7i: v0.7.0 ships the bc-emit `scenarios` VCS-pinned dependency so
    the published artifact's lazy import resolves on a clean install. The
    delivered pyproject (carried inside the sdist) must declare `scenarios` as a
    project dependency, or a clean tag-install leaves bc-emit dead-on-arrival
    when its lazy scenarios import fires."""
    pyproject = _sdist_member(built_sdist, "/pyproject.toml", prefer_shallowest=True)
    assert SCENARIOS_DEP_TOKEN in pyproject, (
        f"delivered pyproject does not declare the {SCENARIOS_DEP_TOKEN!r} "
        f"dependency (lead-ld7i); a clean tag-install would leave bc-emit's lazy "
        f"scenarios import unresolved"
    )


def test_delivered_provision_uses_screaming_snake_credential_keys(built_sdist):
    """lead-l95x (2936c70): v0.8.0 ships the agent-vault-provision credential-key
    rename from kebab-case to SCREAMING_SNAKE_CASE. The delivered
    ops/agent-vault-provision must carry the SCREAMING_SNAKE credential keys
    (`GITHUB_PAT_USER`, `GITHUB_PAT`) — both in the `vault credential set` store
    and the `vault service add --username-key/--password-key` references — and
    MUST NOT carry the old kebab-case `github-pat` / `github-pat-user` credential
    keys, which agent-vault rejects. A tag-install that poured the stale kebab
    casing would crash the dummyco spike (lead-jdfb) at credential set time."""
    body = _sdist_member(built_sdist, PROVISION_REL)
    missing = [k for k in PROVISION_SCREAMING_SNAKE_KEYS if k not in body]
    assert not missing, (
        f"delivered ops/agent-vault-provision lacks the SCREAMING_SNAKE "
        f"credential keys {missing} (lead-l95x rename 2936c70); a tag-install "
        f"would pour the stale kebab-cased provision script"
    )
    present_kebab = [k for k in PROVISION_FORBIDDEN_KEBAB_KEYS if k in body]
    assert not present_kebab, (
        f"delivered ops/agent-vault-provision still carries kebab-case credential "
        f"keys {present_kebab}; agent-vault rejects kebab credential keys and the "
        f"lead-l95x rename (2936c70) replaced them with SCREAMING_SNAKE_CASE"
    )


def test_delivered_provision_registers_claude_broker_service(built_sdist):
    """lead-8jar (4797c35): v0.9.0 ships the five-live-fleet-service provision
    rewrite. The delivered ops/agent-vault-provision must register the Claude
    broker service `claude-api` against host `api.anthropic.com` attaching the
    `CLAUDE_OAUTH` bearer credential, so a fresh dummyco provision (spike iter-7)
    wires the full broker service set rather than crashing the iter-6 Claude-401.
    A tag-install that poured a provision without these service-add calls would
    leave the broker unable to attach the OAuth bearer to Anthropic requests."""
    body = _sdist_member(built_sdist, PROVISION_REL)
    missing = [t for t in PROVISION_CLAUDE_SERVICE_TOKENS if t not in body]
    assert not missing, (
        f"delivered ops/agent-vault-provision is missing the Claude broker "
        f"service-registration tokens {missing} (lead-8jar 4797c35); a fresh "
        f"dummyco provision would not wire claude-api -> api.anthropic.com with "
        f"the CLAUDE_OAUTH bearer and would reproduce the iter-6 Claude-401"
    )


def test_delivered_human_gate_uses_screaming_snake_claude_oauth(built_sdist):
    """lead-8jar: the delivered provision human-gate prompt must reference the
    OAuth credential by its authoritative SCREAMING_SNAKE name `CLAUDE_OAUTH`
    and MUST NOT carry the old kebab `claude-oauth` — agent-vault rejects kebab
    credential keys, so a tag-install that poured the kebab name would crash the
    dummyco spike at credential set time."""
    body = _sdist_member(built_sdist, PROVISION_REL)
    assert "CLAUDE_OAUTH" in body, (
        "delivered ops/agent-vault-provision human-gate does not reference the "
        "SCREAMING_SNAKE credential name CLAUDE_OAUTH (lead-8jar)"
    )
    assert PROVISION_FORBIDDEN_KEBAB_OAUTH not in body, (
        f"delivered ops/agent-vault-provision still carries the forbidden kebab "
        f"credential name {PROVISION_FORBIDDEN_KEBAB_OAUTH!r}; agent-vault rejects "
        f"kebab credential keys and lead-8jar uses CLAUDE_OAUTH"
    )


def test_delivered_provision_env_writeback_references_vault_and_ca(built_sdist):
    """lead-8jar: the delivered provision .env writeback must reference both
    AGENT_VAULT_VAULT and AGENT_VAULT_CA_PEM so the provisioned broker
    vault/CA ride into the launched shop's .env (folds lead-eqzi + lead-71tq).
    A tag-install whose provision omitted these writeback keys would leave a
    bootstrapped shop without the broker vault selector or the CA pin."""
    body = _sdist_member(built_sdist, PROVISION_REL)
    missing = [k for k in PROVISION_ENV_WRITEBACK_KEYS if k not in body]
    assert not missing, (
        f"delivered ops/agent-vault-provision .env writeback is missing "
        f"{missing} (lead-8jar); a bootstrapped shop's .env would lack the broker "
        f"vault selector / CA pin"
    )


def test_delivered_provision_uses_oauth_proposal_gate_not_flat_credential_set(
    built_sdist,
):
    """lead-yrex (d47c110): v0.10.0 ships the Claude-OAuth human-gate rewrite.
    The delivered ops/agent-vault-provision must drive the CLAUDE_OAUTH
    credential through a PRE-POPULATED OAuth-TYPED credential-slot PROPOSAL —
    it must carry the proposal verbs (`proposal create` + `proposal approve`)
    and an OAuth type marker (`type:oauth` / `"type": "oauth"`), and MUST NOT
    carry a flat `credential set CLAUDE_OAUTH` fallback.

    The proposal path preserves the refresh machinery (type:oauth + token_url);
    a flat static `credential set CLAUDE_OAUTH=<token>` would store a
    non-refreshing bearer and reproduce the broker token-expiry lead-yrex fixed.
    A tag-install that poured the pre-d47c110 flat-credential-set provision
    would crash the dummyco spike's long-lived Claude broker once the pasted
    token expired."""
    body = _sdist_member(built_sdist, PROVISION_REL)
    missing_verbs = [t for t in PROVISION_PROPOSAL_GATE_TOKENS if t not in body]
    assert not missing_verbs, (
        f"delivered ops/agent-vault-provision is missing the OAuth-proposal gate "
        f"verbs {missing_verbs} (lead-yrex d47c110); a tag-install would not pour "
        f"the proposal-based CLAUDE_OAUTH human gate"
    )
    assert any(form in body for form in PROVISION_OAUTH_TYPE_FORMS), (
        f"delivered ops/agent-vault-provision carries no OAuth type marker "
        f"(one of {PROVISION_OAUTH_TYPE_FORMS}); the lead-yrex proposal must set "
        f"type:oauth so the slot keeps its refresh machinery"
    )
    assert PROVISION_FORBIDDEN_FLAT_OAUTH_SET not in body, (
        f"delivered ops/agent-vault-provision still carries the flat "
        f"{PROVISION_FORBIDDEN_FLAT_OAUTH_SET!r} fallback; lead-yrex (d47c110) "
        f"replaced it with the OAuth-typed proposal gate, and a flat static set "
        f"would store a non-refreshing CLAUDE_OAUTH bearer"
    )
    # CORRECTED BEHAVIOR (lead-9qdn / WALL-2): the proposal gate must run under a
    # vault-scoped session, not the bare owner session. This EXTENDS the gate
    # assertion above (it does not relax the proposal-verb / number-parse pins).
    missing_scope = [t for t in PROVISION_SCOPED_SESSION_TOKENS if t not in body]
    assert not missing_scope, (
        f"delivered ops/agent-vault-provision is missing the vault-scoped session "
        f"wiring {missing_scope} (lead-9qdn / WALL-2); proposal create/approve run "
        f"in agent mode and need a vault-scoped session, else a tag-install dies on "
        f'"Session requires vault scope" at provision time'
    )


def test_delivered_gitignore_ignores_dotenv_but_tracks_example(
    built_sdist, built_wheel
):
    """lead-7if5 (af58736): v0.11.0 ships the bootstrap `.gitignore` fix. The
    delivered `templates/gitignore.template` — which the CLI pours verbatim into
    a launched shop's top-level `.gitignore` — must ignore `.env` while keeping
    the `.env.example` scaffold tracked via a `!.env.example` negation.

    This is the master-password-commit gap: an operator runs `cp .env.example
    .env` and populates the real `.env` with AGENT_VAULT_MASTER_PASSWORD / broker
    token; without a `.env` ignore rule that secret-bearing file is a `git add`
    away from being committed. The negation keeps the shipped `.env.example`
    scaffold tracked so the bootstrap render path still finds it.

    Asserts against the BUILT ARTIFACTS (sdist + wheel), not the source tree, so
    a tag-install that dropped or omitted the template from the package is caught
    — the same delivery-currency discipline the rest of this module applies."""
    sdist_body = _sdist_member(built_sdist, GITIGNORE_TEMPLATE_REL)
    missing = [t for t in GITIGNORE_ENV_IGNORE_TOKENS if t not in sdist_body]
    assert not missing, (
        f"delivered {GITIGNORE_TEMPLATE_REL} lacks the .env ignore rule(s) "
        f"{missing} (lead-7if5 af58736); a tag-install would pour a .gitignore "
        f"that leaves an operator's secret-bearing .env a `git add` away from "
        f"being committed"
    )
    assert GITIGNORE_ENV_EXAMPLE_NEGATION in sdist_body, (
        f"delivered {GITIGNORE_TEMPLATE_REL} lacks the "
        f"{GITIGNORE_ENV_EXAMPLE_NEGATION!r} negation (lead-7if5); the shipped "
        f".env.example scaffold must stay tracked so the bootstrap render path "
        f"still finds it"
    )
    # The template must actually ride along in BOTH built artifacts, or a clean
    # install pours no top-level .gitignore at all.
    assert _sdist_has_member(built_sdist, GITIGNORE_TEMPLATE_REL), (
        f"delivered sdist is missing {GITIGNORE_TEMPLATE_REL!r}; a clean install "
        f"would pour no top-level .gitignore"
    )
    assert _wheel_has_member(built_wheel, GITIGNORE_TEMPLATE_REL), (
        f"delivered wheel is missing {GITIGNORE_TEMPLATE_REL!r}; a clean install "
        f"would pour no top-level .gitignore"
    )


def test_delivered_lead_po_moves_scenario_hash_to_authoring_time(built_sdist):
    """lead-xgs0 (59d2b93): v0.12.0 ships the authoring-time @scenario_hash move.
    The delivered `templates/lead-po.md` must instruct the PO to write the
    `@scenario_hash` tag at AUTHORING time as an explicit step (compute it with
    `scenarios hash` as part of authoring), and MUST NOT carry the old
    prohibition that the hash is "not yours" / "do NOT add @scenario_hash". The
    `@bc:<name>` tag must remain dispatch-time (Architect/assignment-added).

    This is delivery-currency: the reframed lead-po only reaches launched lead
    shops once the published version advances past 0.11.0 and the artifact
    actually carries the authoring-time hash step. Asserts against the BUILT
    ARTIFACT so a tag-install that omitted the reframed template is caught."""
    body = _sdist_member(built_sdist, LEAD_PO_REL)
    lowered = body.lower()

    missing = [t for t in LEAD_PO_AUTHORING_HASH_TOKENS if t not in body]
    assert not missing, (
        f"delivered {LEAD_PO_REL} lacks the authoring-time @scenario_hash "
        f"vocabulary {missing} (lead-xgs0 59d2b93); a tag-install would pour a "
        f"lead-po that does not own the hash at authoring time"
    )
    assert LEAD_PO_AUTHORING_PHRASE in lowered, (
        f"delivered {LEAD_PO_REL} does not frame @scenario_hash computation as "
        f"'{LEAD_PO_AUTHORING_PHRASE}' (lead-xgs0); the authoring-time hash step "
        f"is the load-bearing reframe this release delivers"
    )

    present_prohibitions = [
        p for p in LEAD_PO_FORBIDDEN_PROHIBITIONS if p in lowered
    ]
    assert not present_prohibitions, (
        f"delivered {LEAD_PO_REL} still carries the removed prohibition "
        f"{present_prohibitions} against authoring @scenario_hash; lead-xgs0 "
        f"(59d2b93) moved the hash to authoring time and removed it"
    )

    # The @bc tag must remain dispatch/assignment-time, not PO-authored.
    assert LEAD_PO_BC_DISPATCH_TOKEN in body, (
        f"delivered {LEAD_PO_REL} no longer references the {LEAD_PO_BC_DISPATCH_TOKEN!r} "
        f"tag; the reframe keeps @bc as a dispatch-time (Architect-added) tag"
    )
    assert "assignment time" in lowered or "dispatch" in lowered, (
        f"delivered {LEAD_PO_REL} does not keep @bc as a dispatch/assignment-time "
        f"tag (lead-xgs0); only @scenario_hash moved to authoring time"
    )


def test_delivered_artifact_ships_lead_skill_group(built_sdist, built_wheel):
    """lead-5mr5 (25fa894): v0.13.0 ships the canonical lead skill-group. The
    lead bootstrap pours `.claude/skills/{create-bc,bring-up-bc}/SKILL.md`, so
    both SKILL.md files must ride along in BOTH the built sdist and the built
    wheel (under `templates/lead_skills/`), or a clean tag-install + `shop-templates
    bootstrap --shop-type lead` would pour an empty / missing skill-group.

    This is delivery-currency: the skill-group only reaches launched lead shops
    once the published version advances past 0.12.0 AND the package-data glob
    (`templates/lead_skills/**/*`) actually carries both SKILL.md files. Asserts
    against the BUILT ARTIFACTS, not the source tree, because the defect this
    guards (a glob that fails to sweep the nested SKILL.md files) is invisible
    from an editable / PYTHONPATH=src run."""
    sdist_missing = [
        rel for rel in LEAD_SKILLS_RELS if not _sdist_has_member(built_sdist, rel)
    ]
    wheel_missing = [
        rel for rel in LEAD_SKILLS_RELS if not _wheel_has_member(built_wheel, rel)
    ]
    assert not sdist_missing and not wheel_missing, (
        f"delivered lead skill-group is incomplete in the BUILT ARTIFACT — a "
        f"fresh pip install + `shop-templates bootstrap --shop-type lead` would "
        f"pour a missing skill-group. sdist missing: {sdist_missing}; wheel "
        f"missing: {wheel_missing}. (Check the `templates/lead_skills/**/*` "
        f"package-data glob.)"
    )


def test_delivered_create_bc_skill_names_bc_creation_mechanism(built_sdist):
    """lead-5mr5: the delivered create-bc SKILL.md body must name the BC-creation
    mechanism it drives — `shop-templates bootstrap --shop-type bc`, `gh repo
    create`, and the bc-container launch flags (`bc-container launch`,
    `--repo-url`). A poured create-bc that does not name these cannot stand up a
    BC, so a tag-install would deliver a hollow skill. Asserts against the BUILT
    ARTIFACT so a stale/empty create-bc shipped in the package is caught."""
    body = _sdist_member(built_sdist, CREATE_BC_REL)
    missing = [t for t in CREATE_BC_BODY_TOKENS if t not in body]
    assert not missing, (
        f"delivered {CREATE_BC_REL} does not name the BC-creation mechanism "
        f"tokens {missing} (lead-5mr5); a poured create-bc skill could not stand "
        f"up a BC (shop-templates bootstrap --shop-type bc / gh repo create / "
        f"bc-container launch flags)"
    )
