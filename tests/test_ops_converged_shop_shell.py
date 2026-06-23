"""Converged ops scaffolding tests (PDR-020 slice 2, ADR-028 D1).

Pins the converged shape that supersedes the fat daily-driver shell:

  - bin/shop-shell is a THIN wrapper that DELEGATES the brokered Claude
    launch to `bc-container` running in an ephemeral bc-base. It brings up
    the compose supporting services, assembles the operator agent-vault
    `--env-file`, then `docker run --rm -it shopsystem-bc-base ... bc-container
    launch --workspace-mount <lead-repo> --mount-docker-socket --startup-prompt
    <lead>` and `bc-container attach`. It constructs NO proxy URL, fetches NO
    CA, builds NO shell image, and mounts NO host credentials.
  - the ops file-set is exactly FIVE shop-owned files (compose.yaml,
    bin/shop-shell, bin/shop-scenario-completion, bin/agent-vault-provision,
    bin/agent-vault-check). NO dedicated shell Dockerfile.
  - SHOPSYSTEM_SHELL_IMAGE knob and Dockerfile.shopsystem-shell are RETIRED.
  - a non-default-slug render (dummyco) carries zero cross-product literals.

Serves carried scenarios 172 (03f1256aefc7fad4), 134 (5e42381f435397f2),
174 (5730de0b80aa6a0b), 175 (399d16c31084dbfc), 137 (82c3a716143014a6).

175 is re-pinned (option 3, lead ruling on clarify tmpl-a5l): the
product-neutral framework image reference `shopsystem-bc-base` is EXEMPT
from the cross-product-literal rule (same precedent as the agent-vault
broker image at compose.yaml:50-52). So the dummyco render's bin/shop-shell
permits `shopsystem` ONLY inside `shopsystem-bc-base` (after removing every
occurrence of that image ref, no `shopsystem`/`fleet` remains) and MUST
still contain `shopsystem-bc-base` (not slug-rewritten to dummyco-bc-base).
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

_SRC = str(Path(__file__).resolve().parent.parent / "src")

# Reuse the hermetic bootstrap harness from the generification suite.
from test_ops_generification import _bootstrap  # noqa: E402


# Positive substrings the converged thin wrapper MUST carry (172/134).
_REQUIRED_SUBSTRINGS = (
    "docker compose",
    "up -d postgres agent-vault",
    "--env-file",
    "docker run --rm",
    "-it",
    "shopsystem-bc-base",
    "/var/run/docker.sock:/var/run/docker.sock",
    "bc-container launch",
    "--workspace-mount",
    "--mount-docker-socket",
    "--startup-prompt",
    "bc-container attach",
)

# Forbidden substrings the converged wrapper MUST NOT carry (172/134):
# proxy-URL construction, CA fetch, readiness-check, retired shell image +
# its Dockerfile, and any host-credential mount.
_FORBIDDEN_SUBSTRINGS = (
    "14322",
    "HTTPS_PROXY",
    "agent-vault ca fetch",
    "agent-vault-check",
    "SHOPSYSTEM_SHELL_IMAGE",
    "docker build",
    "$HOME/.claude",
    "$HOME/.gitconfig",
    "~/.claude",
    "~/.gitconfig",
)


def test_shopsystem_shop_shell_is_thin_bc_container_wrapper(tmp_path):
    """172/134: the rendered shop-shell is the thin delegating wrapper —
    shebang + owner-exec, every required substring present, every forbidden
    substring absent, SHOPSYSTEM_DATA default, and the bc-base image ref."""
    target = _bootstrap(tmp_path, "shopsystem-product")
    shell = target / "bin" / "shop-shell"
    body = shell.read_text()

    # shebang + owner-execute bit
    assert body.splitlines()[0] == "#!/usr/bin/env bash"
    import stat as _stat

    assert shell.stat().st_mode & _stat.S_IXUSR, "shop-shell must be owner-executable"

    # SHOPSYSTEM_DATA env default (134)
    assert "SHOPSYSTEM_DATA" in body
    assert "$HOME/.local/share/shopsystem" in body

    for needle in _REQUIRED_SUBSTRINGS:
        assert needle in body, f"thin shop-shell missing required substring {needle!r}"
    for needle in _FORBIDDEN_SUBSTRINGS:
        assert needle not in body, (
            f"thin shop-shell must NOT contain forbidden substring {needle!r}"
        )

    # ordering: `docker compose` precedes `up -d postgres agent-vault`
    assert body.find("docker compose") < body.find("up -d postgres agent-vault")


def test_shop_shell_brings_up_postgres_and_agent_vault(tmp_path):
    """134: the wrapper brings up postgres (and agent-vault) via compose so a
    fresh operator can run ./bin/shop-shell with no further configuration."""
    target = _bootstrap(tmp_path, "shopsystem-product")
    body = (target / "bin" / "shop-shell").read_text()
    i = body.find("docker compose")
    j = body.find("up -d postgres")
    assert i != -1 and j != -1 and i < j


def test_ops_set_is_exactly_five_files_no_dockerfile(tmp_path):
    """174/137: bootstrap writes exactly the five shop-owned ops files and NO
    dedicated shell Dockerfile, none under .claude/canonical/."""
    target = _bootstrap(tmp_path, "shopsystem-product")

    for rel in (
        "compose.yaml",
        "bin/shop-shell",
        "bin/shop-scenario-completion",
        "bin/agent-vault-provision",
        "bin/agent-vault-check",
    ):
        assert (target / rel).is_file(), f"missing converged ops file {rel}"

    # NO dedicated shell Dockerfile (any slug spelling).
    assert not (target / "Dockerfile.shopsystem-shell").exists()
    assert not list(target.glob("Dockerfile.*-shell")), (
        "converged ops set writes no dedicated shell Dockerfile"
    )

    # The canonical dir does not carry the shop-owned ops files.
    canon = target / ".claude" / "canonical"
    for name in (
        "compose.yaml",
        "shop-shell",
        "shop-scenario-completion",
        "agent-vault-provision",
        "agent-vault-check",
    ):
        assert not (canon / name).exists()


def test_lead_ops_files_enumeration_is_five_without_dockerfile():
    """174/137: the cli file-set enumeration is exactly five and drops the
    Dockerfile.shopsystem-shell entry."""
    from shop_templates.cli import _LEAD_OPS_FILES

    rels = {rel for _tn, rel, _exe in _LEAD_OPS_FILES}
    tmpls = {tn for tn, _rel, _exe in _LEAD_OPS_FILES}
    assert len(_LEAD_OPS_FILES) == 5, (
        f"converged ops-tool set must be exactly five; got {len(_LEAD_OPS_FILES)}"
    )
    assert "Dockerfile.shopsystem-shell" not in tmpls
    assert "Dockerfile.shopsystem-shell" not in rels
    assert rels == {
        "compose.yaml",
        "bin/shop-shell",
        "bin/shop-scenario-completion",
        "bin/agent-vault-provision",
        "bin/agent-vault-check",
    }


def test_dummyco_render_has_zero_cross_product_slug_literals(tmp_path):
    """175 (399d16c31084dbfc): a non-default-slug render (dummyco) carries zero
    cross-product SLUG-derived literals — compose.yaml has no case-insensitive
    `shopsystem`/`fleet`; bin/shop-shell permits `shopsystem` ONLY as part of
    the product-neutral framework image reference `shopsystem-bc-base` (after
    removing every occurrence of that ref, no `shopsystem`/`fleet` remains) and
    MUST still contain `shopsystem-bc-base` (not slug-rewritten); and no
    dedicated shell Dockerfile is written."""
    target = _bootstrap(tmp_path, "dummyco")

    # compose.yaml: zero case-insensitive shopsystem/fleet.
    compose = (target / "compose.yaml").read_text().lower()
    assert "shopsystem" not in compose, "compose.yaml leaked a 'shopsystem' literal"
    assert "fleet" not in compose, "compose.yaml leaked a 'fleet' literal"

    # bin/shop-shell: the ONLY permitted shopsystem literal is within the
    # product-neutral image ref shopsystem-bc-base. Strip every occurrence of
    # that ref (case-insensitively) and assert nothing else remains.
    shell = (target / "bin" / "shop-shell").read_text()
    assert "shopsystem-bc-base" in shell, (
        "bin/shop-shell must preserve the product-neutral framework image "
        "reference shopsystem-bc-base (not slug-rewritten to dummyco-bc-base)"
    )
    shell_lower = shell.lower()
    residual = shell_lower.replace("shopsystem-bc-base", "")
    assert "shopsystem" not in residual, (
        "bin/shop-shell leaked a 'shopsystem' literal outside shopsystem-bc-base"
    )
    assert "fleet" not in residual, "bin/shop-shell leaked a 'fleet' literal"

    assert not (target / "Dockerfile.dummyco-shell").exists()
    assert not (target / "Dockerfile.shopsystem-shell").exists()


def test_dockerfile_template_is_removed_from_package_data():
    """174: the shell Dockerfile template is gone from the source tree's ops
    package data."""
    ops = Path(_SRC) / "shop_templates" / "templates" / "ops"
    assert not (ops / "Dockerfile.shopsystem-shell").is_file(), (
        "Dockerfile.shopsystem-shell template must be deleted"
    )
