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
# Import shop_templates from the worktree source tree (ahead of any installed
# copy) so the in-process _LEAD_OPS_FILES enumeration reflects this branch.
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

# Reuse the hermetic bootstrap harness from the generification suite.
from test_ops_generification import _bootstrap  # noqa: E402


# Positive substrings the converged thin wrapper MUST carry (172/134).
_REQUIRED_SUBSTRINGS = (
    "docker compose",
    "up -d postgres agent-vault",
    "--env-file",
    "docker run --rm",
    "-it",
    "shopsystem-bc-lead",
    "/var/run/docker.sock:/var/run/docker.sock",
    "bc-container launch",
    "--workspace-mount",
    "--mount-docker-socket",
    "--network",
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
    Dockerfile.shopsystem-shell entry.

    Resolved out-of-process against the worktree `src/` (via PYTHONPATH) — the
    same hermetic convention `_bootstrap` uses — so the assertion reflects this
    branch's `_LEAD_OPS_FILES` rather than any installed/cached copy."""
    env = dict(os.environ)
    env["PYTHONPATH"] = _SRC + os.pathsep + env.get("PYTHONPATH", "")
    probe = (
        "import json;"
        "from shop_templates.cli import _LEAD_OPS_FILES as f;"
        "print(json.dumps([[tn, rel] for tn, rel, _ in f]))"
    )
    proc = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True,
        text=True,
        env=env,
    )
    assert proc.returncode == 0, f"probe failed: {proc.stderr}"
    import json as _json

    entries = _json.loads(proc.stdout)
    rels = {rel for _tn, rel in entries}
    tmpls = {tn for tn, _rel in entries}
    assert len(entries) == 5, (
        f"converged ops-tool set must be exactly five; got {len(entries)}"
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
    """175 (re-pinned, lead-ss6k): a non-default-slug render (dummyco) carries
    zero cross-product SLUG-derived literals — compose.yaml has no
    case-insensitive `shopsystem`/`fleet`; bin/shop-shell permits `shopsystem`
    ONLY as part of the product-neutral framework image reference
    `shopsystem-bc-lead` (now BOTH the launcher AND the leaf-BC runtime, since
    the leaf needs the docker CLI too) — after removing every occurrence of that
    ref, no `shopsystem`/`fleet` remains — and MUST still contain
    `shopsystem-bc-lead` (not slug-rewritten); and no dedicated shell Dockerfile
    is written."""
    target = _bootstrap(tmp_path, "dummyco")

    # compose.yaml: zero case-insensitive shopsystem/fleet.
    compose = (target / "compose.yaml").read_text().lower()
    assert "shopsystem" not in compose, "compose.yaml leaked a 'shopsystem' literal"
    assert "fleet" not in compose, "compose.yaml leaked a 'fleet' literal"

    # bin/shop-shell: the ONLY permitted shopsystem literals are within the
    # product-neutral image ref shopsystem-bc-lead (launcher AND leaf-BC).
    # Strip every occurrence of that ref (case-insensitively) and assert
    # nothing else remains.
    shell = (target / "bin" / "shop-shell").read_text()
    assert "shopsystem-bc-lead" in shell, (
        "bin/shop-shell must preserve the product-neutral framework image "
        "reference shopsystem-bc-lead (not slug-rewritten to dummyco-bc-lead)"
    )
    shell_lower = shell.lower()
    residual = shell_lower.replace("shopsystem-bc-lead", "")
    assert "shopsystem" not in residual, (
        "bin/shop-shell leaked a 'shopsystem' literal outside the framework ref"
    )
    assert "fleet" not in residual, "bin/shop-shell leaked a 'fleet' literal"

    assert not (target / "Dockerfile.dummyco-shell").exists()
    assert not (target / "Dockerfile.shopsystem-shell").exists()


# The full, pullable public framework image reference. The bare name
# `shopsystem-bc-base` resolves to docker.io/library/shopsystem-bc-base which
# does not exist; only the registry-qualified, tagged ref is pullable on a
# fresh host (request_bugfix lead-zcob, DEFECT 1).
_FULL_BC_BASE_REF = "ghcr.io/dstengle/shopsystem-bc-base:latest"

# The ephemeral LAUNCHER image. Per PDR-020 Addendum II decision (b), the
# launcher must run on the thin lead-launcher image (bc-base + docker CLI) so
# it can run `bc-container launch`; bc-base itself carries NO docker CLI. The
# leaf-BC session the launcher stands up keeps the bc-base runtime image,
# handed in via `bc-container launch --image`.
_FULL_BC_LEAD_REF = "ghcr.io/dstengle/shopsystem-bc-lead:latest"


def _docker_run_image(block_tokens):
    """Given the shlex tokens of a `docker run ... <image> <cmd...>` invocation,
    return the image reference: the first non-option token after `run` that is
    not consumed as the value of a preceding flag."""
    # Flags in these blocks that take a value argument.
    value_flags = {
        "--network",
        "--env-file",
        "--group-add",
        "-v",
        "-w",
    }
    assert block_tokens[0] == "docker" and block_tokens[1] == "run", block_tokens
    i = 2
    while i < len(block_tokens):
        tok = block_tokens[i]
        if tok in value_flags:
            i += 2
            continue
        if tok.startswith("-"):
            # value-less flag (e.g. --rm, -it)
            i += 1
            continue
        # first bare (non-flag) token => the image reference
        return tok
    raise AssertionError(f"no image ref found in docker run block: {block_tokens}")


def _flag_value_after_subcommand(tokens, prog, subcommand, flag):
    """For a `<prog> <subcommand> ...` token stream, return the value token
    immediately following ``flag`` (e.g. the ``--image`` argument), or None if
    the flag is absent."""
    assert tokens[0] == prog and tokens[1] == subcommand, tokens
    for i in range(2, len(tokens) - 1):
        if tokens[i] == flag:
            return tokens[i + 1]
    return None


def _positional_after_subcommand(tokens, prog, subcommand):
    """For a `<prog> <subcommand> ...` token stream, return the first bare
    (non-flag, non-flag-value) token after the subcommand — the positional
    argument. Returns None if there is no positional before the next flag."""
    assert tokens[0] == prog and tokens[1] == subcommand, tokens
    # Flags on bc-container launch/attach that take a value.
    value_flags = {
        "--workspace-mount",
        "--startup-prompt",
        "--repo-url",
        "--shopmsg-dsn",
        "--image",
        "--network",
        "--agent-vault-broker",
        "--env-file",
    }
    i = 2
    while i < len(tokens):
        tok = tokens[i]
        if tok in value_flags:
            i += 2
            continue
        if tok.startswith("-"):
            i += 1
            continue
        return tok
    return None


def _render_shop_shell(slug):
    """Render the bin/shop-shell ops template for ``slug``, resolved
    out-of-process against the worktree ``src/`` (via PYTHONPATH) — the same
    hermetic convention ``_bootstrap`` and the file-set enumeration test use, so
    the render reflects THIS branch's canonical template rather than any
    installed/editable copy that an in-process import would resolve to first."""
    env = dict(os.environ)
    env["PYTHONPATH"] = _SRC + os.pathsep + env.get("PYTHONPATH", "")
    probe = (
        "import sys;"
        "from shop_templates.cli import render_ops_template;"
        "sys.stdout.write(render_ops_template('shop-shell', %r))" % slug
    )
    proc = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True,
        text=True,
        env=env,
    )
    assert proc.returncode == 0, f"render probe failed: {proc.stderr}"
    return proc.stdout


