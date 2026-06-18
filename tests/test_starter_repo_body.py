"""Pins the shopsystem-starter repo BODY rendered as template/package data
(tmpl-3ch / lead-v0m7; PDR-019 U1, ADR-040 D1/D3, briefs/012 §2).

`shopsystem-starter` is a lead-owned, standalone, forkable "Use this
template" repo carrying NO framework code (framework lives only in the
published image). This BC renders its BODY as package/template data — it does
NOT create the GitHub repo or mark it a template repository.

Required body (all served from importlib.resources package data, NOT read
from a path under the product working directory):

  (1) compose.yaml — postgres + agent-vault referencing the published
      bc-base image; MUST NOT pin the image tag (the bootstrap script
      resolves the floating :latest at run time and records the resolved
      digest/tag in the run's .env, ADR-040 D3).
  (2) a deterministic bootstrap script — the adopter's entry point after
      "Use this template" that produces their <product>-lead repo. It
      validates the repo name against the *-lead shape and offers
      `gh repo rename` on mismatch (deriving <product>, U4); runs the ONE
      up-front consolidated human auth gate (Claude OAuth proposal
      create->approve + GitHub PAT + owner password); invokes the U3 footing
      orchestration (services up -> `shop-templates bootstrap` pour ->
      create <product>-lead-beads -> wire git+beads remotes ->
      `bd dolt push` smoke-test -> STOP at green push); and uses the U2
      interactive bootstrap image MODE on the bc-base/bc-launcher lineage.
  (3) .env.example and a README — zero-install (Docker + a GitHub account
      only; Discovery is an explicit NEXT step, NOT part of the script).
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from shop_templates.cli import (
    iter_starter_files,
    read_starter_file,
)


def _yaml_load(text: str):
    """Parse YAML, preferring an in-process import, falling back to a
    yaml-capable interpreter round-tripped through JSON (the conftest
    pattern; the test venv may lack PyYAML)."""
    try:  # pragma: no cover - environment dependent
        import yaml  # type: ignore

        return yaml.safe_load(text)
    except ModuleNotFoundError:
        pass
    helper = (
        "import sys, json, yaml\n"
        "json.dump(yaml.safe_load(sys.stdin.read()), sys.stdout)\n"
    )
    for interp in (sys.executable, shutil.which("python3"), shutil.which("python")):
        if not interp:
            continue
        proc = subprocess.run(
            [interp, "-c", helper], input=text, capture_output=True, text=True
        )
        if proc.returncode == 0:
            return json.loads(proc.stdout)
    pytest.skip("no yaml-capable interpreter available")


# -----------------------------------------------------------------------
# The package-data accessor surface.
# -----------------------------------------------------------------------


def test_iter_starter_files_yields_relative_paths_and_bytes():
    files = dict(iter_starter_files())
    # The forkable repo body ships all four required artifacts.
    assert "compose.yaml" in files
    assert ".env.example" in files
    assert "README.md" in files
    # Exactly one bootstrap script entry point.
    bootstrap_names = [r for r in files if r in ("bootstrap", "bin/bootstrap")]
    assert len(bootstrap_names) == 1, f"expected one bootstrap script, got {bootstrap_names}"
    for rel, body in files.items():
        assert not rel.startswith("/")
        assert "\\" not in rel
        assert isinstance(body, bytes) and len(body) > 0


def _starter(rel):
    return read_starter_file(rel)


def _bootstrap_rel():
    files = dict(iter_starter_files())
    for cand in ("bin/bootstrap", "bootstrap"):
        if cand in files:
            return cand
    raise AssertionError("no bootstrap script in starter body")


def test_read_starter_file_matches_iter():
    files = dict(iter_starter_files())
    for rel, body in files.items():
        assert read_starter_file(rel) == body.decode()


def test_read_starter_file_missing_raises():
    with pytest.raises(FileNotFoundError):
        read_starter_file("does-not-exist.txt")


# -----------------------------------------------------------------------
# (1) compose.yaml — postgres + agent-vault, references the bc-base image,
#     does NOT pin the image tag.
# -----------------------------------------------------------------------


def test_starter_compose_has_postgres_and_agent_vault():
    data = _yaml_load(_starter("compose.yaml"))
    services = data["services"]
    assert "postgres" in services, "compose must define a postgres service"
    assert "agent-vault" in services, "compose must define an agent-vault service"


def test_starter_compose_agent_vault_references_bc_base_image():
    data = _yaml_load(_starter("compose.yaml"))
    av = data["services"]["agent-vault"]
    assert "image" in av, "agent-vault service must declare an image"
    assert "agent-vault" in av["image"], (
        f"agent-vault must reference the agent-vault broker image, got {av['image']!r}"
    )


def test_starter_compose_does_not_pin_the_image_tag():
    """ADR-040 D3: the bootstrap script resolves the floating :latest at run
    time and records the resolved digest/tag in the run's .env. The committed
    starter compose MUST NOT pin a fixed image tag — it floats on :latest (or
    leaves the tag unspecified) so the bootstrap is what records the resolve.
    A pinned semver/digest is a regression."""
    text = _starter("compose.yaml")
    data = _yaml_load(text)
    for name, svc in data["services"].items():
        image = svc.get("image", "")
        if "agent-vault" not in image and "postgres" not in image:
            continue
        # No digest pin.
        assert "@sha256:" not in image, (
            f"service {name} pins a digest ({image!r}); the starter must float"
        )
        # If a tag is present at all on the bc-base/agent-vault lineage, it
        # must be the floating :latest, never a fixed version.
        if "agent-vault" in image and ":" in image.rsplit("/", 1)[-1]:
            tag = image.rsplit(":", 1)[-1]
            assert tag == "latest", (
                f"agent-vault image must float on :latest, not pin {tag!r}"
            )


# -----------------------------------------------------------------------
# (2) the deterministic bootstrap script.
# -----------------------------------------------------------------------


def test_starter_bootstrap_validates_lead_shape_and_offers_gh_rename():
    body = _starter(_bootstrap_rel())
    assert "-lead" in body, "bootstrap must validate the *-lead repo shape"
    assert "gh repo rename" in body, "bootstrap must offer `gh repo rename` on mismatch"


def test_starter_bootstrap_runs_single_up_front_auth_gate():
    body = _starter(_bootstrap_rel()).lower()
    # Claude OAuth via proposal create -> approve.
    assert "proposal" in body and "approve" in body
    assert "oauth" in body
    # GitHub PAT.
    assert "github" in body and ("pat" in body or "token" in body)
    # owner password.
    assert "owner password" in body or "owner_password" in body or "owner pw" in body
    # consolidated / up-front / single gate.
    assert "auth gate" in body or "up-front" in body or "up front" in body


def test_starter_bootstrap_invokes_footing_orchestration():
    """It must invoke the U3 footing orchestration rather than fork its logic
    (strongly-prefer-REUSE constraint). The starter ships/wraps the footing
    script; the bootstrap drives it (or its steps): services up ->
    `shop-templates bootstrap` pour -> create <product>-lead-beads -> wire
    remotes -> `bd dolt push` smoke-test."""
    body = _starter(_bootstrap_rel())
    # The footing entry point is reused, not duplicated.
    assert "footing" in body, "bootstrap must reuse/invoke the footing script"
    # The U3 footing landmarks the bootstrap drives reach.
    assert "bd dolt push" in body, "footing must reach the `bd dolt push` smoke test"


def test_starter_bootstrap_uses_interactive_image_mode():
    body = _starter(_bootstrap_rel()).lower()
    assert "interactive" in body, "bootstrap must use the U2 interactive image MODE"
    assert "bc-base" in body or "bc-launcher" in body, (
        "bootstrap must use the bc-base/bc-launcher image lineage"
    )


def test_starter_bootstrap_does_not_duplicate_footing_logic():
    """REUSE, not fork: the bootstrap must not re-implement the footing
    internals (creating the beads repo, wiring remotes by hand). Those belong
    to the footing script it invokes."""
    body = _starter(_bootstrap_rel())
    # The bootstrap delegates remote-wiring/beads-repo creation to footing; it
    # should not itself run `gh repo create ... -beads` or `bd dolt remote add`.
    assert "gh repo create" not in body, (
        "bootstrap must delegate beads-repo creation to footing, not duplicate it"
    )
    assert "bd dolt remote add" not in body, (
        "bootstrap must delegate remote-wiring to footing, not duplicate it"
    )


# -----------------------------------------------------------------------
# (3) .env.example + README — zero-install.
# -----------------------------------------------------------------------


def test_starter_env_example_is_placeholder_only():
    body = _starter(".env.example")
    assert body.strip(), ".env.example must be non-empty"
    # Carries the broker master password slot the compose consumes.
    assert "AGENT_VAULT_MASTER_PASSWORD" in body
    # Placeholder-only: no obviously-real secret material.
    assert "changeme" in body.lower() or "<" in body, (
        ".env.example must carry placeholder values only"
    )


def test_starter_readme_is_zero_install():
    body = _starter("README.md").lower()
    # Prereqs: Docker + a GitHub account only (zero-install).
    assert "docker" in body
    assert "github" in body
    # "Use this template" then run the script.
    assert "use this template" in body
    # Discovery is an explicit NEXT step, NOT part of the script.
    assert "discovery" in body
    assert "next step" in body or "next steps" in body or "not part of" in body


def test_starter_readme_does_not_promise_framework_code():
    """The starter carries NO framework code; the README must be honest that
    framework lives only in the published image."""
    body = _starter("README.md").lower()
    assert "no framework" in body or "framework lives only" in body or (
        "published image" in body
    )