def _parse_shop_shell(slug):
    """Render bin/shop-shell for ``slug`` and return a structured view of the
    two docker-run invocations and the embedded bc-container launch/attach
    commands, parsed with shlex (so we assert on command STRUCTURE, not loose
    substrings)."""
    import shlex

    body = _render_shop_shell(slug)

    # Collapse line-continuations so each logical command is one token stream.
    logical = body.replace("\\\n", " ")

    docker_run_images = []
    launch_positional = None
    attach_positional = None
    launch_image_flag = None
    launch_network_flag = None
    for raw_line in logical.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        # The shop-shell prefixes the second docker run with `exec`.
        probe = line[len("exec ") :].strip() if line.startswith("exec ") else line
        try:
            tokens = shlex.split(probe)
        except ValueError:
            continue
        if not tokens:
            continue
        if tokens[:2] != ["docker", "run"]:
            continue
        # Image ref = the first bare token after `run` flags.
        docker_run_images.append(_docker_run_image(tokens))
        # The container command (`bc-container launch|attach ...`) is the tail
        # of the same line-continued docker run invocation: everything from the
        # `bc-container` token onward.
        if "bc-container" in tokens:
            ci = tokens.index("bc-container")
            inner = tokens[ci:]
            if inner[:2] == ["bc-container", "launch"]:
                launch_positional = _positional_after_subcommand(
                    inner, "bc-container", "launch"
                )
                launch_image_flag = _flag_value_after_subcommand(
                    inner, "bc-container", "launch", "--image"
                )
                launch_network_flag = _flag_value_after_subcommand(
                    inner, "bc-container", "launch", "--network"
                )
            elif inner[:2] == ["bc-container", "attach"]:
                attach_positional = _positional_after_subcommand(
                    inner, "bc-container", "attach"
                )
    return {
        "docker_run_images": docker_run_images,
        "launch_positional": launch_positional,
        "attach_positional": attach_positional,
        "launch_image_flag": launch_image_flag,
        "launch_network_flag": launch_network_flag,
    }


def test_both_docker_run_blocks_use_full_pullable_launcher_image_ref():
    """PDR-020 Addendum II (b) + lead-zcob DEFECT 1: BOTH `docker run` blocks
    reference the full, registry-qualified, tagged LAUNCHER image ref
    `ghcr.io/dstengle/shopsystem-bc-lead:latest` — the thin lead-launcher image
    (bc-base + docker CLI). bc-base carries NO docker CLI and cannot run
    `bc-container launch`, so the launcher must run on bc-lead, not bc-base."""
    parsed = _parse_shop_shell("shopsystem")
    images = parsed["docker_run_images"]
    assert len(images) == 2, f"expected two docker run blocks; got {images}"
    for img in images:
        assert img == _FULL_BC_LEAD_REF, (
            f"docker run LAUNCHER image ref must be the full pullable bc-lead ref "
            f"{_FULL_BC_LEAD_REF!r}, not {img!r}"
        )


def test_launch_hands_leaf_bc_its_runtime_image_via_image_flag():
    """lead-ss6k (172 superseded): the inner `bc-container launch` hands the
    leaf-BC session its runtime image by `--image
    ghcr.io/dstengle/shopsystem-bc-lead:latest` — the SAME bc-lead image the
    launcher runs on, because the leaf-BC's own router needs the docker CLI to
    run `bc-container launch` itself, and bc-base carries no docker CLI."""
    for slug in ("shopsystem", "dummyco"):
        parsed = _parse_shop_shell(slug)
        assert parsed["launch_image_flag"] == _FULL_BC_LEAD_REF, (
            f"bc-container launch must carry --image {_FULL_BC_LEAD_REF!r} for "
            f"slug {slug!r} (leaf-BC runtime image — bc-lead, not bc-base); got "
            f"{parsed['launch_image_flag']!r}"
        )


def test_launch_attaches_leaf_to_slug_scoped_network_via_network_flag():
    """lead-ss6k DEFECT 1 (172 superseded, additive assertion): the inner
    `bc-container launch` carries `--network <slug>` so the SEPARATE leaf
    container it creates is attached to the slug-scoped compose network and can
    reach postgres + agent-vault by compose hostname. The outer launcher's
    --network does NOT attach the leaf, so the inner launch must carry its own."""
    for slug in ("shopsystem", "dummyco"):
        parsed = _parse_shop_shell(slug)
        assert parsed["launch_network_flag"] == slug, (
            f"bc-container launch must carry --network {slug!r} (slug-scoped) so "
            f"the leaf reaches the compose postgres/agent-vault; got "
            f"{parsed['launch_network_flag']!r}"
        )


def test_framework_image_literal_present_in_render():
    """lead-ss6k (172 superseded): the rendered shop-shell carries the
    `shopsystem-bc-lead` framework image literal — now BOTH the launcher image
    ref AND the inner --image leaf-BC runtime ref — and no longer carries
    `shopsystem-bc-base` (the leaf collapsed onto bc-lead)."""
    for slug in ("shopsystem", "dummyco"):
        body = _render_shop_shell(slug)
        assert "shopsystem-bc-lead" in body, (
            f"slug {slug!r} render must carry the bc-lead framework image literal"
        )
        assert "shopsystem-bc-base" not in body, (
            f"slug {slug!r} render must NOT carry shopsystem-bc-base — the leaf-BC "
            f"now runs on bc-lead (it needs the docker CLI too)"
        )


def test_launch_and_attach_carry_slug_lead_positional():
    """lead-zcob DEFECT 2: BOTH `bc-container launch` AND `bc-container attach`
    carry the required `bc_name` positional, derived from the slug as
    `<slug>-lead` (so the dummyco render yields `dummyco-lead`). Without the
    positional, bc-container fails 'the following arguments are required:
    bc_name'."""
    for slug, expected in (("shopsystem", "shopsystem-lead"), ("dummyco", "dummyco-lead")):
        parsed = _parse_shop_shell(slug)
        assert parsed["launch_positional"] == expected, (
            f"bc-container launch must carry the {expected!r} positional for "
            f"slug {slug!r}; got {parsed['launch_positional']!r}"
        )
        assert parsed["attach_positional"] == expected, (
            f"bc-container attach must carry the {expected!r} positional for "
            f"slug {slug!r}; got {parsed['attach_positional']!r}"
        )


def test_full_image_ref_preserves_172_and_175_constraints():
    """lead-ss6k keeps scenario 172 (substring) and 175 (dummyco
    cross-product-literal) green: the bc-lead framework ref still CONTAINS its
    `shopsystem-bc-lead` substring; the dummyco render, after stripping every
    `shopsystem-bc-lead` occurrence, retains NO `shopsystem`/`fleet`; and the
    `<slug>-lead` positional introduces no forbidden literal."""
    # 172: the bc-lead ref still carries the framework-image substring.
    assert "shopsystem-bc-lead" in _FULL_BC_LEAD_REF

    # 175 on the dummyco render: no shopsystem/fleet residue outside the single
    # exempt framework image ref, and the bc_name positional is dummyco-lead.
    dummyco = _render_shop_shell("dummyco")
    assert "shopsystem-bc-lead" in dummyco
    residual = dummyco.lower().replace("shopsystem-bc-lead", "")
    assert "shopsystem" not in residual, (
        "dummyco shop-shell leaked a 'shopsystem' literal outside the framework "
        "image ref after the lead-ss6k edits"
    )
    assert "fleet" not in residual, "dummyco shop-shell leaked a 'fleet' literal"
    assert "dummyco-lead" in dummyco, (
        "dummyco render must carry the dummyco-lead bc_name positional"
    )
    # And the full ghcr ref minus the framework substring leaves no shopsystem.
    assert "shopsystem" not in _FULL_BC_LEAD_REF.replace("shopsystem-bc-lead", "")


def test_dockerfile_template_is_removed_from_package_data():
    """174: the shell Dockerfile template is gone from the source tree's ops
    package data."""
    ops = Path(_SRC) / "shop_templates" / "templates" / "ops"
    assert not (ops / "Dockerfile.shopsystem-shell").is_file(), (
        "Dockerfile.shopsystem-shell template must be deleted"
    )
